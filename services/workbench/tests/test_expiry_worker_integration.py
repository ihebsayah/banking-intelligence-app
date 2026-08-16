"""Real-PostgreSQL integration tests for the approval expiry worker (AP5).

These tests run the worker against an actual migrated database and are the
real-DB evidence for the 2B.8 closure gate (FK on activity_timeline.actor_id
-> users(user_id), atomic side effects, idempotency).

Requires a scratch database already migrated to head:

    createdb banking_worker_integration
    DATABASE_URL=... alembic upgrade head
    cd services && INTEGRATION_DATABASE_URL=postgresql://... python3 -m pytest \\
        workbench/tests/test_expiry_worker_integration.py -q

Skipped automatically when INTEGRATION_DATABASE_URL is not set.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("INTEGRATION_DATABASE_URL"),
    reason="INTEGRATION_DATABASE_URL not set (real-Postgres integration test)",
)

URL = os.environ.get("INTEGRATION_DATABASE_URL", "")
REQ = "analyst_expiry_001"
DUMMY_BCRYPT_HASH = "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y"

from shared.database import DatabaseConnector  # noqa: E402
from workbench.expiry_worker import SYSTEM_ACTOR_ID, expire_due  # noqa: E402

INSERT_APPROVALS = """
    INSERT INTO approval_requests
        (action_type, entity_type, entity_id, requested_by, rationale,
         required_approvals, status, expires_at, version)
    VALUES
        ('alert_dismissal_critical_high', 'alert', 'a1111111-1111-1111-1111-111111111111', $1,
         'overdue pending', 1, 'pending', NOW() - interval '5 minutes', 1),
        ('alert_dismissal_critical_high', 'alert', 'a2222222-2222-2222-2222-222222222222', $1,
         'future pending', 1, 'pending', NOW() + interval '5 minutes', 1),
        ('alert_dismissal_critical_high', 'alert', 'a3333333-3333-3333-3333-333333333333', $1,
         'overdue approved', 1, 'approved', NOW() - interval '5 minutes', 1),
        ('alert_dismissal_critical_high', 'alert', 'a4444444-4444-4444-4444-444444444444', $1,
         'overdue rejected', 1, 'rejected', NOW() - interval '5 minutes', 1),
        ('alert_dismissal_critical_high', 'alert', 'a5555555-5555-5555-5555-555555555555', $1,
         'already expired', 1, 'expired', NOW() - interval '5 minutes', 1)
    RETURNING approval_request_id, status
"""


@pytest.fixture
async def db():
    connector = DatabaseConnector(URL)
    await connector.initialize()
    yield connector
    await connector.close()


CLEANUP = (
    ("DELETE FROM audit_outbox WHERE event_type = 'approval.expired'", None),
    ("DELETE FROM activity_timeline WHERE event_type = 'approval_expired' OR actor_id = $1", REQ),
    ("DELETE FROM notifications WHERE notification_type = 'approval_expired' OR user_id = $1", REQ),
    ("DELETE FROM approval_decisions WHERE approval_request_id IN (SELECT approval_request_id FROM approval_requests WHERE requested_by = $1)", REQ),
    ("DELETE FROM approval_requests WHERE requested_by = $1", REQ),
    ("DELETE FROM user_scopes WHERE user_id = $1", REQ),
    ("DELETE FROM users WHERE user_id = $1", REQ),
)


@pytest.fixture
async def seeded(db):
    pool = None
    try:
        pool = await connector_pool()
        for stmt, params in CLEANUP:
            await _run(pool, stmt, params)
        await pool.execute(
            "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
            "VALUES ($1, $1::text || '@bankintel.hq', 'Analyst One', 'analyst', 'hq_main', $2, 'active') "
            "ON CONFLICT (user_id) DO NOTHING", REQ, DUMMY_BCRYPT_HASH,
        )
        rows = await pool.fetch(INSERT_APPROVALS, REQ)
        yield pool, [r["approval_request_id"] for r in rows]
    finally:
        if pool is not None:
            for stmt, params in CLEANUP:
                await _run(pool, stmt, params)
            await pool.close()


async def connector_pool():
    import asyncpg
    return await asyncpg.create_pool(URL)


async def _run(pool, stmt, params):
    return await pool.execute(stmt, params) if params is not None else await pool.execute(stmt)


async def test_expiry_worker_real_db_flow(db, seeded):
    pool, ids = seeded

    first = await expire_due(db, batch_size=50)
    second = await expire_due(db, batch_size=50)
    assert len(first) == 1, first
    assert second == [], second

    statuses = await pool.fetch(
        "SELECT entity_id, status, version FROM approval_requests "
        "WHERE approval_request_id = ANY($1::uuid[])", ids,
    )
    got = {str(r["entity_id"]): (r["status"], r["version"]) for r in statuses}
    expected = {
        "11111111-1111-1111-1111-111111111111": ("expired", 2),  # overdue pending
        "22222222-2222-2222-2222-222222222222": ("pending", 1),  # future pending
        "33333333-3333-3333-3333-333333333333": ("approved", 1),
        "44444444-4444-4444-4444-444444444444": ("rejected", 1),
        "55555555-5555-5555-5555-555555555555": ("expired", 1),  # already expired
    }
    assert got == expected, got

    timeline = await pool.fetchrow(
        "SELECT actor_id, event_type FROM activity_timeline WHERE event_type = 'approval_expired'")
    assert timeline is not None and timeline["actor_id"] == SYSTEM_ACTOR_ID, timeline

    notification = await pool.fetchrow(
        "SELECT user_id FROM notifications WHERE notification_type = 'approval_expired'")
    assert notification is not None and notification["user_id"] == REQ, notification

    outbox = await pool.fetchrow(
        "SELECT actor_id, actor_role, event_type FROM audit_outbox WHERE event_type = 'approval.expired'")
    assert outbox is not None, outbox
    assert outbox["actor_id"] == SYSTEM_ACTOR_ID and outbox["actor_role"] == "system", outbox

    counts = await pool.fetchrow(
        "SELECT (SELECT count(*) FROM activity_timeline WHERE event_type = 'approval_expired') AS t,"
        "       (SELECT count(*) FROM notifications WHERE notification_type = 'approval_expired') AS n,"
        "       (SELECT count(*) FROM audit_outbox WHERE event_type = 'approval.expired') AS o")
    assert (counts["t"], counts["n"], counts["o"]) == (1, 1, 1), counts
