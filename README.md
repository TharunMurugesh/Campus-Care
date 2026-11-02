# CampusCare

Multi-tenant issue reporting and support coordination for communities of all kinds: schools, universities, nonprofits, neighborhood groups, workplaces, volunteer organizations, and online communities. Built with Flask and PostgreSQL.

## Features

- Separate, isolated workspaces for each community or organization
- Self-service community onboarding without requiring an institutional email domain
- Community type selection during registration
- Member, staff, and community admin roles
- Issue reporting, team routing, comments, escalation, and resolution tracking
- Manual and CSV member onboarding with optional member IDs
- Searchable, sortable, paginated views
- CSRF protection, password hashing, connection pooling, and stats caching

## Quick Start

### Option A — Docker

```bash
cp .env.example .env
# edit .env with your DB credentials
docker compose up --build
```

The app runs at http://localhost:5000.

### Option B — Local Development

For a **fresh local database only**:

```bash
sudo bash setup_db.sh
docker compose -f docker-compose.dev.yml up --build
```

`setup_db.sh` loads `schema.sql`, which drops and recreates the application tables. Do not use it on a database that contains data you want to keep.

## First Steps

1. Create a workspace at `/community/register` and choose its community type.
2. Save the generated community access code and sign in at `/community/admin-login`.
3. Create support teams that fit your community, such as facilities, moderation, or volunteer coordination.
4. Add members and staff directly or import them from CSV. Email is required; member IDs are optional.
5. Members sign in at `/login` to report and track issues.
6. Staff sign in at `/login` to work on issues assigned to their teams.
7. Community admins manage teams, accounts, and reports from the admin dashboard.

The previous `/campus/register` and `/campus/login` URLs remain as aliases for existing links.

## Existing Installations

To preserve existing data, back up the database and apply the non-destructive community expansion migration:

```bash
psql -v ON_ERROR_STOP=1 -d campus_issue_system -f db/community_expansion_migration.sql
```

The migration adds a community type, makes institutional domains optional, and changes existing student accounts into general members. Internal database column names retain some campus/school-era terminology for compatibility.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, Flask |
| Database | PostgreSQL 16 (psycopg2, connection pool) |
| Frontend | HTML5, Bootstrap 5, Jinja2 |
| Production | Gunicorn, Docker |

## Project Structure

```
app.py                  # Flask application and routes
db.py                   # Connection pool, pagination, caching
wsgi.py                 # Gunicorn entry point
schema.sql              # Fresh-install database schema
setup_db.sh             # Fresh local database bootstrap
db/community_expansion_migration.sql # Safe in-place community migration
db/partitioning_migration.sql        # Optional ticket partitioning
Dockerfile
docker-compose.yml
docker-compose.dev.yml
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

## Database Scaling

- Connection pooling via `psycopg2.pool.ThreadedConnectionPool`
- Composite and partial indexes for dashboard and queue queries
- Per-community ticket counters and stats rollups
- Optional monthly ticket partitioning in `db/partitioning_migration.sql`

## License

MIT
