"""Add C5 investigation-review notification types (Step C5)

Revision ID: 0017_c5_notification_types
Revises: 0016_review_decisions
Create Date: 2026-09-03

C5 reports the final compliance outcome to the report analyst via
NotificationRepo.insert. The two new notification types are:
- `investigation_reviewed`  (investigation closed as Not Harmful)
- `investigation_escalated` (investigation escalated to a Compliance Case)

These were not part of the approved set in migration 0010, so this migration
drops and recreates the notifications.notification_type CHECK constraint with
the two additional types appended. 0016 is already applied to environments, so
this is a separate migration rather than an edit to 0016.
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0017_c5_notification_types"
down_revision: Union[str, None] = "0016_review_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APPROVED_TYPES = [
    "alert_assigned",
    "alert_dismissed",
    "alert_escalated",
    "investigation_assigned",
    "investigation_returned",
    "investigation_submitted",
    "investigation_completed",
    "investigation_cancelled",
    "investigation_reviewed",
    "investigation_escalated",
    "case_assigned",
    "case_decision_recorded",
    "case_resolved",
    "case_closed",
    "case_reopened",
    "ir_created",
    "ir_acknowledged",
    "ir_responded",
    "ir_accepted",
    "ir_returned",
    "approval_requested",
    "approval_decided",
    "approval_expired",
]


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text
    conn.execute(text("ALTER TABLE notifications DROP CONSTRAINT notifications_notification_type_check"))
    type_list = ", ".join(f"'{t}'" for t in APPROVED_TYPES)
    conn.execute(text(f"""
        ALTER TABLE notifications
        ADD CONSTRAINT notifications_notification_type_check
        CHECK (notification_type::text = ANY (ARRAY[{type_list}]::text[]))
    """))


def downgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text
    conn.execute(text("ALTER TABLE notifications DROP CONSTRAINT notifications_notification_type_check"))
    base_types = [
        "alert_assigned", "alert_dismissed", "alert_escalated",
        "investigation_assigned", "investigation_returned", "investigation_submitted",
        "investigation_completed", "investigation_cancelled",
        "case_assigned", "case_decision_recorded", "case_resolved", "case_closed",
        "case_reopened",
        "ir_created", "ir_acknowledged", "ir_responded", "ir_accepted", "ir_returned",
        "approval_requested", "approval_decided", "approval_expired",
    ]
    type_list = ", ".join(f"'{t}'" for t in base_types)
    conn.execute(text(f"""
        ALTER TABLE notifications
        ADD CONSTRAINT notifications_notification_type_check
        CHECK (notification_type::text = ANY (ARRAY[{type_list}]::text[]))
    """))
