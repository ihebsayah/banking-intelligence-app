"""Alert service tests.
"""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser

from workbench.exceptions import (
    ApprovalConsumed, ApprovalRequired, IdempotencyMismatch,
    InvalidAssignee, InvalidTransition, ResourceNotFound, VersionConflict,
)
from workbench.models import Alert, ApprovalRequest, Investigation
from workbench.schemas.alerts import (
    AcknowledgeAlertRequest, AlertResponse, AssignAlertRequest,
    DismissAlertRequest, EscalateAlertRequest, InvestigateAlertRequest,
    MutationResponse,
)
from workbench.services.alert_service import AlertService, _validate_assignee

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

MOCK_USER = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "alert:read_assigned", "alert:acknowledge", "alert:dismiss",
    "alert:investigate", "alert:transition",
])
ADMIN_USER = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "alert:read", "alert:assign",
])
OTHER_USER = ApplicationUser(user_id="user3", role="analyst", permissions=[
    "alert:read_assigned",
])


def make_alert(**kw):
    defaults = dict(alert_id=UID(), alert_type="kpi_breach", severity="high",
                    title="Test Alert", description=None, scope_id="hq_main",
                    status="new", assigned_to=None, version=1,
                    dismissed_reason=None, dismissed_at=None, dismissed_by=None,
                    resolved_at=None, resolved_by=None,
                    dismissal_approval_id=None,
                    source_rule_type=None, source_rule_id=None,
                    related_entity_type=None, related_entity_id=None,
                    created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Alert(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


UOW_TARGET = "workbench.services.alert_service.UnitOfWork"
AUTH_TARGET = "workbench.services.alert_service.authorise"
HASH = lambda body: __import__("hashlib").sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


# ── list_assigned ────────────────────────────────────────────────────────────

class TestListAssigned:
    @pytest.mark.asyncio
    async def test_own_alerts_only(self, mock_db):
        a = make_alert(assigned_to="user1", status="new")
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[a.model_dump()])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await AlertService(mock_db).list_assigned(MOCK_USER, "hq_main")
        assert len(items) == 1
        assert items[0].alert_id == a.alert_id

    @pytest.mark.asyncio
    async def test_filtering(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            await AlertService(mock_db).list_assigned(MOCK_USER, "hq_main", status="new", severity="high")
        assert "assigned_to" in mock_fetch.call_args[0][1]

    @pytest.mark.asyncio
    async def test_pagination(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            await AlertService(mock_db).list_assigned(MOCK_USER, "hq_main", page=2, per_page=10)
        assert "LIMIT" in mock_fetch.call_args[0][1]
        assert "OFFSET" in mock_fetch.call_args[0][1]

    @pytest.mark.asyncio
    async def test_authorise_called(self, mock_db):
        mock_auth = AsyncMock()
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, mock_auth):
            await AlertService(mock_db).list_assigned(MOCK_USER, "hq_main")
        mock_auth.assert_awaited_once()


# ── get_by_id ────────────────────────────────────────────────────────────────

class TestGetById:
    @pytest.mark.asyncio
    async def test_assigned_user_success(self, mock_db):
        a = make_alert(assigned_to="user1", status="assigned")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())), \
             patch(AUTH_TARGET, AsyncMock()):
            result = await AlertService(mock_db).get_by_id(MOCK_USER, a.alert_id)
        assert result.alert_id == a.alert_id

    @pytest.mark.asyncio
    async def test_nonexistent_alert(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await AlertService(mock_db).get_by_id(MOCK_USER, "no-such-id")

    @pytest.mark.asyncio
    async def test_no_permission(self, mock_db):
        a = make_alert(assigned_to="user1", status="assigned")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])):
            with pytest.raises(ResourceNotFound):
                await AlertService(mock_db).get_by_id(OTHER_USER, a.alert_id)


# ── assign ───────────────────────────────────────────────────────────────────

class TestAssign:
    @pytest.mark.asyncio
    async def test_assign_new_alert(self, mock_db):
        a = make_alert(status="new")
        req = AssignAlertRequest(assigned_to="user2", expected_version=1, reason="workload")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.services.alert_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await AlertService(mock_db).assign(ADMIN_USER, a.alert_id, req)
        assert result.alert.status == "assigned"

    @pytest.mark.asyncio
    async def test_no_alert_raises(self, mock_db):
        req = AssignAlertRequest(assigned_to="user2", expected_version=1, reason="workload")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await AlertService(mock_db).assign(ADMIN_USER, "bad-id", req)


# ── acknowledge ──────────────────────────────────────────────────────────────

class TestAcknowledge:
    @pytest.mark.asyncio
    async def test_successful_acknowledge(self, mock_db):
        a = make_alert(assigned_to="user1", status="assigned", version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await AlertService(mock_db).acknowledge(MOCK_USER, a.alert_id, 1)
        assert result.alert.status == "acknowledged"

    @pytest.mark.asyncio
    async def test_already_acknowledged_is_idempotent(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            result = await AlertService(mock_db).acknowledge(MOCK_USER, a.alert_id, 2)
        assert result.alert.status == "acknowledged"

    @pytest.mark.asyncio
    async def test_wrong_assignee_raises(self, mock_db):
        a = make_alert(assigned_to="other_user", status="assigned", version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            with pytest.raises(Exception):
                await AlertService(mock_db).acknowledge(MOCK_USER, a.alert_id, 1)

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        a = make_alert(assigned_to="user1", status="assigned", version=1)
        a_dump = a.model_dump()
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 a_dump,  # fetch_by_id in service
                 None,    # fetch_by_id inside update (stale → alert gone)
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await AlertService(mock_db).acknowledge(MOCK_USER, a.alert_id, 1)

    @pytest.mark.asyncio
    async def test_invalid_transition(self, mock_db):
        a = make_alert(assigned_to="user1", status="new", version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            with pytest.raises(InvalidTransition):
                await AlertService(mock_db).acknowledge(MOCK_USER, a.alert_id, 1)


# ── dismiss ──────────────────────────────────────────────────────────────────

class TestDismiss:
    @pytest.mark.asyncio
    async def test_dismiss_acknowledged_low_severity(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", severity="low", version=1)
        req = DismissAlertRequest(dismissed_reason="false positive", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await AlertService(mock_db).dismiss(MOCK_USER, a.alert_id, req)
        assert result.alert.status == "dismissed"

    @pytest.mark.asyncio
    async def test_critical_requires_approval(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", severity="critical", version=1)
        req = DismissAlertRequest(dismissed_reason="test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            with pytest.raises(ApprovalRequired):
                await AlertService(mock_db).dismiss(MOCK_USER, a.alert_id, req)

    @pytest.mark.asyncio
    async def test_consumed_approval_rejected(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", severity="critical", version=1)
        req = DismissAlertRequest(dismissed_reason="test", expected_version=1,
                                  approval_request_id=UID())
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id",
                   AsyncMock(return_value=ApprovalRequest(
                       approval_request_id=req.approval_request_id,
                       action_type="alert_dismissal_critical_high",
                       entity_type="alert", entity_id=a.alert_id,
                       requested_by="user1", rationale="test",
                       status="approved", expires_at=NOW,
                       executed_at=NOW, version=1, created_at=NOW, updated_at=NOW,
                   ))):
            with pytest.raises(ApprovalConsumed):
                await AlertService(mock_db).dismiss(MOCK_USER, a.alert_id, req)

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", severity="low", version=1)
        a_dump = a.model_dump()
        req = DismissAlertRequest(dismissed_reason="test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 a_dump,  # fetch_by_id in service
                 None,    # fetch_by_id inside update (stale → alert gone)
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await AlertService(mock_db).dismiss(MOCK_USER, a.alert_id, req)


# ── investigate ──────────────────────────────────────────────────────────────

class TestInvestigate:
    @pytest.mark.asyncio
    async def test_create_investigation(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", version=1)
        req = InvestigateAlertRequest(title="Investigation", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 a.model_dump(),  # fetch_by_id
                 None,  # no existing inv
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 0 1")):
            result = await AlertService(mock_db).investigate(MOCK_USER, a.alert_id, req)
        assert result.investigation_id is not None

    @pytest.mark.asyncio
    async def test_existing_investigation_returns_idem(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", version=2)
        inv_id = UID()
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 a.model_dump(),
                 dict(investigation_id=inv_id, title="Existing", created_by="user1",
                      scope_id="hq_main", status="open", version=1,
                      alert_id=a.alert_id, description=None,
                      created_at=NOW, updated_at=NOW),
             ])):
            result = await AlertService(mock_db).investigate(
                MOCK_USER, a.alert_id,
                InvestigateAlertRequest(title="New", expected_version=2))
        assert result.investigation_id == inv_id

    @pytest.mark.asyncio
    async def test_wrong_alert_state(self, mock_db):
        a = make_alert(assigned_to="user1", status="new", version=1)
        req = InvestigateAlertRequest(title="Test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            with pytest.raises(InvalidTransition):
                await AlertService(mock_db).investigate(MOCK_USER, a.alert_id, req)


# ── escalate ─────────────────────────────────────────────────────────────────

class TestEscalate:
    @pytest.mark.asyncio
    async def test_create_case(self, mock_db):
        a = make_alert(assigned_to="user1", status="under_investigation", version=2)
        inv_id = UID()
        req = EscalateAlertRequest(title="Escalation", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 a.model_dump(),  # fetch_by_id
                 dict(investigation_id=inv_id, title="Inv", created_by="user1",
                      status="open", scope_id="hq_main", alert_id=a.alert_id,
                      description=None, version=1,
                      created_at=NOW, updated_at=NOW),  # investigation
                 None,  # no existing case
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 0 1")):
            result = await AlertService(mock_db).escalate(MOCK_USER, a.alert_id, req)
        assert result.case_id is not None

    @pytest.mark.asyncio
    async def test_no_investigation_raises(self, mock_db):
        a = make_alert(assigned_to="user1", status="under_investigation", version=2)
        req = EscalateAlertRequest(title="Test", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 a.model_dump(),  # fetch_by_id
                 None,  # no investigation
             ])):
            with pytest.raises(ResourceNotFound):
                await AlertService(mock_db).escalate(MOCK_USER, a.alert_id, req)

    @pytest.mark.asyncio
    async def test_wrong_alert_state(self, mock_db):
        a = make_alert(assigned_to="user1", status="acknowledged", version=1)
        req = EscalateAlertRequest(title="Test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            with pytest.raises(InvalidTransition):
                await AlertService(mock_db).escalate(MOCK_USER, a.alert_id, req)


# ── idempotency ──────────────────────────────────────────────────────────────

class TestIdempotency:
    @pytest.mark.asyncio
    async def test_replay_returns_stored_response(self, mock_db):
        a = make_alert(assigned_to="user1", status="assigned", version=1)
        req = AcknowledgeAlertRequest(expected_version=1)
        fake_resp = MutationResponse(alert=AlertResponse(**a.model_dump()), version=1)
        stored_body = fake_resp.model_dump_json()
        body_hash = HASH({"expected_version": 1})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path=f"/api/v1/alerts/{a.alert_id}/acknowledge",
                 request_body_sha256=body_hash,
                 response_status=200, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await AlertService(mock_db).acknowledge(
                MOCK_USER, a.alert_id, 1, idempotency_key="dup-key")
        assert result.alert.alert_id == a.alert_id

    @pytest.mark.asyncio
    async def test_mismatched_body_raises(self, mock_db):
        other_hash = HASH({"expected_version": 99})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path="/api/v1/alerts/any/acknowledge",
                 request_body_sha256=other_hash,
                 response_status=200, response_body="{}",
                 created_at=NOW,
             ))):
            with pytest.raises(IdempotencyMismatch):
                await AlertService(mock_db).acknowledge(
                    MOCK_USER, "any", 1, idempotency_key="dup-key")


# ── assignee validation ──────────────────────────────────────────────────────

class TestAssigneeValidation:
    @pytest.mark.asyncio
    async def test_suspended_user_rejected(self, mock_db):
        conn_mock = MagicMock()
        mock_db.fetch_one = AsyncMock(return_value={"status": "suspended"})
        with pytest.raises(InvalidAssignee, match="not active"):
            await _validate_assignee(mock_db, "suspended_user", "hq_main", conn_mock)

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, mock_db):
        conn_mock = MagicMock()
        mock_db.fetch_one = AsyncMock(return_value=None)
        with pytest.raises(InvalidAssignee, match="not found"):
            await _validate_assignee(mock_db, "no-such", "hq_main", conn_mock)
