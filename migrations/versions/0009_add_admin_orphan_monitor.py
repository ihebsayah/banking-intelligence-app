"""Seed admin:orphan_monitor permission for AD3 orphan-assignment endpoint

Revision ID: 0009_add_admin_orphan_monitor
Revises: 0008_add_system_actor
Create Date: 2026-08-01

Data migration following the 0005_add_permission_seeds pattern. The 2B.10b
contract (increment-2B-api-contracts.md AD3) requires `admin:orphan_monitor`
permission gating, but the code was never seeded in 0005. Grants it to the
admin role only (orphan monitoring is admin-only; analyst, compliance,
manager, and system roles are denied by the absence of a role_permissions row).
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = "0009_add_admin_orphan_monitor"
down_revision: Union[str, None] = "0008_add_system_actor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("""
            INSERT INTO permissions (permission_key, label, description, category)
            VALUES ('admin:orphan_monitor', 'Monitor Orphan Assignments',
                    'List resources assigned to ineligible users (admin only)', 'admin')
            ON CONFLICT (permission_key) DO NOTHING
        """),
    )
    conn.execute(
        text("""
            INSERT INTO role_permissions (role_id, permission_key)
            VALUES ('admin', 'admin:orphan_monitor')
            ON CONFLICT DO NOTHING
        """),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text("DELETE FROM role_permissions WHERE permission_key = 'admin:orphan_monitor'"),
    )
    conn.execute(
        text("DELETE FROM permissions WHERE permission_key = 'admin:orphan_monitor'"),
    )
