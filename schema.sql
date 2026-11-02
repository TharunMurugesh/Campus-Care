BEGIN;

DROP TABLE IF EXISTS activity_logs CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS import_jobs CASCADE;
DROP TABLE IF EXISTS tickets CASCADE;
DROP TABLE IF EXISTS campus_stats CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS campus_counters CASCADE;
DROP TABLE IF EXISTS departments CASCADE;
DROP TABLE IF EXISTS campuses CASCADE;
DROP FUNCTION IF EXISTS touch_updated_at() CASCADE;
DROP FUNCTION IF EXISTS refresh_campus_stats(integer) CASCADE;
DROP SEQUENCE IF EXISTS campus_code_seq;

CREATE SEQUENCE campus_code_seq START 1;

CREATE TABLE campuses (
    id                   SERIAL PRIMARY KEY,
    campus_code          VARCHAR(20) UNIQUE NOT NULL,
    campus_name          VARCHAR(150) NOT NULL,
    organization_type    VARCHAR(40) NOT NULL DEFAULT 'other',
    official_domain      VARCHAR(150),
    campus_password_hash VARCHAR(255) NOT NULL,
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE campus_counters (
    campus_id  INTEGER PRIMARY KEY REFERENCES campuses(id) ON DELETE CASCADE,
    ticket_seq INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE departments (
    id         SERIAL PRIMARY KEY,
    campus_id  INTEGER NOT NULL REFERENCES campuses(id) ON DELETE CASCADE,
    name       VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campus_id, name)
);

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    campus_id     INTEGER NOT NULL REFERENCES campuses(id) ON DELETE CASCADE,
    university_id VARCHAR(50),
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL
        CHECK (role IN ('member','staff','campus_admin')),
    department_id INTEGER REFERENCES departments(id) ON DELETE SET NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campus_id, email),
    UNIQUE(campus_id, university_id)
);

CREATE INDEX idx_users_campus_role  ON users(campus_id, role);
CREATE INDEX idx_users_department   ON users(department_id);
CREATE INDEX idx_users_campus_email ON users(campus_id, email);

CREATE TABLE tickets (
    id                SERIAL PRIMARY KEY,
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
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE comments (
    id         SERIAL PRIMARY KEY,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    comment    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE activity_logs (
    id           SERIAL PRIMARY KEY,
    ticket_id    INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    action       VARCHAR(255) NOT NULL,
    performed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE import_jobs (
    id           SERIAL PRIMARY KEY,
    campus_id    INTEGER NOT NULL REFERENCES campuses(id) ON DELETE CASCADE,
    uploaded_by  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename     VARCHAR(255) NOT NULL,
    total_rows   INTEGER DEFAULT 0,
    success_rows INTEGER DEFAULT 0,
    failed_rows  INTEGER DEFAULT 0,
    status       VARCHAR(20) NOT NULL
        CHECK (status IN ('PENDING','PROCESSING','COMPLETED','FAILED')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tickets_campus_status      ON tickets(campus_id, status);
CREATE INDEX idx_tickets_campus_dept_status ON tickets(campus_id, department_id, status);
CREATE INDEX idx_tickets_assigned_status    ON tickets(assigned_to, status)
    WHERE assigned_to IS NOT NULL;
CREATE INDEX idx_tickets_student_campus      ON tickets(student_id, campus_id);
CREATE INDEX idx_tickets_dept_open           ON tickets(department_id, campus_id, created_at)
    WHERE status = 'OPEN' AND assigned_to IS NULL;
CREATE INDEX idx_tickets_created_desc        ON tickets(created_at DESC);

CREATE INDEX idx_comments_ticket_created     ON comments(ticket_id, created_at);
CREATE INDEX idx_activity_ticket_created     ON activity_logs(ticket_id, created_at DESC);
CREATE INDEX idx_import_jobs_campus          ON import_jobs(campus_id, created_at DESC);

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_tickets_touch_updated
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE campus_stats (
    campus_id       INTEGER PRIMARY KEY REFERENCES campuses(id) ON DELETE CASCADE,
    total_tickets   INTEGER NOT NULL DEFAULT 0,
    open_tickets    INTEGER NOT NULL DEFAULT 0,
    in_progress     INTEGER NOT NULL DEFAULT 0,
    escalated       INTEGER NOT NULL DEFAULT 0,
    resolved        INTEGER NOT NULL DEFAULT 0,
    closed          INTEGER NOT NULL DEFAULT 0,
    avg_resolve_hrs NUMERIC(10,2) NOT NULL DEFAULT 0,
    refreshed_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION refresh_campus_stats(target_campus INTEGER DEFAULT NULL)
RETURNS void AS $$
BEGIN
    INSERT INTO campus_stats
        (campus_id, total_tickets, open_tickets, in_progress,
         escalated, resolved, closed, avg_resolve_hrs, refreshed_at)
    SELECT
        c.id,
        COUNT(t.id),
        COUNT(t.id) FILTER (WHERE t.status = 'OPEN'),
        COUNT(t.id) FILTER (WHERE t.status IN ('CLAIMED','IN_PROGRESS')),
        COUNT(t.id) FILTER (WHERE t.status = 'ESCALATED'),
        COUNT(t.id) FILTER (WHERE t.status = 'RESOLVED'),
        COUNT(t.id) FILTER (WHERE t.status = 'CLOSED'),
        COALESCE(AVG(EXTRACT(EPOCH FROM (t.resolved_at - t.created_at)) / 3600)
                 FILTER (WHERE t.resolved_at IS NOT NULL), 0)::NUMERIC(10,2),
        CURRENT_TIMESTAMP
    FROM campuses c
    LEFT JOIN tickets t ON t.campus_id = c.id
    WHERE c.is_active = TRUE
      AND (target_campus IS NULL OR c.id = target_campus)
    GROUP BY c.id
    ON CONFLICT (campus_id) DO UPDATE SET
        total_tickets   = EXCLUDED.total_tickets,
        open_tickets    = EXCLUDED.open_tickets,
        in_progress     = EXCLUDED.in_progress,
        escalated       = EXCLUDED.escalated,
        resolved        = EXCLUDED.resolved,
        closed          = EXCLUDED.closed,
        avg_resolve_hrs = EXCLUDED.avg_resolve_hrs,
        refreshed_at    = EXCLUDED.refreshed_at;
END;
$$ LANGUAGE plpgsql;

SELECT setval(pg_get_serial_sequence('campuses','id'), 1, false);

COMMIT;
