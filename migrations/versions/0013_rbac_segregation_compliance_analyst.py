"""RBAC segregation: compliance standalone module removal + analyst case removal

Revision ID: 0013_rbac_segregation
Revises: 0012_investigation_attachments
Create Date: 2026-09-02

Fixes P0 findings from the Compliance Workflow As-Built Audit:
- Removes compliance standalone alert access (alert:read_assigned, alert:transition)
- Removes analyst standalone case access (case:read_assigned)
- Ensures compliance has case:decision and case:close (idempotent repair)

Analyst retains alert:transition so the accepted alert->case escalation flow
(POST /alerts/{id}/escalate, scenarios T08/V03) keeps working; the compliance
escalation path is via investigation:review + InvestigationService.escalate_to_case.

NOTE: revision id shortened to <=32 chars to fit varchar(32) alembic_version.
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0013_rbac_segregation"
down_revision: Union[str, None] = "0012_investigation_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    # ── Compliance: remove standalone alert access ──────────────────────────
    # Compliance must NOT have standalone Alerts module.
    # Alert context is available through authorized Investigations.
    for perm in ("alert:read_assigned", "alert:transition"):
        conn.execute(
            text("DELETE FROM role_permissions WHERE role_id = 'compliance' AND permission_key = :perm"),
            {"perm": perm},
        )

    # ── Compliance: ensure case:decision and case:close (idempotent) ───────
    # The init SQL seeds these correctly; this is a safety net for DBs where
    # only migration 0005 ran (which has a SENSITIVE_PERMISSIONS gate bug).
    for perm in ("case:decision", "case:close"):
        conn.execute(
            text("""
                INSERT INTO role_permissions (role_id, permission_key)
                VALUES ('compliance', :perm)
                ON CONFLICT DO NOTHING
            """),
            {"perm": perm},
        )

    # ── Analyst: remove standalone case access ─────────────────────────────
    # Analyst must NOT have standalone Compliance Cases module.
    conn.execute(
        text("DELETE FROM role_permissions WHERE role_id = 'analyst' AND permission_key = 'case:read_assigned'"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    # Restore compliance standalone alert permissions
    for perm in ("alert:read_assigned", "alert:transition"):
        conn.execute(
            text("""
                INSERT INTO role_permissions (role_id, permission_key)
                VALUES ('compliance', :perm)
                ON CONFLICT DO NOTHING
            """),
            {"perm": perm},
        )

    # Restore analyst case:read_assigned
    conn.execute(
        text("""
            INSERT INTO role_permissions (role_id, permission_key)
            VALUES ('analyst', 'case:read_assigned')
            ON CONFLICT DO NOTHING
        """),
    )

    # Remove compliance case:decision and case:close (restoring 0005 bug state)
    for perm in ("case:decision", "case:close"):
        conn.execute(
            text("DELETE FROM role_permissions WHERE role_id = 'compliance' AND permission_key = :perm"),
            {"perm": perm},
        )
