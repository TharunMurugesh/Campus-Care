# Cumin

> **Unified multi-tenant operations, issue tracking, and service desk platform for organizations, firms, enterprises, communities, and educational institutions.** Built with Python, Flask, and PostgreSQL.

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black.svg)](https://palletsprojects.com/p/flask/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

**Cumin** is a multi-tenant service desk and operational coordination system designed to scale across diverse organizational models:
- **Corporate Firms & Enterprises:** IT helpdesk, Human Resources (HR) inquiries, facilities, procurement, and legal requests.
- **Tech Startups & Small Businesses:** Developer operations, equipment provisioning, workplace ops.
- **Educational Institutions:** School & campus facilities, academic inquiries, student welfare, IT help.
- **Nonprofits & Foundations:** Volunteer coordination, donor relations, grant and outreach tracking.
- **Residential & Property Communities:** HOAs, property management, maintenance and building requests.
- **Co-working Spaces & Collectives:** Member amenities, conference room issues, community management.

Each organization operates inside its own isolated tenant workspace with customized support teams, dedicated member/employee rosters, role-based access control, and SLA-aware resolution tracking.

---

## Key Features

- **Multi-Tenant Isolation:** Complete data separation for each organization or firm, secured by scoped tenant identifiers.
- **Flexible Organization Types:** Tailored onboarding for Companies, Startups, Schools, Universities, Nonprofits, Co-working spaces, Residential communities, and more.
- **Self-Service Workspace Provisioning:** Instant workspace creation without requiring mandatory institutional domain whitelists.
- **Role-Based Access Control (RBAC):**
  - **Organization Admins:** Workspace configuration, support team management, member roster provisioning, assignment, and global metrics.
  - **Support Staff / Agents:** Department-scoped queues, ticket claiming, status lifecycle updates, and activity logging.
  - **Members & Employees:** Issue submission, real-time status tracking, two-way discussion threads.
- **Support Team Dispatching:** Routing to specialized teams (e.g., IT Support, HR & People Ops, Workplace Facilities, Finance & Billing, Legal).
- **Comprehensive Lifecycle Tracking:** Six distinct ticket statuses (`OPEN`, `CLAIMED`, `IN_PROGRESS`, `ESCALATED`, `RESOLVED`, `CLOSED`) with escalation reason audits.
- **Bulk CSV Provisioning:** One-click onboarding for staff and members with optional Employee/Member IDs and department mappings.
- **Modern UI & Design System:** Responsive Bootstrap 5 + Bootstrap Icons interface with warm Cumin design language, KPI metric cards, dynamic filter pills, and mobile-ready layouts.
- **Production-Ready Core:** CSRF token verification, PBKDF2 password hashing with salt, `ThreadedConnectionPool` connection pooling, and multi-tier query optimization.

---

## Quick Start

### Option A — Docker Compose (Recommended)

1. Clone the repository and configure the environment:
   ```bash
   git clone https://github.com/TharunMurugesh/cumin.git
   cd cumin
   cp .env.example .env
   ```
2. Start the application stack:
   ```bash
   docker compose up --build
   ```
3. Open your browser at **http://localhost:5000**.

### Option B — Local Development

For a **fresh local database bootstrap**:

```bash
sudo bash setup_db.sh
docker compose -f docker-compose.dev.yml up --build
```

> [!NOTE]
> `setup_db.sh` loads `schema.sql`, which bootstraps the fresh application tables and creates a dedicated database role. For existing deployments with active data, use the non-destructive migration script described below.

---

## First Steps & User Journey

1. **Create an Organization Workspace:**
   - Navigate to `/org/register` (or `/community/register`).
   - Enter your company/organization name, choose its category (e.g. *Company / Enterprise / Firm*), and create the initial admin account.
   - Save your generated access code (e.g. `CM20260001`).

2. **Access Admin Portal:**
   - Sign in at `/org/admin-login` with your access code and master password.

3. **Configure Support Teams:**
   - Go to **Support Teams** (`/admin/departments`) and add the departments your organization needs (e.g., *IT Support*, *Facilities & Workplace*, *Human Resources*).

4. **Add Members & Staff:**
   - In **Users & Roster** (`/admin/users`), add team members individually or upload a CSV file with columns: `name, email, member_id, team`.

5. **Submit & Coordinate Requests:**
   - Members and employees sign in at `/login` to file support tickets.
   - Staff sign in at `/login` to claim tickets from their team queue (`/staff/queue`) or manage assigned tickets (`/staff/dashboard`).

---

## Existing Installations & Upgrades

To upgrade an existing installation while preserving all tenant data, tickets, and accounts:

```bash
psql -v ON_ERROR_STOP=1 -d cumin_db -f db/cumin_rebranding_migration.sql
```

The migration updates user role constraints to include `employee` and `org_admin`, ensures organization types are available, and creates the `organizations` view. Legacy `/campus/*` and `/community/*` URLs and identifiers remain fully backwards compatible.

---

## Project Structure

```text
cumin/
├── app.py                      # Flask application, routing, and controllers
├── db.py                       # PostgreSQL connection pooling, query execution, caching
├── wsgi.py                     # WSGI production entrypoint
├── schema.sql                  # Fresh-install database schema and indexes
├── setup_db.sh                 # Database bootstrap script
├── Dockerfile                  # Production container configuration
├── docker-compose.yml          # Production multi-container compose file
├── docker-compose.dev.yml      # Development compose file with live volume reload
├── requirements.txt            # Python dependencies
├── db/
│   ├── cumin_rebranding_migration.sql   # Safe in-place migration for Cumin rebranding
│   ├── community_expansion_migration.sql # Prior community expansion migration
│   └── partitioning_migration.sql        # High-volume ticket partitioning migration
├── templates/                  # Jinja2 templates
│   ├── base.html               # Master layout with modern Cumin navbar & footer
│   ├── _macros.html            # UI components (status badges, pagination, search)
│   ├── user_login.html         # Member & staff portal sign in
│   ├── campus_login.html       # Organization admin sign in
│   ├── campus_create.html      # Organization workspace registration
│   ├── admin_dashboard.html    # Organization admin analytics & ticket queue
│   ├── student_dashboard.html  # Member & employee request dashboard
│   ├── staff_dashboard.html    # Support staff assigned tickets
│   ├── department_queue.html   # Support staff team triage queue
│   ├── ticket_details.html     # Ticket discussion, assignment & status workflow
│   ├── create_ticket.html      # Ticket submission form
│   ├── manage_users.html       # User directory & bulk CSV onboarding
│   └── manage_departments.html # Support teams & department manager
└── static/
    └── css/
        └── style.css           # Cumin design system & modern CSS variables
```

---

## Configuration Reference

Configuration is managed via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` / `127.0.0.1` | PostgreSQL database host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `cumin_db` | Database name (falls back to `campus_issue_system`) |
| `DB_USER` | `cumin_app` | Dedicated database user role |
| `DB_PASSWORD` | — | Database user password |
| `FLASK_SECRET_KEY` | — | Session signature key |
| `FLASK_ENV` | `dev` | `dev` or `production` |
| `DB_POOL_MIN` | `2` | Minimum connection pool size |
| `DB_POOL_MAX` | `10` | Maximum connection pool size |
| `SESSION_COOKIE_SECURE` | `0` | Set to `1` when running in production with HTTPS |

---

## Technology Stack

- **Backend:** Python 3.12+, Flask
- **Database:** PostgreSQL 16 (via `psycopg2` threaded connection pool)
- **Frontend:** HTML5, Bootstrap 5.3, Bootstrap Icons, Jinja2, Custom CSS Design System
- **Server:** Gunicorn WSGI, Docker Alpine

---

## License

This project is licensed under the [MIT License](LICENSE).
