import os
import csv
import io
import datetime
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import execute_query, paginate, invalidate_stats_cache, cached

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"

VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH"}
VALID_STATUSES = {"OPEN", "CLAIMED", "IN_PROGRESS", "ESCALATED", "RESOLVED", "CLOSED"}
SORT_WHITELIST = {
    "code": "ticket_code", "title": "title", "status": "status",
    "priority": "priority", "updated": "updated_at", "created": "created_at",
    "department": "department_name", "student": "student_name",
    "tickets": "total_tickets", "open": "open_tickets", "resolved": "resolved_tickets",
    "name": "name", "email": "email", "role": "role",
}


@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        token = session.get("_csrf_token")
        if not token or token != request.form.get("_csrf_token"):
            abort(403, description="CSRF token missing or incorrect.")


def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = generate_csrf_token


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("user_login"))
        return f(*args, **kwargs)
    return decorated


def role_required(roles):
    if isinstance(roles, str):
        roles = [roles]
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


def log_activity(ticket_id, action, user_id):
    execute_query(
        "INSERT INTO activity_logs (ticket_id, action, performed_by) VALUES (%s, %s, %s)",
        (ticket_id, action, user_id), commit=True,
    )


def refresh_stats(campus_id=None):
    execute_query("SELECT refresh_campus_stats(%s)", (campus_id,), commit=True)
    invalidate_stats_cache()


def parse_pagination(default_per_page=15):
    return {
        "page": max(1, int(request.args.get("page", 1) or 1)),
        "per_page": max(1, min(int(request.args.get("per_page", default_per_page) or default_per_page), 100)),
    }


def parse_sort(default, allowed):
    sort = request.args.get("sort", default)
    col = allowed.get(sort, allowed[default])
    direction = "DESC" if request.args.get("dir", "desc").lower() == "desc" else "ASC"
    return col, direction


def search_filter(fields):
    q = (request.args.get("q") or "").strip()
    clause = ""
    params = []
    if q:
        clause = " AND (" + " OR ".join([f"{f}::text ILIKE %s" for f in fields]) + ")"
        params = [f"%{q}%"] * len(fields)
    return q, clause, params


def status_filter():
    status = (request.args.get("status") or "").strip().upper()
    if status not in VALID_STATUSES:
        status = ""
    clause = f" AND t.status = '{status}'" if status else ""
    return status, clause


def next_ticket_number(campus_id):
    execute_query(
        "INSERT INTO campus_counters (campus_id, ticket_seq) VALUES (%s, 0) "
        "ON CONFLICT (campus_id) DO NOTHING",
        (campus_id,), commit=True,
    )
    row = execute_query(
        "UPDATE campus_counters SET ticket_seq = ticket_seq + 1 "
        "WHERE campus_id = %s RETURNING ticket_seq",
        (campus_id,), fetch=True, commit=True,
    )
    return row["ticket_seq"] if row else 1


def next_campus_code():
    year = datetime.datetime.now().year
    n = execute_query("SELECT nextval('campus_code_seq') AS n", fetch=True)["n"]
    return f"CC{year}{n:04d}"


@app.route("/")
def index():
    role = session.get("role")
    if role == "student":
        return redirect(url_for("student_dashboard"))
    if role == "staff":
        return redirect(url_for("staff_dashboard"))
    if role == "campus_admin":
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("user_login"))


@app.route("/campus/register", methods=["GET", "POST"])
def campus_create():
    if request.method == "POST":
        campus_name = request.form.get("campus_name", "").strip()
        official_domain = request.form.get("official_domain", "").strip()
        password = request.form.get("password")

        if not campus_name or not official_domain or not password:
            flash("All fields are required.", "danger")
            return redirect(url_for("campus_create"))

        campus_code = next_campus_code()
        campus_hash = generate_password_hash(password)
        admin_hash = generate_password_hash(password)

        try:
            campus = execute_query(
                "INSERT INTO campuses (campus_code, campus_name, official_domain, campus_password_hash) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (campus_code, campus_name, official_domain, campus_hash),
                fetch=True, commit=True,
            )
            execute_query(
                "INSERT INTO users (campus_id, name, email, password_hash, role) "
                "VALUES (%s, %s, %s, %s, %s)",
                (campus["id"], "Campus Admin", f"admin@{official_domain}", admin_hash, "campus_admin"),
                commit=True,
            )
            flash(f"Campus created! Your Campus Code is {campus_code}. Save it.", "success")
            return redirect(url_for("campus_login"))
        except Exception:
            flash("Error creating campus. It may already exist.", "danger")

    return render_template("campus_create.html")


@app.route("/campus/login", methods=["GET", "POST"])
def campus_login():
    if request.method == "POST":
        campus_code = request.form.get("campus_code")
        password = request.form.get("password")

        campus = execute_query(
            "SELECT * FROM campuses WHERE campus_code = %s AND is_active = TRUE",
            (campus_code,), fetch=True,
        )
        if campus and check_password_hash(campus["campus_password_hash"], password):
            session.clear()
            session["_csrf_token"] = secrets.token_hex(32)

            admin = execute_query(
                "SELECT * FROM users WHERE campus_id = %s AND role = 'campus_admin' LIMIT 1",
                (campus["id"],), fetch=True,
            )
            if admin:
                session["user_id"] = admin["id"]
                session["campus_id"] = campus["id"]
                session["campus_name"] = campus["campus_name"]
                session["role"] = "campus_admin"
                session["name"] = admin["name"]
                flash(f"Welcome back, {campus['campus_name']}!", "success")
                return redirect(url_for("admin_dashboard"))

        flash("Invalid campus code or password.", "danger")
    return render_template("campus_login.html")


@app.route("/login", methods=["GET", "POST"])
def user_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password")

        user = execute_query(
            "SELECT u.*, c.campus_name FROM users u "
            "JOIN campuses c ON u.campus_id = c.id "
            "WHERE u.email = %s AND u.is_active = TRUE AND c.is_active = TRUE",
            (email,), fetch=True,
        )
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["_csrf_token"] = secrets.token_hex(32)
            session["user_id"] = user["id"]
            session["campus_id"] = user["campus_id"]
            session["campus_name"] = user["campus_name"]
            session["role"] = user["role"]
            session["name"] = user["name"]
            session["department_id"] = user["department_id"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("index"))
        flash("Invalid email or password, or account deactivated.", "danger")
    return render_template("user_login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("user_login"))


@cached(key_fn=lambda: "dash:student:" + str(session.get("user_id")))
def _student_tickets_count(user_id, campus_id):
    return execute_query(
        "SELECT COUNT(*) FROM tickets WHERE student_id = %s AND campus_id = %s",
        (user_id, campus_id), fetch=True,
    )["count"]


@app.route("/student/dashboard")
@login_required
@role_required("student")
def student_dashboard():
    user_id = session["user_id"]
    campus_id = session["campus_id"]
    q, search_clause, search_params = search_filter(["t.title", "t.ticket_code", "d.name"])
    status, status_clause = status_filter()
    sort_col, sort_dir = parse_sort("updated", {"updated": "updated_at", "code": "ticket_code", "title": "title", "status": "status", "priority": "priority"})

    base = (
        "SELECT t.*, d.name AS department_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        f"WHERE t.student_id = %s AND t.campus_id = %s {search_clause} {status_clause}"
    )
    pager = paginate(base, [user_id, campus_id, *search_params], **parse_pagination())
    pager["rows"] = sorted(pager["rows"], key=lambda r: r[sort_col] or "", reverse=(sort_dir == "DESC"))

    return render_template("student_dashboard.html", pager=pager, q=q, status=status, sort=sort_col, dir=sort_dir)


@app.route("/staff/dashboard")
@login_required
@role_required("staff")
def staff_dashboard():
    user_id = session["user_id"]
    campus_id = session["campus_id"]
    q, search_clause, search_params = search_filter(["t.title", "t.ticket_code", "u.name"])
    status, status_clause = status_filter()
    sort_col, sort_dir = parse_sort("updated", {"updated": "updated_at", "code": "ticket_code", "title": "title", "status": "status", "priority": "priority"})

    base = (
        "SELECT t.*, d.name AS department_name, u.name AS student_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "JOIN users u ON t.student_id = u.id "
        f"WHERE t.assigned_to = %s AND t.campus_id = %s {search_clause} {status_clause}"
    )
    pager = paginate(base, [user_id, campus_id, *search_params], **parse_pagination())
    pager["rows"] = sorted(pager["rows"], key=lambda r: r[sort_col] or "", reverse=(sort_dir == "DESC"))
    return render_template("staff_dashboard.html", pager=pager, q=q, status=status, sort=sort_col, dir=sort_dir)


@app.route("/staff/queue")
@login_required
@role_required("staff")
def department_queue():
    dept_id = session.get("department_id")
    campus_id = session["campus_id"]

    if not dept_id:
        flash("You are not assigned to any department.", "warning")
        return render_template("department_queue.html", pager=None)

    q, search_clause, search_params = search_filter(["t.title", "t.ticket_code", "u.name"])
    base = (
        "SELECT t.*, u.name AS student_name FROM tickets t "
        "JOIN users u ON t.student_id = u.id "
        f"WHERE t.department_id = %s AND t.campus_id = %s AND t.status = 'OPEN' AND t.assigned_to IS NULL {search_clause}"
    )
    pager = paginate(base, [dept_id, campus_id, *search_params], **parse_pagination())
    return render_template("department_queue.html", pager=pager, q=q)


@app.route("/admin/dashboard")
@login_required
@role_required("campus_admin")
def admin_dashboard():
    campus_id = session["campus_id"]
    refresh_stats(campus_id)

    stats = execute_query("SELECT * FROM campus_stats WHERE campus_id = %s", (campus_id,), fetch=True) or {}
    q, search_clause, search_params = search_filter(["t.title", "t.ticket_code", "u.name"])
    status, status_clause = status_filter()
    sort_col, sort_dir = parse_sort("updated", {"updated": "updated_at", "code": "ticket_code", "title": "title", "status": "status", "priority": "priority", "department": "department_name", "student": "student_name"})

    base = (
        "SELECT t.*, d.name AS department_name, u.name AS student_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "JOIN users u ON t.student_id = u.id "
        f"WHERE t.campus_id = %s {search_clause} {status_clause}"
    )
    pager = paginate(base, [campus_id, *search_params], **parse_pagination())
    pager["rows"] = sorted(pager["rows"], key=lambda r: r[sort_col] or "", reverse=(sort_dir == "DESC"))
    return render_template("admin_dashboard.html", stats=stats, pager=pager, q=q, status=status, sort=sort_col, dir=sort_dir)


@app.route("/ticket/create", methods=["GET", "POST"])
@login_required
@role_required("student")
def create_ticket():
    campus_id = session["campus_id"]

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        department_id = request.form.get("department_id")
        priority = (request.form.get("priority") or "").upper()
        user_id = session["user_id"]

        if priority not in VALID_PRIORITIES:
            abort(400, "Invalid priority.")

        dept = execute_query(
            "SELECT id FROM departments WHERE id = %s AND campus_id = %s",
            (department_id, campus_id), fetch=True,
        )
        if not dept:
            abort(403, "Invalid department.")

        num = next_ticket_number(campus_id)
        ticket_code = f"TK-{campus_id}-{num:04d}"

        result = execute_query(
            "INSERT INTO tickets (campus_id, ticket_code, title, description, priority, status, student_id, department_id) "
            "VALUES (%s, %s, %s, %s, %s, 'OPEN', %s, %s) RETURNING id",
            (campus_id, ticket_code, title, description, priority, user_id, department_id),
            fetch=True, commit=True,
        )
        if result:
            log_activity(result["id"], "Ticket created", user_id)
            refresh_stats(campus_id)
            flash("Ticket submitted.", "success")
            return redirect(url_for("student_dashboard"))
        flash("Error creating ticket.", "danger")

    departments = execute_query(
        "SELECT * FROM departments WHERE campus_id = %s ORDER BY name",
        (campus_id,), fetch=True, fetchall=True,
    )
    return render_template("create_ticket.html", departments=departments)


@app.route("/ticket/<int:id>")
@login_required
def ticket_details(id):
    user_id = session["user_id"]
    role = session["role"]
    campus_id = session.get("campus_id")

    ticket = execute_query(
        """
        SELECT t.*, d.name AS department_name, s.name AS student_name, a.name AS assignee_name
        FROM tickets t
        JOIN departments d ON t.department_id = d.id
        JOIN users s ON t.student_id = s.id
        LEFT JOIN users a ON t.assigned_to = a.id
        WHERE t.id = %s AND t.campus_id = %s
        """,
        (id, campus_id), fetch=True,
    )
    if not ticket:
        abort(404)

    if role == "student" and ticket["student_id"] != user_id:
        abort(403)
    if role == "staff" and ticket["department_id"] != session.get("department_id"):
        abort(403)

    comments = execute_query(
        "SELECT c.*, u.name AS user_name, u.role AS user_role FROM comments c "
        "JOIN users u ON c.user_id = u.id WHERE c.ticket_id = %s ORDER BY c.created_at ASC",
        (id,), fetch=True, fetchall=True,
    )
    activities = execute_query(
        "SELECT a.*, u.name AS user_name FROM activity_logs a "
        "LEFT JOIN users u ON a.performed_by = u.id WHERE a.ticket_id = %s ORDER BY a.created_at DESC",
        (id,), fetch=True, fetchall=True,
    )

    staff_members = []
    if role == "campus_admin":
        staff_members = execute_query(
            "SELECT id, name FROM users WHERE role = 'staff' AND department_id = %s AND campus_id = %s AND is_active = TRUE ORDER BY name",
            (ticket["department_id"], campus_id), fetch=True, fetchall=True,
        )

    return render_template("ticket_details.html", ticket=ticket, comments=comments, activities=activities, staff_members=staff_members)


@app.route("/ticket/<int:id>/claim", methods=["POST"])
@login_required
@role_required("staff")
def claim_ticket(id):
    user_id = session["user_id"]
    dept_id = session["department_id"]
    campus_id = session["campus_id"]

    ticket = execute_query(
        "SELECT * FROM tickets WHERE id = %s AND campus_id = %s",
        (id, campus_id), fetch=True,
    )
    if not ticket or ticket["department_id"] != dept_id or ticket["status"] != "OPEN":
        flash("Ticket not available for claiming.", "danger")
        return redirect(url_for("department_queue"))

    execute_query(
        "UPDATE tickets SET assigned_to = %s, status = 'CLAIMED', claimed_at = CURRENT_TIMESTAMP "
        "WHERE id = %s AND status = 'OPEN'",
        (user_id, id), commit=True,
    )
    log_activity(id, "Ticket claimed", user_id)
    refresh_stats(campus_id)
    flash("Ticket claimed.", "success")
    return redirect(url_for("ticket_details", id=id))


@app.route("/ticket/<int:id>/status", methods=["POST"])
@login_required
def update_status(id):
    status = request.form.get("status", "").upper()
    user_id = session["user_id"]
    role = session["role"]
    campus_id = session["campus_id"]

    if status not in VALID_STATUSES:
        abort(400, "Invalid status.")

    ticket = execute_query("SELECT * FROM tickets WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    if not ticket:
        abort(404)

    if role == "staff" and ticket["assigned_to"] != user_id:
        abort(403)

    update_query = "UPDATE tickets SET status = %s"
    params = [status]
    if status == "ESCALATED":
        update_query += ", escalation_reason = %s"
        params.append(request.form.get("escalation_reason", ""))
    elif status == "RESOLVED":
        update_query += ", resolved_at = CURRENT_TIMESTAMP"
    elif status == "CLOSED":
        update_query += ", closed_at = CURRENT_TIMESTAMP"
    update_query += " WHERE id = %s"
    params.append(id)

    execute_query(update_query, tuple(params), commit=True)
    log_activity(id, f"Status changed to {status}", user_id)
    refresh_stats(campus_id)
    flash(f"Status updated to {status}.", "success")
    return redirect(url_for("ticket_details", id=id))


@app.route("/ticket/<int:id>/comment", methods=["POST"])
@login_required
def add_comment(id):
    comment = request.form.get("comment", "").strip()
    user_id = session["user_id"]
    campus_id = session["campus_id"]

    if not comment:
        flash("Comment cannot be empty.", "danger")
        return redirect(url_for("ticket_details", id=id))

    ticket = execute_query("SELECT * FROM tickets WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    if not ticket:
        abort(404)
    if session["role"] == "student" and ticket["student_id"] != user_id:
        abort(403)
    if session["role"] == "staff" and ticket["department_id"] != session.get("department_id"):
        abort(403)

    execute_query(
        "INSERT INTO comments (ticket_id, user_id, comment) VALUES (%s, %s, %s)",
        (id, user_id, comment), commit=True,
    )
    log_activity(id, "Added a comment", user_id)
    flash("Comment added.", "success")
    return redirect(url_for("ticket_details", id=id))


@app.route("/admin/users")
@login_required
@role_required("campus_admin")
def manage_users():
    campus_id = session["campus_id"]
    q, search_clause, search_params = search_filter(["u.name", "u.email", "u.university_id"])
    sort_col, sort_dir = parse_sort("name", {"name": "name", "email": "email", "role": "role"})

    base = (
        "SELECT u.*, d.name AS department_name FROM users u "
        "LEFT JOIN departments d ON u.department_id = d.id "
        f"WHERE u.campus_id = %s AND u.role IN ('staff', 'student') {search_clause}"
    )
    pager = paginate(base, [campus_id, *search_params], **parse_pagination(20))
    pager["rows"] = sorted(pager["rows"], key=lambda r: (r[sort_col] or "").lower(), reverse=(sort_dir == "DESC"))

    departments = execute_query("SELECT * FROM departments WHERE campus_id = %s ORDER BY name", (campus_id,), fetch=True, fetchall=True)
    staffs = [u for u in pager["rows"] if u["role"] == "staff"]
    students = [u for u in pager["rows"] if u["role"] == "student"]

    return render_template("manage_users.html", staffs=staffs, students=students, departments=departments, pager=pager, q=q)


@app.route("/admin/users/add", methods=["POST"])
@login_required
@role_required("campus_admin")
def add_user():
    campus_id = session["campus_id"]
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    university_id = request.form.get("university_id", "").strip()
    role = request.form.get("role", "").strip()
    department_id = request.form.get("department_id") or None
    password = request.form.get("password")

    if role not in ("student", "staff"):
        abort(400, "Invalid role.")
    if not name or not email or not password:
        flash("Name, email and password are required.", "danger")
        return redirect(url_for("manage_users"))
    if role == "staff" and not department_id:
        flash("Staff must be assigned to a department.", "danger")
        return redirect(url_for("manage_users"))

    hashed = generate_password_hash(password)
    try:
        execute_query(
            "INSERT INTO users (campus_id, university_id, name, email, password_hash, role, department_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (campus_id, university_id, name, email, hashed, role, department_id),
            commit=True,
        )
        flash(f"{role.capitalize()} created.", "success")
    except Exception:
        flash("Error creating user (email or ID may exist).", "danger")
    return redirect(url_for("manage_users"))


@app.route("/admin/users/<int:id>/toggle", methods=["POST"])
@login_required
@role_required("campus_admin")
def toggle_user(id):
    campus_id = session["campus_id"]
    user = execute_query("SELECT * FROM users WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    if not user:
        abort(404)
    if user["role"] == "campus_admin":
        flash("Cannot deactivate campus admin.", "danger")
        return redirect(url_for("manage_users"))

    execute_query("UPDATE users SET is_active = %s WHERE id = %s", (not user["is_active"], id), commit=True)
    flash(f"{user['name']} {'activated' if not user['is_active'] else 'deactivated'}.", "success")
    return redirect(url_for("manage_users"))


@app.route("/admin/departments", methods=["GET", "POST"])
@login_required
@role_required("campus_admin")
def manage_departments():
    campus_id = session["campus_id"]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            try:
                execute_query("INSERT INTO departments (campus_id, name) VALUES (%s, %s)", (campus_id, name), commit=True)
                flash("Department added.", "success")
            except Exception:
                flash("Department might already exist.", "danger")
        return redirect(url_for("manage_departments"))

    departments = execute_query(
        "SELECT d.*, COUNT(t.id) AS ticket_count FROM departments d "
        "LEFT JOIN tickets t ON d.id = t.department_id AND t.campus_id = %s "
        "WHERE d.campus_id = %s GROUP BY d.id ORDER BY d.name",
        (campus_id, campus_id), fetch=True, fetchall=True,
    )
    return render_template("manage_departments.html", departments=departments)


@app.route("/admin/departments/<int:id>/delete", methods=["POST"])
@login_required
@role_required("campus_admin")
def delete_department(id):
    campus_id = session["campus_id"]
    open_count = execute_query(
        "SELECT COUNT(*) AS c FROM tickets WHERE department_id = %s AND campus_id = %s AND status IN ('OPEN','CLAIMED','IN_PROGRESS','ESCALATED')",
        (id, campus_id), fetch=True,
    )["c"]
    if open_count > 0:
        flash(f"Cannot delete: {open_count} open ticket(s) still in this department. Resolve or move them first.", "danger")
        return redirect(url_for("manage_departments"))

    try:
        execute_query("DELETE FROM departments WHERE id = %s AND campus_id = %s", (id, campus_id), commit=True)
        flash("Department deleted.", "success")
    except Exception:
        flash("Cannot delete department (it may have historical tickets).", "danger")
    return redirect(url_for("manage_departments"))


@app.route("/admin/users/bulk-upload", methods=["POST"])
@login_required
@role_required("campus_admin")
def bulk_upload_users():
    campus_id = session["campus_id"]
    user_id = session["user_id"]
    role = request.form.get("role", "student")
    if role not in ("student", "staff"):
        abort(400, "Invalid role.")

    if "csv_file" not in request.files:
        flash("No file part.", "danger")
        return redirect(url_for("manage_users"))

    file = request.files["csv_file"]
    if not file.filename or not file.filename.endswith(".csv"):
        flash("Please choose a CSV file.", "danger")
        return redirect(url_for("manage_users"))

    try:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        rows = list(csv_input)
        if len(rows) > 5000:
            flash("CSV exceeds 5000 row limit.", "danger")
            return redirect(url_for("manage_users"))

        job = execute_query(
            "INSERT INTO import_jobs (campus_id, uploaded_by, filename, status) VALUES (%s, %s, %s, 'PROCESSING') RETURNING id",
            (campus_id, user_id, file.filename), fetch=True, commit=True,
        )
        job_id = job["id"]

        success = 0
        failed = 0
        default_hash = generate_password_hash("password123")
        for row in rows:
            try:
                university_id = (row.get("university_id") or "").strip()
                name = (row.get("name") or "").strip()
                email = (row.get("official_email") or row.get("email") or "").strip()
                if not all([university_id, name, email]):
                    failed += 1
                    continue
                execute_query(
                    "INSERT INTO users (campus_id, university_id, name, email, password_hash, role) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (campus_id, university_id, name, email, default_hash, role),
                    commit=True,
                )
                success += 1
            except Exception:
                failed += 1

        total = success + failed
        execute_query(
            "UPDATE import_jobs SET total_rows = %s, success_rows = %s, failed_rows = %s, status = 'COMPLETED' WHERE id = %s",
            (total, success, failed, job_id), commit=True,
        )
        flash(f"Import done. Success: {success}, Failed: {failed}.", "success")
    except Exception as e:
        flash(f"Error processing file: {e}", "danger")
    return redirect(url_for("manage_users"))


@app.route("/health")
def health():
    from db import health_check
    return ("OK", 200) if health_check() else ("DB unavailable", 503)


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_ENV") != "production", host="0.0.0.0", port=5000)
