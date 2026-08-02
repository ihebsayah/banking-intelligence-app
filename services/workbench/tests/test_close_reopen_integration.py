"""Real-PostgreSQL integration verification for case resume (C4), close (C5/C9),
and reopen (C6/C12).

Runs the full service + authorise stack against a migrated scratch database.
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

CLOSE_USER_ID = "r_close_compliance"
ADMIN_USER_ID = "r_close_admin"
REQUESTOR_USER_ID = "r_close_requestor"

from shared.authorise import ApplicationUser  # noqa: E402
from workbench.exceptions import (  # noqa: E402
    ApprovalRequired, ApprovalConsumed, InvalidTransition,
)
from workbench.schemas.cases import (  # noqa: E402
    CloseCaseRequest, ReopenCaseRequest,
)
from workbench.services.case_service import CaseService  # noqa: E402

CLOSE_USER = ApplicationUser(
    user_id=CLOSE_USER_ID, role="compliance",
    permissions=["case:read_assigned", "case:read",
                 "case:transition", "case:close"],
    scopes=["hq_main"])
REOPEN_ADMIN = ApplicationUser(
    user_id=ADMIN_USER_ID, role="admin",
    permissions=["case:read_assigned", "case:read", "case:reopen"],
    scopes=["hq_main"])


CASE_LOW = "aaaaaaa1-0000-0000-0000-000000000001"
CASE_HIGH = "aaaaaaa1-0000-0000-0000-000000000002"
APPROVAL_REOPEN = "bbbbbbb1-0000-0000-0000-000000000001"
APPROVAL_CLOSE = "bbbbbbb1-0000-0000-0000-000000000002"


async def _run(pool, stmt, params=None):
    return await pool.execute(stmt, params) if params is not None else await pool.execute(stmt)


async def _fetch_one(pool, stmt, params=None):
    return await pool.fetchrow(stmt, *params) if params is not None else await pool.fetchrow(stmt)


CLEANUP = [
    ("DELETE FROM notifications WHERE entity_id::text LIKE 'aaaaaaa1%' OR user_id LIKE 'r_close%'", None),
    ("DELETE FROM activity_timeline WHERE entity_id::text LIKE 'aaaaaaa1%'", None),
    ("DELETE FROM audit_outbox WHERE entity_id::text LIKE 'aaaaaaa1%'", None),
    ("DELETE FROM api_idempotency WHERE request_path LIKE '%aaaaaaa1%'", None),
    ("DELETE FROM compliance_cases WHERE case_id::text LIKE 'aaaaaaa1%'", None),
    ("DELETE FROM approval_decisions WHERE approval_request_id::text LIKE 'bbbbbbb1%'", None),
    ("DELETE FROM approval_requests WHERE entity_id::text LIKE 'aaaaaaa1%'", None),
    ("DELETE FROM user_scopes WHERE user_id LIKE 'r_close%'", None),
    ("DELETE FROM users WHERE user_id LIKE 'r_close%'", None),
]


@pytest.fixture
async def db():
    from shared.database import DatabaseConnector
    connector = DatabaseConnector(URL)
    await connector.initialize()
    yield connector
    await connector.close()


@pytest.fixture
async def seeded(db):
    import asyncpg
    pool = await asyncpg.create_pool(URL)
    try:
        for stmt, params in CLEANUP:
            await _run(pool, stmt, params)
        for uid, role in ((CLOSE_USER_ID, "compliance"),
                          (ADMIN_USER_ID, "admin"),
                          (REQUESTOR_USER_ID, "compliance")):
            await pool.execute(
                "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
                "VALUES ($1, $2, $1, $3, 'hq_main', $4, 'active') "
                "ON CONFLICT (user_id) DO NOTHING",
                uid, f"{uid}@bankintel.hq", role, DUMMY_BCRYPT_HASH,
            )
        await pool.execute(
            "INSERT INTO user_scopes (user_id, scope_id, granted_by) "
            "VALUES ($1, 'hq_main', $2) ON CONFLICT DO NOTHING",
            CLOSE_USER_ID, ADMIN_USER_ID)
        await pool.execute(
            "INSERT INTO user_scopes (user_id, scope_id, granted_by) "
            "VALUES ($1, 'hq_main', $2) ON CONFLICT DO NOTHING",
            ADMIN_USER_ID, ADMIN_USER_ID)
        for case_id, risk in ((CASE_LOW, "low"), (CASE_HIGH, "high")):
            await pool.execute(
                "INSERT INTO compliance_cases "
                "(case_id, title, scope_id, status, priority, risk_level, assigned_to, created_by, resolution, resolved_at, resolved_by, version) "
                "VALUES ($1::uuid, 'real-db close/reopen case', 'hq_main', 'resolved', 'medium', $2, $3, $4, 'Reviewed, all clear', NOW(), $3, 1)",
                case_id, risk, CLOSE_USER_ID, ADMIN_USER_ID)
        yield pool
    finally:
        for stmt, params in CLEANUP:
            await _run(pool, stmt, params)
        await pool.close()


async def test_close_low_risk_real_db(db, seeded):
    await CaseService(db).close(
        CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=1))

    row = await _fetch_one(seeded,
        "SELECT status, closed_at, closed_by, version FROM compliance_cases WHERE case_id = $1",
        [CASE_LOW])
    assert row["status"] == "closed"
    assert row["closed_at"] is not None
    assert row["closed_by"] == CLOSE_USER_ID
    assert row["version"] == 2

    tl = await _fetch_one(seeded,
        "SELECT event_type FROM activity_timeline WHERE entity_id = $1 AND event_type = 'case.closed'",
        [CASE_LOW])
    assert tl is not None

    note = await _fetch_one(seeded,
        "SELECT notification_type FROM notifications WHERE entity_id = $1 AND notification_type = 'case_closed'",
        [CASE_LOW])
    assert note is not None

    outbox = await _fetch_one(seeded,
        "SELECT event_type FROM audit_outbox WHERE entity_id = $1 AND event_type = 'case.closed'",
        [CASE_LOW])
    assert outbox is not None
    assert outbox["event_type"] == "case.closed"


async def test_close_high_risk_requires_approval_real_db(db, seeded):
    from shared.authorise import ApprovalRequiredError
    with pytest.raises(ApprovalRequiredError):
        await CaseService(db).close(
            CLOSE_USER, CASE_HIGH, CloseCaseRequest(expected_version=1))

    row = await _fetch_one(seeded,
        "SELECT status FROM compliance_cases WHERE case_id = $1", [CASE_HIGH])
    assert row["status"] == "resolved"


async def test_close_high_risk_with_approval_real_db(db, seeded):
    await seeded.execute(
        "INSERT INTO approval_requests "
        "(approval_request_id, action_type, entity_type, entity_id, requested_by, rationale, required_approvals, approval_count, status, expires_at) "
        "VALUES ($1::uuid, 'case_closure_critical_high', 'compliance_case', $2::uuid, $3, 'close approval', 1, 1, 'approved', NOW() + INTERVAL '24 hours')",
        APPROVAL_CLOSE, CASE_HIGH, REQUESTOR_USER_ID)

    await CaseService(db).close(
        CLOSE_USER, CASE_HIGH,
        CloseCaseRequest(expected_version=1, approval_request_id=APPROVAL_CLOSE))

    row = await _fetch_one(seeded,
        "SELECT status, closure_approval_id FROM compliance_cases WHERE case_id = $1",
        [CASE_HIGH])
    assert row["status"] == "closed"
    assert str(row["closure_approval_id"]) == APPROVAL_CLOSE

    executed = await _fetch_one(seeded,
        "SELECT executed_at FROM approval_requests WHERE approval_request_id = $1",
        [APPROVAL_CLOSE])
    assert executed["executed_at"] is not None


async def test_reopen_requires_approval_real_db(db, seeded):
    from shared.authorise import ApprovalRequiredError
    await CaseService(db).close(
        CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=1))

    with pytest.raises(ApprovalRequiredError):
        await CaseService(db).reopen(
            REOPEN_ADMIN, CASE_LOW,
            ReopenCaseRequest(reopen_reason="new evidence", expected_version=2,
                              approval_request_id="ffffffff-0000-0000-0000-000000000000"))

    row = await _fetch_one(seeded,
        "SELECT status FROM compliance_cases WHERE case_id = $1", [CASE_LOW])
    assert row["status"] == "closed"


async def test_reopen_real_db(db, seeded):
    await CaseService(db).close(
        CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=1))

    await seeded.execute(
        "INSERT INTO approval_requests "
        "(approval_request_id, action_type, entity_type, entity_id, requested_by, rationale, required_approvals, approval_count, status, expires_at) "
        "VALUES ($1::uuid, 'case_reopen', 'compliance_case', $2::uuid, $3, 'reopen approval', 1, 1, 'approved', NOW() + INTERVAL '24 hours')",
        APPROVAL_REOPEN, CASE_LOW, REQUESTOR_USER_ID)

    await CaseService(db).reopen(
        REOPEN_ADMIN, CASE_LOW,
        ReopenCaseRequest(reopen_reason="fresh evidence found", expected_version=2,
                          approval_request_id=APPROVAL_REOPEN))

    row = await _fetch_one(seeded,
        "SELECT status, closed_at, closed_by, closure_approval_id, reopen_reason, version "
        "FROM compliance_cases WHERE case_id = $1", [CASE_LOW])
    assert row["status"] == "open"
    assert row["closed_at"] is None
    assert row["closed_by"] is None
    assert row["closure_approval_id"] is None
    assert row["reopen_reason"] == "fresh evidence found"
    assert row["version"] == 3

    executed = await _fetch_one(seeded,
        "SELECT executed_at FROM approval_requests WHERE approval_request_id = $1",
        [APPROVAL_REOPEN])
    assert executed["executed_at"] is not None

    tl = await _fetch_one(seeded,
        "SELECT event_type FROM activity_timeline WHERE entity_id = $1 AND event_type = 'case.reopened'",
        [CASE_LOW])
    assert tl is not None

    note = await _fetch_one(seeded,
        "SELECT notification_type FROM notifications WHERE entity_id = $1 AND notification_type = 'case_reopened' AND user_id = $2",
        [CASE_LOW, CLOSE_USER_ID])
    assert note is not None

    outbox = await _fetch_one(seeded,
        "SELECT event_type FROM audit_outbox WHERE entity_id = $1 AND event_type = 'case.reopened'",
        [CASE_LOW])
    assert outbox is not None


async def test_double_reopen_rejected_real_db(db, seeded):
    from shared.authorise import WorkflowStateError
    await CaseService(db).close(
        CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=1))

    await seeded.execute(
        "INSERT INTO approval_requests "
        "(approval_request_id, action_type, entity_type, entity_id, requested_by, rationale, required_approvals, approval_count, status, expires_at) "
        "VALUES ($1::uuid, 'case_reopen', 'compliance_case', $2::uuid, $3, 'reopen approval', 1, 1, 'approved', NOW() + INTERVAL '24 hours')",
        APPROVAL_REOPEN, CASE_LOW, REQUESTOR_USER_ID)

    req = ReopenCaseRequest(reopen_reason="fresh evidence", expected_version=2,
                            approval_request_id=APPROVAL_REOPEN)
    await CaseService(db).reopen(REOPEN_ADMIN, CASE_LOW, req)
    with pytest.raises(WorkflowStateError):
        await CaseService(db).reopen(REOPEN_ADMIN, CASE_LOW, req)

    row = await _fetch_one(seeded,
        "SELECT status FROM compliance_cases WHERE case_id = $1", [CASE_LOW])
    assert row["status"] == "open"


async def test_double_close_rejected_real_db(db, seeded):
    from shared.authorise import WorkflowStateError
    await CaseService(db).close(
        CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=1))
    with pytest.raises(WorkflowStateError):
        await CaseService(db).close(
            CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=2))

    row = await _fetch_one(seeded,
        "SELECT status, version FROM compliance_cases WHERE case_id = $1", [CASE_LOW])
    assert row["status"] == "closed"
    assert row["version"] == 2


async def test_close_not_resolved_rejected_real_db(db, seeded):
    from shared.authorise import WorkflowStateError
    await seeded.execute(
        "UPDATE compliance_cases SET status = 'under_review' WHERE case_id = $1",
        CASE_LOW)
    with pytest.raises(WorkflowStateError):
        await CaseService(db).close(
            CLOSE_USER, CASE_LOW, CloseCaseRequest(expected_version=1))
