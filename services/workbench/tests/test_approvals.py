"""Approval service tests (AP1-AP4)."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser, ConflictOfInterestError

from workbench.exceptions import (
    IdempotencyMismatch, InvalidTransition, PermissionDenied,
    ResourceNotFound, WorkbenchError,
)
from workbench.models import Alert, ApprovalDecision, ApprovalRequest, ComplianceCase
from workbench.schemas.approvals import (
    ApprovalActionType, ApprovalEntityType,
    ApprovalRequestMutationResponse, CreateApprovalRequest,
    VoteApprovalRequest,
)
from workbench.services.approval_service import ApprovalService

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

ANALYST = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "approval:request", "approval:read",
])
COMPLIANCE = ApplicationUser(user_id="user1", role="compliance", permissions=[
    "approval:request", "approval:approve", "approval:read",
])
OTHER_COMPLIANCE = ApplicationUser(user_id="user2", role="compliance", permissions=[
    "approval:approve", "approval:read",
])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "approval:request", "approval:read",
])


def make_alert(**kw):
    defaults = dict(alert_id=UID(), alert_type="suspicious_transfer",
                    severity="critical", title="Test Alert", description=None,
                    source_rule_type=None, source_rule_id=None,
                    related_entity_type=None, related_entity_id=None,
                    scope_id="hq_main", status="acknowledged",
                    assigned_to="user1", dismissed_reason=None,
                    dismissed_at=None, dismissed_by=None,
                    resolved_at=None, resolved_by=None,
                    dismissal_approval_id=None,
                    version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Alert(**defaults)


def make_case(**kw):
    defaults = dict(case_id=UID(), title="Test Case",
                    description=None, alert_id=None, investigation_id=None,
                    scope_id="hq_main", status="resolved", priority="medium",
                    risk_level="high", regulatory_frameworks=None,
                    assigned_to="user1", created_by="user1",
                    target_date=None, resolution=None, resolved_at=None,
                    resolved_by=None, closed_at=None, closed_by=None,
                    current_disposition_id=None, closure_approval_id=None,
                    reopen_reason=None,
                    version=2, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ComplianceCase(**defaults)


def make_approval(**kw):
    defaults = dict(approval_request_id=UID(), action_type="alert_dismissal_critical_high",
                    entity_type="alert", entity_id=UID(), requested_by="user1",
                    rationale="Needs sign-off", required_approvals=1,
                    approval_count=0, status="pending", expires_at=NOW,
                    executed_at=None, version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ApprovalRequest(**defaults)


def make_decision(**kw):
    defaults = dict(approval_decision_id=UID(), approval_request_id="ar1",
                    approver_id="user2", decision="approved",
                    rationale=None, decided_at=NOW)
    defaults.update(kw)
    return ApprovalDecision(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


UOW_TARGET = "workbench.services.approval_service.UnitOfWork"
AUTH_TARGET = "workbench.services.approval_service.authorise"
HASH = lambda body: __import__("hashlib").sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def replays(key, method, path, body, status, resp):
    return {key: (method, path, HASH(body), status, resp)}


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_alert_dismissal(self, mock_db):
        a = make_alert()
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Confirmed suspicious")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[a.model_dump(), None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.services.approval_service._fetch_eligible_approvers",
                   AsyncMock(return_value=["user2"])):
            result = await ApprovalService(mock_db).create(ANALYST, req)
        assert result.approval_request.status == "pending"
        assert result.approval_request.requested_by == "user1"
        assert result.approval_request.action_type == "alert_dismissal_critical_high"
        assert result.approval_request.required_approvals == 1
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_create_case_closure(self, mock_db):
        c = make_case(status="resolved", risk_level="high")
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.CASE_CLOSURE_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.COMPLIANCE_CASE, entity_id=c.case_id,
            rationale="Closure sign-off")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[c.model_dump(), None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.services.approval_service._fetch_eligible_approvers",
                   AsyncMock(return_value=[])):
            result = await ApprovalService(mock_db).create(COMPLIANCE, req)
        assert result.approval_request.entity_type == "compliance_case"
        assert result.approval_request.status == "pending"

    @pytest.mark.asyncio
    async def test_create_decision_report_requires_payload(self, mock_db):
        c = make_case(status="decision_pending")
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.DECISION_REPORT_TO_AUTHORITY,
            entity_type=ApprovalEntityType.COMPLIANCE_CASE, entity_id=c.case_id,
            proposed_payload={"decision_type": "wrong"},
            rationale="Refer to authority")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(WorkbenchError) as exc:
                await ApprovalService(mock_db).create(COMPLIANCE, req)
        assert exc.value.http_status == 400

    @pytest.mark.asyncio
    async def test_create_decision_report_ok(self, mock_db):
        c = make_case(status="decision_pending")
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.DECISION_REPORT_TO_AUTHORITY,
            entity_type=ApprovalEntityType.COMPLIANCE_CASE, entity_id=c.case_id,
            proposed_payload={"decision_type": "report_to_authority_recommended"},
            rationale="Refer to authority")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[c.model_dump(), None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.services.approval_service._fetch_eligible_approvers",
                   AsyncMock(return_value=["user2"])):
            result = await ApprovalService(mock_db).create(COMPLIANCE, req)
        assert result.approval_request.action_type == "decision_report_to_authority"

    @pytest.mark.asyncio
    async def test_create_role_restricted(self, mock_db):
        c = make_case(status="closed")
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.CASE_REOPEN,
            entity_type=ApprovalEntityType.COMPLIANCE_CASE, entity_id=c.case_id,
            rationale="New info")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(PermissionDenied):
                await ApprovalService(mock_db).create(ANALYST, req)

    @pytest.mark.asyncio
    async def test_create_entity_type_mismatch(self, mock_db):
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.CASE_REOPEN,
            entity_type=ApprovalEntityType.ALERT, entity_id=UID(),
            rationale="New info")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()):
            with pytest.raises(WorkbenchError) as exc:
                await ApprovalService(mock_db).create(ADMIN, req)
        assert exc.value.http_status == 400

    @pytest.mark.asyncio
    async def test_create_alert_not_found(self, mock_db):
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id="bad-id",
            rationale="Test")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await ApprovalService(mock_db).create(ANALYST, req)

    @pytest.mark.asyncio
    async def test_create_wrong_entity_state(self, mock_db):
        a = make_alert(status="new")
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Test")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=a.model_dump())):
            with pytest.raises(WorkbenchError) as exc:
                await ApprovalService(mock_db).create(ANALYST, req)
        assert exc.value.http_status == 400

    @pytest.mark.asyncio
    async def test_create_duplicate_active_blocked(self, mock_db):
        a = make_alert()
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Test")
        active = make_approval()
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[a.model_dump(), active.model_dump()])):
            with pytest.raises(InvalidTransition):
                await ApprovalService(mock_db).create(ANALYST, req)

    @pytest.mark.asyncio
    async def test_create_notifies_eligible_approvers(self, mock_db):
        a = make_alert()
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Test")
        uow_mock = make_uow_mock()
        inserted = []
        def fake_insert(notification, conn=None):
            inserted.append(notification)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[a.model_dump(), None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.services.approval_service._fetch_eligible_approvers",
                   AsyncMock(return_value=["user2", "user3"])) as approvers, \
             patch("workbench.repos.NotificationRepo.insert",
                   AsyncMock(side_effect=fake_insert)):
            await ApprovalService(mock_db).create(ANALYST, req)
        assert approvers.await_count == 1
        assert len(inserted) == 2
        assert all(n.notification_type == "approval_requested" for n in inserted)

    @pytest.mark.asyncio
    async def test_create_writes_audit_outbox(self, mock_db):
        a = make_alert()
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Test")
        uow_mock = make_uow_mock()
        events = []
        def fake_outbox(ev, conn=None):
            events.append(ev)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[a.model_dump(), None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.services.approval_service._fetch_eligible_approvers",
                   AsyncMock(return_value=[])), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock(side_effect=fake_outbox)):
            await ApprovalService(mock_db).create(ANALYST, req)
        assert len(events) == 1
        assert events[0].event_type == "approval.created"
        assert "rationale_sha256" in events[0].payload["after"]

    @pytest.mark.asyncio
    async def test_create_idempotent_replay(self, mock_db):
        a = make_alert()
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Test")
        uow_mock = make_uow_mock()
        resp = ApprovalRequestMutationResponse(
            approval_request=__import__(
                "workbench.schemas.approvals", fromlist=["ApprovalRequestDetailResponse"]
            ).ApprovalRequestDetailResponse(
                **make_approval().model_dump(), decisions=[]),
            version=1)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.services.approval_service._check_idempotency",
                   AsyncMock(return_value=(201, resp.model_dump_json()))), \
             patch("workbench.services.approval_service._store_idempotency", AsyncMock()):
            result = await ApprovalService(mock_db).create(
                ANALYST, req, idempotency_key="k1")
        assert result.approval_request.status == "pending"

    @pytest.mark.asyncio
    async def test_create_idempotency_mismatch(self, mock_db):
        a = make_alert()
        req = CreateApprovalRequest(
            action_type=ApprovalActionType.ALERT_DISMISSAL_CRITICAL_HIGH,
            entity_type=ApprovalEntityType.ALERT, entity_id=a.alert_id,
            rationale="Test")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.services.approval_service._check_idempotency",
                   AsyncMock(side_effect=IdempotencyMismatch())):
            with pytest.raises(IdempotencyMismatch):
                await ApprovalService(mock_db).create(
                    ANALYST, req, idempotency_key="k1")


class TestList:
    @pytest.mark.asyncio
    async def test_list_filters_by_role_and_scope(self, mock_db):
        ar = make_approval()
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[ar.model_dump()])):
            items, total = await ApprovalService(mock_db).list(COMPLIANCE, "pending", "alert_dismissal_critical_high", 1, 20)
        assert total == 1
        assert items[0].status == "pending"

    @pytest.mark.asyncio
    async def test_list_empty(self, mock_db):
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])):
            items, total = await ApprovalService(mock_db).list(ADMIN)
        assert items == []
        assert total == 0


class TestGetById:
    @pytest.mark.asyncio
    async def test_get_detail_with_decisions(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        decision = make_decision(approval_request_id=ar.approval_request_id)
        with patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump()])), \
             patch("workbench.repos._fetch_all",
                   AsyncMock(return_value=[decision.model_dump()])), \
             patch(AUTH_TARGET, AsyncMock()):
            result = await ApprovalService(mock_db).get_by_id(
                COMPLIANCE, ar.approval_request_id)
        assert result.approval_request_id == ar.approval_request_id
        assert len(result.decisions) == 1
        assert result.decisions[0].approver_id == "user2"

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await ApprovalService(mock_db).get_by_id(COMPLIANCE, "bad-id")

    @pytest.mark.asyncio
    async def test_analyst_cannot_read_others(self, mock_db):
        ar = make_approval(requested_by="user9", entity_id="alert1")
        a = make_alert(alert_id="alert1")
        with patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch(AUTH_TARGET, AsyncMock()):
            with pytest.raises(ResourceNotFound):
                await ApprovalService(mock_db).get_by_id(ANALYST, ar.approval_request_id)


class TestVote:
    def _vote_req(self, decision="approved", rationale=None):
        return VoteApprovalRequest(decision=decision, rationale=rationale)

    @pytest.mark.asyncio
    async def test_approve_approves_request(self, mock_db):
        ar = make_approval(entity_id="alert1", required_approvals=1)
        a = make_alert(alert_id="alert1")
        approved = make_approval(**{**ar.model_dump(),
                                    "status": "approved", "approval_count": 1,
                                    "version": 2})
        uow_mock = make_uow_mock()
        notified = []
        def fake_notify(notification, conn=None):
            notified.append(notification)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), approved.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.repos.NotificationRepo.insert",
                   AsyncMock(side_effect=fake_notify)):
            result = await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())
        assert result.approval_request.status == "approved"
        assert result.approval_request.approval_count == 1
        assert result.version == 2
        assert len(notified) == 1
        assert notified[0].notification_type == "approval_decided"
        assert notified[0].user_id == ar.requested_by

    @pytest.mark.asyncio
    async def test_approve_not_terminal_stays_pending(self, mock_db):
        ar = make_approval(entity_id="alert1", required_approvals=2)
        a = make_alert(alert_id="alert1")
        pending = make_approval(**{**ar.model_dump(),
                                   "approval_count": 1, "version": 2})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), pending.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()):
            result = await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())
        assert result.approval_request.status == "pending"
        assert result.approval_request.approval_count == 1
        assert result.approval_request.required_approvals == 2

    @pytest.mark.asyncio
    async def test_reject_requires_rationale(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump()])):
            with pytest.raises(WorkbenchError) as exc:
                await ApprovalService(mock_db).vote(
                    OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req("rejected"))
        assert exc.value.http_status == 400

    @pytest.mark.asyncio
    async def test_reject_rejects_request(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        rejected = make_approval(**{**ar.model_dump(),
                                    "status": "rejected", "approval_count": 1,
                                    "version": 2})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), rejected.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()):
            result = await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id,
                self._vote_req("rejected", rationale="Insufficient evidence"))
        assert result.approval_request.status == "rejected"
        assert result.approval_request.approval_count == 1

    @pytest.mark.asyncio
    async def test_requester_cannot_vote_own(self, mock_db):
        ar = make_approval(entity_id="alert1", requested_by="user1")
        a = make_alert(alert_id="alert1")
        uow_mock = make_uow_mock()
        def boom(user, action, resource, db=None, request_context=None):
            raise ConflictOfInterestError()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock(side_effect=boom)), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump()])):
            with pytest.raises(ConflictOfInterestError):
                await ApprovalService(mock_db).vote(
                    COMPLIANCE, ar.approval_request_id, self._vote_req())

    @pytest.mark.asyncio
    async def test_already_voted(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        existing = make_decision(approval_request_id=ar.approval_request_id,
                                 approver_id="user2")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump()])), \
             patch("workbench.repos._fetch_all",
                   AsyncMock(return_value=[existing.model_dump()])):
            with pytest.raises(InvalidTransition):
                await ApprovalService(mock_db).vote(
                    OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())

    @pytest.mark.asyncio
    async def test_vote_on_non_pending(self, mock_db):
        ar = make_approval(entity_id="alert1", status="approved", executed_at=NOW)
        a = make_alert(alert_id="alert1")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])):
            with pytest.raises(InvalidTransition):
                await ApprovalService(mock_db).vote(
                    OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())

    @pytest.mark.asyncio
    async def test_vote_race_returns_none(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), None])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])):
            with pytest.raises(InvalidTransition):
                await ApprovalService(mock_db).vote(
                    OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())

    @pytest.mark.asyncio
    async def test_vote_appends_decision_and_audit(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        approved = make_approval(**{**ar.model_dump(),
                                    "status": "approved", "approval_count": 1,
                                    "version": 2})
        uow_mock = make_uow_mock()
        decisions, events = [], []
        def fake_decision(ad, conn=None):
            decisions.append(ad)
        def fake_outbox(ev, conn=None):
            events.append(ev)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), approved.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.repos.ApprovalDecisionRepo.create",
                   AsyncMock(side_effect=fake_decision)), \
             patch("workbench.repos.OutboxRepo.insert",
                   AsyncMock(side_effect=fake_outbox)):
            result = await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())
        assert len(decisions) == 1
        assert decisions[0].approver_id == "user2"
        assert decisions[0].decision == "approved"
        assert len(result.approval_request.decisions) == 1
        assert [e.event_type for e in events] == ["approval.approved"]

    @pytest.mark.asyncio
    async def test_vote_audit_non_terminal(self, mock_db):
        ar = make_approval(entity_id="alert1", required_approvals=2)
        a = make_alert(alert_id="alert1")
        pending = make_approval(**{**ar.model_dump(),
                                   "approval_count": 1, "version": 2})
        uow_mock = make_uow_mock()
        events = []
        def fake_outbox(ev, conn=None):
            events.append(ev)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), pending.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.repos.OutboxRepo.insert",
                   AsyncMock(side_effect=fake_outbox)):
            await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id, self._vote_req())
        assert [e.event_type for e in events] == ["approval.vote"]

    @pytest.mark.asyncio
    async def test_reject_audit_event(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        rejected = make_approval(**{**ar.model_dump(),
                                    "status": "rejected", "approval_count": 1,
                                    "version": 2})
        uow_mock = make_uow_mock()
        events = []
        def fake_outbox(ev, conn=None):
            events.append(ev)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one",
                   AsyncMock(side_effect=[ar.model_dump(), a.model_dump(), rejected.model_dump()])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 1")), \
             patch("workbench.repos.OutboxRepo.insert",
                   AsyncMock(side_effect=fake_outbox)):
            await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id,
                self._vote_req("rejected", rationale="No basis"))
        assert [e.event_type for e in events] == ["approval.rejected"]

    @pytest.mark.asyncio
    async def test_vote_idempotent_replay(self, mock_db):
        ar = make_approval(entity_id="alert1")
        a = make_alert(alert_id="alert1")
        uow_mock = make_uow_mock()
        resp = ApprovalRequestMutationResponse(
            approval_request=__import__(
                "workbench.schemas.approvals", fromlist=["ApprovalRequestDetailResponse"]
            ).ApprovalRequestDetailResponse(
                **make_approval(status="approved", approval_count=1, version=2).model_dump(),
                decisions=[]),
            version=2)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.services.approval_service._check_idempotency",
                   AsyncMock(return_value=(200, resp.model_dump_json()))), \
             patch("workbench.services.approval_service._store_idempotency", AsyncMock()):
            result = await ApprovalService(mock_db).vote(
                OTHER_COMPLIANCE, ar.approval_request_id,
                self._vote_req(), idempotency_key="k1")
        assert result.approval_request.status == "approved"


class TestConsumeRepo:
    @pytest.mark.asyncio
    async def test_consume_requires_approved_and_unexecuted(self, mock_db):
        from workbench.repos import ApprovalRepo
        calls = []
        def capture(db, sql, params, conn=None):
            calls.append(sql)
            return None
        with patch("workbench.repos._fetch_one", AsyncMock(side_effect=capture)):
            result = await ApprovalRepo(mock_db).consume("ar1")
        assert result is None
        assert "status='approved'" in calls[0]
        assert "executed_at IS NULL" in calls[0]
