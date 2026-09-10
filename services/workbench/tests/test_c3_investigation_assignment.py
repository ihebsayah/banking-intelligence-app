"""C3 Investigation Submission & Compliance-Officer Assignment — real-DB integration proof.

Covers the canonical handoff: Analyst -> Investigation -> selected eligible
Compliance Officer, with row-level ownership enforced at the backend.

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

ANALYST_A = "c3_analyst_a"
ANALYST_B = "c3_analyst_b"
COMPLIANCE_X = "c3_compliance_x"
COMPLIANCE_Y = "c3_compliance_y"
ADMIN_ID = "c3_admin"
INACTIVE_COMPLIANCE = "c3_compliance_inactive"
UNKNOWN_UUID = "c3dddddd-0000-0000-0000-000000000099"

ALERT_A = "c3000000-0000-0000-0000-000000000001"
ALERT_B = "c3000000-0000-0000-0000-000000000002"
ALERT_C = "c3000000-0000-0000-0000-000000000003"
INV_A = "c3111111-0000-0000-0000-000000000001"
INV_B = "c3111111-0000-0000-0000-000000000002"
INV_A2 = "c3111111-0000-0000-0000-000000000003"
CASE_ESCALATE = "c3cccccc-0000-0000-0000-000000000001"

IDS = (ANALYST_A, ANALYST_B, COMPLIANCE_X, COMPLIANCE_Y, ADMIN_ID, INACTIVE_COMPLIANCE)

CLEANUP = [
    ("DELETE FROM comments WHERE author_id = ANY($1) OR redacted_by = ANY($1) OR entity_id::text LIKE 'c3%'", (IDS,)),
    ("DELETE FROM information_requests WHERE investigation_id::text LIKE 'c3%' OR case_id IN (SELECT case_id FROM compliance_cases WHERE case_id::text LIKE 'c3%' OR investigation_id::text LIKE 'c3%' OR alert_id::text LIKE 'c3%')", None),
    ("DELETE FROM decisions WHERE case_id IN (SELECT case_id FROM compliance_cases WHERE case_id::text LIKE 'c3%' OR investigation_id::text LIKE 'c3%' OR alert_id::text LIKE 'c3%')", None),
    ("DELETE FROM investigation_review_decisions WHERE investigation_id::text LIKE 'c3%'", None),
    ("DELETE FROM compliance_cases WHERE case_id::text LIKE 'c3%' OR investigation_id::text LIKE 'c3%' OR alert_id::text LIKE 'c3%'", None),
    ("DELETE FROM assignment_history WHERE entity_id::text LIKE 'c3%' OR assigned_to = ANY($1) OR assigned_from = ANY($1)", (IDS,)),
    ("DELETE FROM investigation_attachments WHERE investigation_id::text LIKE 'c3%' OR uploaded_by = ANY($1)", (IDS,)),
    ("DELETE FROM notifications WHERE user_id = ANY($1) OR entity_id::text LIKE 'c3%'", (IDS,)),
    ("DELETE FROM activity_timeline WHERE entity_id::text LIKE 'c3%' OR actor_id = ANY($1)", (IDS,)),
    ("DELETE FROM audit_outbox WHERE entity_id::text LIKE 'c3%'", None),
    ("DELETE FROM api_idempotency WHERE request_path LIKE '%c3%'", None),
    ("DELETE FROM investigations WHERE investigation_id::text LIKE 'c3%'", None),
    ("DELETE FROM alerts WHERE alert_id::text LIKE 'c3%'", None),
    ("DELETE FROM user_scopes WHERE user_id = ANY($1) OR granted_by = ANY($1)", (IDS,)),
    ("DELETE FROM users WHERE user_id = ANY($1)", (IDS,)),
]


async def _run(pool, stmt, params=None):
    await pool.execute(stmt, *params) if params else await pool.execute(stmt)


async def _hydrate(db, user_id):
    from shared.authorise import ApplicationUser
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

        users = [
            (ANALYST_A, "analyst"), (ANALYST_B, "analyst"),
            (COMPLIANCE_X, "compliance"), (COMPLIANCE_Y, "compliance"),
            (ADMIN_ID, "admin"),
        ]
        for uid, role in users:
            await pool.execute(
                "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
                "VALUES ($1, $2, $1, $3, 'hq_main', $4, 'active') "
                "ON CONFLICT (user_id) DO NOTHING",
                uid, f"{uid}@bankintel.hq", role, DUMMY_BCRYPT_HASH)
        await pool.execute(
            "INSERT INTO users (user_id, email, name, role, bank_id, password_hash, status) "
            "VALUES ($1, $2, $1, 'compliance', 'hq_main', $3, 'inactive') "
            "ON CONFLICT (user_id) DO NOTHING",
            INACTIVE_COMPLIANCE, f"{INACTIVE_COMPLIANCE}@bankintel.hq", DUMMY_BCRYPT_HASH)
        for uid, _role in users:
            await pool.execute(
                "INSERT INTO user_scopes (user_id, scope_id, granted_by) "
                "VALUES ($1, 'hq_main', $2) ON CONFLICT DO NOTHING",
                uid, ADMIN_ID)
        # inactivate compliance has no scope (still excluded by status anyway)

        # Alerts owned by each analyst
        await pool.execute(
            "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status, assigned_to, version) "
            "VALUES ($1::uuid, 'system_rule', 'high', 'C3 alert A', 'x', 'hq_main', 'acknowledged', $2, 1)",
            ALERT_A, ANALYST_A)
        await pool.execute(
            "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status, assigned_to, version) "
            "VALUES ($1::uuid, 'system_rule', 'high', 'C3 alert B', 'x', 'hq_main', 'acknowledged', $2, 1)",
            ALERT_B, ANALYST_B)
        await pool.execute(
            "INSERT INTO alerts (alert_id, alert_type, severity, title, description, scope_id, status, assigned_to, version) "
            "VALUES ($1::uuid, 'system_rule', 'medium', 'C3 alert C', 'x', 'hq_main', 'acknowledged', $2, 1)",
            ALERT_C, ANALYST_A)

        # Investigation A: owned + assigned to Analyst A, active with findings+conclusion
        await pool.execute(
            "INSERT INTO investigations (investigation_id, alert_id, title, scope_id, status, priority, assigned_to, created_by, findings_text, conclusion, started_at, submitted_at, version) "
            "VALUES ($1::uuid, $2::uuid, 'C3 inv A', 'hq_main', 'active', 'high', $3, $3, 'findings here', 'conclusion here', NOW(), NULL, 2)",
            INV_A, ALERT_A, ANALYST_A)
        # Investigation B: owned + assigned to Analyst B, active
        await pool.execute(
            "INSERT INTO investigations (investigation_id, alert_id, title, scope_id, status, priority, assigned_to, created_by, findings_text, conclusion, started_at, version) "
            "VALUES ($1::uuid, $2::uuid, 'C3 inv B', 'hq_main', 'active', 'medium', $3, $3, 'f', 'c', NOW(), 2)",
            INV_B, ALERT_B, ANALYST_B)
        # Investigation A2: Analyst A's investigation already submitted to Compliance X
        await pool.execute(
            "INSERT INTO investigations (investigation_id, alert_id, title, scope_id, status, priority, assigned_to, created_by, findings_text, conclusion, submitted_at, compliance_officer_id, version) "
            "VALUES ($1::uuid, $2::uuid, 'C3 inv A2', 'hq_main', 'submitted', 'medium', $3, $3, 'f', 'c', NOW(), $4, 3)",
            INV_A2, ALERT_C, ANALYST_A, COMPLIANCE_X)
        yield pool
    finally:
        for stmt, params in CLEANUP:
            await _run(pool, stmt, params)
        await pool.close()


async def _fetch_inv(db, inv_id):
    row = await db.fetch_one(
        "SELECT * FROM investigations WHERE investigation_id = $1::uuid", [inv_id])
    return row


from workbench.schemas.investigations import (  # noqa: E402
    SubmitInvestigationRequest,
)
from workbench.services.investigation_service import (  # noqa: E402
    InvestigationService,
)
from shared.authorise import (  # noqa: E402
    OwnershipDeniedError as AuthOwnershipDenied,
    PermissionDeniedError as AuthPermissionDenied,
)
from workbench.exceptions import (  # noqa: E402
    InvalidAssignee, InvalidTransition, ResourceNotFound,
)


# ── 1. Eligible officer discovery ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_eligible_officers_returns_only_active_eligible_compliance(db, seeded):
    svc = InvestigationService(db)
    rows = await svc.list_eligible_compliance_officers(
        await _hydrate(db, ANALYST_A), "hq_main")
    ids = {r.user_id for r in rows}
    assert COMPLIANCE_X in ids
    assert COMPLIANCE_Y in ids
    # analyst/admin/inactive excluded
    assert ANALYST_A not in ids
    assert ADMIN_ID not in ids
    assert INACTIVE_COMPLIANCE not in ids


# ── Assignee validation matrix (via a real submitted submission attempt) ──────

@pytest.mark.asyncio
async def test_submit_to_analyst_denied(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    with pytest.raises(InvalidAssignee):
        await InvestigationService(db).submit_to_compliance(
            analyst_a, INV_A,
            SubmitInvestigationRequest(compliance_officer_id=ANALYST_B, expected_version=2))


@pytest.mark.asyncio
async def test_submit_to_admin_denied(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    with pytest.raises(InvalidAssignee):
        await InvestigationService(db).submit_to_compliance(
            analyst_a, INV_A,
            SubmitInvestigationRequest(compliance_officer_id=ADMIN_ID, expected_version=2))


@pytest.mark.asyncio
async def test_submit_to_inactive_compliance_denied(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    with pytest.raises(InvalidAssignee):
        await InvestigationService(db).submit_to_compliance(
            analyst_a, INV_A,
            SubmitInvestigationRequest(compliance_officer_id=INACTIVE_COMPLIANCE, expected_version=2))


@pytest.mark.asyncio
async def test_submit_to_unknown_user_denied(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    with pytest.raises(InvalidAssignee):
        await InvestigationService(db).submit_to_compliance(
            analyst_a, INV_A,
            SubmitInvestigationRequest(compliance_officer_id=UNKNOWN_UUID, expected_version=2))


# ── Ownership / assignment ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyst_a_submits_own_inv_to_officer_x_allowed(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    res = await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    assert res.investigation.status == "submitted"
    assert res.investigation.compliance_officer_id == COMPLIANCE_X
    assert res.investigation.submitted_at is not None
    # analyst ownership preserved
    assert res.investigation.assigned_to == ANALYST_A
    assert res.investigation.created_by == ANALYST_A
    # persisted in DB
    row = await _fetch_inv(db, INV_A)
    assert row["status"] == "submitted"
    assert row["compliance_officer_id"] == COMPLIANCE_X
    assert row["assigned_to"] == ANALYST_A


@pytest.mark.asyncio
async def test_analyst_a_submits_analyst_b_inv_denied(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    with pytest.raises(AuthOwnershipDenied):
        await InvestigationService(db).submit_to_compliance(
            analyst_a, INV_B,
            SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))


@pytest.mark.asyncio
async def test_admin_cannot_submit_on_behalf_of_analyst(db, seeded):
    admin = await _hydrate(db, ADMIN_ID)
    # admin lacks investigation:transition -> permission denied; also prohibited
    # from ownership path. Expect AuthorisationError (permission).
    from shared.authorise import ProhibitedComboError
    with pytest.raises(Exception):
        await InvestigationService(db).submit_to_compliance(
            admin, INV_A,
            SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))


# ── Queue filtering (compliance sees only assigned) ───────────────────────────

@pytest.mark.asyncio
async def test_officer_x_queue_contains_assigned_inv(db, seeded):
    officer_x = await _hydrate(db, COMPLIANCE_X)
    items, total = await InvestigationService(db).list_submitted(officer_x, "hq_main")
    ids = {i.investigation_id for i in items}
    assert INV_A2 in ids  # assigned to X in seed

@pytest.mark.asyncio
async def test_officer_y_queue_excludes_xs_inv(db, seeded):
    officer_y = await _hydrate(db, COMPLIANCE_Y)
    items, total = await InvestigationService(db).list_submitted(officer_y, "hq_main")
    ids = {i.investigation_id for i in items}
    assert INV_A2 not in ids


# ── Detail authorization (IDOR) ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_officer_x_detail_allowed(db, seeded):
    officer_x = await _hydrate(db, COMPLIANCE_X)
    inv = await InvestigationService(db).get_by_id(officer_x, INV_A2)
    assert inv is not None


@pytest.mark.asyncio
async def test_officer_y_detail_denied(db, seeded):
    officer_y = await _hydrate(db, COMPLIANCE_Y)
    with pytest.raises(ResourceNotFound):
        await InvestigationService(db).get_by_id(officer_y, INV_A2)


@pytest.mark.asyncio
async def test_analyst_b_does_not_see_analyst_a_submitted_inv(db, seeded):
    analyst_b = await _hydrate(db, ANALYST_B)
    with pytest.raises(ResourceNotFound):
        await InvestigationService(db).get_by_id(analyst_b, INV_A2)


@pytest.mark.asyncio
async def test_analyst_a_still_sees_own_submitted_inv(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    inv = await InvestigationService(db).get_by_id(analyst_a, INV_A2)
    assert inv is not None
    assert inv.investigation_id == INV_A2


# ── Review action authorization ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_officer_x_review_not_harmful_allowed(db, seeded):
    from workbench.schemas.investigations import ReviewNotHarmfulRequest
    officer_x = await _hydrate(db, COMPLIANCE_X)
    res = await InvestigationService(db).review_not_harmful(
        officer_x, INV_A2, ReviewNotHarmfulRequest(rationale="not harmful", expected_version=3))
    assert res.investigation.status == "completed"


@pytest.mark.asyncio
async def test_officer_y_review_not_harmful_denied(db, seeded):
    from workbench.schemas.investigations import ReviewNotHarmfulRequest
    officer_y = await _hydrate(db, COMPLIANCE_Y)
    with pytest.raises(AuthOwnershipDenied):
        await InvestigationService(db).review_not_harmful(
            officer_y, INV_A2, ReviewNotHarmfulRequest(rationale="x", expected_version=3))


@pytest.mark.asyncio
async def test_officer_y_escalate_to_case_denied(db, seeded):
    from workbench.schemas.investigations import EscalateInvestigationRequest
    officer_y = await _hydrate(db, COMPLIANCE_Y)
    with pytest.raises(AuthOwnershipDenied):
        await InvestigationService(db).escalate_to_case(
            officer_y, INV_A2,
            EscalateInvestigationRequest(title="x", rationale="x", expected_version=3))


@pytest.mark.asyncio
async def test_officer_x_escalate_to_case_allowed_when_state_permits(db, seeded):
    from workbench.schemas.investigations import EscalateInvestigationRequest
    from workbench.repos import ReportSubmissionRepo
    from workbench.models import InvestigationReportSubmission
    from datetime import datetime, timezone
    import uuid
    # C5: escalation requires an immutable report submission snapshot to exist
    # for the investigation (otherwise escalate 409s with NO_SUBMISSION_SNAPSHOT).
    # INV_A2 was seeded already `submitted`, so it has no snapshot — create one
    # directly via the same immutable INSERT-only repo submit uses.
    await ReportSubmissionRepo(db).insert(
        InvestigationReportSubmission(
            submission_id=str(uuid.uuid4()),
            investigation_id=INV_A2,
            analyst_id=ANALYST_A,
            compliance_officer_id=COMPLIANCE_X,
            findings_text="f",
            findings_refs=[],
            conclusion="c",
            submitted_at=datetime.now(timezone.utc),
            evidence_manifest=[],
            report_hash="c3snap",
        )
    )
    officer_x = await _hydrate(db, COMPLIANCE_X)
    res = await InvestigationService(db).escalate_to_case(
        officer_x, INV_A2,
        EscalateInvestigationRequest(title="escalate", rationale="x", expected_version=3))
    assert res.investigation.status == "completed"


@pytest.mark.asyncio
async def test_admin_cannot_perform_compliance_review_action(db, seeded):
    from workbench.schemas.investigations import ReviewNotHarmfulRequest
    from shared.authorise import ProhibitedComboError
    admin = await _hydrate(db, ADMIN_ID)
    with pytest.raises(ProhibitedComboError):
        await InvestigationService(db).review_not_harmful(
            admin, INV_A2, ReviewNotHarmfulRequest(rationale="x", expected_version=3))


# ── Contextual information requests (assigned officer only) ──────────────────

@pytest.mark.asyncio
async def test_officer_x_create_ir_on_assigned_inv_allowed(db, seeded):
    from workbench.services.information_request_service import InformationRequestService
    from workbench.schemas.information_requests import CreateInformationRequest
    officer_x = await _hydrate(db, COMPLIANCE_X)
    res = await InformationRequestService(db).create_for_investigation(
        officer_x, INV_A2,
        CreateInformationRequest(assigned_to=ANALYST_A, question="please provide docs"))
    assert res.information_request.investigation_id == INV_A2


@pytest.mark.asyncio
async def test_officer_y_create_ir_on_xs_inv_denied(db, seeded):
    from workbench.services.information_request_service import InformationRequestService
    from workbench.schemas.information_requests import CreateInformationRequest
    officer_y = await _hydrate(db, COMPLIANCE_Y)
    with pytest.raises(AuthOwnershipDenied):
        await InformationRequestService(db).create_for_investigation(
            officer_y, INV_A2,
            CreateInformationRequest(assigned_to=ANALYST_A, question="please provide docs"))


# ── Immutability / no reassign / no self-claim ────────────────────────────────

@pytest.mark.asyncio
async def test_analyst_cannot_reassign_after_submission(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    # submitted state is not in submit-able states -> WorkflowStateError
    from shared.authorise import WorkflowStateError
    with pytest.raises(WorkflowStateError):
        await InvestigationService(db).submit_to_compliance(
            analyst_a, INV_A2,
            SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_Y, expected_version=3))


@pytest.mark.asyncio
async def test_compliance_cannot_self_claim_via_submit(db, seeded):
    # The submit path is analyst-driven; there is no claim endpoint. Ensure
    # compliance cannot submit (no investigation:transition permission) and
    # cannot re-assign a submitted inv to itself via submit.
    officer_y = await _hydrate(db, COMPLIANCE_Y)
    from shared.authorise import PermissionDeniedError as PDen
    with pytest.raises(PDen):
        await InvestigationService(db).submit_to_compliance(
            officer_y, INV_A2,
            SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_Y, expected_version=3))


# ── Idempotency / invariants ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_submitted_without_assignee_for_new_submissions(db, seeded):
    # After Analyst A submits to X, verify both submitted and assignee present.
    analyst_a = await _hydrate(db, ANALYST_A)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    row = await _fetch_inv(db, INV_A)
    assert row["status"] == "submitted"
    assert row["compliance_officer_id"] is not None


@pytest.mark.asyncio
async def test_audit_timeline_event_emitted(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    rows = await db.fetch_all(
        "SELECT event_type FROM activity_timeline WHERE entity_id = $1::uuid",
        [INV_A])
    assert any(r["event_type"] == "investigation.submitted_to_compliance" for r in rows)


@pytest.mark.asyncio
async def test_notification_emitted_to_officer(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    rows = await db.fetch_all(
        "SELECT * FROM notifications WHERE user_id = $1 AND entity_id = $2::uuid",
        [COMPLIANCE_X, INV_A])
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_outbox_event_emitted(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    rows = await db.fetch_all(
        "SELECT event_type FROM audit_outbox WHERE entity_id = $1::uuid",
        [INV_A])
    assert any(r["event_type"] == "investigation.submitted_to_compliance" for r in rows)


# ── C4: Immutable report snapshot ─────────────────────────────────────────────

@ pytest.mark.asyncio
async def test_submit_creates_immutable_report_snapshot(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    res = await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    # Snapshot is surfaced on the response
    snap = res.investigation.submission_snapshot
    assert snap is not None
    assert snap.analyst_id == ANALYST_A
    assert snap.compliance_officer_id == COMPLIANCE_X
    assert snap.findings_text == "findings here"
    assert snap.conclusion == "conclusion here"
    assert snap.report_hash
    # Persisted, INSERT-only snapshot row
    row = await db.fetch_one(
        "SELECT * FROM investigation_report_submissions WHERE investigation_id = $1::uuid",
        [INV_A])
    assert row is not None
    assert row["findings_text"] == "findings here"
    assert row["conclusion"] == "conclusion here"
    assert row["analyst_id"] == ANALYST_A
    assert row["compliance_officer_id"] == COMPLIANCE_X
    # Original report row is unchanged
    inv_row = await _fetch_inv(db, INV_A)
    assert inv_row["findings_text"] == "findings here"
    assert inv_row["conclusion"] == "conclusion here"


@ pytest.mark.asyncio
async def test_post_submit_findings_edit_denied(db, seeded):
    from shared.authorise import WorkflowStateError
    from workbench.schemas.investigations import UpdateInvestigationRequest
    analyst_a = await _hydrate(db, ANALYST_A)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    with pytest.raises(WorkflowStateError):
        await InvestigationService(db).update(
            analyst_a, INV_A,
            UpdateInvestigationRequest(findings_text="tampered", expected_version=3))


@ pytest.mark.asyncio
async def test_submitted_response_returns_snapshot_for_assigned_officer(db, seeded):
    analyst_a = await _hydrate(db, ANALYST_A)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))
    officer_x = await _hydrate(db, COMPLIANCE_X)
    detail = await InvestigationService(db).get_by_id(officer_x, INV_A)
    assert detail.submission_snapshot is not None
    assert detail.submission_snapshot.findings_text == "findings here"
    assert detail.submission_snapshot.report_hash
    assert detail.findings_text == "findings here"


@ pytest.mark.asyncio
async def test_full_ir_cycle_preserves_snapshot_and_assignee(db, seeded):
    from workbench.services.information_request_service import InformationRequestService
    from workbench.schemas.information_requests import (
        AcknowledgeInformationRequest, AcceptInformationRequest,
        CreateInformationRequest, RespondInformationRequest,
    )
    analyst_a = await _hydrate(db, ANALYST_A)
    officer_x = await _hydrate(db, COMPLIANCE_X)
    await InvestigationService(db).submit_to_compliance(
        analyst_a, INV_A,
        SubmitInvestigationRequest(compliance_officer_id=COMPLIANCE_X, expected_version=2))

    ir_svc = InformationRequestService(db)
    await ir_svc.create_for_investigation(
        officer_x, INV_A,
        CreateInformationRequest(assigned_to=ANALYST_A, question="provide docs"))
    ir_row = await db.fetch_one(
        "SELECT ir_id FROM information_requests WHERE investigation_id = $1::uuid ORDER BY created_at DESC LIMIT 1",
        [INV_A])
    ir_id = ir_row["ir_id"]
    from workbench.repos import InfoRequestRepo
    cur = await InfoRequestRepo(db).fetch_by_id(ir_id)
    v = cur.version

    # awaiting_information state: report cannot be edited
    from shared.authorise import WorkflowStateError
    from workbench.schemas.investigations import UpdateInvestigationRequest as _U
    with pytest.raises(WorkflowStateError):
        await InvestigationService(db).update(analyst_a, INV_A, _U(findings_text="x", expected_version=v))

    await ir_svc.acknowledge(analyst_a, ir_id, AcknowledgeInformationRequest(expected_version=v))
    ir2 = await InfoRequestRepo(db).fetch_by_id(ir_id)
    await ir_svc.respond(analyst_a, ir_id, RespondInformationRequest(response_text="new evidence", expected_version=ir2.version))
    ir3 = await InfoRequestRepo(db).fetch_by_id(ir_id)
    await ir_svc.accept(officer_x, ir_id, AcceptInformationRequest(acceptance_note="ok", expected_version=ir3.version))

    # Investigation returned to submitted with assignee preserved
    inv_row = await _fetch_inv(db, INV_A)
    assert inv_row["status"] == "submitted"
    assert inv_row["compliance_officer_id"] == COMPLIANCE_X
    assert inv_row["assigned_to"] == ANALYST_A
    assert inv_row["findings_text"] == "findings here"
    assert inv_row["conclusion"] == "conclusion here"
    # Only ONE snapshot row persists and equals the original submission
    rows = await db.fetch_all(
        "SELECT * FROM investigation_report_submissions WHERE investigation_id = $1::uuid",
        [INV_A])
    assert len(rows) == 1
    assert rows[0]["findings_text"] == "findings here"
    assert rows[0]["conclusion"] == "conclusion here"
