"""Phase 2B.17b-R remediation tests: case resume (C4), close (C5/C9), reopen (C6/C12).

Covers the four confirmed frozen-workflow gaps:
  1. awaiting_information -> under_review (case resume) missing from
     case_service.ALLOWED_TRANSITIONS and shared/authorise CASE_TRANSITIONS.
  2. POST /cases/{id}/close (contract C5 / state machine C9) missing.
  3. POST /cases/{id}/reopen (contract C6 / state machine C12) missing.
  4. Investigation awaiting_information -> active permission gap in
     shared/authorise INVESTIGATION_TRANSITIONS.
"""
import json
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser, OwnershipDeniedError

from workbench.exceptions import (
    ApprovalConsumed, ApprovalRequired, IdempotencyMismatch,
    InvalidTransition, ResourceNotFound, VersionConflict,
    WorkbenchError,
)
from workbench.models import Alert, ApprovalRequest, ComplianceCase, Investigation
from workbench.schemas.cases import (
    CaseAdminResponse, CaseAdminView, CloseCaseRequest,
    ReopenCaseRequest, TransitionCaseRequest,
)
from workbench.services.case_service import CaseService

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

CLOSER = ApplicationUser(user_id="compliance1", role="compliance", permissions=[
    "case:read_assigned", "case:transition", "case:close",
])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "case:reopen", "case:read_assigned",
])

UOW_TARGET = "workbench.services.case_service.UnitOfWork"
AUTH_TARGET = "workbench.services.case_service.authorise"


def make_case(**kw):
    defaults = dict(case_id=UID(), title="Test Case",
                    description=None, alert_id=None, investigation_id=None,
                    scope_id="hq_main", status="resolved", priority="medium",
                    risk_level="low", regulatory_frameworks=None,
                    assigned_to="compliance1", created_by="user1",
                    target_date=None, resolution="Reviewed, no issues", resolved_at=NOW,
                    resolved_by="compliance1", closed_at=None, closed_by=None,
                    current_disposition_id=None, closure_approval_id=None,
                    reopen_reason=None,
                    version=3, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ComplianceCase(**defaults)


def make_approval(case_id, action_type="case_closure_critical_high",
                  status="approved", executed_at=None):
    return ApprovalRequest(
        approval_request_id="ap1", action_type=action_type,
        entity_type="compliance_case", entity_id=case_id, requested_by="user1",
        rationale="approval", required_approvals=1, approval_count=1,
        status=status, expires_at=NOW, executed_at=executed_at)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


@contextmanager
def close_ctx(case, *, fetch=None, update=None, alert=None, inv=None,
              consume=None, approval_fetch=None, auth=None, admin="admin1",
              timeline=None, notify=None, outbox=None):
    uow_mock = make_uow_mock()
    with patch(UOW_TARGET, return_value=uow_mock), \
         patch(AUTH_TARGET, auth or AsyncMock()), \
         patch("workbench.repos.CaseRepo.fetch_by_id",
               fetch or AsyncMock(return_value=case)), \
         patch("workbench.repos.CaseRepo.update",
               update or AsyncMock(return_value=case)), \
         patch("workbench.repos.ApprovalRepo.consume",
               consume or AsyncMock(return_value=MagicMock())), \
         patch("workbench.repos.ApprovalRepo.fetch_by_id",
               approval_fetch or AsyncMock(return_value=None)), \
         patch("workbench.repos.TimelineRepo.insert", timeline or AsyncMock()), \
         patch("workbench.repos.NotificationRepo.insert", notify or AsyncMock()), \
         patch("workbench.repos.OutboxRepo.insert", outbox or AsyncMock()), \
         patch("workbench.repos.AlertRepo.fetch_by_id", AsyncMock(return_value=alert)), \
         patch("workbench.repos.InvestigationRepo.fetch_by_id", AsyncMock(return_value=inv)), \
         patch("workbench.services.case_service._fetch_admin_for_scope",
               AsyncMock(return_value=admin)):
        yield uow_mock


# ── Resume: awaiting_information -> under_review (C4) ────────────────────────


class TestResume:
    @pytest.mark.asyncio
    async def test_resume_valid(self, mock_db):
        c = make_case(status="awaiting_information", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        with close_ctx(c):
            result = await CaseService(mock_db).transition(CLOSER, c.case_id, req)
        assert result.case.status == "under_review"
        assert result.version == 5

    @pytest.mark.asyncio
    async def test_resume_side_effects_use_resume_event_names(self, mock_db):
        c = make_case(status="awaiting_information", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        mock_timeline = AsyncMock()
        mock_outbox = AsyncMock()
        with close_ctx(c, timeline=mock_timeline, outbox=mock_outbox):
            await CaseService(mock_db).transition(CLOSER, c.case_id, req)
        assert mock_timeline.await_args[0][0].event_type == "under_review_resumed"
        assert mock_outbox.await_args[0][0].event_type == "case.resumed"

    @pytest.mark.asyncio
    async def test_resume_wrong_state_rejected(self, mock_db):
        c = make_case(status="decision_pending", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        with close_ctx(c):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).transition(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_resume_ownership_denied_for_non_assignee(self, mock_db):
        c = make_case(status="awaiting_information", assigned_to="other-user", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        with close_ctx(c, auth=AsyncMock(side_effect=OwnershipDeniedError())):
            with pytest.raises(OwnershipDeniedError):
                await CaseService(mock_db).transition(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_resume_stale_version(self, mock_db):
        c = make_case(status="awaiting_information", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        with close_ctx(c, update=AsyncMock(return_value=None)):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).transition(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_resume_rollback_on_failure(self, mock_db):
        c = make_case(status="awaiting_information", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        mock_timeline = AsyncMock()
        mock_outbox = AsyncMock()
        with close_ctx(c, update=AsyncMock(return_value=None),
                      timeline=mock_timeline, outbox=mock_outbox):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).transition(CLOSER, c.case_id, req)
        mock_timeline.assert_not_awaited()
        mock_outbox.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_resume_notification_none(self, mock_db):
        c = make_case(status="awaiting_information", version=4)
        req = TransitionCaseRequest(target_status="under_review", expected_version=4)
        mock_notify = AsyncMock()
        with close_ctx(c, notify=mock_notify):
            await CaseService(mock_db).transition(CLOSER, c.case_id, req)
        mock_notify.assert_not_awaited()


# ── Close (C5 / C9) ──────────────────────────────────────────────────────────


class TestClose:
    @pytest.mark.asyncio
    async def test_close_low_risk_no_approval(self, mock_db):
        c = make_case(risk_level="low", version=3)
        req = CloseCaseRequest(expected_version=3)
        mock_consume = AsyncMock()
        mock_update = AsyncMock(return_value=c)
        with close_ctx(c, update=mock_update, consume=mock_consume):
            result = await CaseService(mock_db).close(CLOSER, c.case_id, req)
        assert result.case.status == "closed"
        assert result.case.closed_by == "compliance1"
        assert result.case.closed_at is not None
        updated = mock_update.await_args[0][0]
        assert updated.closure_approval_id is None
        mock_consume.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_medium_no_approval(self, mock_db):
        c = make_case(risk_level="medium", version=3)
        req = CloseCaseRequest(expected_version=3)
        mock_update = AsyncMock(return_value=c)
        with close_ctx(c, update=mock_update):
            result = await CaseService(mock_db).close(CLOSER, c.case_id, req)
        assert result.case.status == "closed"
        assert mock_update.await_args[0][0].closure_approval_id is None

    @pytest.mark.asyncio
    async def test_close_high_requires_approval(self, mock_db):
        c = make_case(risk_level="high", version=3)
        req = CloseCaseRequest(expected_version=3)
        with close_ctx(c):
            with pytest.raises(ApprovalRequired):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_consumes_approval(self, mock_db):
        c = make_case(risk_level="high", version=3)
        approval = make_approval(c.case_id)
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        mock_consume = AsyncMock(return_value=approval)
        mock_update = AsyncMock(return_value=c)
        with close_ctx(c, update=mock_update, consume=mock_consume,
                       approval_fetch=AsyncMock(return_value=approval)) as uow_mock:
            result = await CaseService(mock_db).close(CLOSER, c.case_id, req)
        assert result.case.status == "closed"
        assert mock_update.await_args[0][0].closure_approval_id == "ap1"
        mock_consume.assert_awaited_once_with("ap1", uow_mock.__aenter__.return_value.conn)

    @pytest.mark.asyncio
    async def test_close_approval_wrong_entity(self, mock_db):
        c = make_case(risk_level="high", version=3)
        approval = make_approval("other-case")
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        with close_ctx(c, approval_fetch=AsyncMock(return_value=approval)):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_approval_wrong_action(self, mock_db):
        c = make_case(risk_level="high", version=3)
        approval = make_approval(c.case_id, action_type="decision_report_to_authority")
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        with close_ctx(c, approval_fetch=AsyncMock(return_value=approval)):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_approval_pending(self, mock_db):
        c = make_case(risk_level="high", version=3)
        approval = make_approval(c.case_id, status="pending")
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        with close_ctx(c, approval_fetch=AsyncMock(return_value=approval)):
            with pytest.raises(ApprovalRequired):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_approval_already_consumed(self, mock_db):
        c = make_case(risk_level="high", version=3)
        approval = make_approval(c.case_id, executed_at=NOW)
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        with close_ctx(c, approval_fetch=AsyncMock(return_value=approval)):
            with pytest.raises(ApprovalConsumed):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_approval_not_found(self, mock_db):
        c = make_case(risk_level="high", version=3)
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        with close_ctx(c, approval_fetch=AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_consume_race(self, mock_db):
        c = make_case(risk_level="high", version=3)
        approval = make_approval(c.case_id)
        req = CloseCaseRequest(expected_version=3, approval_request_id="ap1")
        with close_ctx(c, consume=AsyncMock(return_value=None),
                       approval_fetch=AsyncMock(return_value=approval)):
            with pytest.raises(ApprovalConsumed):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_stale_version(self, mock_db):
        c = make_case(risk_level="low", version=3)
        req = CloseCaseRequest(expected_version=3)
        with close_ctx(c, update=AsyncMock(return_value=None)):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_double_close_rejected(self, mock_db):
        c = make_case(status="closed", risk_level="low", version=5)
        req = CloseCaseRequest(expected_version=5)
        with close_ctx(c):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_requires_resolution(self, mock_db):
        c = make_case(resolution=None, risk_level="low", version=3)
        req = CloseCaseRequest(expected_version=3)
        with close_ctx(c):
            with pytest.raises(WorkbenchError):
                await CaseService(mock_db).close(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_close_side_effects(self, mock_db):
        c = make_case(risk_level="low", investigation_id="inv1", version=3)
        inv = Investigation(investigation_id="inv1", title="Inv", created_by="user1",
                            assigned_to="analyst1", status="active")
        req = CloseCaseRequest(expected_version=3, resolution="all clear")
        mock_timeline = AsyncMock()
        mock_notify = AsyncMock()
        mock_outbox = AsyncMock()
        with close_ctx(c, inv=inv, timeline=mock_timeline,
                       notify=mock_notify, outbox=mock_outbox):
            await CaseService(mock_db).close(CLOSER, c.case_id, req)
        timeline_events = [a[0][0].event_type for a in mock_timeline.await_args_list]
        assert "case.closed" in timeline_events
        notify_types = [a[0][0].notification_type for a in mock_notify.await_args_list]
        assert set(notify_types) == {"case_closed"}
        user_ids = {a[0][0].user_id for a in mock_notify.await_args_list}
        assert user_ids == {"admin1", "analyst1"}
        outbox_events = [a[0][0].event_type for a in mock_outbox.await_args_list]
        assert "case.closed" in outbox_events
        payload = [a[0][0] for a in mock_outbox.await_args_list
                   if a[0][0].event_type == "case.closed"][0].payload
        assert payload["event_type"] == "case.closed"
        assert payload["actor_id"] == "compliance1"

    @pytest.mark.asyncio
    async def test_close_resolves_linked_alert(self, mock_db):
        c = make_case(alert_id="alert1", risk_level="low", version=3)
        req = CloseCaseRequest(expected_version=3)
        alert = Alert(alert_id="alert1", alert_type="suspicious_activity",
                      severity="high", title="Alert", scope_id="hq_main",
                      status="under_investigation", version=1)
        mock_alert_update = AsyncMock(return_value=alert)
        mock_timeline = AsyncMock()
        mock_outbox = AsyncMock()
        with close_ctx(c, alert=alert, timeline=mock_timeline, outbox=mock_outbox), \
             patch("workbench.repos.AlertRepo.update", mock_alert_update):
            await CaseService(mock_db).close(CLOSER, c.case_id, req)
        updated = mock_alert_update.await_args[0][0]
        assert updated.status == "resolved"
        assert updated.resolved_by == "compliance1"
        events = [a[0][0].event_type for a in mock_timeline.await_args_list]
        assert "alert.resolved" in events
        outbox_events = [a[0][0].event_type for a in mock_outbox.await_args_list]
        assert "alert.resolved" in outbox_events

    @pytest.mark.asyncio
    async def test_close_idempotency_replay(self, mock_db):
        c = make_case(risk_level="low", version=3)
        req = CloseCaseRequest(expected_version=3)
        fake_resp = CaseAdminResponse(case=CaseAdminView(**c.model_dump()), version=3)
        stored_body = fake_resp.model_dump_json()
        body_hash = __import__("hashlib").sha256(
            json.dumps({"closure_reason": None, "resolution": None,
                        "expected_version": 3, "approval_request_id": None},
                       sort_keys=True, default=str).encode()).hexdigest()
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="POST",
                 request_path=f"/api/v1/cases/{c.case_id}/close",
                 request_body_sha256=body_hash,
                 response_status=200, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await CaseService(mock_db).close(
                CLOSER, c.case_id, req, idempotency_key="dup-key")
        assert result.case.case_id == c.case_id

    @pytest.mark.asyncio
    async def test_close_idempotency_mismatch(self, mock_db):
        c = make_case(risk_level="low", version=3)
        req = CloseCaseRequest(expected_version=3)
        other_hash = __import__("hashlib").sha256(b"other").hexdigest()
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="POST",
                 request_path=f"/api/v1/cases/{c.case_id}/close",
                 request_body_sha256=other_hash,
                 response_status=200, response_body="{}",
                 created_at=NOW,
             ))):
            with pytest.raises(IdempotencyMismatch):
                await CaseService(mock_db).close(
                    CLOSER, c.case_id, req, idempotency_key="dup-key")


# ── Reopen (C6 / C12) ────────────────────────────────────────────────────────


@contextmanager
def reopen_ctx(case, *, approval=None, fetch=None, update=None, consume=None,
               auth=None, admin="admin1", timeline=None, notify=None, outbox=None):
    uow_mock = make_uow_mock()
    with patch(UOW_TARGET, return_value=uow_mock), \
         patch(AUTH_TARGET, auth or AsyncMock()), \
         patch("workbench.repos.CaseRepo.fetch_by_id",
               fetch or AsyncMock(return_value=case)), \
         patch("workbench.repos.CaseRepo.update",
               update or AsyncMock(return_value=case)), \
         patch("workbench.repos.ApprovalRepo.fetch_by_id",
               AsyncMock(return_value=approval)), \
         patch("workbench.repos.ApprovalRepo.consume",
               consume or AsyncMock(return_value=approval)), \
         patch("workbench.repos.TimelineRepo.insert", timeline or AsyncMock()), \
         patch("workbench.repos.NotificationRepo.insert", notify or AsyncMock()), \
         patch("workbench.repos.OutboxRepo.insert", outbox or AsyncMock()), \
         patch("workbench.services.case_service._fetch_admin_for_scope",
               AsyncMock(return_value=admin)):
        yield uow_mock


class TestReopen:
    def closed_case(self, **kw):
        return make_case(status="closed", assigned_to="compliance1",
                         closed_at=NOW, closed_by="compliance1",
                         closure_approval_id="ap0", risk_level="low", **kw)

    @pytest.mark.asyncio
    async def test_reopen_valid(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="new evidence", expected_version=4,
                                approval_request_id="ap1")
        mock_update = AsyncMock(return_value=c)
        with reopen_ctx(c, approval=approval, update=mock_update):
            result = await CaseService(mock_db).reopen(ADMIN, c.case_id, req)
        assert result.case.status == "open"
        assert result.case.closed_at is None
        assert result.case.closed_by is None
        assert result.case.reopen_reason == "new evidence"
        assert result.version == 5
        updated = mock_update.await_args[0][0]
        assert updated.closure_approval_id is None

    def test_reopen_approval_request_id_required_by_schema(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ReopenCaseRequest(reopen_reason="reason", expected_version=4)

    @pytest.mark.asyncio
    async def test_reopen_wrong_state(self, mock_db):
        c = make_case(status="open", risk_level="low", version=4)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_approval_wrong_entity(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval("other-case", action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_approval_wrong_action(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_closure_critical_high")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_approval_pending(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen", status="pending")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval):
            with pytest.raises(ApprovalRequired):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_approval_already_consumed(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen", executed_at=NOW)
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval):
            with pytest.raises(ApprovalConsumed):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_approval_not_found(self, mock_db):
        c = self.closed_case(version=4)
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=None):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_consume_race(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval, consume=AsyncMock(return_value=None)):
            with pytest.raises(ApprovalConsumed):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_stale_version(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval, update=AsyncMock(return_value=None)):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_double_reopen_rejected(self, mock_db):
        c = make_case(status="open", risk_level="low", version=6)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=6,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).reopen(ADMIN, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_side_effects(self, mock_db):
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="fresh evidence", expected_version=4,
                                approval_request_id="ap1")
        mock_timeline = AsyncMock()
        mock_notify = AsyncMock()
        mock_outbox = AsyncMock()
        with reopen_ctx(c, approval=approval, timeline=mock_timeline,
                        notify=mock_notify, outbox=mock_outbox):
            await CaseService(mock_db).reopen(ADMIN, c.case_id, req)
        assert mock_timeline.await_args[0][0].event_type == "case.reopened"
        notify = mock_notify.await_args[0][0]
        assert notify.notification_type == "case_reopened"
        assert notify.user_id == "compliance1"
        outbox = mock_outbox.await_args[0][0]
        assert outbox.event_type == "case.reopened"
        payload = outbox.payload
        assert payload["event_type"] == "case.reopened"
        assert payload["after"]["reopen_reason_sha256"]

    @pytest.mark.asyncio
    async def test_reopen_non_admin_denied_by_permission(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = self.closed_case(version=4)
        approval = make_approval(c.case_id, action_type="case_reopen")
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        with reopen_ctx(c, approval=approval,
                        auth=AsyncMock(side_effect=PermissionDeniedError("case:reopen"))):
            with pytest.raises(PermissionDeniedError):
                await CaseService(mock_db).reopen(CLOSER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_reopen_idempotency_replay(self, mock_db):
        c = self.closed_case(version=4)
        req = ReopenCaseRequest(reopen_reason="reason", expected_version=4,
                                approval_request_id="ap1")
        fake_resp = CaseAdminResponse(case=CaseAdminView(**c.model_dump()), version=4)
        stored_body = fake_resp.model_dump_json()
        body_hash = __import__("hashlib").sha256(
            json.dumps({"reopen_reason": "reason", "expected_version": 4,
                        "approval_request_id": "ap1"},
                       sort_keys=True, default=str).encode()).hexdigest()
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="POST",
                 request_path=f"/api/v1/cases/{c.case_id}/reopen",
                 request_body_sha256=body_hash,
                 response_status=200, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await CaseService(mock_db).reopen(
                ADMIN, c.case_id, req, idempotency_key="dup-key")
        assert result.case.case_id == c.case_id
