-- =============================================================================
-- Increment 2B Domain Model
-- Target: postgres-main (banking_dev)
-- Migration: 0004_add_operational_entities.py
-- All additive — no DROP, no RENAME, no destructive ALTER
-- ON DELETE RESTRICT for all regulated records
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. ACTIVITY TIMELINE (created first — referenced by nothing, references users)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS activity_timeline (
    timeline_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(50) NOT NULL
                    CHECK (entity_type IN (
                        'alert','investigation','compliance_case',
                        'information_request','approval_request','comment'
                    )),
    entity_id       UUID        NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    -- e.g. 'status_changed','assigned','comment_added','ir_created',
    --      'approval_requested','approval_decided','decision_recorded'
    actor_id        VARCHAR(100) NOT NULL REFERENCES users(user_id),
    old_value       JSONB,
    new_value       JSONB,
    metadata        JSONB,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_entity
    ON activity_timeline(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_timeline_occurred
    ON activity_timeline(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_timeline_actor
    ON activity_timeline(actor_id);

-- ---------------------------------------------------------------------------
-- 2. NOTIFICATIONS (in-DB only; no email/push in Phase 2B)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    notification_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         VARCHAR(100) NOT NULL REFERENCES users(user_id),
    notification_type VARCHAR(50) NOT NULL
                    CHECK (notification_type IN (
                        'alert_assigned','alert_dismissed','alert_escalated',
                        'investigation_assigned','investigation_returned','investigation_submitted',
                        'case_assigned','case_decision_recorded','case_resolved','case_closed','case_reopened',
                        'ir_created','ir_acknowledged','ir_responded','ir_accepted','ir_returned',
                        'approval_requested','approval_decided','approval_expired'
                    )),
    title           VARCHAR(255) NOT NULL,
    body            TEXT        NOT NULL,
    entity_type     VARCHAR(50),
    entity_id       UUID,
    is_read         BOOLEAN     NOT NULL DEFAULT FALSE,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON notifications(user_id, is_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_entity
    ON notifications(entity_type, entity_id);

-- ---------------------------------------------------------------------------
-- 3. ALERTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alerts (
    alert_id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type          VARCHAR(50) NOT NULL
                        CHECK (alert_type IN (
                            'transaction_anomaly','kpi_breach','risk_threshold',
                            'pattern_match','system_rule'
                        )),
    severity            VARCHAR(20) NOT NULL
                        CHECK (severity IN ('critical','high','medium','low')),
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    source_rule_type    VARCHAR(50),
    source_rule_id      VARCHAR(100),
    -- Related banking entity: application-level integrity only (not FK)
    -- to avoid coupling operational schema to banking tables
    related_entity_type VARCHAR(50),
    related_entity_id   VARCHAR(100),
    scope_id            VARCHAR(100) NOT NULL DEFAULT 'hq_main'
                        REFERENCES organisation_scopes(scope_id),
    status              VARCHAR(30) NOT NULL DEFAULT 'new'
                        CHECK (status IN (
                            'new','assigned','acknowledged',
                            'under_investigation','resolved','dismissed'
                        )),
    -- NOTE: 'escalated' and 'reopened' removed from alert status.
    -- Escalation creates a ComplianceCase; alert transitions to under_investigation.
    -- Reopening is handled by admin creating a new assignment from dismissed/resolved.
    assigned_to         VARCHAR(100) REFERENCES users(user_id),
    dismissed_reason    TEXT,
    dismissed_at        TIMESTAMPTZ,
    dismissed_by        VARCHAR(100) REFERENCES users(user_id),
    resolved_at         TIMESTAMPTZ,
    resolved_by         VARCHAR(100) REFERENCES users(user_id),
    -- Approval reference for four-eyes dismissal
    dismissal_approval_id UUID,      -- FK to approval_requests; set after table created below
    version             INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_assigned
    ON alerts(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity_status
    ON alerts(severity, status);
CREATE INDEX IF NOT EXISTS idx_alerts_scope
    ON alerts(scope_id);
CREATE INDEX IF NOT EXISTS idx_alerts_created
    ON alerts(created_at DESC);

-- ---------------------------------------------------------------------------
-- 4. INVESTIGATIONS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    alert_id            UUID        REFERENCES alerts(alert_id) ON DELETE RESTRICT,
    -- One investigation per alert in Phase 2B.
    -- alert_id UNIQUE constraint enforced at application level; allow NULL for manual creation.
    scope_id            VARCHAR(100) NOT NULL DEFAULT 'hq_main'
                        REFERENCES organisation_scopes(scope_id),
    status              VARCHAR(30) NOT NULL DEFAULT 'open'
                        CHECK (status IN (
                            'open','active','awaiting_information',
                            'submitted','returned','completed','cancelled'
                        )),
    priority            VARCHAR(10) NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('critical','high','medium','low')),
    assigned_to         VARCHAR(100) REFERENCES users(user_id),
    created_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
    -- Findings: text + structured JSON references. No file uploads in Phase 2B.
    findings_text       TEXT,
    findings_refs       JSONB,   -- [{type, id, description}] — references to external docs
    conclusion          TEXT,
    started_at          TIMESTAMPTZ,
    submitted_at        TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    return_reason       TEXT,    -- populated when status -> returned
    version             INTEGER  NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_investigations_assigned
    ON investigations(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_investigations_alert
    ON investigations(alert_id);
CREATE INDEX IF NOT EXISTS idx_investigations_scope
    ON investigations(scope_id);
CREATE INDEX IF NOT EXISTS idx_investigations_status
    ON investigations(status);

-- ---------------------------------------------------------------------------
-- 5. COMPLIANCE CASES
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS compliance_cases (
    case_id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    title               VARCHAR(255) NOT NULL,
    description         TEXT,
    alert_id            UUID        REFERENCES alerts(alert_id) ON DELETE RESTRICT,
    investigation_id    UUID        REFERENCES investigations(investigation_id) ON DELETE RESTRICT,
    scope_id            VARCHAR(100) NOT NULL DEFAULT 'hq_main'
                        REFERENCES organisation_scopes(scope_id),
    status              VARCHAR(40) NOT NULL DEFAULT 'open'
                        CHECK (status IN (
                            'open','assigned','under_review','awaiting_information',
                            'decision_pending','awaiting_compliance_action',
                            'resolved','closed','cancelled','reopened'
                        )),
    -- NOTE: 'escalated' removed — was inconsistent. If further escalation needed,
    -- a new case or admin alert covers it in Phase 2E.
    -- 'remediation_required' and 'remediation_in_progress' removed — Phase 2D.
    priority            VARCHAR(10) NOT NULL DEFAULT 'medium'
                        CHECK (priority IN ('critical','high','medium','low')),
    risk_level          VARCHAR(10)
                        CHECK (risk_level IN ('high','medium','low')),
    regulatory_frameworks TEXT[],
    assigned_to         VARCHAR(100) REFERENCES users(user_id),
    created_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
    target_date         DATE,
    resolution          TEXT,
    resolved_at         TIMESTAMPTZ,
    resolved_by         VARCHAR(100) REFERENCES users(user_id),
    closed_at           TIMESTAMPTZ,
    closed_by           VARCHAR(100) REFERENCES users(user_id),
    -- current_disposition_id: set by application after decision recorded.
    -- Validated at application level: decision must belong to this case.
    -- NOT an FK to avoid circular dependency; validated before write.
    current_disposition_id UUID,
    -- Closure approval reference (four-eyes for critical/high)
    closure_approval_id UUID,       -- FK set below after approval_requests created
    reopen_reason       TEXT,
    version             INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cases_assigned
    ON compliance_cases(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_cases_scope
    ON compliance_cases(scope_id);
CREATE INDEX IF NOT EXISTS idx_cases_status
    ON compliance_cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_investigation
    ON compliance_cases(investigation_id);
CREATE INDEX IF NOT EXISTS idx_cases_alert
    ON compliance_cases(alert_id);

-- ---------------------------------------------------------------------------
-- 6. DECISIONS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decisions (
    decision_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID        NOT NULL
                        REFERENCES compliance_cases(case_id) ON DELETE RESTRICT,
    decision_type       VARCHAR(50) NOT NULL
                        CHECK (decision_type IN (
                            'no_action',
                            'warning',
                            'enhanced_due_diligence_recommended',
                            'report_to_authority_recommended',
                            'account_action_recommended',
                            'case_closed'
                        )),
    rationale           TEXT        NOT NULL,
    decided_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_final            BOOLEAN     NOT NULL DEFAULT FALSE,
    supersedes_decision_id UUID     REFERENCES decisions(decision_id) ON DELETE RESTRICT,
    -- Approval reference: required for report_to_authority_recommended
    approval_id         UUID,       -- FK set below after approval_requests created
    version             INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
    -- No updated_at: decisions are append-only; supersede to change
);

CREATE INDEX IF NOT EXISTS idx_decisions_case
    ON decisions(case_id, decided_at DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_decided_by
    ON decisions(decided_by);

-- ---------------------------------------------------------------------------
-- 7. INFORMATION REQUESTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS information_requests (
    ir_id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id             UUID        NOT NULL
                        REFERENCES compliance_cases(case_id) ON DELETE RESTRICT,
    investigation_id    UUID        REFERENCES investigations(investigation_id) ON DELETE RESTRICT,
    created_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
    assigned_to         VARCHAR(100) NOT NULL REFERENCES users(user_id),
    -- The analyst asked to respond
    question            TEXT        NOT NULL,
    due_date            DATE,
    status              VARCHAR(30) NOT NULL DEFAULT 'open'
                        CHECK (status IN (
                            'open','acknowledged','responded','accepted',
                            'returned','cancelled'
                        )),
    -- Response fields (populated by analyst)
    response_text       TEXT,
    -- response_attachments: Phase 2D (Evidence enabled)
    responded_at        TIMESTAMPTZ,
    -- Compliance accept/return
    acceptance_note     TEXT,
    return_reason       TEXT,
    accepted_at         TIMESTAMPTZ,
    returned_at         TIMESTAMPTZ,
    accepted_by         VARCHAR(100) REFERENCES users(user_id),
    returned_by         VARCHAR(100) REFERENCES users(user_id),
    -- Cancellation
    cancelled_at        TIMESTAMPTZ,
    cancelled_by        VARCHAR(100) REFERENCES users(user_id),
    cancel_reason       TEXT,
    version             INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ir_case
    ON information_requests(case_id, status);
CREATE INDEX IF NOT EXISTS idx_ir_assigned
    ON information_requests(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_ir_due
    ON information_requests(due_date)
    WHERE status IN ('open','acknowledged');

-- ---------------------------------------------------------------------------
-- 8. APPROVAL REQUESTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approval_requests (
    approval_request_id UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type         VARCHAR(60) NOT NULL
                        CHECK (action_type IN (
                            'alert_dismissal_critical_high',
                            'case_closure_critical_high',
                            'decision_report_to_authority',
                            'case_reopen'
                        )),
    entity_type         VARCHAR(50) NOT NULL
                        CHECK (entity_type IN ('alert','compliance_case','decision')),
    entity_id           UUID        NOT NULL,
    requested_by        VARCHAR(100) NOT NULL REFERENCES users(user_id),
    rationale           TEXT        NOT NULL,
    required_approvals  SMALLINT    NOT NULL DEFAULT 1,
    approval_count      SMALLINT    NOT NULL DEFAULT 0,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending','approved','rejected','expired','cancelled'
                        )),
    expires_at          TIMESTAMPTZ NOT NULL,
    -- Set to NOW() + 72h at creation. Configurable default in seed data.
    executed_at         TIMESTAMPTZ,
    -- Set when the gated action is actually performed; prevents reuse.
    version             INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_entity
    ON approval_requests(entity_type, entity_id, status);
CREATE INDEX IF NOT EXISTS idx_approval_requested_by
    ON approval_requests(requested_by);
CREATE INDEX IF NOT EXISTS idx_approval_pending
    ON approval_requests(status, expires_at)
    WHERE status = 'pending';

-- ---------------------------------------------------------------------------
-- 9. APPROVAL DECISIONS (individual approver votes)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS approval_decisions (
    approval_decision_id UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
    approval_request_id  UUID       NOT NULL
                        REFERENCES approval_requests(approval_request_id) ON DELETE RESTRICT,
    approver_id         VARCHAR(100) NOT NULL REFERENCES users(user_id),
    decision            VARCHAR(10) NOT NULL CHECK (decision IN ('approved','rejected')),
    rationale           TEXT,
    -- Required when decision = 'rejected'
    decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Uniqueness: one vote per approver per request
    CONSTRAINT uq_approval_decision_approver
        UNIQUE (approval_request_id, approver_id)
);

CREATE INDEX IF NOT EXISTS idx_approval_decisions_request
    ON approval_decisions(approval_request_id);

-- ---------------------------------------------------------------------------
-- 10. COMMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS comments (
    comment_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         VARCHAR(50) NOT NULL
                        CHECK (entity_type IN (
                            'alert','investigation','compliance_case','information_request'
                        )),
    entity_id           UUID        NOT NULL,
    content             TEXT        NOT NULL,
    author_id           VARCHAR(100) NOT NULL REFERENCES users(user_id),
    is_internal         BOOLEAN     NOT NULL DEFAULT FALSE,
    -- Internal comments visible only to compliance + admin
    is_redacted         BOOLEAN     NOT NULL DEFAULT FALSE,
    redacted_at         TIMESTAMPTZ,
    redacted_by         VARCHAR(100) REFERENCES users(user_id),
    version             INTEGER     NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_comments_entity
    ON comments(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_author
    ON comments(author_id);

-- ---------------------------------------------------------------------------
-- 11. ASSIGNMENT HISTORY
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assignment_history (
    history_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type         VARCHAR(50) NOT NULL
                        CHECK (entity_type IN (
                            'alert','investigation','compliance_case','information_request'
                        )),
    entity_id           UUID        NOT NULL,
    assigned_from       VARCHAR(100) REFERENCES users(user_id),
    assigned_to         VARCHAR(100) REFERENCES users(user_id),
    assigned_by         VARCHAR(100) NOT NULL REFERENCES users(user_id),
    reason              TEXT,
    assigned_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assignment_entity
    ON assignment_history(entity_type, entity_id, assigned_at DESC);

-- ---------------------------------------------------------------------------
-- 12. DEFERRED FK CONSTRAINTS (circular references resolved after table creation)
-- ---------------------------------------------------------------------------

-- alerts.dismissal_approval_id -> approval_requests
ALTER TABLE alerts
    ADD CONSTRAINT fk_alerts_dismissal_approval
    FOREIGN KEY (dismissal_approval_id)
    REFERENCES approval_requests(approval_request_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

-- compliance_cases.closure_approval_id -> approval_requests
ALTER TABLE compliance_cases
    ADD CONSTRAINT fk_cases_closure_approval
    FOREIGN KEY (closure_approval_id)
    REFERENCES approval_requests(approval_request_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

-- decisions.approval_id -> approval_requests
ALTER TABLE decisions
    ADD CONSTRAINT fk_decisions_approval
    FOREIGN KEY (approval_id)
    REFERENCES approval_requests(approval_request_id)
    ON DELETE RESTRICT
    DEFERRABLE INITIALLY DEFERRED;

-- ---------------------------------------------------------------------------
-- 13. AUDIT OUTBOX (already in 0003 — no repeat here)
-- ---------------------------------------------------------------------------
-- See migration 0003_add_audit_outbox.py

-- ---------------------------------------------------------------------------
-- 14. LIFECYCLE NOTES
-- ---------------------------------------------------------------------------
-- Archive / cancel behaviour:
--   alert:      dismissed (terminal, immutable fields: dismissed_reason, dismissed_at, dismissed_by)
--   alert:      resolved (terminal)
--   investigation: cancelled (terminal, requires reason in cancel_reason comment)
--   investigation: completed (terminal; read-only after completed_at set)
--   compliance_case: closed (terminal; read-only after closed_at set)
--   compliance_case: cancelled (terminal; requires reason)
--   decision:   append-only; superseded by new decision with supersedes_decision_id
--   ir:         cancelled (terminal; requires cancel_reason)
--   approval_request: expired by worker after expires_at; cancelled by requester before any approval
--   comment:    redacted (not deleted); content replaced by '[REDACTED]' by admin

-- Retention:
--   alerts, investigations, cases, decisions, IRs: minimum 7 years (regulatory)
--   audit_outbox: 90 days after delivered; poison events: 1 year
--   activity_timeline: life of entity + 7 years
--   notifications: 90 days
--   assignment_history: 7 years

-- Controlled purge: outside normal APIs; admin batch job with legal hold check;
--   separate Phase 2H design; not implementable by any API in 2B
