"""Real-PostgreSQL integration tests for admin orphan-assignment detection (AD3).

Runs the canonical contract query (increment-2B-api-contracts.md AD3) against a
migrated scratch database. Requires a scratch database already migrated to head:

    createdb banking_orphan_integration
    DATABASE_URL=... alembic upgrade head
    cd services && INTEGRATION_DATABASE_URL=postgresql://... python3 -m pytest \\
        workbench/tests/test_orphan_integration.py -q

Skipped automatically when INTEGRATION_DATABASE_URL is not set.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("INTEGRATION_DATABASE_URL"),
    reason="INTEGRATION_DATABASE_URL not set (real-Postgres integration test)",
)

URL = os.environ.get("INTEGRATION_DATABASE_URL", "")
DUMMY_BCRYPT_HASH = "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y"

USERS = {
    "orphan_admin": ("admin", "active"),
    "orphan_active": ("analyst", "active"),
    "orphan_susp": ("analyst", "suspended"),
    "orphan_inact": ("analyst", "inactive"),
    "orphan_noscope": ("analyst", "active"),
    "orphan_otherscope": ("analyst", "active"),
}
SCOPES = {
    "orphan_admin": ["hq_main"],
    "orphan_active": ["hq_main"],
    "orphan_susp": ["hq_main"],
    "orphan_inact": ["hq_main"],
    "orphan_noscope": [],
    "orphan_otherscope": ["global"],
}
ALERTS = [
    ("11111111-1111-1111-1111-111111111111", "orphan_active", "assigned", "valid"),
    ("22222222-2222-2222-2222-222222222222", "orphan_susp", "assigned", "status orphan"),
    ("33333333-3333-3333-3333-333333333333", "orphan_susp", "dismissed", "terminal, status orphan"),
    ("44444444-4444-4444-4444-444444444444", None, "new", "unassigned"),
]
INVESTIGATIONS = [
    ("55555555-5555-5555-5555-555555555555", "orphan_inact", "open", "status orphan"),
    ("66666666-6666-6666-6666-666666666666", "orphan_noscope", "active", "scope orphan"),
    ("77777777-7777-7777-7777-777777777777", "orphan_active", "completed", "valid, terminal"),
]
CASES = [
    ("88888888-8888-8888-8888-888888888888", "orphan_otherscope", "under_review", "scope orphan"),
    ("99999999-9999-9999-9999-999999999999", "orphan_active", "closed", "valid, terminal"),
]

from shared.database import DatabaseConnector  # noqa: E402
from workbench.repos import OrphanRepo  # noqa: E402


async def connector_pool():
    import asyncpg
    return await asyncpg.create_pool(URL)


async def _run(pool, stmt, params):
    return await pool.execute(stmt, params) if params is not None else await pool.execute(stmt)


CLEANUP = [
    ("DELETE FROM compliance_cases WHERE case_id::text LIKE '88888888%' OR case_id::text LIKE '99999999%'", None),
    ("DELETE FROM investigations WHERE investigation_id::text LIKE '55555555%' OR investigation_id::text LIKE '66666666%' OR investigation_id::text LIKE '77777777%'", None),
    ("DELETE FROM alerts WHERE alert_id::text LIKE '11111111%' OR alert_id::text LIKE '22222222%' OR alert_id::text LIKE '33333333%' OR alert_id::text LIKE '44444444%'", None),
    ("DELETE FROM user_scopes WHERE user_id LIKE 'orphan%'", None),
    ("DELETE FROM users WHERE user_id LIKE 'orphan%'", None),
]


@pytest.fixture
async def db():
    connector = DatabaseConnector(URL)
    await connector.initialize()
    yield connector
    await connector.close()


@pytest.fixture
async def seeded(db):
    pool = None
    try:
        pool = await connector_pool()
        for stmt, params in CLEANUP:
            await _run(pool, stmt, params)
        for uid, (role, status) in USERS.items():
            await pool.execute(
                "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
                "VALUES ($1, $2, $1, $3, 'hq_main', $4, $5) "
                "ON CONFLICT (user_id) DO NOTHING",
                uid, f"{uid}@bankintel.hq", role, DUMMY_BCRYPT_HASH, status,
            )
        for uid, scopes in SCOPES.items():
            for scope in scopes:
                await pool.execute(
                    "INSERT INTO user_scopes (user_id, scope_id, granted_by) "
                    "VALUES ($1, $2, 'orphan_admin') ON CONFLICT DO NOTHING",
                    uid, scope,
                )
        for eid, assigned, status, _label in ALERTS:
            await pool.execute(
                "INSERT INTO alerts (alert_id, alert_type, severity, title, scope_id, status, assigned_to) "
                "VALUES ($1::uuid, 'kpi_breach', 'medium', $2, 'hq_main', $3, $4)",
                eid, _label, status, assigned,
            )
        for eid, assigned, status, _label in INVESTIGATIONS:
            await pool.execute(
                "INSERT INTO investigations "
                "(investigation_id, title, scope_id, status, assigned_to, created_by) "
                "VALUES ($1::uuid, $2, 'hq_main', $3, $4, 'orphan_admin')",
                eid, _label, status, assigned,
            )
        for eid, assigned, status, _label in CASES:
            await pool.execute(
                "INSERT INTO compliance_cases "
                "(case_id, title, scope_id, status, assigned_to, created_by) "
                "VALUES ($1::uuid, $2, 'hq_main', $3, $4, 'orphan_admin')",
                eid, _label, status, assigned,
            )
        yield pool
    finally:
        if pool is not None:
            for stmt, params in CLEANUP:
                await _run(pool, stmt, params)
            await pool.close()


async def test_orphan_detection_real_db(db, seeded):
    rows = await OrphanRepo(db).orphan_assignments()
    got = {(r["entity_type"], str(r["entity_id"])) for r in rows}
    expected = {
        ("alert", "22222222-2222-2222-2222-222222222222"),
        ("alert", "33333333-3333-3333-3333-333333333333"),
        ("investigation", "55555555-5555-5555-5555-555555555555"),
        ("investigation", "66666666-6666-6666-6666-666666666666"),
        ("compliance_case", "88888888-8888-8888-8888-888888888888"),
    }
    assert got == expected, got

    valid = {(r["entity_type"], str(r["entity_id"])) for r in rows if
             r["entity_id"] in ("11111111-1111-1111-1111-111111111111",
                                "77777777-7777-7777-7777-777777777777",
                                "99999999-9999-9999-9999-999999999999")}
    assert valid == set(), valid

    by_id = {str(r["entity_id"]): r for r in rows}
    assert by_id["22222222-2222-2222-2222-222222222222"]["assigned_user_status"] == "suspended"
    assert by_id["66666666-6666-6666-6666-666666666666"]["assigned_user_status"] == "active"
    assert by_id["66666666-6666-6666-6666-666666666666"]["title"] == "scope orphan"

    ids = [str(r["entity_id"]) for r in rows if r["entity_type"] == "alert"]
    assert ids == sorted(ids)


async def test_terminal_records_reported_per_contract(db, seeded):
    rows = await OrphanRepo(db).orphan_assignments()
    statuses = {str(r["entity_id"]): r["status"] for r in rows}
    assert statuses["33333333-3333-3333-3333-333333333333"] == "dismissed"
    assert statuses["55555555-5555-5555-5555-555555555555"] == "open"


async def test_no_sensitive_fields_in_result(db, seeded):
    rows = await OrphanRepo(db).orphan_assignments()
    keys = set(rows[0].keys())
    assert keys == {
        "entity_type", "entity_id", "title", "status",
        "assigned_user_id", "assigned_user_status",
    }, keys
