"""Add information_request_attachments table for analyst response file uploads.

Information requests currently only accept a text response. This migration adds
a dedicated attachment table so an analyst can attach a file (bank statements,
exported records, etc.) alongside their response, reusing the private evidence
storage subsystem already used for investigation attachments.

Revision ID: 0018_information_request_attachments
Revises: 0017_c5_notification_types
Create Date: 2026-09-07

NOTE: revision id kept within 32 chars to fit the alembic_version.version_num
varchar(32) column ("0018_information_request_attachments" is 34 chars, so the
file id is shortened to "0018_info_request_attachments").
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = "0018_info_request_attachments"
down_revision: Union[str, None] = "0017_c5_notification_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS information_request_attachments (
            attachment_id       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            ir_id               UUID        NOT NULL REFERENCES information_requests(ir_id) ON DELETE RESTRICT,
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
        CREATE INDEX IF NOT EXISTS idx_ir_attachments_ir
            ON information_request_attachments(ir_id);
    """))
    conn.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_ir_attachments_uploaded_by
            ON information_request_attachments(uploaded_by);
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("DROP INDEX IF EXISTS idx_ir_attachments_uploaded_by;"))
    conn.execute(text("DROP INDEX IF EXISTS idx_ir_attachments_ir;"))
    conn.execute(text("DROP TABLE IF EXISTS information_request_attachments;"))