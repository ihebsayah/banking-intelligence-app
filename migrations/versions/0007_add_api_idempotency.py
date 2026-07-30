"""Add api_idempotency table for idempotent mutation endpoints

Revision ID: 0007_add_api_idempotency
Revises: 0006_deprecate_manager_role
Create Date: 2026-07-30
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0007_add_api_idempotency"
down_revision: Union[str, None] = "0006_deprecate_manager_role"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_idempotency (
            idempotency_key     VARCHAR(255) PRIMARY KEY,
            request_method      VARCHAR(10)  NOT NULL,
            request_path        VARCHAR(500) NOT NULL,
            request_body_sha256 VARCHAR(64)  NOT NULL,
            response_status     SMALLINT     NOT NULL,
            response_body       TEXT         NOT NULL,
            created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_idempotency;")
