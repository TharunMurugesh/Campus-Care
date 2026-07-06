-- =====================================================================
-- OPTIONAL migration: convert `tickets` to a monthly range-partitioned table
-- =====================================================================
-- WHEN to apply this:
--   Only once ticket volume is large enough that the tickets table is a
--   measurable bottleneck (typically millions of rows). The base schema
--   is already well-indexed and will handle most workloads comfortably.
--
-- WHY this is a separate file (not the default schema):
--   A partitioned table's PRIMARY KEY must include the partition key
--   (created_at). That means the FKs from comments / activity_logs /
--   import_jobs -> tickets(id) would need to become composite, which in
--   turn changes every application query. We keep the base schema simple
--   and ship this as a documented, ready-to-run path instead.
--
-- WHAT this migration does:
--   1. Renames the existing tickets table to tickets_old.
--   2. Creates a new partitioned tickets table (PK = id + created_at).
--   3. Creates an initial set of monthly partitions (current year +/- 1).
--   4. Copies data over, then rebuilds indexes.
--   5. Drops tickets_old.
--
-- RUN:  psql -U postgres -d campus_issue_system -f db/partitioning_migration.sql
--       (take a backup first; this is a one-way migration)
-- =====================================================================

\set ON_ERROR_STOP on

BEGIN;

-- 1. Move the original table aside (keeping its data).
ALTER TABLE tickets RENAME TO tickets_old;

-- 2. New partitioned parent.
CREATE TABLE tickets (
    id                SERIAL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    campus_id         INTEGER NOT NULL REFERENCES campuses(id) ON DELETE CASCADE,
    ticket_code       VARCHAR(50) UNIQUE NOT NULL,
    title             VARCHAR(255) NOT NULL,
    description       TEXT NOT NULL,
    priority          VARCHAR(20) NOT NULL
        CHECK (priority IN ('LOW','MEDIUM','HIGH')),
    status            VARCHAR(20) NOT NULL
        CHECK (status IN ('OPEN','CLAIMED','IN_PROGRESS','ESCALATED','RESOLVED','CLOSED')),
    student_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department_id     INTEGER NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
    assigned_to       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    escalation_reason TEXT,
    claimed_at        TIMESTAMPTZ,
    resolved_at       TIMESTAMPTZ,
    closed_at         TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- 3. Helper to create a single month's partition, then create a range
--    of partitions spanning last year through next year.
CREATE OR REPLACE FUNCTION _create_monthly_partition(month_start DATE)
RETURNS void AS $$
DECLARE
    part_name TEXT := 'tickets_' || to_char(month_start, 'YYYY_MM');
    next_month DATE := (month_start + INTERVAL '1 month')::date;
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF tickets FOR VALUES FROM (%L) TO (%L)',
        part_name, month_start, next_month
    );
END;
$$ LANGUAGE plpgsql;

SELECT _create_monthly_partition(d::date)
FROM generate_series(
    date_trunc('month', CURRENT_DATE) - INTERVAL '1 year',
    date_trunc('month', CURRENT_DATE) + INTERVAL '1 year',
    INTERVAL '1 month'
) AS d;

DROP FUNCTION _create_monthly_partition(DATE);

-- 4. Copy data from the old table.
INSERT INTO tickets (id, campus_id, ticket_code, title, description, priority,
                     status, student_id, department_id, assigned_to,
                     escalation_reason, claimed_at, resolved_at, closed_at,
                     created_at, updated_at)
SELECT id, campus_id, ticket_code, title, description, priority,
       status, student_id, department_id, assigned_to,
       escalation_reason, claimed_at, resolved_at, closed_at,
       created_at, updated_at
FROM tickets_old;

-- Keep the SERIAL sequence in sync with the max existing id.
SELECT setval(pg_get_serial_sequence('tickets','id'),
              COALESCE((SELECT MAX(id) FROM tickets), 1), true);

-- 5. Recreate indexes (partitioned; propagated to each partition).
CREATE INDEX idx_tickets_campus_status      ON tickets(campus_id, status);
CREATE INDEX idx_tickets_campus_dept_status ON tickets(campus_id, department_id, status);
CREATE INDEX idx_tickets_assigned_status    ON tickets(assigned_to, status)
    WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_tickets_student_campus      ON tickets(student_id, campus_id);
CREATE INDEX idx_tickets_dept_open           ON tickets(department_id, campus_id, created_at)
    WHERE status = 'OPEN' AND assigned_to IS NULL;
CREATE INDEX idx_tickets_created_desc        ON tickets(created_at DESC);

-- Recreate the updated_at trigger on the new partitioned table.
CREATE TRIGGER trg_tickets_touch_updated
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- 6. Drop the old table now that data + indexes are migrated.
DROP TABLE tickets_old;

COMMIT;

-- Note: the FKs from comments/activity_logs/import_jobs reference
-- tickets(id). On the partitioned table these must be re-pointed to
-- tickets(id, created_at); if your application still references only id,
-- leave those FKs dropped and enforce integrity at the application layer,
-- OR add a non-partitioned tickets_meta table keyed by id for FK purposes.
