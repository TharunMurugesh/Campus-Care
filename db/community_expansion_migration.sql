-- Expand existing CampusCare tenants to support schools and non-school communities.
-- Safe to run once against an existing installation; this preserves tenant data.
-- Run: psql -v ON_ERROR_STOP=1 -d campus_issue_system -f db/community_expansion_migration.sql

BEGIN;

ALTER TABLE campuses
    ADD COLUMN IF NOT EXISTS organization_type VARCHAR(40) NOT NULL DEFAULT 'other';

-- Communities do not need an institutional email domain to register.
ALTER TABLE campuses
    ALTER COLUMN official_domain DROP NOT NULL;

-- Existing student accounts become general members. Keep the old role accepted
-- during migration/rollback windows; the app normalizes it when a user signs in.
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
UPDATE users SET role = 'member' WHERE role = 'student';
ALTER TABLE users
    ADD CONSTRAINT users_role_check
    CHECK (role IN ('member', 'student', 'staff', 'campus_admin'));

COMMIT;
