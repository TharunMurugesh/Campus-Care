#!/usr/bin/env bash
# One-time database bootstrap for Cumin Operations & Service Desk.
#
# Usage:  sudo bash setup_db.sh
#
# Designed to recover gracefully if a previous run partially completed
# (e.g. role + DB created but schema load or seeder failed).
set -euo pipefail

DB_NAME="${DB_NAME:-cumin_db}"
DB_USER="${DB_USER:-cumin_app}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REAL_USER="${SUDO_USER:-${USER:-$(logname 2>/dev/null || echo nobody)}}"

green()  { printf '\033[1;32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[1;33m%s\033[0m\n' "$*"; }
red()    { printf '\033[1;31m%s\033[0m\n' "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
  red "Run as root: sudo bash setup_db.sh"
  exit 1
fi

command -v psql >/dev/null 2>&1 || { red "psql not found."; exit 1; }
command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 || { red "python not found."; exit 1; }
[[ -f "$SCRIPT_DIR/schema.sql" ]] || { red "schema.sql missing."; exit 1; }

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
rand_str() { "$PY" -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range($1)))"; }

green "==> Cumin Operations & Support Platform database bootstrap"
echo    "    Database : $DB_NAME"
echo    "    Role     : $DB_USER"
echo    "    Repo user: $REAL_USER"
echo

# ---- Detect prior partial run -----------------------------------------------
ROLE_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | tr -d '[:space:]')
DB_EXISTS=$(sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | tr -d '[:space:]')
TABLE_COUNT=0
if [[ "$DB_EXISTS" == "1" ]]; then
  TABLE_COUNT=$(sudo -u postgres psql -d "$DB_NAME" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null | tr -d '[:space:]' || echo 0)
fi

echo "    Role exists        : ${ROLE_EXISTS:-no}"
echo "    Database exists    : ${DB_EXISTS:-no}"
echo "    Tables loaded      : $TABLE_COUNT"
echo

# Always (re)set the app password — this is the only thing that strictly
# needs sudo, because tm lacks CREATEROLE.
APP_PASSWORD="$(rand_str 24)"
[[ -n "$APP_PASSWORD" ]] || { red "password generation failed."; exit 1; }

if [[ "$ROLE_EXISTS" == "1" ]]; then
  green "==> Resetting password for existing role '$DB_USER'"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "ALTER ROLE $DB_USER WITH LOGIN PASSWORD '$APP_PASSWORD';"
else
  green "==> Creating role '$DB_USER'"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE ROLE $DB_USER LOGIN PASSWORD '$APP_PASSWORD';"
  DB_EXISTS=no
fi

# ---- Database + schema ------------------------------------------------------
if [[ "$DB_EXISTS" != "1" ]]; then
  green "==> Creating database '$DB_NAME'"
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
  TABLE_COUNT=0
fi

# Schema loads are idempotent (schema.sql drops & recreates everything).
# We load as $DB_USER over TCP so the postgres OS user doesn't need to read
# files inside the (700-mode) home directory — fixes the WSL permission error.
green "==> Loading schema.sql as $DB_USER (over TCP)"
PGPASSWORD="$APP_PASSWORD" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 -f "$SCRIPT_DIR/schema.sql"

# ---- Write .env ------------------------------------------------------------
ENV_FILE="$SCRIPT_DIR/.env"
SECRET_KEY="$("$PY" -c 'import secrets;print(secrets.token_hex(32))')"
[[ -n "$SECRET_KEY" ]] || SECRET_KEY="$(date +%s | sha256sum | head -c 64)"

cat > "$ENV_FILE" <<EOF
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$APP_PASSWORD
FLASK_SECRET_KEY=$SECRET_KEY
FLASK_ENV=dev
DB_POOL_MIN=2
DB_POOL_MAX=10
SESSION_COOKIE_SECURE=0
EOF
chmod 600 "$ENV_FILE"
chown "$REAL_USER" "$ENV_FILE" 2>/dev/null || true

echo
green "==> Done."
echo    "    Database : $DB_NAME (schema loaded)"
echo    "    App role : $DB_USER (password written to .env)"
echo    "    .env     : regenerated"
echo
yellow "Next:"
echo    "    source venv/bin/activate"
echo    "    pip install -r requirements.txt"
echo    "    python app.py   ->  http://127.0.0.1:5000"
echo
