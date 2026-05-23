import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from db import execute_query

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'default-dev-key')

# --- Decorators for Access Control ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('student_login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('student_login'))
            if session.get('role') != role:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Helper to Log Activity ---
def log_activity(ticket_id, action, user_id):
    query = "INSERT INTO activity_logs (ticket_id, action, performed_by) VALUES (%s, %s, %s)"
    execute_query(query, (ticket_id, action, user_id), commit=True)

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role')
        if role == 'student':
            return redirect(url_for('student_dashboard'))
        elif role == 'staff':
            return redirect(url_for('staff_dashboard'))
        elif role == 'superadmin':
            return redirect(url_for('superadmin_dashboard'))
    return redirect(url_for('student_login'))

# --- Auth Routes ---

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = execute_query("SELECT * FROM users WHERE email = %s AND role = 'student'", (email,), fetch=True)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password for Student.", "danger")
            
    return render_template('student_login.html')

@app.route('/student/register', methods=['GET', 'POST'])
def student_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = 'student'
        hashed_password = generate_password_hash(password)
        
        try:
            execute_query(
                "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, role),
                commit=True
            )
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('student_login'))
        except Exception:
            flash("Email already registered.", "danger")
            
    return render_template('student_register.html')

@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = execute_query("SELECT * FROM users WHERE email = %s AND role IN ('staff', 'superadmin')", (email,), fetch=True)
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['name'] = user['name']
            session['department_id'] = user['department_id']
            
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password for Staff/Admin.", "danger")
            
    return render_template('staff_login.html')

@app.route('/staff/register', methods=['GET', 'POST'])
def staff_register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        department_id = request.form['department_id']
        role = 'staff'
        hashed_password = generate_password_hash(password)
        
        try:
            execute_query(
                "INSERT INTO users (name, email, password_hash, role, department_id) VALUES (%s, %s, %s, %s, %s)",
                (name, email, hashed_password, role, department_id),
                commit=True
            )
            flash("Staff account created successfully! You can now log in.", "success")
            return redirect(url_for('staff_login'))
        except Exception:
            flash("Email already registered.", "danger")
            
    departments = execute_query("SELECT * FROM departments ORDER BY name", fetch=True, fetchall=True)
    return render_template('staff_register.html', departments=departments)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('student_login'))

# --- Student Routes ---

@app.route('/student/dashboard')
@login_required
@role_required('student')
def student_dashboard():
    tickets = execute_query(
        "SELECT t.*, d.name as department_name, u.name as student_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "JOIN users u ON t.student_id = u.id "
        "ORDER BY t.created_at DESC",
        fetch=True, fetchall=True
    )
    return render_template('student_dashboard.html', tickets=tickets)

@app.route('/student/ticket/create', methods=['GET', 'POST'])
@login_required
@role_required('student')
def create_ticket():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        department_id = request.form['department_id']
        priority = request.form['priority']
        user_id = session['user_id']
        
        # Generate a simple ticket code
        code_res = execute_query("SELECT count(*) FROM tickets", fetch=True)
        count = code_res['count'] + 101 if code_res else 101
        ticket_code = f"CAMP-{count}"
        
        query = """
            INSERT INTO tickets (ticket_code, title, description, priority, status, student_id, department_id)
            VALUES (%s, %s, %s, %s, 'OPEN', %s, %s) RETURNING id
        """
        result = execute_query(query, (ticket_code, title, description, priority, user_id, department_id), fetch=True, commit=True)
        
        if result:
            ticket_id = result['id']
            log_activity(ticket_id, "Ticket created", user_id)
            flash("Ticket submitted successfully.", "success")
            return redirect(url_for('student_dashboard'))
        else:
            flash("Error creating ticket.", "danger")
            
    departments = execute_query("SELECT * FROM departments ORDER BY name", fetch=True, fetchall=True)
    return render_template('create_ticket.html', departments=departments)

# --- Staff Routes ---

@app.route('/staff/dashboard')
@login_required
@role_required('staff')
def staff_dashboard():
    user_id = session['user_id']
    tickets = execute_query(
        "SELECT t.*, d.name as department_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "WHERE t.assigned_to = %s ORDER BY t.updated_at DESC",
        (user_id,), fetch=True, fetchall=True
    )
    return render_template('staff_dashboard.html', tickets=tickets)

@app.route('/staff/queue')
@login_required
@role_required('staff')
def department_queue():
    dept_id = session.get('department_id')
    tickets = execute_query(
        "SELECT t.*, u.name as student_name FROM tickets t "
        "JOIN users u ON t.student_id = u.id "
        "WHERE t.department_id = %s AND t.status = 'OPEN' AND t.assigned_to IS NULL "
        "ORDER BY t.created_at ASC",
        (dept_id,), fetch=True, fetchall=True
    )
    return render_template('department_queue.html', tickets=tickets)

@app.route('/ticket/<int:id>/claim', methods=['POST'])
@login_required
@role_required('staff')
def claim_ticket(id):
    user_id = session['user_id']
    dept_id = session['department_id']
    
    ticket = execute_query("SELECT * FROM tickets WHERE id = %s", (id,), fetch=True)
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
    
    ticket = execute_query("SELECT * FROM tickets WHERE id = %s", (id,), fetch=True)
    if not ticket:
        abort(404)
        
    # Validation: Only assigned staff or superadmin can update status
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

# --- Common Routes ---

@app.route('/ticket/<int:id>')
@login_required
def ticket_details(id):
    user_id = session['user_id']
    role = session['role']
    
    ticket = execute_query(
        """
        SELECT t.*, d.name as department_name, s.name as student_name, a.name as assignee_name 
        FROM tickets t 
        JOIN departments d ON t.department_id = d.id 
        JOIN users s ON t.student_id = s.id 
        LEFT JOIN users a ON t.assigned_to = a.id 
        WHERE t.id = %s
        """, (id,), fetch=True
    )
    
    if not ticket:
        abort(404)
        
    # Visibility checks
    if role == 'staff' and ticket['department_id'] != session['department_id']:
        abort(403)
        
    comments = execute_query(
        "SELECT c.*, u.name as user_name, u.role as user_role FROM comments c JOIN users u ON c.user_id = u.id WHERE c.ticket_id = %s ORDER BY c.created_at ASC",
        (id,), fetch=True, fetchall=True
    )
    
    activities = execute_query(
        "SELECT a.*, u.name as user_name FROM activity_logs a LEFT JOIN users u ON a.performed_by = u.id WHERE a.ticket_id = %s ORDER BY a.created_at DESC",
        (id,), fetch=True, fetchall=True
    )
    
    return render_template('ticket_details.html', ticket=ticket, comments=comments, activities=activities)

@app.route('/ticket/<int:id>/comment', methods=['POST'])
@login_required
def add_comment(id):
    comment = request.form['comment']
    user_id = session['user_id']
    
    execute_query(
        "INSERT INTO comments (ticket_id, user_id, comment) VALUES (%s, %s, %s)",
        (id, user_id, comment), commit=True
    )
    
    log_activity(id, "Added a comment", user_id)
    flash("Comment added.", "success")
    return redirect(url_for('ticket_details', id=id))

# --- Super Admin Routes ---

@app.route('/superadmin/dashboard')
@login_required
@role_required('superadmin')
def superadmin_dashboard():
    stats = {
        'total': execute_query("SELECT COUNT(*) FROM tickets", fetch=True)['count'],
        'open': execute_query("SELECT COUNT(*) FROM tickets WHERE status = 'OPEN'", fetch=True)['count'],
        'in_progress': execute_query("SELECT COUNT(*) FROM tickets WHERE status IN ('CLAIMED', 'IN_PROGRESS')", fetch=True)['count'],
        'escalated': execute_query("SELECT COUNT(*) FROM tickets WHERE status = 'ESCALATED'", fetch=True)['count'],
        'resolved': execute_query("SELECT COUNT(*) FROM tickets WHERE status IN ('RESOLVED', 'CLOSED')", fetch=True)['count']
    }
    
    recent_tickets = execute_query(
        "SELECT t.*, d.name as department_name, u.name as student_name FROM tickets t "
        "JOIN departments d ON t.department_id = d.id "
        "JOIN users u ON t.student_id = u.id "
        "ORDER BY t.created_at DESC LIMIT 10", fetch=True, fetchall=True
    )
    
    return render_template('superadmin_dashboard.html', stats=stats, tickets=recent_tickets)

@app.route('/superadmin/users', methods=['GET', 'POST'])
@login_required
@role_required('superadmin')
def manage_users():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        role = request.form['role']
        department_id = request.form.get('department_id')
        password = request.form['password']
        
        if department_id == '':
            department_id = None
            
        hashed_password = generate_password_hash(password)
        
        try:
            execute_query(
                "INSERT INTO users (name, email, password_hash, role, department_id) VALUES (%s, %s, %s, %s, %s)",
                (name, email, hashed_password, role, department_id), commit=True
            )
            flash("User created successfully.", "success")
        except Exception:
            flash("Error creating user (email might exist).", "danger")
            
        return redirect(url_for('manage_users'))
        
    users = execute_query(
        "SELECT u.*, d.name as department_name FROM users u LEFT JOIN departments d ON u.department_id = d.id ORDER BY u.created_at DESC", 
        fetch=True, fetchall=True
    )
    departments = execute_query("SELECT * FROM departments ORDER BY name", fetch=True, fetchall=True)
    return render_template('manage_users.html', users=users, departments=departments)

@app.route('/superadmin/departments', methods=['GET', 'POST'])
@login_required
@role_required('superadmin')
def manage_departments():
    if request.method == 'POST':
        name = request.form['name']
        try:
            execute_query("INSERT INTO departments (name) VALUES (%s)", (name,), commit=True)
            flash("Department added successfully.", "success")
        except Exception:
            flash("Department might already exist.", "danger")
        return redirect(url_for('manage_departments'))
        
    departments = execute_query(
        "SELECT d.*, COUNT(t.id) as ticket_count FROM departments d "
        "LEFT JOIN tickets t ON d.id = t.department_id GROUP BY d.id ORDER BY d.name", 
        fetch=True, fetchall=True
    )
    return render_template('manage_departments.html', departments=departments)

if __name__ == '__main__':
    app.run(debug=True)
