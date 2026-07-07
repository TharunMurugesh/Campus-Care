-- Optional: convert tickets to monthly range-partitioned table.
-- Apply only when ticket volume justifies it (millions of rows).
-- A partitioned table needs (id, created_at) as PK, which would break
-- the single-column FKs from comments/activity_logs/import_jobs, so this
-- ships separately from the base schema. Take a backup before running.
-- Run: psql -U postgres -d campus_issue_system -f db/partitioning_migration.sql

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE tickets RENAME TO tickets_old;

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

INSERT INTO tickets (id, campus_id, ticket_code, title, description, priority,
                     status, student_id, department_id, assigned_to,
                     escalation_reason, claimed_at, resolved_at, closed_at,
                     created_at, updated_at)
SELECT id, campus_id, ticket_code, title, description, priority,
       status, student_id, department_id, assigned_to,
       escalation_reason, claimed_at, resolved_at, closed_at,
       created_at, updated_at
FROM tickets_old;

SELECT setval(pg_get_serial_sequence('tickets','id'),
              COALESCE((SELECT MAX(id) FROM tickets), 1), true);

CREATE INDEX idx_tickets_campus_status      ON tickets(campus_id, status);
CREATE INDEX idx_tickets_campus_dept_status ON tickets(campus_id, department_id, status);
CREATE INDEX idx_tickets_assigned_status    ON tickets(assigned_to, status)
    WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_tickets_student_campus      ON tickets(student_id, campus_id);
CREATE INDEX idx_tickets_dept_open           ON tickets(department_id, campus_id, created_at)
    WHERE status = 'OPEN' AND assigned_to IS NULL;
CREATE INDEX idx_tickets_created_desc        ON tickets(created_at DESC);

CREATE TRIGGER trg_tickets_touch_updated
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

DROP TABLE tickets_old;

COMMIT;
