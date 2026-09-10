"""Investigation review decisions + remove analyst alert:transition (Step C5)

Revision ID: 0016_review_decisions
Revises: 0015_report_submissions
Create Date: 2026-09-02

C5 finalizes the compliance decision layer:
- Adds an INSERT-only `investigation_review_decisions` table capturing the
  immutable investigation-level final decision (NOT_HARMFUL or
  ESCALATE_TO_CASE) with a mandatory rationale. This replaces the previous
  practice of storing the rationale only as an internal comment prefix
  ("[Not Harmful]" / "[Escalated to Case]"), giving a durable, queryable,
  immutable record.
- Removes `alert:transition` from the analyst role. The legacy direct
  Alert -> ComplianceCase escalation path (POST /alerts/{id}/escalate) has
  been removed in C5; the only canonical formal case creation path is
  Investigation -> assigned Compliance Officer -> escalation. Analyst retains
  alert:read_assigned / alert:acknowledge / alert:dismiss / alert:investigate
  (Start Investigation path is untouched).
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


revision: str = "0016_review_decisions"
down_revision: Union[str, None] = "0015_report_submissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_review_decisions",
        sa.Column("review_decision_id", sa.VARCHAR(100), primary_key=True),
        sa.Column("investigation_id", sa.UUID(),
                  sa.ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("compliance_officer_id", sa.VARCHAR(100),
                  sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("decision_type", sa.VARCHAR(32), nullable=False),
        sa.Column("rationale", sa.TEXT(), nullable=False),
        sa.Column("resulting_case_id", sa.UUID(),
                  sa.ForeignKey("compliance_cases.case_id"),
                  nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_review_decisions_investigation",
        "investigation_review_decisions", ["investigation_id"])

    # C5: legacy direct Alert -> Case path removed; analyst no longer needs
    # alert:transition (its only canonical use was alert escalation).
    conn = op.get_bind()
    from sqlalchemy import text
    conn.execute(
        text("DELETE FROM role_permissions WHERE role_id = 'analyst' AND permission_key = 'alert:transition'"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text
    conn.execute(
        text("""
            INSERT INTO role_permissions (role_id, permission_key)
            VALUES ('analyst', 'alert:transition')
            ON CONFLICT DO NOTHING
        """),
    )
    op.drop_index("idx_review_decisions_investigation",
                  table_name="investigation_review_decisions")
    op.drop_table("investigation_review_decisions")
