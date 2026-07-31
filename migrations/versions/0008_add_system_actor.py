"""Seed the canonical system actor for background workers (AP5 expiry worker)

Revision ID: 0008_add_system_actor
Revises: 0007_add_api_idempotency
Create Date: 2026-07-31

Resolves the 2B.8 closure blocker: activity_timeline.actor_id is
NOT NULL REFERENCES users(user_id), so the expiry worker's timeline
writes need a real, seeded user. The frozen specs never defined a
persistence model for the "system" actor (increment-2B-state-machines.md
AP5: Actor=Worker, Perm=(system)), so this migration seeds one:

  * roles:    'system'      — non-interactive service role, zero permissions
  * users:    'system_001'  — deterministic, status 'inactive' (login is
              rejected at api_gateway/auth.py before any session), identity
              provider 'system' (never issued by Keycloak), same dummy hash
              convention as the other dev seed users.

audit_outbox.actor_id is free-form (no FK) and records the same stable ID.

NOTE: This is a data migration. downgrade() removes only the seeded rows
plus the timeline rows the system actor may have written (the only FK
dependency), never the surrounding tables.
"""
from typing import Sequence, Union
from alembic import op
from sqlalchemy import text

revision: str = "0008_add_system_actor"
down_revision: Union[str, None] = "0007_add_api_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same dummy hash convention as the other dev seed users (status blocks login).
SYSTEM_USER_ID = "system_001"
SYSTEM_EMAIL = "system_001@bankintel.hq"
DUMMY_BCRYPT_HASH = "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y"


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text("""
            INSERT INTO roles (role_id, label, description)
            VALUES ('system', 'System Actor',
                    'Non-interactive service identity for background workers')
            ON CONFLICT (role_id) DO NOTHING
        """),
    )
    conn.execute(
        text("""
            INSERT INTO users (user_id, email, name, role, bank_id,
                               password_hash, permissions, status, identity_provider)
            VALUES (:user_id, :email, 'System Actor', 'system', 'hq_main',
                    :password_hash, ARRAY[]::TEXT[], 'inactive', 'system')
            ON CONFLICT (user_id) DO NOTHING
        """),
        {"user_id": SYSTEM_USER_ID, "email": SYSTEM_EMAIL,
         "password_hash": DUMMY_BCRYPT_HASH},
    )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text("DELETE FROM activity_timeline WHERE actor_id = :user_id"),
        {"user_id": SYSTEM_USER_ID},
    )
    conn.execute(
        text("DELETE FROM users WHERE user_id = :user_id"),
        {"user_id": SYSTEM_USER_ID},
    )
    conn.execute(text("DELETE FROM roles WHERE role_id = 'system'"))
