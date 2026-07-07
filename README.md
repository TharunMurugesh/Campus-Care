# CampusCare

Multi-tenant issue reporting and ticketing system for universities and institutions. Built with Flask and PostgreSQL.

## Features

- Multi-campus isolation with unique campus codes
- Campus admin self-service onboarding
- Role-based access: student, staff, campus admin, super admin
- Ticket lifecycle: create → claim → resolve → close (with escalation)
- Department-wise routing and queue management
- Bulk user import via CSV
- Global super admin analytics with per-campus and per-department breakdowns
- Paginated, searchable, sortable views across all dashboards
- Connection pooling and stats caching for performance
- CSRF protection and scrypt password hashing

## Quick Start

### Option A — Docker

```bash
cp .env.example .env
# edit .env with your DB credentials
docker compose up --build
```

The app runs at http://localhost:5000.

### Option B — Local Development

```bash
sudo bash setup_db.sh
# follow the prompts to create the super admin

source venv/bin/activate
pip install -r requirements.txt
python app.py
```

The app runs at http://127.0.0.1:5000.

For hot-reload with Docker:

```bash
docker compose -f docker-compose.dev.yml up --build
```

## First Steps

1. **Register a campus** at `/campus/register`. Save the generated campus code.
2. **Campus admin login** at `/campus/login` with the campus code and password.
3. **Create departments** from the admin dashboard.
4. **Add users** (manually or via bulk CSV import).
5. **Students** log in at `/login` to create and track tickets.
6. **Staff** log in at `/login` to claim and resolve tickets from their department queue.
7. **Super admin** logs in at `/superadmin/login` for cross-campus analytics.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Database | PostgreSQL 16 (psycopg2, connection pool) |
| Frontend | HTML5, Bootstrap 5, Jinja2 |
| Production | Gunicorn, Docker |

## Project Structure

```
app.py                  # Flask application and all routes
db.py                   # Connection pool, pagination, caching
wsgi.py                 # Gunicorn entry point
schema.sql              # Database schema (sequences, indexes, triggers, rollups)
seed_superadmin.py      # Interactive super admin seeder
setup_db.sh             # One-time database bootstrap script
db/partitioning_migration.sql  # Optional ticket partitioning (for high volume)
Dockerfile
docker-compose.yml      # Production
docker-compose.dev.yml  # Development (hot-reload)
templates/              # Jinja2 HTML templates
static/                 # CSS and JS
```

## Configuration

All config is through `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| DB_HOST | localhost | Database host |
| DB_PORT | 5432 | Database port |
| DB_NAME | campus_issue_system | Database name |
| DB_USER | campus_app | App database role |
| DB_PASSWORD | — | App role password |
| FLASK_SECRET_KEY | — | Session signing key |
| FLASK_ENV | dev | dev or production |
| DB_POOL_MIN | 2 | Min connection pool size |
| DB_POOL_MAX | 10 | Max connection pool size |
| SESSION_COOKIE_SECURE | 0 | Set to 1 in production with HTTPS |

## Super Admin

The super admin account is created during `setup_db.sh`. It has cross-campus access to all analytics:

- Global KPIs (total campuses, users, tickets, resolution times)
- Per-campus breakdown (sortable)
- Department load analysis (top 20)
- Top performing staff

## Database Scaling

- **Connection pooling** via `psycopg2.pool.ThreadedConnectionPool`
- **Composite and partial indexes** for dashboard and queue queries
- **Stats rollups** in `campus_stats` table, refreshed on ticket state changes
- **Partitioning readiness** — run `db/partitioning_migration.sql` to convert tickets to monthly range partitions when volume warrants it

## License

MIT
