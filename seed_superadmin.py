import getpass
import sys

import psycopg2
from werkzeug.security import generate_password_hash

SUPERADMIN_CAMPUS_ID = 0


def prompt_credentials():
    print()
    print("Create the global superadmin account.")
    print()
    email = ""
    while not email or "@" not in email:
        email = input("Superadmin email: ").strip()
        if "@" not in email:
            print("  Enter a valid email.")

    name = ""
    while not name:
        name = input("Display name: ").strip()

    while True:
        pw = getpass.getpass("Password: ")
        if len(pw) < 8:
            print("  At least 8 characters.")
            continue
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print("  Passwords did not match.")
            continue
        break
    return email, name, pw


def main():
    if len(sys.argv) < 2:
        print("Usage: seed_superadmin.py <db_name>", file=sys.stderr)
        sys.exit(1)
    db_name = sys.argv[1]

    email, name, pw = prompt_credentials()
    pw_hash = generate_password_hash(pw)

    conn = psycopg2.connect(dbname=db_name, user="postgres")
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (campus_id, email, name, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, 'superadmin', TRUE)
                    ON CONFLICT (campus_id, email) DO UPDATE SET
                        name          = EXCLUDED.name,
                        password_hash = EXCLUDED.password_hash,
                        role          = 'superadmin',
                        is_active     = TRUE
                    """,
                    (SUPERADMIN_CAMPUS_ID, email, name, pw_hash),
                )
    finally:
        conn.close()

    print()
    print(f"Superadmin '{email}' created. Login at /superadmin/login.")


if __name__ == "__main__":
    main()
