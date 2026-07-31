"""Create all Phase 2B operational entity tables

Order: activity_timeline, notifications, alerts, investigations,
compliance_cases, decisions, information_requests, approval_requests,
approval_decisions, comments, assignment_history.

Then add deferred FK constraints, trigger, and partial unique indexes.

Revision ID: 0004_add_operational_entities
Revises: 0003_add_audit_outbox
Create Date: 2026-07-30
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0004_add_operational_entities"
down_revision: Union[str, None] = "0003_add_audit_outbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. ACTIVITY TIMELINE ──────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS activity_timeline (
            timeline_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            entity_type     VARCHAR(50) NOT NULL
                            CHECK (entity_type IN (
                                'alert','investigation','compliance_case',
                                'information_request','approval_request','comment'
                            )),
            entity_id       UUID        NOT NULL,
            event_type      VARCHAR(100) NOT NULL,
            actor_id        VARCHAR(100) NOT NULL REFERENCES users(user_id),
            old_value       JSONB,
            new_value       JSONB,
            metadata        JSONB,
            occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_timeline_entity ON activity_timeline(entity_type, entity_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_timeline_occurred ON activity_timeline(occurred_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_timeline_actor ON activity_timeline(actor_id);")

    # ── 2. NOTIFICATIONS ──────────────────────────────────────────────
    op.execute("""
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
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
            ON notifications(user_id, is_read, created_at DESC);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_notifications_entity
            ON notifications(entity_type, entity_id);
    """)

    # ── 3. ALERTS ─────────────────────────────────────────────────────
    op.execute("""
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
            related_entity_type VARCHAR(50),
            related_entity_id   VARCHAR(100),
            scope_id            VARCHAR(100) NOT NULL DEFAULT 'hq_main'
                                REFERENCES organisation_scopes(scope_id),
            status              VARCHAR(30) NOT NULL DEFAULT 'new'
                                CHECK (status IN (
                                    'new','assigned','acknowledged',
                                    'under_investigation','resolved','dismissed'
                                )),
            assigned_to         VARCHAR(100) REFERENCES users(user_id),
            dismissed_reason    TEXT,
            dismissed_at        TIMESTAMPTZ,
            dismissed_by        VARCHAR(100) REFERENCES users(user_id),
            resolved_at         TIMESTAMPTZ,
            resolved_by         VARCHAR(100) REFERENCES users(user_id),
            dismissal_approval_id UUID,
            version             INTEGER     NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_assigned ON alerts(assigned_to, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity_status ON alerts(severity, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_scope ON alerts(scope_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);")

    # ── 4. INVESTIGATIONS ─────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS investigations (
            investigation_id    UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            title               VARCHAR(255) NOT NULL,
            description         TEXT,
            alert_id            UUID        REFERENCES alerts(alert_id) ON DELETE RESTRICT,
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
            findings_text       TEXT,
            findings_refs       JSONB,
            conclusion          TEXT,
            started_at          TIMESTAMPTZ,
            submitted_at        TIMESTAMPTZ,
            completed_at        TIMESTAMPTZ,
            return_reason       TEXT,
            version             INTEGER  NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_investigations_assigned ON investigations(assigned_to, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_investigations_alert ON investigations(alert_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_investigations_scope ON investigations(scope_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations(status);")

    # ── 5. COMPLIANCE CASES ───────────────────────────────────────────
    # The Inc 1 baseline (0001) created a legacy compliance_cases table
    # (compliance_case_id PK, French 'ouvert' status). Phase 2B defines its own
    # compliance_cases with a different schema and the same name, so on any DB
    # where the legacy table exists (empty-DB chain OR stamped Inc 1 DB) it is
    # renamed aside first. The legacy table has no column-level consumers (only
    # table-name allowlists in the Inc 1 SQL agents). compliance_reviews' FK
    # follows the rename automatically. Idempotent: the Phase 2B table has
    # case_id, so a re-run skips the rename.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = current_schema()
                         AND table_name = 'compliance_cases')
               AND NOT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_schema = current_schema()
                                 AND table_name = 'compliance_cases'
                                 AND column_name = 'case_id') THEN
                ALTER TABLE compliance_cases RENAME TO legacy_compliance_cases;
            END IF;
        END $$;
    """)
    op.execute("""
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
                                    'resolved','closed','cancelled'
                                )),
            priority            VARCHAR(10) NOT NULL DEFAULT 'medium'
                                CHECK (priority IN ('critical','high','medium','low')),
            risk_level          VARCHAR(10)
                                CHECK (risk_level IN ('critical','high','medium','low')),
            regulatory_frameworks TEXT[],
            assigned_to         VARCHAR(100) REFERENCES users(user_id),
            created_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
            target_date         DATE,
            resolution          TEXT,
            resolved_at         TIMESTAMPTZ,
            resolved_by         VARCHAR(100) REFERENCES users(user_id),
            closed_at           TIMESTAMPTZ,
            closed_by           VARCHAR(100) REFERENCES users(user_id),
            current_disposition_id UUID,
            closure_approval_id UUID,
            reopen_reason       TEXT,
            version             INTEGER     NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_assigned ON compliance_cases(assigned_to, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_scope ON compliance_cases(scope_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON compliance_cases(status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_investigation ON compliance_cases(investigation_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cases_alert ON compliance_cases(alert_id);")

    # ── 6. DECISIONS ──────────────────────────────────────────────────
    op.execute("""
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
                                    'closure_recommended'
                                )),
            rationale           TEXT        NOT NULL,
            decided_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
            decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            is_final            BOOLEAN     NOT NULL DEFAULT FALSE,
            supersedes_decision_id UUID     REFERENCES decisions(decision_id) ON DELETE RESTRICT,
            approval_id         UUID,
            version             INTEGER     NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_decisions_case ON decisions(case_id, decided_at DESC);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_decisions_decided_by ON decisions(decided_by);")

    # ── 7. INFORMATION REQUESTS ───────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS information_requests (
            ir_id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id             UUID        NOT NULL
                                REFERENCES compliance_cases(case_id) ON DELETE RESTRICT,
            investigation_id    UUID        REFERENCES investigations(investigation_id) ON DELETE RESTRICT,
            created_by          VARCHAR(100) NOT NULL REFERENCES users(user_id),
            assigned_to         VARCHAR(100) NOT NULL REFERENCES users(user_id),
            question            TEXT        NOT NULL,
            due_date            DATE,
            status              VARCHAR(30) NOT NULL DEFAULT 'open'
                                CHECK (status IN (
                                    'open','acknowledged','responded','accepted',
                                    'returned','cancelled'
                                )),
            response_text       TEXT,
            responded_at        TIMESTAMPTZ,
            acceptance_note     TEXT,
            return_reason       TEXT,
            accepted_at         TIMESTAMPTZ,
            returned_at         TIMESTAMPTZ,
            accepted_by         VARCHAR(100) REFERENCES users(user_id),
            returned_by         VARCHAR(100) REFERENCES users(user_id),
            cancelled_at        TIMESTAMPTZ,
            cancelled_by        VARCHAR(100) REFERENCES users(user_id),
            cancel_reason       TEXT,
            version             INTEGER     NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ir_case ON information_requests(case_id, status);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ir_assigned ON information_requests(assigned_to, status);")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_ir_due
            ON information_requests(due_date)
            WHERE status IN ('open','acknowledged');
    """)

    # ── 8. APPROVAL REQUESTS ──────────────────────────────────────────
    op.execute("""
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
                                CHECK (entity_type IN ('alert','compliance_case')),
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
            executed_at         TIMESTAMPTZ,
            version             INTEGER     NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_entity
            ON approval_requests(entity_type, entity_id, status);
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_approval_requested_by ON approval_requests(requested_by);")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_pending
            ON approval_requests(status, expires_at)
            WHERE status = 'pending';
    """)

    # ── 9. APPROVAL DECISIONS ─────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS approval_decisions (
            approval_decision_id UUID       PRIMARY KEY DEFAULT gen_random_uuid(),
            approval_request_id  UUID       NOT NULL
                                REFERENCES approval_requests(approval_request_id) ON DELETE RESTRICT,
            approver_id         VARCHAR(100) NOT NULL REFERENCES users(user_id),
            decision            VARCHAR(10) NOT NULL CHECK (decision IN ('approved','rejected')),
            rationale           TEXT,
            decided_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_approval_decision_approver
                UNIQUE (approval_request_id, approver_id)
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_approval_decisions_request
            ON approval_decisions(approval_request_id);
    """)

    # ── 10. COMMENTS ──────────────────────────────────────────────────
    op.execute("""
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
            is_redacted         BOOLEAN     NOT NULL DEFAULT FALSE,
            redacted_at         TIMESTAMPTZ,
            redacted_by         VARCHAR(100) REFERENCES users(user_id),
            original_content_hash VARCHAR(64),
            redaction_reason    TEXT,
            version             INTEGER     NOT NULL DEFAULT 1,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_comments_entity
            ON comments(entity_type, entity_id, created_at DESC);
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_comments_author ON comments(author_id);")

    # ── 11. ASSIGNMENT HISTORY ────────────────────────────────────────
    op.execute("""
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
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_assignment_entity
            ON assignment_history(entity_type, entity_id, assigned_at DESC);
    """)

    # ── 12. DEFERRED FK CONSTRAINTS ──────────────────────────────────
    op.execute("""
        ALTER TABLE alerts
            ADD CONSTRAINT fk_alerts_dismissal_approval
            FOREIGN KEY (dismissal_approval_id)
            REFERENCES approval_requests(approval_request_id)
            ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED;
    """)
    op.execute("""
        ALTER TABLE compliance_cases
            ADD CONSTRAINT fk_cases_closure_approval
            FOREIGN KEY (closure_approval_id)
            REFERENCES approval_requests(approval_request_id)
            ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED;
    """)
    op.execute("""
        ALTER TABLE decisions
            ADD CONSTRAINT fk_decisions_approval
            FOREIGN KEY (approval_id)
            REFERENCES approval_requests(approval_request_id)
            ON DELETE RESTRICT
            DEFERRABLE INITIALLY DEFERRED;
    """)

    # ── 13. TRIGGER: validate_case_disposition ───────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION validate_case_disposition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.current_disposition_id IS NOT NULL THEN
                IF NOT EXISTS (
                    SELECT 1 FROM decisions d
                    WHERE d.decision_id = NEW.current_disposition_id
                      AND d.case_id = NEW.case_id
                ) THEN
                    RAISE EXCEPTION 'current_disposition_id % does not reference a decision belonging to case %',
                        NEW.current_disposition_id, NEW.case_id;
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        DROP TRIGGER IF EXISTS trg_validate_case_disposition ON compliance_cases;
        CREATE TRIGGER trg_validate_case_disposition
            BEFORE INSERT OR UPDATE OF current_disposition_id ON compliance_cases
            FOR EACH ROW
            EXECUTE FUNCTION validate_case_disposition();
    """)

    # ── 14. PARTIAL UNIQUE INDEXES ───────────────────────────────────
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_investigations_active_alert
            ON investigations(alert_id) WHERE status NOT IN ('cancelled');
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_active_alert
            ON compliance_cases(alert_id) WHERE status NOT IN ('cancelled');
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_approval_active_entity_action
            ON approval_requests(entity_type, entity_id, action_type) WHERE status = 'pending';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_approval_active_entity_action;")
    op.execute("DROP INDEX IF EXISTS idx_cases_active_alert;")
    op.execute("DROP INDEX IF EXISTS idx_investigations_active_alert;")
    op.execute("DROP TRIGGER IF EXISTS trg_validate_case_disposition ON compliance_cases;")
    op.execute("DROP FUNCTION IF EXISTS validate_case_disposition;")
    op.execute("ALTER TABLE decisions DROP CONSTRAINT IF EXISTS fk_decisions_approval;")
    op.execute("ALTER TABLE compliance_cases DROP CONSTRAINT IF EXISTS fk_cases_closure_approval;")
    op.execute("ALTER TABLE alerts DROP CONSTRAINT IF EXISTS fk_alerts_dismissal_approval;")
    op.execute("DROP TABLE IF EXISTS assignment_history;")
    op.execute("DROP TABLE IF EXISTS comments;")
    op.execute("DROP TABLE IF EXISTS approval_decisions;")
    op.execute("DROP TABLE IF EXISTS approval_requests;")
    op.execute("DROP TABLE IF EXISTS information_requests;")
    op.execute("DROP TABLE IF EXISTS decisions;")
    op.execute("DROP TABLE IF EXISTS compliance_cases;")
    op.execute("DROP TABLE IF EXISTS investigations;")
    op.execute("DROP TABLE IF EXISTS alerts;")
    op.execute("DROP TABLE IF EXISTS notifications;")
    op.execute("DROP TABLE IF EXISTS activity_timeline;")
