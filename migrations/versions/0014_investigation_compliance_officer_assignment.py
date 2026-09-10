"""Investigation compliance-officer assignment (Step C3)

Revision ID: 0014_investigation_assignment
Revises: 0013_rbac_segregation
Create Date: 2026-09-02

Adds compliance_officer_id to investigations for the analyst→compliance
handoff. nullable for pre-C3 investigations.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op


revision: str = "0014_investigation_assignment"
down_revision: Union[str, None] = "0013_rbac_segregation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column(
        "compliance_officer_id", sa.VARCHAR(100), sa.ForeignKey("users.user_id"),
        nullable=True))
    op.create_index(
        "idx_investigations_compliance_officer",
        "investigations", ["compliance_officer_id"])


def downgrade() -> None:
    op.drop_index("idx_investigations_compliance_officer", table_name="investigations")
    op.drop_column("investigations", "compliance_officer_id")
