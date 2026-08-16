"""Allow investigation-linked information requests by making case_id nullable
and enforcing an XOR check constraint (exactly one parent: case_id or investigation_id).

Revision ID: 0011_allow_investigation_irs
Revises: 0010_fix_notification_types
Create Date: 2026-08-16
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text


revision: str = "0011_allow_investigation_irs"
down_revision: Union[str, None] = "0010_fix_notification_types"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE information_requests ALTER COLUMN case_id DROP NOT NULL;"))
    conn.execute(text("""
        ALTER TABLE information_requests
        ADD CONSTRAINT chk_ir_exactly_one_parent
        CHECK ((case_id IS NOT NULL)::integer + (investigation_id IS NOT NULL)::integer = 1);
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE information_requests DROP CONSTRAINT IF EXISTS chk_ir_exactly_one_parent;"))
    conn.execute(text("ALTER TABLE information_requests ALTER COLUMN case_id SET NOT NULL;"))
