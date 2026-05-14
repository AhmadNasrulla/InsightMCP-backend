-- Application tables (auth + audit). Lives in a separate `app` schema so it
-- cannot be touched by the analyst flow (which is scoped to retail_dw).
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.users (
    id              BIGSERIAL PRIMARY KEY,
    email           VARCHAR(254) NOT NULL UNIQUE,
    full_name       VARCHAR(120) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL DEFAULT 'analyst',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_email ON app.users(email);

CREATE TABLE IF NOT EXISTS app.audit_log (
    id                BIGSERIAL PRIMARY KEY,
    user_id           BIGINT REFERENCES app.users(id) ON DELETE SET NULL,
    user_email        VARCHAR(254),
    user_role         VARCHAR(20),
    question          TEXT NOT NULL,
    generated_sql     TEXT,
    validation_status VARCHAR(20) NOT NULL,          -- valid | invalid | refused
    safety_status     VARCHAR(20) NOT NULL,          -- safe | blocked | refused
    safety_reason     TEXT,
    execution_status  VARCHAR(20) NOT NULL,          -- success | error | skipped
    execution_error   TEXT,
    row_count         INTEGER,
    execution_ms      INTEGER,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user_created ON app.audit_log(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_created ON app.audit_log(created_at DESC);

-- Read-only role for the analyst SQL execution path. Idempotent.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mcp_readonly') THEN
        EXECUTE 'CREATE ROLE mcp_readonly LOGIN PASSWORD ''readonly_demo_pw_change_me''';
    END IF;
END $$;

GRANT USAGE ON SCHEMA retail_dw TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA retail_dw TO mcp_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA retail_dw GRANT SELECT ON TABLES TO mcp_readonly;

-- Explicitly DENY anything in app schema to the read-only role.
REVOKE ALL ON SCHEMA app FROM mcp_readonly;
