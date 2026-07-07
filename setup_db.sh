#!/usr/bin/env bash
set -euo pipefail

DB_NAME="${DB_NAME:-campus_issue_system}"
DB_USER="${DB_USER:-campus_app}"
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
[[ -f "$SCRIPT_DIR/schema.sql" ]]         || { red "schema.sql missing."; exit 1; }
[[ -f "$SCRIPT_DIR/seed_superadmin.py" ]] || { red "seed_superadmin.py missing."; exit 1; }

PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python
rand_str() { "$PY" -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range($1)))"; }

green "==> CampusCare database bootstrap"
echo    "    Database : $DB_NAME"
echo    "    Role     : $DB_USER"
echo    "    Repo user: $REAL_USER"
echo

read -r -p "This will DROP and recreate '$DB_NAME' and role '$DB_USER'. Continue? [y/N] " ans
case "$ans" in
  y|Y) ;;
  *) yellow "Aborted."; exit 0 ;;
esac

APP_PASSWORD="$(rand_str 24)"
[[ -n "$APP_PASSWORD" ]] || { red "password generation failed."; exit 1; }

green "==> Creating role '$DB_USER'"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
   IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DB_USER') THEN
      CREATE ROLE $DB_USER LOGIN PASSWORD '$APP_PASSWORD';
   ELSE
      ALTER ROLE $DB_USER LOGIN PASSWORD '$APP_PASSWORD';
   END IF;
END\$\$;
SQL

green "==> Recreating database '$DB_NAME'"
sudo -u postgres dropdb --if-exists "$DB_NAME"
sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"

green "==> Loading schema.sql as $DB_USER (over TCP)"
PGPASSWORD="$APP_PASSWORD" psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 -f "$SCRIPT_DIR/schema.sql"

green "==> Seeding superadmin (as $REAL_USER)"
if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
  SEED_PY="$SCRIPT_DIR/venv/bin/python"
else
  SEED_PY="$PY"
fi
sudo -u "$REAL_USER" env \
  PGHOST=127.0.0.1 PGPORT=5432 PGUSER="$DB_USER" PGPASSWORD="$APP_PASSWORD" PGDATABASE="$DB_NAME" \
  PYTHONPATH="$SCRIPT_DIR" "$SEED_PY" "$SCRIPT_DIR/seed_superadmin.py"

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
echo    "    Database : $DB_NAME"
echo    "    App role : $DB_USER (password written to .env)"
echo    "    .env     : regenerated"
echo
yellow "Next:"
echo    "    source venv/bin/activate"
echo    "    pip install -r requirements.txt"
echo    "    python app.py   ->  http://127.0.0.1:5000"
echo
yellow "Superadmin login: http://127.0.0.1:5000/superadmin/login"
