-- =============================================================================
-- Audit Log Database (Write-Once, Immutable)
-- postgres-audit: audit_logs
-- =============================================================================

-- Audit Log Table (append-only, immutable)
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id VARCHAR(100) UNIQUE NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id VARCHAR(100) NOT NULL,
    user_role VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,          -- e.g. login, api_call, query_execute
    query_intent VARCHAR(255),
    tables_accessed TEXT,                  -- JSON array as text
    rows_accessed INTEGER DEFAULT 0,
    execution_time_ms INTEGER DEFAULT 0,
    status VARCHAR(20) NOT NULL,           -- success, error, rejected
    ip_address VARCHAR(50),
    endpoint VARCHAR(255),
    http_method VARCHAR(10),
    query_signature VARCHAR(255),
    data_freshness VARCHAR(50),
    error_message TEXT,
    metadata JSONB,                        -- flexible extra context
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_status ON audit_log(status);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_audit_id ON audit_log(audit_id);

-- =============================================================================
-- Enforce Immutability: Write-once only (no UPDATEs, no DELETEs)
-- =============================================================================

-- Prevent updates to any row
CREATE OR REPLACE RULE audit_log_no_update AS
    ON UPDATE TO audit_log DO INSTEAD NOTHING;

-- Prevent deletion of any row
CREATE OR REPLACE RULE audit_log_no_delete AS
    ON DELETE TO audit_log DO INSTEAD NOTHING;

-- =============================================================================
-- Grant Limited Permissions (audit_user can INSERT + SELECT only)
-- =============================================================================
GRANT INSERT ON audit_log TO audit_user;
GRANT SELECT ON audit_log TO audit_user;
-- Intentionally NO UPDATE or DELETE privileges
