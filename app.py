import os
import csv
import io
import datetime
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import execute_query

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# --- CSRF Protection ---
@app.before_request
def csrf_protect():
    if request.method in ["POST", "PUT", "PATCH", "DELETE"]:
        token = session.get('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403, description="CSRF token missing or incorrect.")

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

# --- Auth Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and 'campus_admin_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('user_login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    if isinstance(roles, str):
        roles = [roles]
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_activity(ticket_id, action, user_id):
    query = "INSERT INTO activity_logs (ticket_id, action, performed_by) VALUES (%s, %s, %s)"
    execute_query(query, (ticket_id, action, user_id), commit=True)

# --- Routes ---

@app.route('/')
def index():
    if 'role' in session:
        role = session['role']
        if role == 'student':
            return redirect(url_for('student_dashboard'))
        elif role == 'staff':
            return redirect(url_for('staff_dashboard'))
        elif role == 'campus_admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'superadmin':
            return redirect(url_for('admin_dashboard')) # For simplicity, superadmin goes to admin_dashboard
    return redirect(url_for('user_login'))

# --- Campus Registration & Login ---

@app.route('/campus/register', methods=['GET', 'POST'])
def campus_create():
    if request.method == 'POST':
        campus_name = request.form.get('campus_name')
        official_domain = request.form.get('official_domain')
        password = request.form.get('password')
        
        # Generate Campus Code CCYYYYNNNN
        year = datetime.datetime.now().year
        code_res = execute_query("SELECT count(*) FROM campuses", fetch=True)
        count = code_res['count'] + 1 if code_res else 1
        campus_code = f"CC{year}{count:04d}"
        
        hashed_password = generate_password_hash(password)
        
        try:
            campus = execute_query(
                "INSERT INTO campuses (campus_code, campus_name, official_domain, campus_password_hash) VALUES (%s, %s, %s, %s) RETURNING id",
                (campus_code, campus_name, official_domain, hashed_password),
                commit=True, fetch=True
            )
            
            # Create a default campus admin user
            admin_hash = generate_password_hash(password)
            execute_query(
                "INSERT INTO users (campus_id, name, email, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
                (campus['id'], 'Campus Admin', f"admin@{official_domain}", admin_hash, 'campus_admin'),
                commit=True
            )
            
            flash(f"Campus created successfully! Your Campus Code is {campus_code}. Please save this.", "success")
            return redirect(url_for('campus_login'))
        except Exception as e:
            flash(f"Error creating campus. It might already exist.", "danger")
            
    return render_template('campus_create.html')

@app.route('/campus/login', methods=['GET', 'POST'])
def campus_login():
    if request.method == 'POST':
        campus_code = request.form.get('campus_code')
        password = request.form.get('password')
        
        campus = execute_query("SELECT * FROM campuses WHERE campus_code = %s AND is_active = TRUE", (campus_code,), fetch=True)
        
        if campus and check_password_hash(campus['campus_password_hash'], password):
            session.clear()
            session['_csrf_token'] = secrets.token_hex(32)
            
            # Find the admin user for this campus
            admin_user = execute_query("SELECT * FROM users WHERE campus_id = %s AND role = 'campus_admin' LIMIT 1", (campus['id'],), fetch=True)
            if admin_user:
                session['user_id'] = admin_user['id']
                session['campus_id'] = campus['id']
                session['campus_name'] = campus['campus_name']
                session['role'] = 'campus_admin'
                session['name'] = admin_user['name']
                flash(f"Welcome back to {campus['campus_name']} Admin Panel!", "success")
                return redirect(url_for('admin_dashboard'))
        
        flash("Invalid campus code or password.", "danger")
    return render_template('campus_login.html')

# --- User Login ---

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        
        user = execute_query(
            "SELECT u.*, c.campus_name FROM users u JOIN campuses c ON u.campus_id = c.id WHERE u.email = %s AND u.is_active = TRUE AND c.is_active = TRUE", 
            (email,), fetch=True
        )
        
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['_csrf_token'] = secrets.token_hex(32)
            
            session['user_id'] = user['id']
            session['campus_id'] = user['campus_id']
            session['campus_name'] = user['campus_name']
            session['role'] = user['role']
            session['name'] = user['name']
            session['department_id'] = user['department_id']
            
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password, or account deactivated.", "danger")
            
    return render_template('user_login.html')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('user_login'))

# --- Dashboards ---

@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    tickets = execute_query(
        "SELECT t.*, d.name as department_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "WHERE t.student_id = %s AND t.campus_id = %s "
        "ORDER BY t.created_at DESC",
        (session['user_id'], session['campus_id']), fetch=True, fetchall=True
    )
    return render_template('student_dashboard.html', tickets=tickets)

@app.route('/staff/dashboard')
@login_required
@role_required(['staff'])
def staff_dashboard():
    user_id = session['user_id']
    campus_id = session['campus_id']
    
    tickets = execute_query(
        "SELECT t.*, d.name as department_name, u.name as student_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "JOIN users u ON t.student_id = u.id "
        "WHERE t.assigned_to = %s AND t.campus_id = %s "
        "ORDER BY t.updated_at DESC",
        (user_id, campus_id), fetch=True, fetchall=True
    )
    return render_template('staff_dashboard.html', tickets=tickets)

@app.route('/staff/queue')
@login_required
@role_required('staff')
def department_queue():
    dept_id = session.get('department_id')
    campus_id = session['campus_id']
    
    if not dept_id:
        flash("You are not assigned to any department.", "warning")
        return render_template('department_queue.html', tickets=[])
        
    tickets = execute_query(
        "SELECT t.*, u.name as student_name FROM tickets t "
        "JOIN users u ON t.student_id = u.id "
        "WHERE t.department_id = %s AND t.campus_id = %s AND t.status = 'OPEN' AND t.assigned_to IS NULL "
        "ORDER BY t.created_at ASC",
        (dept_id, campus_id), fetch=True, fetchall=True
    )
    return render_template('department_queue.html', tickets=tickets)

@app.route('/admin/dashboard')
@login_required
@role_required(['campus_admin', 'superadmin'])
def admin_dashboard():
    campus_id = session['campus_id']
    
    stats = {
        'total': execute_query("SELECT COUNT(*) FROM tickets WHERE campus_id = %s", (campus_id,), fetch=True)['count'],
        'open': execute_query("SELECT COUNT(*) FROM tickets WHERE status = 'OPEN' AND campus_id = %s", (campus_id,), fetch=True)['count'],
        'in_progress': execute_query("SELECT COUNT(*) FROM tickets WHERE status IN ('CLAIMED', 'IN_PROGRESS') AND campus_id = %s", (campus_id,), fetch=True)['count'],
        'escalated': execute_query("SELECT COUNT(*) FROM tickets WHERE status = 'ESCALATED' AND campus_id = %s", (campus_id,), fetch=True)['count'],
        'resolved': execute_query("SELECT COUNT(*) FROM tickets WHERE status IN ('RESOLVED', 'CLOSED') AND campus_id = %s", (campus_id,), fetch=True)['count']
    }
    
    recent_tickets = execute_query(
        "SELECT t.*, d.name as department_name, u.name as student_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "JOIN users u ON t.student_id = u.id "
        "WHERE t.campus_id = %s "
        "ORDER BY t.created_at DESC LIMIT 10", (campus_id,), fetch=True, fetchall=True
    )
    
    return render_template('admin_dashboard.html', stats=stats, tickets=recent_tickets)

# --- Tickets ---

@app.route('/ticket/create', methods=['GET', 'POST'])
@login_required
@role_required('student')
def create_ticket():
    campus_id = session['campus_id']
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        department_id = request.form['department_id']
        priority = request.form['priority']
        user_id = session['user_id']
        
        # Verify department belongs to campus
        dept = execute_query("SELECT id FROM departments WHERE id = %s AND campus_id = %s", (department_id, campus_id), fetch=True)
        if not dept:
            abort(403, description="Invalid department.")
        
        # Generate ticket code
        code_res = execute_query("SELECT count(*) FROM tickets WHERE campus_id = %s", (campus_id,), fetch=True)
        count = code_res['count'] + 101 if code_res else 101
        ticket_code = f"TK-{campus_id}-{count}"
        
        query = """
            INSERT INTO tickets (campus_id, ticket_code, title, description, priority, status, student_id, department_id)
            VALUES (%s, %s, %s, %s, %s, 'OPEN', %s, %s) RETURNING id
        """
        result = execute_query(query, (campus_id, ticket_code, title, description, priority, user_id, department_id), fetch=True, commit=True)
        
        if result:
            ticket_id = result['id']
            log_activity(ticket_id, "Ticket created", user_id)
            flash("Ticket submitted successfully.", "success")
            return redirect(url_for('student_dashboard'))
        else:
            flash("Error creating ticket.", "danger")
            
    departments = execute_query("SELECT * FROM departments WHERE campus_id = %s ORDER BY name", (campus_id,), fetch=True, fetchall=True)
    return render_template('create_ticket.html', departments=departments)

@app.route('/ticket/<int:id>')
@login_required
def ticket_details(id):
    user_id = session['user_id']
    role = session['role']
    campus_id = session['campus_id']
    
    ticket = execute_query(
        """
        SELECT t.*, d.name as department_name, s.name as student_name, a.name as assignee_name 
        FROM tickets t 
        JOIN departments d ON t.department_id = d.id 
        JOIN users s ON t.student_id = s.id 
        LEFT JOIN users a ON t.assigned_to = a.id 
        WHERE t.id = %s AND t.campus_id = %s
        """, (id, campus_id), fetch=True
    )
    
    if not ticket:
        abort(404)
        
    # Visibility checks
    if role == 'student' and ticket['student_id'] != user_id:
        abort(403)
    if role == 'staff' and ticket['department_id'] != session.get('department_id'):
        abort(403)
        
    comments = execute_query(
        "SELECT c.*, u.name as user_name, u.role as user_role FROM comments c JOIN users u ON c.user_id = u.id WHERE c.ticket_id = %s ORDER BY c.created_at ASC",
        (id,), fetch=True, fetchall=True
    )
    
    activities = execute_query(
        "SELECT a.*, u.name as user_name FROM activity_logs a LEFT JOIN users u ON a.performed_by = u.id WHERE a.ticket_id = %s ORDER BY a.created_at DESC",
        (id,), fetch=True, fetchall=True
    )
    
    staff_members = []
    if role in ['campus_admin', 'superadmin']:
        staff_members = execute_query(
            "SELECT id, name FROM users WHERE role = 'staff' AND department_id = %s AND campus_id = %s AND is_active = TRUE ORDER BY name",
            (ticket['department_id'], campus_id), fetch=True, fetchall=True
        )
    
    return render_template('ticket_details.html', ticket=ticket, comments=comments, activities=activities, staff_members=staff_members)

@app.route('/ticket/<int:id>/claim', methods=['POST'])
@login_required
@role_required('staff')
def claim_ticket(id):
    user_id = session['user_id']
    dept_id = session['department_id']
    campus_id = session['campus_id']
    
    ticket = execute_query("SELECT * FROM tickets WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    if not ticket or ticket['department_id'] != dept_id or ticket['status'] != 'OPEN':
        flash("Ticket not available for claiming.", "danger")
        return redirect(url_for('department_queue'))
        
    query = "UPDATE tickets SET assigned_to = %s, status = 'CLAIMED', claimed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'OPEN'"
    execute_query(query, (user_id, id), commit=True)
    
    log_activity(id, "Ticket claimed", user_id)
    flash("Ticket claimed successfully.", "success")
    return redirect(url_for('ticket_details', id=id))

@app.route('/ticket/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    status = request.form['status']
    user_id = session['user_id']
    role = session['role']
    campus_id = session['campus_id']
    
    ticket = execute_query("SELECT * FROM tickets WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    if not ticket:
        abort(404)
        
    # Validation: Only assigned staff or admins can update status
    if role == 'staff' and ticket['assigned_to'] != user_id:
        abort(403)
        
    update_query = "UPDATE tickets SET status = %s, updated_at = CURRENT_TIMESTAMP "
    params = [status]
    
    if status == 'ESCALATED':
        reason = request.form.get('escalation_reason', '')
        update_query += ", escalation_reason = %s "
        params.append(reason)
    elif status == 'RESOLVED':
        update_query += ", resolved_at = CURRENT_TIMESTAMP "
    elif status == 'CLOSED':
        update_query += ", closed_at = CURRENT_TIMESTAMP "
        
    update_query += "WHERE id = %s"
    params.append(id)
    
    execute_query(update_query, tuple(params), commit=True)
    log_activity(id, f"Status changed to {status}", user_id)
    
    flash(f"Ticket status updated to {status}.", "success")
    return redirect(url_for('ticket_details', id=id))

@app.route('/ticket/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    comment = request.form['comment']
    user_id = session['user_id']
    campus_id = session['campus_id']
    
    # Simple check to ensure user has access to ticket
    ticket = execute_query("SELECT * FROM tickets WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    if not ticket:
        abort(404)
        
    if session['role'] == 'student' and ticket['student_id'] != user_id:
        abort(403)
    if session['role'] == 'staff' and ticket['department_id'] != session.get('department_id'):
        abort(403)
        
    execute_query(
        "INSERT INTO comments (ticket_id, user_id, comment) VALUES (%s, %s, %s)",
        (id, user_id, comment), commit=True
    )
    
    log_activity(id, "Added a comment", user_id)
    flash("Comment added.", "success")
    return redirect(url_for('ticket_details', id=id))


# --- Admin Management Routes ---

@app.route('/admin/users', methods=['GET'])
@login_required
@role_required(['campus_admin', 'superadmin'])
def manage_users():
    campus_id = session['campus_id']
    
    users = execute_query(
        "SELECT u.*, d.name as department_name FROM users u LEFT JOIN departments d ON u.department_id = d.id WHERE u.campus_id = %s ORDER BY u.created_at DESC", 
        (campus_id,), fetch=True, fetchall=True
    )
    departments = execute_query("SELECT * FROM departments WHERE campus_id = %s ORDER BY name", (campus_id,), fetch=True, fetchall=True)
    
    staffs = [u for u in users if u['role'] == 'staff']
    students = [u for u in users if u['role'] == 'student']
    
    return render_template('manage_users.html', staffs=staffs, students=students, departments=departments)

@app.route('/admin/users/add', methods=['POST'])
@login_required
@role_required(['campus_admin', 'superadmin'])
def add_user():
    campus_id = session['campus_id']
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    university_id = request.form.get('university_id', '').strip()
    role = request.form.get('role', '').strip()
    department_id = request.form.get('department_id') or None
    password = request.form.get('password')
    
    hashed_password = generate_password_hash(password)
    
    try:
        execute_query(
            "INSERT INTO users (campus_id, university_id, name, email, password_hash, role, department_id) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (campus_id, university_id, name, email, hashed_password, role, department_id),
            commit=True
        )
        flash(f"{role.capitalize()} created successfully.", "success")
    except Exception:
        flash("Error creating user (Email or ID might exist).", "danger")
        
    return redirect(url_for('manage_users'))

@app.route('/admin/users/<int:id>/toggle', methods=['POST'])
@login_required
@role_required(['campus_admin', 'superadmin'])
def toggle_user(id):
    campus_id = session['campus_id']
    user = execute_query("SELECT * FROM users WHERE id = %s AND campus_id = %s", (id, campus_id), fetch=True)
    
    if not user:
        abort(404)
    if user['role'] == 'campus_admin':
        flash("Cannot deactivate campus admin.", "danger")
        return redirect(url_for('manage_users'))
        
    new_status = not user['is_active']
    execute_query("UPDATE users SET is_active = %s WHERE id = %s", (new_status, id), commit=True)
    
    status_str = "activated" if new_status else "deactivated"
    flash(f"User {user['name']} has been {status_str}.", "success")
    return redirect(url_for('manage_users'))

@app.route('/admin/departments', methods=['GET', 'POST'])
@login_required
@role_required(['campus_admin', 'superadmin'])
def manage_departments():
    campus_id = session['campus_id']
    if request.method == 'POST':
        name = request.form['name']
        try:
            execute_query("INSERT INTO departments (campus_id, name) VALUES (%s, %s)", (campus_id, name), commit=True)
            flash("Department added successfully.", "success")
        except Exception:
            flash("Department might already exist.", "danger")
        return redirect(url_for('manage_departments'))
        
    departments = execute_query(
        "SELECT d.*, COUNT(t.id) as ticket_count FROM departments d "
        "LEFT JOIN tickets t ON d.id = t.department_id AND t.campus_id = %s "
        "WHERE d.campus_id = %s GROUP BY d.id ORDER BY d.name", 
        (campus_id, campus_id), fetch=True, fetchall=True
    )
    return render_template('manage_departments.html', departments=departments)

@app.route('/admin/users/bulk-upload', methods=['POST'])
@login_required
@role_required(['campus_admin', 'superadmin'])
def bulk_upload_users():
    campus_id = session['campus_id']
    user_id = session['user_id']
    role = request.form.get('role', 'student')
    
    if 'csv_file' not in request.files:
        flash("No file part", "danger")
        return redirect(url_for('manage_users'))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash("No selected file", "danger")
        return redirect(url_for('manage_users'))
        
    if not file.filename.endswith('.csv'):
        flash("File must be a CSV.", "danger")
        return redirect(url_for('manage_users'))
        
    try:
        # Read CSV
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        # Create Import Job
        job = execute_query(
            "INSERT INTO import_jobs (campus_id, uploaded_by, filename, status) VALUES (%s, %s, %s, 'PROCESSING') RETURNING id",
            (campus_id, user_id, file.filename), commit=True, fetch=True
        )
        job_id = job['id']
        
        success_count = 0
        failed_count = 0
        
        for row in csv_input:
            try:
                university_id = row.get('university_id', '').strip()
                name = row.get('name', '').strip()
                email = row.get('official_email', '').strip()
                
                if not all([university_id, name, email]):
                    failed_count += 1
                    continue
                    
                default_password = generate_password_hash("password123")
                execute_query(
                    "INSERT INTO users (campus_id, university_id, name, email, password_hash, role) VALUES (%s, %s, %s, %s, %s, %s)",
                    (campus_id, university_id, name, email, default_password, role),
                    commit=True
                )
                success_count += 1
            except Exception as e:
                failed_count += 1
                
        total_rows = success_count + failed_count
        execute_query(
            "UPDATE import_jobs SET total_rows = %s, success_rows = %s, failed_rows = %s, status = 'COMPLETED' WHERE id = %s",
            (total_rows, success_count, failed_count, job_id), commit=True
        )
        
        flash(f"{role.capitalize()} import completed. Success: {success_count}, Failed: {failed_count}.", "success")
        
    except Exception as e:
        flash(f"Error processing file: {str(e)}", "danger")
        
    return redirect(url_for('manage_users'))

if __name__ == '__main__':
    app.run(debug=True)
