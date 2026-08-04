"""HTTP-level regression tests for the Workbench HTTP Contract Remediation (Defects A/B/C).

Drives real HTTP requests against the deployed Workbench service (port 8014)
using X-Test-User identity injection. Asserts that:
  - every mutation route returns valid JSON with ISO-8601 datetimes (no 500)
  - admin alert detail dispatches the restricted DTO (no title/updated_at leak)
  - the admin orphan endpoint is mounted, reachable, and permission-gated
  - idempotency replay returns an identical serialised body and body-mismatch
    yields the canonical 409

All tests operate on the canonical Phase 2B demo dataset; no new workflow
entities are inserted, so re-runs are safe after the session-scoped cleanup.
"""
from datetime import datetime

import httpx
import psycopg2
import pytest

WORKBENCH_URL = "http://localhost:8014"

# Canonical demo IDs from scripts/seed_canonical_demo.sql.
A1 = "11111111-1111-4111-8111-111111111111"
A2 = "22222222-2222-4222-8222-222222222222"
A3 = "33333333-3333-4333-8333-333333333333"
C1 = "bbbbbbbb-1111-4111-8111-111111111111"
I1 = "aaaaaaaa-1111-4111-8111-111111111111"
IR2 = "cccccccc-2222-4222-8222-222222222222"
NOTIF1 = "eeeeeeee-1111-4111-8111-111111111111"


def _db():
    import os
    url = os.environ.get(
        "INTEGRATION_DATABASE_URL",
        "postgresql://integration_user:integrationpass123@localhost:5435/banking_integration",
    )
    return psycopg2.connect(url)


def _headers(user):
    return {"X-Test-User": user}


def _iso(s):
    try:
        datetime.fromisoformat(s.replace("Z", "+00:00"))
        return True
    except Exception:
        return False


def _assert_iso_body(body, *keys):
    for k in keys:
        val = body[k]
        assert isinstance(val, str), f"{k} is {type(val)} not str"
        assert _iso(val), f"{k}={val!r} is not ISO-8601"


def _db_version(table, col, id_val):
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT version FROM {table} WHERE {col}=%s", [id_val])
            row = cur.fetchone()
            return row[0] if row else None


# ── session-scoped cleanup: restore canonical state before tests run ─────────


@pytest.fixture(scope="session", autouse=True)
def _reset_canonical_state():
    conn = _db()
    cur = conn.cursor()
    # A2 approval: delete any non-canonical requests for A2 + dismiss action.
    cur.execute(
        "DELETE FROM approval_decisions WHERE approval_request_id IN "
        "(SELECT approval_request_id FROM approval_requests "
        " WHERE entity_id=%s AND action_type='alert_dismissal_critical_high' "
        " AND approval_request_id != 'dddddddd-1111-4111-8111-111111111111')",
        [A2],
    )
    cur.execute(
        "DELETE FROM approval_requests WHERE entity_id=%s AND action_type='alert_dismissal_critical_high' "
        "AND approval_request_id != 'dddddddd-1111-4111-8111-111111111111'",
        [A2],
    )
    # C1 case: reset to assigned v1.
    cur.execute(
        "UPDATE compliance_cases SET status='assigned', version=1, updated_at=now() "
        "WHERE case_id=%s", [C1])
    # I1 investigation: reset findings_text/conclusion/version.
    cur.execute(
        "UPDATE investigations SET findings_text='Preliminary evidence points to queue backlog in the KYB step.', "
        "conclusion=NULL, version=1, updated_at=now() "
        "WHERE investigation_id=%s", [I1])
    # IR2: reset to acknowledged v1.
    cur.execute(
        "UPDATE information_requests SET status='acknowledged', response_text=NULL, responded_at=NULL, "
        "version=1, updated_at=now() WHERE ir_id=%s", [IR2])
    # Comment on A1: delete our test comment.
    cur.execute(
        "DELETE FROM comments WHERE entity_id=%s AND author_id='analyst_001' "
        "AND content LIKE '%%HTTP remediation test comment%%'", [A1])
    # Notification N1: reset is_read.
    cur.execute(
        "UPDATE notifications SET is_read=false, read_at=NULL WHERE notification_id=%s", [NOTIF1])
    conn.commit()
    cur.close()
    conn.close()


# ── liveness gate ─────────────────────────────────────────────────────────────


class TestLiveness:
    def test_workbench_health(self):
        r = httpx.get(f"{WORKBENCH_URL}/health", timeout=5)
        assert r.status_code == 200


# ── Part 1: mutation serialization (Defect B) ─────────────────────────────────


class TestAlertMutationSerialization:
    def test_analyst_acknowledge_already_acknowledged_returns_200_and_valid_json(self):
        """A3 is already acknowledged; acknowledge must serialise cleanly (was 500)."""
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.patch(
                f"/api/v1/alerts/{A3}/acknowledge",
                headers=_headers("analyst_001"),
                json={"expected_version": 999},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        alert = body["alert"]
        assert alert["alert_id"] == A3
        assert alert["status"] == "acknowledged"
        _assert_iso_body(alert, "created_at", "updated_at")
        assert isinstance(body["version"], int)


class TestCaseMutationSerialization:
    def test_compliance_transition_case_under_review(self):
        v_before = _db_version("compliance_cases", "case_id", C1)
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.patch(
                f"/api/v1/cases/{C1}/transition",
                headers=_headers("compliance_001"),
                json={"target_status": "under_review", "expected_version": v_before},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        case = body["case"]
        assert case["status"] == "under_review"
        assert case["case_id"] == C1
        assert body["version"] == v_before + 1
        _assert_iso_body(case, "created_at", "updated_at")


class TestInvestigationMutationSerialization:
    def test_analyst_update_findings(self):
        v_before = _db_version("investigations", "investigation_id", I1)
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.patch(
                f"/api/v1/investigations/{I1}",
                headers=_headers("analyst_001"),
                json={"findings_text": "Updated findings", "expected_version": v_before},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        inv = body["investigation"]
        assert inv["investigation_id"] == I1
        assert body["version"] == v_before + 1
        _assert_iso_body(inv, "created_at", "updated_at")


class TestApprovalMutationSerialization:
    def test_analyst_create_approval_request_201_and_compliance_votes_approved(self):
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.post(
                "/api/v1/approval-requests",
                headers=_headers("analyst_001"),
                json={
                    "action_type": "alert_dismissal_critical_high",
                    "entity_type": "alert",
                    "entity_id": A2,
                    "rationale": "False positive confirmed after ledger reconciliation.",
                },
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["success"] is True
        assert body["version"] == 1
        ar = body["approval_request"]
        assert ar["status"] == "pending"
        assert ar["requested_by"] == "analyst_001"
        _assert_iso_body(ar, "created_at")
        approval_id = ar["approval_request_id"]

        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.post(
                f"/api/v1/approval-requests/{approval_id}/vote",
                headers=_headers("compliance_001"),
                json={"decision": "approved", "rationale": "Confirmed false positive."},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        ar = body["approval_request"]
        assert ar["status"] == "approved"
        assert ar["approval_count"] >= 1
        decisions = ar.get("decisions", [])
        assert any(d["approver_id"] == "compliance_001" and d["decision"] == "approved"
                   for d in decisions)


class TestInformationRequestMutationSerialization:
    def test_analyst_respond_ir(self):
        v_before = _db_version("information_requests", "ir_id", IR2)
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.patch(
                f"/api/v1/information-requests/{IR2}/respond",
                headers=_headers("analyst_001"),
                json={"response_text": "Rationale documented in case file.",
                      "expected_version": v_before},
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        ir = body["information_request"]
        assert ir["status"] == "responded"
        assert body["version"] == v_before + 1
        _assert_iso_body(ir, "responded_at")


class TestNotificationMutationSerialization:
    def test_analyst_mark_read(self):
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.patch(
                f"/api/v1/notifications/{NOTIF1}/read",
                headers=_headers("analyst_001"),
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["success"] is True
        n = body["notification"]
        assert n["is_read"] is True


class TestCommentMutationSerialization:
    def test_analyst_create_comment(self):
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.post(
                f"/api/v1/alerts/{A1}/comments",
                headers=_headers("analyst_001"),
                json={"content": "HTTP remediation test comment", "is_internal": False},
            )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["success"] is True
        assert body["version"] == 1
        cmt = body["comment"]
        assert cmt["entity_type"] == "alert"
        assert cmt["entity_id"] == A1
        assert cmt["author_id"] == "analyst_001"


# ── Part 2: admin alert response contract (Defect A) ─────────────────────────


class TestAdminAlertContract:
    def test_analyst_gets_full_view(self):
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.get(f"/api/v1/alerts/{A1}", headers=_headers("analyst_001"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "title" in body
        assert "updated_at" in body
        assert body["alert_id"] == A1

    def test_admin_gets_restricted_view(self):
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.get(f"/api/v1/alerts/{A1}", headers=_headers("admin_001"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "title" not in body
        assert "updated_at" not in body
        assert body["alert_id"] == A1
        assert body["alert_type"] == "kpi_breach"
        assert body["scope_id"] == "hq_main"
        assert "version" in body


# ── Part 3: admin orphan mount (Defect C) ────────────────────────────────────


class TestAdminOrphanMount:
    def test_route_in_openapi(self):
        r = httpx.get(f"{WORKBENCH_URL}/openapi.json", timeout=10)
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert "/api/v1/admin/orphan-assignments" in paths

    def test_admin_sees_results(self):
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r = c.get("/api/v1/admin/orphan-assignments", headers=_headers("admin_001"))
        assert r.status_code == 200, r.text
        body = r.json()
        assert "alerts" in body
        assert "investigations" in body
        assert "cases" in body

    def test_non_admin_denied(self):
        for user in ("analyst_001", "compliance_001"):
            with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
                r = c.get("/api/v1/admin/orphan-assignments", headers=_headers(user))
            assert r.status_code == 403, f"{user} got {r.status_code}: {r.text}"


# ── Idempotency replay (Part 4 requirement) ──────────────────────────────────


class TestIdempotencyReplay:
    KEY = "http:remediation:idem:i1:v1"

    def test_idempotency_fresh_replay_mismatch(self):
        v0 = _db_version("investigations", "investigation_id", I1)
        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r1 = c.patch(
                f"/api/v1/investigations/{I1}",
                headers={**_headers("analyst_001"), "X-Idempotency-Key": self.KEY},
                json={"findings_text": "Idem fresh", "expected_version": v0},
            )
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["success"] is True
        assert body1["version"] == v0 + 1

        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r2 = c.patch(
                f"/api/v1/investigations/{I1}",
                headers={**_headers("analyst_001"), "X-Idempotency-Key": self.KEY},
                json={"findings_text": "Idem fresh", "expected_version": v0},
            )
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2 == body1, f"replay mismatch:\n  fresh={body1}\n  replay={body2}"
        inv = body2["investigation"]
        _assert_iso_body(inv, "created_at", "updated_at")

        with httpx.Client(base_url=WORKBENCH_URL, timeout=10) as c:
            r3 = c.patch(
                f"/api/v1/investigations/{I1}",
                headers={**_headers("analyst_001"), "X-Idempotency-Key": self.KEY},
                json={"findings_text": "Different findings", "expected_version": v0},
            )
        assert r3.status_code == 409, r3.text
        body3 = r3.json()
        assert body3["error"] == "IDEMPOTENCY_MISMATCH"
