"""Update notifications notification_type CHECK constraint to the complete
approved type set emitted by all Phase 2B services.

migration 0004 seeded a subset; investigation_completed, investigation_cancelled
and case_reopened were added by later services without updating the constraint.
This migration drops the old constraint and recreates it with the approved set.
"""
from typing import Sequence, Union
from alembic import op

revision = "0010_fix_notification_types"
down_revision: Union[str, None] = "0009_add_admin_orphan_monitor"
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
    conn.execute(text("""
        ALTER TABLE notifications
        ADD CONSTRAINT notifications_notification_type_check
        CHECK (notification_type::text = ANY (ARRAY[
            'alert_assigned'::text, 'alert_dismissed'::text, 'alert_escalated'::text,
            'investigation_assigned'::text, 'investigation_returned'::text,
            'investigation_submitted'::text, 'case_assigned'::text,
            'case_decision_recorded'::text, 'case_resolved'::text, 'case_closed'::text,
            'ir_created'::text, 'ir_acknowledged'::text, 'ir_responded'::text,
            'ir_accepted'::text, 'ir_returned'::text,
            'approval_requested'::text, 'approval_decided'::text, 'approval_expired'::text
        ]::text[]))
    """))
