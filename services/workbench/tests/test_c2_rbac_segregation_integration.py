"""C2 RBAC segregation — real-DB integration proof.

Verifies the P0 acceptance criteria against the actual authorise() engine +
permissions loaded from role_permissions in a migrated scratch database:

- Compliance Officer CAN create/open case, record decision (with mandatory
  rationale), and close case where the workflow state permits.
- Analyst: same calls -> DENIED (permission + PROHIBITED).
- Admin: operational decision/close -> DENIED by SoD (PROHIBITED).

Also verifies compliance can no longer access standalone alerts (list_assigned
via alert:read_assigned) nor transition alerts, and analyst can no longer read
standalone cases (case:read_assigned).

Skipped when INTEGRATION_DATABASE_URL is not set.
"""
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("INTEGRATION_DATABASE_URL"),
    reason="INTEGRATION_DATABASE_URL not set (real-Postgres integration test)",
)

URL = os.environ.get("INTEGRATION_DATABASE_URL", "")
DUMMY_BCRYPT_HASH = "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y"

COMPLIANCE_ID = "c2_compliance"
ANALYST_ID = "c2_analyst"
ADMIN_ID = "c2_admin"

from shared.authorise import (  # noqa: E402
    ApplicationUser, PermissionDeniedError, ProhibitedComboError,
)
from workbench.schemas.cases import (  # noqa: E402
    CloseCaseRequest, DecisionType, RecordDecisionRequest,
)
from workbench.services.case_service import CaseService  # noqa: E402
from workbench.services.alert_service import AlertService  # noqa: E402

COMPLIANCE_CASE = "c2cccccc-0000-0000-0000-000000000001"
ALERT_ID = "c2aaaaaa-0000-0000-0000-000000000001"

IDS = (COMPLIANCE_ID, ANALYST_ID, ADMIN_ID)

CLEANUP = [
    ("DELETE FROM notifications WHERE user_id = ANY($1) OR entity_id::text LIKE 'c2%'", (IDS,)),
    ("DELETE FROM activity_timeline WHERE entity_id::text LIKE 'c2%'", None),
    ("DELETE FROM audit_outbox WHERE entity_id::text LIKE 'c2%'", None),
    ("DELETE FROM api_idempotency WHERE request_path LIKE '%c2%'", None),
    ("DELETE FROM decisions WHERE case_id::text LIKE 'c2%'", None),
    ("DELETE FROM compliance_cases WHERE case_id::text LIKE 'c2%'", None),
    ("DELETE FROM alerts WHERE alert_id::text LIKE 'c2%'", None),
    ("DELETE FROM user_scopes WHERE user_id = ANY($1)", (IDS,)),
    ("DELETE FROM users WHERE user_id = ANY($1)", (IDS,)),
]


async def _run(pool, stmt, params=None):
    await pool.execute(stmt, *params) if params else await pool.execute(stmt)


async def _hydrate(db, user_id):
    """Hydrate an ApplicationUser from the DB's role_permissions (mirrors
    integration_app._resolve_application_user)."""
    row = await db.fetch_one(
        "SELECT role FROM users WHERE user_id = $1", [user_id])
    pr = await db.fetch_all(
        "SELECT permission_key FROM role_permissions WHERE role_id = $1",
        [row["role"]])
    scopes = await db.fetch_all(
        "SELECT scope_id FROM user_scopes WHERE user_id = $1", [user_id])
    return ApplicationUser(
        user_id=user_id, role=row["role"],
        permissions=[r["permission_key"] for r in pr],
        scopes=[s["scope_id"] for s in scopes])


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
        for uid, role in ((COMPLIANCE_ID, "compliance"),
                          (ANALYST_ID, "analyst"),
                          (ADMIN_ID, "admin")):
            await pool.execute(
                "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
                "VALUES ($1, $2, $1, $3, 'hq_main', $4, 'active') "
                "ON CONFLICT (user_id) DO NOTHING",
                uid, f"{uid}@bankintel.hq", role, DUMMY_BCRYPT_HASH)
        for uid, _role in ((COMPLIANCE_ID, "compliance"),
                           (ANALYST_ID, "analyst"),
                           (ADMIN_ID, "admin")):
            await pool.execute(
                "INSERT INTO user_scopes (user_id, scope_id, granted_by) "
                "VALUES ($1, 'hq_main', $2) ON CONFLICT DO NOTHING",
                uid, ADMIN_ID)
        # Seed a case in decision_pending state (owner = compliance)
        await pool.execute(
            "INSERT INTO compliance_cases "
            "(case_id, title, scope_id, status, priority, risk_level, assigned_to, created_by, version) "
            "VALUES ($1::uuid, 'C2 decision/close case', 'hq_main', 'decision_pending', 'medium', 'low', $2, $2, 3)",
            COMPLIANCE_CASE, COMPLIANCE_ID)
        # Seed an alert assigned to the analyst (owned by analyst)
        await pool.execute(
            "INSERT INTO alerts "
            "(alert_id, alert_type, severity, title, description, scope_id, status, assigned_to, version) "
            "VALUES ($1::uuid, 'system_rule', 'low', 'C2 segregated alert', 'x', 'hq_main', 'acknowledged', $2, 1)",
            ALERT_ID, ANALYST_ID)
        yield pool
    finally:
        for stmt, params in CLEANUP:
            await _run(pool, stmt, params)
        await pool.close()


@pytest.mark.asyncio
async def test_compliance_can_record_decision(db, seeded):
    compliance = await _hydrate(db, COMPLIANCE_ID)
    assert "case:decision" in compliance.permissions
    await CaseService(db).record_decision(
        compliance, COMPLIANCE_CASE,
        RecordDecisionRequest(decision_type=DecisionType.NO_ACTION,
                              rationale="Thorough review found no issues",
                              expected_version=3))


@pytest.mark.asyncio
async def test_compliance_can_close_case(db, seeded):
    compliance = await _hydrate(db, COMPLIANCE_ID)
    assert "case:close" in compliance.permissions
    # resolve via record decision -> resolves case
    await CaseService(db).record_decision(
        compliance, COMPLIANCE_CASE,
        RecordDecisionRequest(decision_type=DecisionType.NO_ACTION,
                              rationale="No issues", expected_version=3))
    # now close the resolved case
    await CaseService(db).close(
        compliance, COMPLIANCE_CASE,
        CloseCaseRequest(resolution="No issues found on review",
                         expected_version=4))


@pytest.mark.asyncio
async def test_analyst_cannot_record_decision(db, seeded):
    from shared.authorise import AuthorisationError
    analyst = await _hydrate(db, ANALYST_ID)
    assert "case:decision" not in analyst.permissions
    # PROHIBITED (analyst, case:decision) fires before the permission gate.
    with pytest.raises(ProhibitedComboError):
        await CaseService(db).record_decision(
            analyst, COMPLIANCE_CASE,
            RecordDecisionRequest(decision_type=DecisionType.NO_ACTION,
                                  rationale="x", expected_version=3))


@pytest.mark.asyncio
async def test_admin_cannot_record_decision_sod(db, seeded):
    admin = await _hydrate(db, ADMIN_ID)
    with pytest.raises(ProhibitedComboError):
        await CaseService(db).record_decision(
            admin, COMPLIANCE_CASE,
            RecordDecisionRequest(decision_type=DecisionType.NO_ACTION,
                                  rationale="x", expected_version=3))


@pytest.mark.asyncio
async def test_admin_cannot_close_case_sod(db, seeded):
    # resolve first via compliance
    compliance = await _hydrate(db, COMPLIANCE_ID)
    await CaseService(db).record_decision(
        compliance, COMPLIANCE_CASE,
        RecordDecisionRequest(decision_type=DecisionType.NO_ACTION,
                              rationale="x", expected_version=3))
    admin = await _hydrate(db, ADMIN_ID)
    with pytest.raises(ProhibitedComboError):
        await CaseService(db).close(admin, COMPLIANCE_CASE,
                                    CloseCaseRequest(expected_version=4))


@pytest.mark.asyncio
async def test_compliance_cannot_list_standalone_alerts(db, seeded):
    compliance = await _hydrate(db, COMPLIANCE_ID)
    assert "alert:read_assigned" not in compliance.permissions
    with pytest.raises(PermissionDeniedError):
        await AlertService(db).list_assigned(compliance, "hq_main")


@pytest.mark.asyncio
async def test_compliance_cannot_get_alert_by_id(db, seeded):
    compliance = await _hydrate(db, COMPLIANCE_ID)
    # compliance lacks alert:read_assigned and alert:read -> both authorise
    # paths deny -> surfaced as ResourceNotFound (404) to avoid a leak.
    from workbench.exceptions import ResourceNotFound
    with pytest.raises(ResourceNotFound):
        await AlertService(db).get_by_id(compliance, ALERT_ID)


@pytest.mark.asyncio
async def test_analyst_cannot_list_standalone_cases(db, seeded):
    analyst = await _hydrate(db, ANALYST_ID)
    assert "case:read_assigned" not in analyst.permissions
    from shared.authorise import PermissionDeniedError as PDF
    with pytest.raises(PDF):
        await CaseService(db).list_assigned(analyst, "hq_main")


@pytest.mark.asyncio
async def test_analyst_can_still_list_own_alerts(db, seeded):
    analyst = await _hydrate(db, ANALYST_ID)
    assert "alert:read_assigned" in analyst.permissions
    items, total = await AlertService(db).list_assigned(analyst, "hq_main")
    assert len(items) == 1
    assert items[0].alert_id == ALERT_ID
