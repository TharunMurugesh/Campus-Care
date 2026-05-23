# Campus Issue Reporting and Escalation System

A minimal, light, and responsive campus ticketing system built with Flask and PostgreSQL.

## Features
- Role-based access (Student, Staff, Super Admin)
- Department-wise ticket routing and queue management
- Ticket claiming and exclusive assignment
- Activity timeline and comments
- Responsive Bootstrap 5 UI

## Setup Instructions

### 1. Database Setup
Create a PostgreSQL database and execute the schema and seed files.
```bash
# Assuming psql is available and postgres user exists
createdb -U postgres campus_tickets_db
psql -U postgres -d campus_tickets_db -f schema.sql
psql -U postgres -d campus_tickets_db -f seed.sql
```

### 2. Environment Variables
Copy `.env.example` to `.env` and update the database credentials.
```bash
cp .env.example .env
```

### 3. Install Dependencies
It's recommended to use a virtual environment.
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```
Access the application at `http://127.0.0.1:5000`

## Default Users (from seed.sql)
- **Superadmin**: admin@campus.edu / password123
- **Student**: student1@campus.edu / password123
- **Staff (IT)**: it_staff@campus.edu / password123
