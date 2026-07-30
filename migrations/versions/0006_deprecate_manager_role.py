"""Deprecate manager role: add legacy_role column, update description

Revision ID: 0006_deprecate_manager_role
Revises: 0005_add_permission_seeds
Create Date: 2026-07-30

No new permissions granted to manager. workbench:access is PROHIBITED.
Existing read:branch_data, read:risk_summary retained for backward compat.
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0006_deprecate_manager_role"
down_revision: Union[str, None] = "0005_add_permission_seeds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE roles
        SET description = 'DEPRECATED — Legacy role. Zero Inc 2 capabilities. Admin must reassign.'
        WHERE role_id = 'manager';
    """)
    op.execute("""
        ALTER TABLE users
          ADD COLUMN IF NOT EXISTS legacy_role BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    op.execute("""
        UPDATE users SET legacy_role = TRUE WHERE role = 'manager';
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE roles
        SET description = 'Branch Manager / Executive'
        WHERE role_id = 'manager';
    """)
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS legacy_role;")
