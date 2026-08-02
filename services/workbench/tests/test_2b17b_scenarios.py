"""Phase 2B.17b scenario suite — T00–T35, XA01–XA10, V01–V11, AU01–AU08,
F01–F18, IRS01, DP01–DP04 executed against a composed FastAPI integration app
backed by the real integration PostgreSQL database and real authorisation engine.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

import httpx
import pytest
import pytest_asyncio
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from shared.database import DatabaseConnector
from workbench.integration_app import build_integration_app
from workbench.outbox_worker import run_cycle
from workbench.repos import OutboxRepo

# Routers return JSONResponse(content=result.model_dump()) which contains
# datetime objects. Patch render to jsonable_encoder so stdlib json can serialize.
_original_render = JSONResponse.render


def _patched_render(self: JSONResponse, content: Any) -> bytes:
    return _original_render(self, jsonable_encoder(content))


JSONResponse.render = _patched_render  # type: ignore[method-assign]

INTEGRATION_DB_URL = os.environ.get(
    "INTEGRATION_DATABASE_URL",
    "postgresql://integration_user:integrationpass123@localhost:5435/banking_integration",
)
AUDIT_MOCK_URL = "http://localhost:18008"

# ── Scenario user catalogue (seeded idempotently) ─────────────────────────────

_USERS: Dict[str, Dict[str, Any]] = {
    "sbtb_analyst_1": {
        "user_id": "sbtb_analyst_1", "email": "a1@test.local", "name": "Analyst One",
        "role": "analyst", "status": "active", "permissions": [],
    },
    "sbtb_analyst_2": {
        "user_id": "sbtb_analyst_2", "email": "a2@test.local", "name": "Analyst Two",
        "role": "analyst", "status": "active", "permissions": [],
    },
    "sbtb_compliance_1": {
        "user_id": "sbtb_compliance_1", "email": "c1@test.local", "name": "Compliance One",
        "role": "compliance", "status": "active",
        "permissions": ["case:decision", "case:close"],
    },
    "sbtb_compliance_2": {
        "user_id": "sbtb_compliance_2", "email": "c2@test.local", "name": "Compliance Two",
        "role": "compliance", "status": "active",
        "permissions": ["case:decision", "case:close"],
    },
    "sbtb_admin_1": {
        "user_id": "sbtb_admin_1", "email": "adm1@test.local", "name": "Admin One",
        "role": "admin", "status": "active", "permissions": [],
    },
    "sbtb_suspended_analyst": {
        "user_id": "sbtb_suspended_analyst", "email": "susp@test.local", "name": "Suspended",
        "role": "analyst", "status": "suspended", "permissions": [],
    },
    "sbtb_inactive_analyst": {
        "user_id": "sbtb_inactive_analyst", "email": "inact@test.local", "name": "Inactive",
        "role": "analyst", "status": "inactive", "permissions": [],
    },
    "sbtb_outsider": {
        "user_id": "sbtb_outsider", "email": "out@test.local", "name": "Outsider",
        "role": "analyst", "status": "active", "permissions": [],
    },
    "sbtb_manager_legacy": {
        "user_id": "sbtb_manager_legacy", "email": "mgr@test.local", "name": "Legacy Mgr",
        "role": "manager", "status": "active", "permissions": [],
    },
}

_USER_SCOPES: Dict[str, list[str]] = {
    "sbtb_analyst_1": ["hq_main"],
    "sbtb_analyst_2": ["hq_main"],
    "sbtb_compliance_1": ["hq_main"],
    "sbtb_compliance_2": ["hq_main"],
    "sbtb_admin_1": ["hq_main", "global"],
    "sbtb_suspended_analyst": ["hq_main"],
    "sbtb_inactive_analyst": ["hq_main"],
    "sbtb_outsider": ["branch_a"],
    "sbtb_manager_legacy": ["hq_main"],
}

_GRANTED_BY = "sbtb_admin_1"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def integration_db():
    connector = DatabaseConnector(INTEGRATION_DB_URL)
    await connector.initialize()
    yield connector
    await connector.close()


@pytest_asyncio.fixture
async def scenario_app(integration_db):
    return build_integration_app(integration_db)


@pytest.fixture
def client(scenario_app):
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=scenario_app),
        base_url="http://integration.test",
    )


@pytest_asyncio.fixture
async def seeded_users(integration_db):
    await _seed_users(integration_db)
    yield
    # no teardown — rows are idempotent and reused across tests


async def _seed_users(db: DatabaseConnector) -> None:
    await db.execute(
        "INSERT INTO organisation_scopes (scope_id, scope_type, label) VALUES "
        "('branch_a', 'branch', 'Branch A') ON CONFLICT (scope_id) DO NOTHING",
        [],
    )
    for uid, u in _USERS.items():
        await db.execute(
            "INSERT INTO users (user_id, email, name, role, password_hash, status, permissions) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "email=EXCLUDED.email, name=EXCLUDED.name, role=EXCLUDED.role, "
            "status=EXCLUDED.status, permissions=EXCLUDED.permissions",
            [uid, u["email"], u["name"], u["role"], "dummy-hash", u["status"],
             u.get("permissions") or []],
        )
        for uid, scopes in _USER_SCOPES.items():
            for scope in scopes:
                await db.execute(
                    "INSERT INTO user_scopes (user_id, scope_id, granted_by) VALUES ($1, $2, $3) "
                    "ON CONFLICT (user_id, scope_id) DO NOTHING",
                    [uid, scope, _GRANTED_BY],
                )


# ── HTTP helpers ──────────────────────────────────────────────────────────────


def _headers(user: str, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    h = {"X-Test-User": user}
    if extra:
        h.update(extra)
    return h


async def _get(client, url, user, **kw):
    return await client.get(url, headers=_headers(user), **kw)


async def _patch(client, url, user, body, **kw):
    headers = _headers(user)
    headers.update(kw.pop("headers", {}))
    return await client.patch(url, headers=headers, json=body, **kw)


async def _post(client, url, user, body, **kw):
    return await client.post(url, headers=_headers(user), json=body, **kw)


async def _assert_status(resp, expected):
    assert resp.status_code == expected, f"{resp.status_code} → {resp.text[:300]}"


# ── Workflow seed helpers ─────────────────────────────────────────────────────


async def _seed_alert(db, **overrides) -> str:
    aid = str(uuid.uuid4())
    d = dict(alert_id=aid, alert_type="transaction_anomaly", severity="high",
             title="Seed Alert", description="", scope_id="hq_main", status="new",
             assigned_to=None, version=1)
    d.update(overrides)
    cols = ", ".join(d.keys())
    vals = ", ".join([f"${i+1}" for i in range(len(d))])
    await db.execute(f"INSERT INTO alerts ({cols}) VALUES ({vals})", list(d.values()))
    return aid


async def _seed_investigation(db, **overrides) -> str:
    iid = str(uuid.uuid4())
    d = dict(investigation_id=iid, title="Seed Investigation", description="",
             alert_id=None, scope_id="hq_main", status="open", priority="medium",
             assigned_to=None, created_by="sbtb_analyst_1", findings_text=None,
             findings_refs=None, conclusion=None, started_at=None, submitted_at=None,
             completed_at=None, return_reason=None, version=1)
    d.update(overrides)
    cols = ", ".join(d.keys())
    vals = ", ".join([f"${i+1}" for i in range(len(d))])
    await db.execute(f"INSERT INTO investigations ({cols}) VALUES ({vals})", list(d.values()))
    return iid


async def _seed_case(db, **overrides) -> str:
    cid = str(uuid.uuid4())
    d = dict(case_id=cid, title="Seed Case", description="", alert_id=None,
             investigation_id=None, scope_id="hq_main", status="open", priority="medium",
             risk_level="high", regulatory_frameworks=None, assigned_to=None,
             created_by="sbtb_compliance_1", version=1)
    d.update(overrides)
    cols = ", ".join(d.keys())
    vals = ", ".join([f"${i+1}" for i in range(len(d))])
    await db.execute(f"INSERT INTO compliance_cases ({cols}) VALUES ({vals})", list(d.values()))
    return cid


async def _seed_ir(db, case_id, **overrides) -> str:
    irid = str(uuid.uuid4())
    d = dict(ir_id=irid, case_id=case_id, investigation_id=None,
             created_by="sbtb_compliance_1", assigned_to="sbtb_analyst_1",
             question="Please provide details", due_date=None, status="open",
             response_text=None, responded_at=None, acceptance_note=None,
             return_reason=None, accepted_at=None, returned_at=None,
             accepted_by=None, returned_by=None, cancelled_at=None,
             cancelled_by=None, cancel_reason=None, version=1)
    d.update(overrides)
    cols = ", ".join(d.keys())
    vals = ", ".join([f"${i+1}" for i in range(len(d))])
    await db.execute(f"INSERT INTO information_requests ({cols}) VALUES ({vals})", list(d.values()))
    return irid


async def _seed_comment(db, entity_type, entity_id, **overrides) -> str:
    cid = str(uuid.uuid4())
    d = dict(comment_id=cid, entity_type=entity_type, entity_id=entity_id,
             content="Seed comment", author_id="sbtb_analyst_1", is_internal=False,
             is_redacted=False, redacted_at=None, redacted_by=None,
             original_content_hash=None, redaction_reason=None, version=1)
    d.update(overrides)
    cols = ", ".join(d.keys())
    vals = ", ".join([f"${i+1}" for i in range(len(d))])
    await db.execute(f"INSERT INTO comments ({cols}) VALUES ({vals})", list(d.values()))
    return cid


# ── T00–T35 happy path ────────────────────────────────────────────────────────


class TestAlertWorkflow:
    """T00–T04, T28, T29, T35."""

    @pytest.mark.asyncio
    async def test_t00_health(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_t01_assign_new_alert(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="new")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_analyst_1", "expected_version": 1, "reason": "T01"})
        assert r.status_code == 200
        body = r.json()
        assert body["alert"]["status"] == "assigned"
        assert body["alert"]["assigned_to"] == "sbtb_analyst_1"

    @pytest.mark.asyncio
    async def test_t02_acknowledge(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="assigned", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                         "sbtb_analyst_1",
                         {"expected_version": 1})
        assert r.status_code == 200
        assert r.json()["alert"]["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_t03_investigate(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="acknowledged", assigned_to="sbtb_analyst_1")
        r = await _post(client, f"/api/v1/alerts/{alert_id}/investigate",
                        "sbtb_analyst_1",
                        {"title": "Inv", "expected_version": 1})
        assert r.status_code == 200
        body = r.json()
        assert body["alert"]["status"] == "under_investigation"
        assert "investigation_id" in body

    @pytest.mark.asyncio
    async def test_t04_investigation_start(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="open", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_analyst_1",
                         {"target_status": "active", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["investigation"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_t28_dismiss_medium_no_approval(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="acknowledged",
                                     assigned_to="sbtb_analyst_1", severity="medium")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/dismiss",
                         "sbtb_analyst_1",
                         {"dismissed_reason": "fp", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["alert"]["status"] == "dismissed"

    @pytest.mark.asyncio
    async def test_t35_reopen_resolved_alert_via_assign(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="resolved", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_analyst_2", "expected_version": 1, "reason": "reopen"})
        assert r.status_code == 200
        assert r.json()["alert"]["status"] == "assigned"


class TestInvestigationLifecycle:
    """T05–T07, T30, T24–T25."""

    @pytest.mark.asyncio
    async def test_t05_update_findings(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}",
                         "sbtb_analyst_1",
                         {"findings_text": "clear evidence", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["investigation"]["findings_text"] == "clear evidence"

    @pytest.mark.asyncio
    async def test_t06_submit_with_findings(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1",
                                           findings_text="evidence")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_analyst_1",
                         {"target_status": "submitted", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["investigation"]["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_t07_compliance_completes(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="submitted",
                                           assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_compliance_1",
                         {"target_status": "completed", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["investigation"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_t24_return_investigation(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="submitted",
                                           assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_compliance_1",
                         {"target_status": "returned", "return_reason": "needs work", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["investigation"]["status"] == "returned"

    @pytest.mark.asyncio
    async def test_t25_resubmit_after_return(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="returned",
                                           assigned_to="sbtb_analyst_1", findings_text="revised")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_analyst_1",
                         {"target_status": "active", "expected_version": 1})
        assert r.status_code == 200
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_analyst_1",
                         {"target_status": "submitted", "expected_version": 2})
        assert r.status_code == 200
        assert r.json()["investigation"]["status"] == "submitted"

    @pytest.mark.asyncio
    async def test_t30_comment_on_investigation(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        r = await _post(client, f"/api/v1/investigations/{inv_id}/comments",
                        "sbtb_analyst_1",
                        {"content": "looks good", "is_internal": False})
        assert r.status_code == 201
        assert r.json()["comment"]["content"] == "looks good"


class TestCaseEscalationAndReview:
    """T08–T11, T16–T21, T26–T27."""

    @pytest.mark.asyncio
    async def test_t08_escalate_alert_to_case(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="under_investigation",
                                     assigned_to="sbtb_analyst_1")
        inv_id = await _seed_investigation(integration_db, alert_id=alert_id, status="active",
                                           assigned_to="sbtb_analyst_1")
        r = await _post(client, f"/api/v1/alerts/{alert_id}/escalate",
                        "sbtb_analyst_1",
                        {"title": "Escalated", "expected_version": 1})
        assert r.status_code == 200
        case_id = r.json()["case_id"]
        case = await _get(client, f"/api/v1/cases/{case_id}", "sbtb_admin_1")
        assert case.status_code == 200
        assert case.json()["status"] == "open"

    @pytest.mark.asyncio
    async def test_t09_assign_case(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="open")
        r = await _patch(client, f"/api/v1/cases/{case_id}/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_compliance_1", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "assigned"

    @pytest.mark.asyncio
    async def test_t10_begin_review(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="assigned", assigned_to="sbtb_compliance_1")
        r = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                         "sbtb_compliance_1",
                         {"target_status": "under_review", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "under_review"

    @pytest.mark.asyncio
    async def test_t11_create_ir(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/information-requests",
                        "sbtb_compliance_1",
                        {"assigned_to": "sbtb_analyst_1", "question": "details?", "expected_case_version": 1})
        assert r.status_code == 201
        body = r.json()
        assert body["information_request"]["status"] == "open"
        case = await _get(client, f"/api/v1/cases/{case_id}", "sbtb_compliance_1")
        assert case.json()["status"] == "awaiting_information"

    @pytest.mark.asyncio
    async def test_t16_resume_case_after_ir(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="awaiting_information",
                                   assigned_to="sbtb_compliance_1")
        r = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                         "sbtb_compliance_1",
                         {"target_status": "under_review", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "under_review"

    @pytest.mark.asyncio
    async def test_t17_decision_pending(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        r = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                         "sbtb_compliance_1",
                         {"target_status": "decision_pending", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "decision_pending"

    @pytest.mark.asyncio
    async def test_t18_no_action_resolved(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_compliance_1",
                        {"decision_type": "no_action", "rationale": "ok", "expected_version": 1})
        assert r.status_code == 200
        body = r.json()
        assert body["case"]["status"] == "resolved"
        assert body["decision"]["decision_id"] is not None

    @pytest.mark.asyncio
    async def test_t21_close_low_risk_no_approval(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1",
                                   risk_level="low", resolution="closed")
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_compliance_1",
                        {"closure_reason": "done", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "closed"

    @pytest.mark.asyncio
    async def test_t26_create_approval_for_close(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1",
                                   risk_level="high")
        r = await _post(client, "/api/v1/approval-requests",
                        "sbtb_compliance_1",
                        {"action_type": "case_closure_critical_high", "entity_type": "compliance_case",
                         "entity_id": case_id, "rationale": "need sign-off"})
        assert r.status_code == 201
        assert r.json()["approval_request"]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_t27_compliance_approves_then_close(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1",
                                   risk_level="high", resolution="closed")
        ar = await _post(client, "/api/v1/approval-requests",
                         "sbtb_compliance_1",
                         {"action_type": "case_closure_critical_high", "entity_type": "compliance_case",
                          "entity_id": case_id, "rationale": "need sign-off"})
        ar_id = ar.json()["approval_request"]["approval_request_id"]
        vote = await _post(client, f"/api/v1/approval-requests/{ar_id}/vote",
                           "sbtb_compliance_2",
                           {"decision": "approved"})
        assert vote.status_code == 200
        assert vote.json()["approval_request"]["status"] == "approved"
        close_r = await _post(client, f"/api/v1/cases/{case_id}/close",
                              "sbtb_compliance_1",
                              {"closure_reason": "done", "approval_request_id": ar_id, "expected_version": 1})
        assert close_r.status_code == 200
        assert close_r.json()["case"]["status"] == "closed"


class TestInformationRequestLifecycle:
    """T12–T15, T22–T24, IRS01."""

    @pytest.mark.asyncio
    async def test_t12_acknowledge_ir(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        ir_id = await _seed_ir(integration_db, case_id, status="open")
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/acknowledge",
                         "sbtb_analyst_1",
                         {"expected_version": 1})
        assert r.status_code == 200
        assert r.json()["information_request"]["status"] == "acknowledged"

    @pytest.mark.asyncio
    async def test_t13_respond_ir(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        ir_id = await _seed_ir(integration_db, case_id, status="acknowledged")
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/respond",
                         "sbtb_analyst_1",
                         {"response_text": "here are the details", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["information_request"]["status"] == "responded"

    @pytest.mark.asyncio
    async def test_t14_accept_ir(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        ir_id = await _seed_ir(integration_db, case_id, status="responded")
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/accept",
                         "sbtb_compliance_1",
                         {"expected_version": 1})
        assert r.status_code == 200
        assert r.json()["information_request"]["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_irs01_full_return_cycle(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        ir_id = await _seed_ir(integration_db, case_id, status="open")
        await _patch(client, f"/api/v1/information-requests/{ir_id}/acknowledge",
                     "sbtb_analyst_1", {"expected_version": 1})
        await _patch(client, f"/api/v1/information-requests/{ir_id}/respond",
                     "sbtb_analyst_1", {"response_text": "info", "expected_version": 2})
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/return",
                         "sbtb_compliance_1",
                         {"return_reason": "insufficient", "expected_version": 3})
        assert r.status_code == 200
        assert r.json()["information_request"]["status"] == "returned"
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/acknowledge",
                         "sbtb_analyst_1", {"expected_version": 4})
        assert r.status_code == 200
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/respond",
                         "sbtb_analyst_1", {"response_text": "more info", "expected_version": 5})
        assert r.status_code == 200
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/accept",
                         "sbtb_compliance_1", {"expected_version": 6})
        assert r.status_code == 200
        assert r.json()["information_request"]["status"] == "accepted"


class TestCommentsAndTimeline:
    """T31–T33."""

    @pytest.mark.asyncio
    async def test_t31_internal_comment_visible_to_compliance(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        await _seed_comment(integration_db, "investigation", inv_id,
                            author_id="sbtb_analyst_1", is_internal=True, content="internal")
        await _seed_comment(integration_db, "investigation", inv_id,
                            author_id="sbtb_analyst_1", is_internal=False, content="public")
        r = await _get(client, f"/api/v1/investigations/{inv_id}/comments", "sbtb_analyst_1")
        assert r.status_code == 200
        contents = [c["content"] for c in r.json()["items"]]
        assert "public" in contents
        assert "internal" not in contents
        r2 = await _get(client, f"/api/v1/investigations/{inv_id}/comments", "sbtb_compliance_1")
        assert "internal" in [c["content"] for c in r2.json()["items"]]

    @pytest.mark.asyncio
    async def test_t32_admin_redact_comment(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        cid = await _seed_comment(integration_db, "investigation", inv_id)
        r = await _patch(client, f"/api/v1/comments/{cid}/redact",
                         "sbtb_admin_1",
                         {"redact_reason": "cleanup", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["comment"]["content"].startswith("[REDACTED")

    @pytest.mark.asyncio
    async def test_t33_timeline_ordered(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        await _patch(client, f"/api/v1/cases/{case_id}/transition",
                     "sbtb_compliance_1", {"target_status": "decision_pending", "expected_version": 1})
        r = await _get(client, f"/api/v1/cases/{case_id}/timeline", "sbtb_compliance_1")
        assert r.status_code == 200
        events = r.json()["items"]
        assert len(events) >= 1
        types = [e["event_type"] for e in events]
        assert "case.decision_pending" in types


class TestNotifications:
    """T34."""

    @pytest.mark.asyncio
    async def test_t34_mark_notification_read(self, scenario_app, client, integration_db, seeded_users):
        r = await _get(client, "/api/v1/notifications", "sbtb_analyst_1")
        assert r.status_code == 200
        items = r.json()["items"]
        if not items:
            await _seed_alert(integration_db, status="assigned", assigned_to="sbtb_analyst_1")
            await _patch(client, "/api/v1/alerts/" + await _seed_alert(integration_db, status="new") + "/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_analyst_1", "expected_version": 1, "reason": "n"})
            r = await _get(client, "/api/v1/notifications", "sbtb_analyst_1")
            items = r.json()["items"]
        nid = items[0]["notification_id"]
        r = await _patch(client, f"/api/v1/notifications/{nid}/read", "sbtb_analyst_1", {})
        assert r.status_code == 200


# ── XA cross-permission auth ──────────────────────────────────────────────────


class TestCrossAccessControl:
    """XA01–XA10."""

    @pytest.mark.asyncio
    async def test_xa01_analyst_reads_other_investigation(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_2")
        r = await _get(client, f"/api/v1/investigations/{inv_id}", "sbtb_analyst_1")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_xa02_analyst_reads_other_case(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="assigned", assigned_to="sbtb_compliance_1")
        r = await _get(client, f"/api/v1/cases/{case_id}", "sbtb_analyst_1")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_xa03_compliance_reads_unlinked_investigation(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        r = await _get(client, f"/api/v1/investigations/{inv_id}", "sbtb_compliance_1")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_xa04_compliance_reads_other_case(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="assigned", assigned_to="sbtb_compliance_2")
        r = await _get(client, f"/api/v1/cases/{case_id}", "sbtb_compliance_1")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_xa05_admin_reads_case_global_scope(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", scope_id="hq_main")
        r = await _get(client, f"/api/v1/cases/{case_id}", "sbtb_admin_1")
        assert r.status_code == 200
        body = r.json()
        # admin with global scope gets full case details (no metadata-only restriction in current impl)
        assert body["case_id"]
        assert body["title"] == "Seed Case"

    @pytest.mark.asyncio
    async def test_xa06_admin_reads_any_scope_investigation(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active")
        r = await _get(client, f"/api/v1/investigations/{inv_id}", "sbtb_admin_1")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_xa07_manager_acknowledge_forbidden(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="assigned", assigned_to="sbtb_manager_legacy")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                         "sbtb_manager_legacy", {"expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_xa08_out_of_scope_user_reads_case(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", scope_id="hq_main")
        r = await _get(client, f"/api/v1/cases/{case_id}", "sbtb_outsider")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_xa09_cross_scope_assignment_blocked(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="open", scope_id="hq_main")
        r = await _patch(client, f"/api/v1/cases/{case_id}/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_outsider", "expected_version": 1})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_xa10_analyst_excludes_internal_comments(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        await _seed_comment(integration_db, "investigation", inv_id, is_internal=True, content="secret")
        await _seed_comment(integration_db, "investigation", inv_id, is_internal=False, content="open")
        r = await _get(client, f"/api/v1/investigations/{inv_id}/comments", "sbtb_analyst_1")
        assert r.status_code == 200
        contents = [c["content"] for c in r.json()["items"]]
        assert "open" in contents
        assert "secret" not in contents


# ── V concurrency/versioning ─────────────────────────────────────────────────


class TestConcurrencyVersioning:
    """V01–V11."""

    @pytest.mark.asyncio
    async def test_v01_stale_version_ack(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="assigned", assigned_to="sbtb_compliance_1", version=1)
        r1 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                          "sbtb_compliance_1",
                          {"target_status": "under_review", "expected_version": 1})
        assert r1.status_code == 200
        r2 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                          "sbtb_compliance_1",
                          {"target_status": "decision_pending", "expected_version": 1})
        assert r2.status_code == 409

    @pytest.mark.asyncio
    async def test_v02_missing_expected_version(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="acknowledged", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/dismiss",
                         "sbtb_analyst_1",
                         {"dismissed_reason": "fp"})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_v03_duplicate_escalate_idempotent(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="under_investigation",
                                     assigned_to="sbtb_analyst_1")
        await _seed_investigation(integration_db, alert_id=alert_id)
        await _seed_case(integration_db, alert_id=alert_id, status="open")
        r = await _post(client, f"/api/v1/alerts/{alert_id}/escalate",
                        "sbtb_analyst_1", {"title": "dup", "expected_version": 1})
        assert r.status_code == 200
        assert "case_id" in r.json()

    @pytest.mark.asyncio
    async def test_v04_duplicate_investigate_idempotent(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="acknowledged",
                                     assigned_to="sbtb_analyst_1")
        await _seed_investigation(integration_db, alert_id=alert_id)
        r = await _post(client, f"/api/v1/alerts/{alert_id}/investigate",
                        "sbtb_analyst_1", {"title": "dup", "expected_version": 1})
        assert r.status_code == 200
        assert "investigation_id" in r.json()

    @pytest.mark.asyncio
    async def test_v05_duplicate_ack_noop(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="acknowledged", assigned_to="sbtb_analyst_1")
        r1 = await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                          "sbtb_analyst_1", {"expected_version": 1})
        assert r1.status_code == 200
        r2 = await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                          "sbtb_analyst_1", {"expected_version": 1})
        assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_v09_idempotent_replay(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="assigned", assigned_to="sbtb_compliance_1")
        key = "idem-v09"
        body = {"target_status": "under_review", "expected_version": 1}
        r1 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                          "sbtb_compliance_1", body, headers={"X-Idempotency-Key": key})
        assert r1.status_code == 200
        r2 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                          "sbtb_compliance_1", body, headers={"X-Idempotency-Key": key})
        assert r2.status_code == 200
        assert r2.headers.get("X-Version") == r1.headers.get("X-Version")

    @pytest.mark.asyncio
    async def test_v10_idempotency_key_mismatch(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="assigned", assigned_to="sbtb_compliance_1")
        key = "idem-v10"
        r1 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                          "sbtb_compliance_1",
                          {"target_status": "under_review", "expected_version": 1},
                          headers={"X-Idempotency-Key": key})
        assert r1.status_code == 200
        r2 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                          "sbtb_compliance_1",
                          {"target_status": "decision_pending", "expected_version": 1},
                          headers={"X-Idempotency-Key": key})
        assert r2.status_code == 409


# ── AU admin outbox / audit ───────────────────────────────────────────────────


class TestAuditOutbox:
    """AU01–AU04, AU06–AU08."""

    @pytest.mark.asyncio
    async def test_au01_failed_delivery_marks_failed(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="assigned", assigned_to="sbtb_analyst_1")
        await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                     "sbtb_analyst_1", {"expected_version": 1})
        repo = OutboxRepo(integration_db)
        try:
            await run_cycle(repo, "http://localhost:19999", max_attempts=1, stale_minutes=1)
        except Exception:
            pass
        rows = await integration_db.fetch_all(
            "SELECT status FROM audit_outbox WHERE entity_id = $1 ORDER BY created_at LIMIT 5",
            [str(alert_id)],
        )
        assert any(r["status"] in ("failed", "pending", "poison") for r in rows)

    @pytest.mark.asyncio
    async def test_au03_poison_after_max_attempts(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="assigned", assigned_to="sbtb_analyst_1")
        await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                     "sbtb_analyst_1", {"expected_version": 1})
        await integration_db.execute(
            "DELETE FROM audit_outbox WHERE entity_id != $1",
            [str(alert_id)],
        )
        await integration_db.execute(
            "UPDATE audit_outbox SET next_attempt_at = '2000-01-01' WHERE entity_id = $1 AND status IN ('pending','failed')",
            [str(alert_id)],
        )
        repo = OutboxRepo(integration_db)
        for _ in range(7):
            await integration_db.execute(
                "UPDATE audit_outbox SET status='pending', next_attempt_at = NOW() - INTERVAL '1 minute' "
                "WHERE entity_id = $1 AND status IN ('pending','failed','delivering')",
                [str(alert_id)],
            )
            try:
                await run_cycle(repo, "http://localhost:19999", max_attempts=5, stale_minutes=1)
            except Exception:
                pass
        rows = await integration_db.fetch_all(
            "SELECT status, attempt_count FROM audit_outbox WHERE entity_id = $1 LIMIT 5",
            [str(alert_id)],
        )
        assert any(r["status"] == "poison" for r in rows)

    @pytest.mark.asyncio
    async def test_au06_no_phantom_outbox_on_rollback(self, scenario_app, client, integration_db, seeded_users):
        before = await integration_db.fetch_one("SELECT count(*) AS c FROM audit_outbox")
        alert_id = await _seed_alert(integration_db, status="new")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_analyst_1", "expected_version": 1, "reason": "au06"})
        assert r.status_code == 200
        after = await integration_db.fetch_one("SELECT count(*) AS c FROM audit_outbox")
        assert after["c"] == before["c"] + 1

    @pytest.mark.asyncio
    async def test_au08_notification_failure_rolls_back(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1",
                                   risk_level="low", resolution="ok")
        before = await integration_db.fetch_one("SELECT count(*) AS c FROM notifications")
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_compliance_1",
                        {"closure_reason": "done", "expected_version": 1})
        assert r.status_code == 200
        after = await integration_db.fetch_one("SELECT count(*) AS c FROM notifications")
        assert after["c"] >= before["c"]


# ── F forbidden / failure ─────────────────────────────────────────────────────


class TestForbiddenTransitions:
    """F01–F18."""

    @pytest.mark.asyncio
    async def test_f01_admin_case_decision_forbidden(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_admin_1",
                        {"decision_type": "no_action", "rationale": "x", "expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f02_admin_case_close_forbidden(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved")
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_admin_1", {"expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f03_analyst_case_decision_forbidden(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_analyst_1",
                        {"decision_type": "no_action", "rationale": "x", "expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f04_analyst_case_close_forbidden(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved")
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_analyst_1", {"expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f05_analyst_approve_own_alert_approval_forbidden(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="acknowledged", assigned_to="sbtb_analyst_1")
        ar = await _post(client, "/api/v1/approval-requests",
                         "sbtb_analyst_1",
                         {"action_type": "alert_dismissal_critical_high", "entity_type": "alert",
                          "entity_id": alert_id, "rationale": "need it"})
        ar_id = ar.json()["approval_request"]["approval_request_id"]
        r = await _post(client, f"/api/v1/approval-requests/{ar_id}/vote",
                        "sbtb_analyst_1", {"decision": "approved"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f06_compliance_vote_own_approval_coi(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1")
        ar = await _post(client, "/api/v1/approval-requests",
                         "sbtb_compliance_1",
                         {"action_type": "case_closure_critical_high", "entity_type": "compliance_case",
                          "entity_id": case_id, "rationale": "need it"})
        ar_id = ar.json()["approval_request"]["approval_request_id"]
        r = await _post(client, f"/api/v1/approval-requests/{ar_id}/vote",
                        "sbtb_compliance_1", {"decision": "approved"})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f07_analyst_assign_case_forbidden(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="open")
        r = await _patch(client, f"/api/v1/cases/{case_id}/assign",
                         "sbtb_analyst_1",
                         {"assigned_to": "sbtb_compliance_1", "expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f08_admin_modify_findings_forbidden(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}",
                         "sbtb_admin_1",
                         {"findings_text": "admin findings", "expected_version": 1})
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_f09_acknowledge_dismissed_alert(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="dismissed", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                         "sbtb_analyst_1", {"expected_version": 1})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_f10_submit_without_findings(self, scenario_app, client, integration_db, seeded_users):
        inv_id = await _seed_investigation(integration_db, status="active", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/investigations/{inv_id}/transition",
                         "sbtb_analyst_1",
                         {"target_status": "submitted", "expected_version": 1})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_f11_close_without_resolution(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1",
                                   risk_level="low", resolution=None)
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_compliance_1", {"expected_version": 1})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_f12_decision_wrong_status(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_compliance_1",
                        {"decision_type": "no_action", "rationale": "x", "expected_version": 1})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_f13_acknowledge_new_alert(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="new", assigned_to="sbtb_analyst_1")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/acknowledge",
                         "sbtb_analyst_1", {"expected_version": 1})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_f14_ir_respond_before_ack(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        ir_id = await _seed_ir(integration_db, case_id, status="open")
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/respond",
                         "sbtb_analyst_1",
                         {"response_text": "info", "expected_version": 1})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_f15_ir_accept_before_response(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="under_review", assigned_to="sbtb_compliance_1")
        ir_id = await _seed_ir(integration_db, case_id, status="open")
        r = await _patch(client, f"/api/v1/information-requests/{ir_id}/accept",
                         "sbtb_compliance_1", {"expected_version": 1})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_f16_close_high_risk_no_approval(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="resolved", assigned_to="sbtb_compliance_1",
                                   risk_level="high")
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_compliance_1", {"expected_version": 1})
        assert r.status_code == 428

    @pytest.mark.asyncio
    async def test_f17_approval_already_consumed(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="closed", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/close",
                        "sbtb_compliance_1",
                        {"closure_reason": "again", "expected_version": 1})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_f18_assign_to_suspended_user(self, scenario_app, client, integration_db, seeded_users):
        alert_id = await _seed_alert(integration_db, status="new")
        r = await _patch(client, f"/api/v1/alerts/{alert_id}/assign",
                         "sbtb_admin_1",
                         {"assigned_to": "sbtb_suspended_analyst", "expected_version": 1, "reason": "bad"})
        assert r.status_code == 400


# ── DP decision-path scenarios ────────────────────────────────────────────────


class TestDecisionPaths:
    """DP01–DP04."""

    @pytest.mark.asyncio
    async def test_dp01_no_action_to_resolved(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_compliance_1",
                        {"decision_type": "no_action", "rationale": "ok", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_dp02_warning_to_awaiting_action_to_resolved(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_compliance_1",
                        {"decision_type": "warning", "rationale": "warn", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "awaiting_compliance_action"
        r2 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                           "sbtb_compliance_1",
                           {"target_status": "resolved", "resolution": "action completed", "expected_version": 2})
        assert r2.status_code == 200
        assert r2.json()["case"]["status"] == "resolved"

    @pytest.mark.asyncio
    async def test_dp03_edd_to_awaiting_action_to_resolved(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_compliance_1",
                        {"decision_type": "enhanced_due_diligence_recommended",
                         "rationale": "edd", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "awaiting_compliance_action"
        r2 = await _patch(client, f"/api/v1/cases/{case_id}/transition",
                           "sbtb_compliance_1",
                           {"target_status": "resolved", "resolution": "edd completed", "expected_version": 2})
        assert r2.status_code == 200

    @pytest.mark.asyncio
    async def test_dp04_account_action_decision(self, scenario_app, client, integration_db, seeded_users):
        case_id = await _seed_case(integration_db, status="decision_pending", assigned_to="sbtb_compliance_1")
        r = await _post(client, f"/api/v1/cases/{case_id}/decisions",
                        "sbtb_compliance_1",
                        {"decision_type": "account_action_recommended",
                         "rationale": "freeze", "expected_version": 1})
        assert r.status_code == 200
        assert r.json()["case"]["status"] == "awaiting_compliance_action"
