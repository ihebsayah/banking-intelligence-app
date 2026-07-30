"""Add organisation_scopes and user_scopes for Phase 2B scope-based access

Revision ID: 0002_add_organisation_scope
Revises: a1b2c3d4e5f6
Create Date: 2026-07-30
"""
from typing import Sequence, Union
from alembic import op


revision: str = "0002_add_organisation_scope"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS organisation_scopes (
            scope_id        VARCHAR(100) PRIMARY KEY,
            scope_type      VARCHAR(30) NOT NULL
                            CHECK (scope_type IN ('bank','region','branch','department')),
            label           VARCHAR(255) NOT NULL,
            parent_scope_id VARCHAR(100) REFERENCES organisation_scopes(scope_id),
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    op.execute("""
        INSERT INTO organisation_scopes (scope_id, scope_type, label) VALUES
            ('hq_main', 'bank', 'Headquarters — Main'),
            ('global',  'bank', 'Global — Admin metadata view')
        ON CONFLICT DO NOTHING;
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS user_scopes (
            user_id     VARCHAR(100) NOT NULL REFERENCES users(user_id),
            scope_id    VARCHAR(100) NOT NULL REFERENCES organisation_scopes(scope_id),
            granted_by  VARCHAR(100) NOT NULL REFERENCES users(user_id),
            granted_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, scope_id)
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_scopes_user ON user_scopes(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_scopes_scope ON user_scopes(scope_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_scopes;")
    op.execute("DROP TABLE IF EXISTS organisation_scopes;")
