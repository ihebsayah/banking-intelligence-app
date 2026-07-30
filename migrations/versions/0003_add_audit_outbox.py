"""Add audit_outbox table and status enum for transactional outbox pattern

Revision ID: 0003_add_audit_outbox
Revises: 0002_add_organisation_scope
Create Date: 2026-07-30
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0003_add_audit_outbox"
down_revision: Union[str, None] = "0002_add_organisation_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE audit_outbox_status AS ENUM (
            'pending', 'delivering', 'delivered', 'failed', 'poison'
        );
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS audit_outbox (
            outbox_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            idempotency_key     VARCHAR(255) NOT NULL UNIQUE,
            event_type          VARCHAR(100) NOT NULL,
            entity_type         VARCHAR(50)  NOT NULL,
            entity_id           UUID         NOT NULL,
            actor_id            VARCHAR(100) NOT NULL,
            actor_role          VARCHAR(50)  NOT NULL,
            occurred_at         TIMESTAMPTZ  NOT NULL,
            payload             JSONB        NOT NULL,
            payload_schema_ver  SMALLINT     NOT NULL DEFAULT 1,
            status              audit_outbox_status NOT NULL DEFAULT 'pending',
            attempt_count       SMALLINT     NOT NULL DEFAULT 0,
            last_attempt_at     TIMESTAMPTZ,
            next_attempt_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            last_error          TEXT,
            locked_by           VARCHAR(100),
            locked_at           TIMESTAMPTZ,
            delivered_at        TIMESTAMPTZ,
            poison_reason       TEXT,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_outbox_pending
            ON audit_outbox(status, next_attempt_at)
            WHERE status IN ('pending','failed');
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_outbox_idem
            ON audit_outbox(idempotency_key);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_outbox;")
    op.execute("DROP TYPE IF EXISTS audit_outbox_status;")
