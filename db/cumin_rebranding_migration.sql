-- ==============================================================================
-- Cumin Platform Migration: Rebrand & Scope Expansion
-- Safe to run against an existing CampusCare database.
-- Preserves all existing tenant data, tickets, comments, and users.
-- Run: psql -v ON_ERROR_STOP=1 -d cumin_db -f db/cumin_rebranding_migration.sql
-- ==============================================================================

BEGIN;

-- 1. Ensure campuses table supports general organization metadata
ALTER TABLE campuses
    ADD COLUMN IF NOT EXISTS organization_type VARCHAR(40) NOT NULL DEFAULT 'other';

ALTER TABLE campuses
    ALTER COLUMN official_domain DROP NOT NULL;

-- 2. Expand role constraint on users table to include employee and org_admin
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;
ALTER TABLE users
    ADD CONSTRAINT users_role_check
    CHECK (role IN ('member', 'employee', 'student', 'staff', 'campus_admin', 'org_admin'));

-- 3. Create convenient organization-level alias views
CREATE OR REPLACE VIEW organizations AS
    SELECT
        id,
        campus_code AS org_code,
        campus_name AS org_name,
        organization_type,
        official_domain,
        campus_password_hash AS org_password_hash,
        is_active,
        created_at
    FROM campuses;

COMMIT;

