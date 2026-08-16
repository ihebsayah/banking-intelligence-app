"""Add investigation_attachments table for secure evidence file persistence (Phase 3A.9D).

Revision ID: 0012_add_investigation_attachments
Revises: 0011_allow_investigation_irs
Create Date: 2026-08-16
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = "0012_add_investigation_attachments"
down_revision: Union[str, None] = "0011_allow_investigation_irs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS investigation_attachments (
            attachment_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            investigation_id    UUID        NOT NULL REFERENCES investigations(investigation_id) ON DELETE RESTRICT,
            original_filename   VARCHAR(255) NOT NULL,
            stored_filename     VARCHAR(255) NOT NULL UNIQUE,
            content_type        VARCHAR(100) NOT NULL,
            size_bytes          BIGINT      NOT NULL CHECK (size_bytes > 0 AND size_bytes <= 10485760),
            sha256_hash         VARCHAR(64) NOT NULL,
            description         TEXT,
            uploaded_by         VARCHAR(100) NOT NULL REFERENCES users(user_id),
            uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_attachments_investigation
            ON investigation_attachments(investigation_id);
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_attachments_uploaded_by
            ON investigation_attachments(uploaded_by);
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_attachments_uploaded_by;"))
    conn.execute(text("DROP INDEX IF EXISTS idx_attachments_investigation;"))
    conn.execute(text("DROP TABLE IF EXISTS investigation_attachments;"))
