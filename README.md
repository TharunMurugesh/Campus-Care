# CampusCare: Multi-Campus Issue Reporting & Escalation System

CampusCare is a secure, light, and highly responsive multi-tenant SaaS application built with Flask and PostgreSQL. It allows multiple universities or institutions to register their own isolated workspaces to manage internal issue reporting, IT support tickets, and facilities management.

## 🌟 Key Features

* **Multi-Tenant Architecture:** Complete data isolation for different campuses. One application instance can securely serve multiple universities.
* **Campus Registration Flow:** Intuitive self-service onboarding that generates unique `Campus Codes` for administrators.
* **Bulk User Import:** Seamless, standard-library-backed CSV imports for rapidly onboarding hundreds of staff and students.
* **Granular Role-Based Access Control:** Distinct dashboards and permissions for Students, Staff, and Campus Admins.
* **Ticket Management:** Department-wise routing, ticket claiming, priority assignments, status tracking, and commenting system.
* **Security-First Approach:** Hardened with strict session-based multi-tenancy, per-request dynamic CSRF tokens, and secure password hashing.
* **Modern Interface:** Built with Bootstrap 5 and vanilla JavaScript/TypeScript for a clean, professional, "zero-bloat" aesthetic.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask
* **Database:** PostgreSQL (with `psycopg2`)
* **Frontend:** HTML5, CSS3, Bootstrap 5, Jinja2, TypeScript (minimal)

---

## 🚀 Setup Instructions

### 1. Database Setup
Create a PostgreSQL database and execute the schema file. There is no seed data required, as the application is designed to be fully self-service from a clean slate.

```bash
# Drop and recreate the database
dropdb -U postgres --if-exists campus_issue_system
createdb -U postgres campus_issue_system

# Apply the multi-campus schema
psql -U postgres -d campus_issue_system -f schema.sql
```

### 2. Environment Variables
Copy `.env.example` to `.env` and update your database credentials and secret key.

```bash
cp .env.example .env
```

Ensure your `.env` looks like this:
```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=campus_issue_system
DB_USER=postgres
DB_PASSWORD=your_password
FLASK_SECRET_KEY=your_secure_random_key
```

### 3. Install Dependencies
It's highly recommended to use a virtual environment.

```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux
venv\Scripts\activate     # On Windows

# Install required packages
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```
Access the application at `http://127.0.0.1:5000`

---

## 📖 Getting Started (User Guide)

1. **Register Your Campus:** 
   Navigate to `http://127.0.0.1:5000/campus/register` to register your institution. You will be provided with a unique **Campus Code** (e.g., `CC20260001`).
2. **Admin Login:** 
   Go to `http://127.0.0.1:5000/campus/login` and use your Campus Code and Admin password to access the Admin Dashboard.
3. **Configure Departments:** 
   From the dashboard, create departments (e.g., "IT Support", "Maintenance").
4. **Onboard Users:** 
   Navigate to the **Users** tab to manually add users or use the **Bulk Add** feature with a `.csv` file. 
   *(CSV Format required: `university_id, name, official_email`)*
5. **Start Reporting:** 
   Students and Staff can now log in at `http://127.0.0.1:5000/login` to create, claim, and resolve tickets.

---

## 🔐 Security Details

* **Tenant Isolation:** Every SQL query hitting the `users`, `departments`, or `tickets` tables is strictly filtered by the authenticated user's `campus_id` stored securely in the Flask session.
* **CSRF Protection:** All `POST`, `PUT`, and `DELETE` requests require a `_csrf_token` which is validated against the user's active session before any request is processed.
* **Password Hashing:** Utilizing Werkzeug's secure hashing algorithms (`scrypt`) with unique salting per user.

## 📄 License
This project is open-source and available under the MIT License.
