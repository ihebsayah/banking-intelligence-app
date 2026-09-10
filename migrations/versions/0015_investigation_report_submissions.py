"""Authoritative immutable investigation report snapshot (Step C4)

Revision ID: 0015_report_submissions
Revises: 0014_investigation_assignment
Create Date: 2026-09-02

Captures an INSERT-only, immutable snapshot of the analyst report at the
moment it is submitted to compliance. The snapshot decouples the authoritative
submitted record from any subsequent working-state changes so that
compliance review (and any downstream case escalation) references exactly the
submitted findings/refs/conclusion/evidence.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op


revision: str = "0015_report_submissions"
down_revision: Union[str, None] = "0014_investigation_assignment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_report_submissions",
        sa.Column("submission_id", sa.VARCHAR(100), primary_key=True),
        sa.Column(        "investigation_id", sa.UUID(),
                  sa.ForeignKey("investigations.investigation_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("analyst_id", sa.VARCHAR(100),
                  sa.ForeignKey("users.user_id"), nullable=False),
        sa.Column("compliance_officer_id", sa.VARCHAR(100),
                  sa.ForeignKey("users.user_id"), nullable=True),
        sa.Column("findings_text", sa.TEXT(), nullable=True),
        sa.Column("findings_refs", postgresql.JSONB(), nullable=True),
        sa.Column("conclusion", sa.TEXT(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_manifest", postgresql.JSONB(), nullable=True),
        sa.Column("report_hash", sa.VARCHAR(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_report_submissions_investigation",
        "investigation_report_submissions", ["investigation_id"])


def downgrade() -> None:
    op.drop_index(
        "idx_report_submissions_investigation",
        table_name="investigation_report_submissions")
    op.drop_table("investigation_report_submissions")
