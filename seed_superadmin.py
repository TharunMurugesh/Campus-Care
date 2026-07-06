#!/usr/bin/env python3
"""
One-time superadmin seeder, run by setup_db.sh.

Usage (invoked by setup_db.sh):
    env PYTHONPATH=. python seed_superadmin.py <db_name>

The DB connection uses the local `postgres` peer-auth role (this script is
run via `sudo -u postgres`), NOT the app role. The superadmin password is
read securely via getpass and hashed with Werkzeug scrypt before being
written to the database. It is never echoed or logged.

Re-running safely updates an existing superadmin row matching the email.
"""
import getpass
import os
import sys

import psycopg2
from werkzeug.security import generate_password_hash

SUPERADMIN_CAMPUS_ID = 0  # sentinel campus created in schema.sql


def prompt_credentials():
    print()
    print("Create the global superadmin account.")
    print("This account can log in at /superadmin/login and see every campus.")
    print()
    email = ""
    while not email or "@" not in email:
        email = input("Superadmin email: ").strip()
        if "@" not in email:
            print("  Please enter a valid email address.")

    name = ""
    while not name:
        name = input("Display name (e.g. 'Root Admin'): ").strip()

    while True:
        pw = getpass.getpass("Password: ")
        if len(pw) < 8:
            print("  Password must be at least 8 characters.")
            continue
        pw2 = getpass.getpass("Confirm password: ")
        if pw != pw2:
            print("  Passwords did not match. Try again.")
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

    # Connect as the local postgres role (peer auth via sudo -u postgres).
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
    print(f"Superadmin '{email}' written. You can now log in at /superadmin/login.")
    print("(The plaintext password was used only to hash it and was not stored.)")


if __name__ == "__main__":
    main()
