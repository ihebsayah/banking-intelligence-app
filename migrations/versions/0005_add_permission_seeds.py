"""Seed Phase 2B permission codes and role_permissions assignments

Revision ID: 0005_add_permission_seeds
Revises: 0004_add_operational_entities
Create Date: 2026-07-30

NOTE: This is a data migration. downgrade() removes only the seeded rows
that this revision inserted, not the permissions or role_permissions tables.
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0005_add_permission_seeds"
down_revision: Union[str, None] = "0004_add_operational_entities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALL_PERMISSIONS: list[tuple[str, str, str, str]] = [
    # workbench gate
    ("workbench:access", "Access Workbench", "Access the investigation workbench UI", "admin"),
    # alert
    ("alert:read_assigned", "Read Assigned Alerts", "List/read alerts assigned to self", "read"),
    ("alert:read", "Read All Alerts", "List/read all alerts (admin)", "read"),
    ("alert:assign", "Assign Alert", "Assign alert to user (admin)", "admin"),
    ("alert:acknowledge", "Acknowledge Alert", "Acknowledge own assigned alert", "write"),
    ("alert:dismiss", "Dismiss Alert", "Dismiss own assigned alert", "write"),
    ("alert:investigate", "Create Investigation", "Create investigation from alert", "write"),
    ("alert:transition", "Transition Alert", "Resolve alert (system-facing)", "write"),
    # investigation
    ("investigation:read_own", "Read Own Investigation", "Read investigations assigned to self", "read"),
    ("investigation:read", "Read Any Investigation", "Read any investigation (compliance, admin)", "read"),
    ("investigation:update", "Update Investigation", "Update findings_text, findings_refs, conclusion", "write"),
    ("investigation:modify_findings", "Modify Findings", "SENSITIVE — explicit audit for findings changes", "write"),
    ("investigation:transition", "Transition Investigation", "Start, submit, revise, complete transitions", "write"),
    ("investigation:review", "Review Investigation", "Approve/return submitted investigations (compliance)", "write"),
    ("investigation:assign", "Assign Investigation", "Assign investigation (admin) + cancel", "admin"),
    # compliance case
    ("case:create", "Create Case", "Create case (compliance, system via escalation)", "write"),
    ("case:read_assigned", "Read Assigned Case", "Read cases assigned to self", "read"),
    ("case:read", "Read Any Case", "Read any case (admin)", "read"),
    ("case:transition", "Transition Case", "Begin_review, request_info, etc", "write"),
    ("case:decision", "Record Decision", "Record decision (compliance ONLY)", "write"),
    ("case:close", "Close Case", "Close case (compliance ONLY)", "write"),
    ("case:assign", "Assign Case", "Assign case (admin) + cancel", "admin"),
    ("case:reopen", "Reopen Case", "Reopen closed case (admin, with approval)", "admin"),
    # information request
    ("info_request:create", "Create IR", "Create information request (compliance)", "write"),
    ("info_request:read_assigned", "Read Assigned IR", "Read IRs assigned to self (analyst)", "read"),
    ("info_request:read", "Read Any IR", "Read any IR on owned case (compliance)", "read"),
    ("info_request:respond", "Respond to IR", "Acknowledge + respond (analyst)", "write"),
    ("info_request:accept", "Accept IR", "Accept response (compliance IR creator)", "write"),
    ("info_request:return", "Return IR", "Return response (compliance IR creator)", "write"),
    ("info_request:cancel", "Cancel IR", "Cancel IR (compliance creator or admin)", "admin"),
    # approval
    ("approval:request", "Request Approval", "Request approval for gated action", "write"),
    ("approval:approve", "Approve", "Vote on approval (compliance only)", "write"),
    ("approval:read", "Read Approval", "Read approval requests (all roles, own scope)", "read"),
    # comments
    ("comment:create", "Create Comment", "Create comment on accessible entity", "write"),
    ("comment:read", "Read Comment", "Read public comments on accessible entity", "read"),
    ("comment:view_internal_content", "View Internal Comments", "Read full internal comment text (compliance)", "read"),
    ("comment:view_metadata", "View Comment Metadata", "See comment existence metadata without content (admin)", "read"),
    ("comment:redact", "Redact Comment", "Redact comment (admin only)", "admin"),
    # timeline
    ("timeline:read", "Read Timeline", "Read timeline of accessible entity", "read"),
    # notifications
    ("notification:read", "Read Notifications", "Read own notifications", "read"),
    ("notification:update", "Update Notifications", "Mark own notifications read", "write"),
    # admin operational
    ("admin:outbox_monitor", "Monitor Outbox", "Read audit outbox status (admin only)", "admin"),
    ("admin:outbox_retry", "Retry Outbox", "Trigger outbox retry (admin only)", "admin"),
]

SENSITIVE_PERMISSIONS = {
    "case:decision", "case:close",
    "investigation:modify_findings",
    "remediation:verify", "evidence:destroy",
}

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "analyst": [
        "workbench:access",
        "alert:read_assigned", "alert:acknowledge", "alert:dismiss",
        "alert:investigate", "alert:transition",
        "investigation:read_own", "investigation:update",
        "investigation:modify_findings", "investigation:transition",
        "case:read_assigned",
        "info_request:read_assigned", "info_request:respond",
        "approval:request", "approval:read",
        "comment:create", "comment:read",
        "timeline:read", "notification:read", "notification:update",
    ],
    "compliance": [
        "workbench:access",
        "alert:read_assigned", "alert:transition",
        "investigation:read", "investigation:review",
        "case:create", "case:read_assigned", "case:transition",
        "case:decision", "case:close",
        "info_request:create", "info_request:read",
        "info_request:accept", "info_request:return", "info_request:cancel",
        "approval:request", "approval:approve", "approval:read",
        "comment:create", "comment:read",
        "comment:view_internal_content",
        "timeline:read", "notification:read", "notification:update",
    ],
    "admin": [
        "workbench:access",
        "alert:read", "alert:assign", "alert:dismiss",
        "investigation:read", "investigation:assign",
        "case:read", "case:assign", "case:reopen",
        "info_request:read", "info_request:cancel",
        "approval:request", "approval:read",
        "comment:create", "comment:read",
        "comment:view_metadata", "comment:redact",
        "timeline:read", "notification:read", "notification:update",
        "admin:outbox_monitor", "admin:outbox_retry",
    ],
}


def upgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    # Empty-DB chain prerequisite: on a stamped Inc 1 DB the base roles already
    # exist (init/02-users-kpis.sql); on an empty DB they must be seeded here so
    # the role_permissions FK below resolves. ON CONFLICT makes it a no-op on
    # the stamped path. 'manager' is seeded (baseline parity) but granted no
    # Phase 2B permissions; 0006 deprecates it.
    conn.execute(
        text("""
            INSERT INTO roles (role_id, label, description) VALUES
                ('analyst', 'Analyst', 'Financial data analyst with read access to reports and key metrics'),
                ('manager', 'Branch Manager', 'Branch manager with operational reporting and summary performance access'),
                ('compliance', 'Compliance Officer', 'Compliance and risk officer with access to risk flags and audit trails'),
                ('admin', 'System Administrator', 'IT administrator with full access to user management and permission governance')
            ON CONFLICT (role_id) DO NOTHING
        """),
    )

    for pk, label, desc, cat in ALL_PERMISSIONS:
        conn.execute(
            text("""
                INSERT INTO permissions (permission_key, label, description, category)
                VALUES (:pk, :label, :desc, :cat)
                ON CONFLICT (permission_key) DO NOTHING
            """),
            {"pk": pk, "label": label, "desc": desc, "cat": cat},
        )

    for role, perms in ROLE_PERMISSIONS.items():
        for perm in perms:
            if perm not in SENSITIVE_PERMISSIONS or role == "analyst":
                conn.execute(
                    text("""
                        INSERT INTO role_permissions (role_id, permission_key)
                        VALUES (:role, :perm)
                        ON CONFLICT DO NOTHING
                    """),
                    {"role": role, "perm": perm},
                )


def downgrade() -> None:
    conn = op.get_bind()
    from sqlalchemy import text

    for pk, _, _, _ in ALL_PERMISSIONS:
        conn.execute(
            text("DELETE FROM role_permissions WHERE permission_key = :pk"),
            {"pk": pk},
        )
        conn.execute(
            text("DELETE FROM permissions WHERE permission_key = :pk"),
            {"pk": pk},
        )
