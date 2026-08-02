"""Case service tests."""
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
from workbench.models import ApprovalRequest, ComplianceCase, Decision
from workbench.schemas.cases import (
    AssignCaseRequest, CaseAdminResponse, CaseAdminView,
    CaseDecisionResponse, CaseResponse, DecisionType,
    RecordDecisionRequest, TransitionCaseRequest,
)
from workbench.services.case_service import CaseService, _validate_assignee

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

MOCK_USER = ApplicationUser(user_id="user1", role="compliance", permissions=[
    "case:read_assigned", "case:assign", "case:transition",
    "case:decision", "case:read",
])
ADMIN_USER = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "case:read_assigned", "case:assign", "case:transition",
])
OTHER_USER = ApplicationUser(user_id="user2", role="compliance", permissions=[
    "case:read_assigned",
])
NO_PERM_USER = ApplicationUser(user_id="analyst1", role="analyst", permissions=[
    "case:read_assigned",
])


def make_case(**kw):
    defaults = dict(case_id=UID(), title="Test Case",
                    description=None, alert_id=None, investigation_id=None,
                    scope_id="hq_main", status="open", priority="medium",
                    risk_level=None, regulatory_frameworks=None,
                    assigned_to=None, created_by="user1",
                    target_date=None, resolution=None, resolved_at=None,
                    resolved_by=None, closed_at=None, closed_by=None,
                    current_disposition_id=None, closure_approval_id=None,
                    reopen_reason=None,
                    version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ComplianceCase(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


UOW_TARGET = "workbench.services.case_service.UnitOfWork"
AUTH_TARGET = "workbench.services.case_service.authorise"
HASH = lambda body: __import__("hashlib").sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class TestListAssigned:
    @pytest.mark.asyncio
    async def test_own_cases_only(self, mock_db):
        c = make_case(assigned_to="user1", status="assigned")
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[c.model_dump()])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await CaseService(mock_db).list_assigned(MOCK_USER, "hq_main")
        assert len(items) == 1
        assert items[0].case_id == c.case_id

    @pytest.mark.asyncio
    async def test_filtering(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            await CaseService(mock_db).list_assigned(MOCK_USER, "hq_main", status="assigned", priority="high")
        assert "assigned_to" in mock_fetch.call_args[0][1]

    @pytest.mark.asyncio
    async def test_authorise_called(self, mock_db):
        mock_auth = AsyncMock()
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, mock_auth):
            await CaseService(mock_db).list_assigned(MOCK_USER, "hq_main")
        mock_auth.assert_awaited_once()


class TestGetById:
    @pytest.mark.asyncio
    async def test_assigned_user_success(self, mock_db):
        c = make_case(assigned_to="user1", status="assigned")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, AsyncMock()):
            result = await CaseService(mock_db).get_by_id(MOCK_USER, c.case_id)
        assert result.case_id == c.case_id

    @pytest.mark.asyncio
    async def test_nonexistent(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).get_by_id(MOCK_USER, "no-such-id")

    @pytest.mark.asyncio
    async def test_admin_with_global_read(self, mock_db):
        c = make_case(assigned_to="user1", status="assigned")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, AsyncMock()):
            result = await CaseService(mock_db).get_by_id(ADMIN_USER, c.case_id)
        assert result.case_id == c.case_id

    @pytest.mark.asyncio
    async def test_no_permission_returns_not_found(self, mock_db):
        c = make_case(assigned_to="user1", status="assigned")
        from shared.authorise import PermissionDeniedError
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("case:read_assigned"),
                 PermissionDeniedError("case:read"),
             ])):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).get_by_id(OTHER_USER, c.case_id)


class TestAssign:
    @pytest.mark.asyncio
    async def test_assign_open_case(self, mock_db):
        c = make_case(status="open", version=1)
        req = AssignCaseRequest(assigned_to="user2", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()):
            result = await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        assert result.case.status == "assigned"
        assert result.case.assigned_to == "user2"

    @pytest.mark.asyncio
    async def test_assign_reassign(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = AssignCaseRequest(assigned_to="user3", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()):
            result = await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        assert result.case.assigned_to == "user3"
        assert result.case.status == "assigned"

    @pytest.mark.asyncio
    async def test_assign_wrong_state(self, mock_db):
        c = make_case(status="under_review", assigned_to="user1", version=2)
        req = AssignCaseRequest(assigned_to="user2", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_assign_version_conflict(self, mock_db):
        c = make_case(status="open", version=1)
        c_dump = c.model_dump()
        req = AssignCaseRequest(assigned_to="user2", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[c_dump, None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_assign_not_found(self, mock_db):
        req = AssignCaseRequest(assigned_to="user2", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).assign(MOCK_USER, "bad-id", req)

    @pytest.mark.asyncio
    async def test_assign_timeline_created(self, mock_db):
        c = make_case(status="open", version=1)
        req = AssignCaseRequest(assigned_to="user2", expected_version=1)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.AssignmentHistoryRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        mock_timeline.assert_awaited_once()
        args = mock_timeline.await_args[0][0]
        assert args.event_type == "case.assigned"

    @pytest.mark.asyncio
    async def test_assign_assignment_history(self, mock_db):
        c = make_case(status="open", version=1)
        req = AssignCaseRequest(assigned_to="user2", expected_version=1, reason="reassigning")
        uow_mock = make_uow_mock()
        mock_history = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.AssignmentHistoryRepo.insert", mock_history), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        mock_history.assert_awaited_once()
        args = mock_history.await_args[0][0]
        assert args.assigned_to == "user2"
        assert args.reason == "reassigning"

    @pytest.mark.asyncio
    async def test_assign_notification(self, mock_db):
        c = make_case(status="open", version=1)
        req = AssignCaseRequest(assigned_to="user2", expected_version=1)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.AssignmentHistoryRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        mock_notify.assert_awaited_once()
        args = mock_notify.await_args[0][0]
        assert args.notification_type == "case_assigned"
        assert args.user_id == "user2"

    @pytest.mark.asyncio
    async def test_assign_outbox(self, mock_db):
        c = make_case(status="open", version=1)
        req = AssignCaseRequest(assigned_to="user2", expected_version=1)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.case_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.AssignmentHistoryRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        mock_outbox.assert_awaited_once()
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "case.assigned"

    @pytest.mark.asyncio
    async def test_assign_invalid_assignee(self, mock_db):
        c = make_case(status="open", version=1)
        req = AssignCaseRequest(assigned_to="bad-user", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.services.case_service._validate_assignee",
                   AsyncMock(side_effect=InvalidAssignee("User not found: bad-user"))):
            with pytest.raises(InvalidAssignee):
                await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_same_assignee_no_op(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = AssignCaseRequest(assigned_to="user1", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            result = await CaseService(mock_db).assign(MOCK_USER, c.case_id, req)
        assert result.version == 2
        assert result.case.assigned_to == "user1"


class TestTransition:
    @pytest.mark.asyncio
    async def test_assigned_to_under_review(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = TransitionCaseRequest(target_status="under_review", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)
        assert result.case.status == "under_review"

    @pytest.mark.asyncio
    async def test_under_review_to_decision_pending(self, mock_db):
        c = make_case(status="under_review", assigned_to="user1", version=3)
        req = TransitionCaseRequest(target_status="decision_pending", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)
        assert result.case.status == "decision_pending"

    @pytest.mark.asyncio
    async def test_awaiting_compliance_to_resolved(self, mock_db):
        c = make_case(status="awaiting_compliance_action", assigned_to="user1", version=4)
        req = TransitionCaseRequest(target_status="resolved", expected_version=4, resolution="All issues addressed")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)
        assert result.case.status == "resolved"
        assert result.case.resolved_at is not None
        assert result.case.resolved_by == "user1"

    @pytest.mark.asyncio
    async def test_resolved_requires_resolution(self, mock_db):
        c = make_case(status="awaiting_compliance_action", assigned_to="user1", version=4)
        req = TransitionCaseRequest(target_status="resolved", expected_version=4)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(InvalidTransition, match="resolution is required"):
                await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_invalid_transition(self, mock_db):
        c = make_case(status="open", version=1)
        req = TransitionCaseRequest(target_status="closed", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        c_dump = c.model_dump()
        req = TransitionCaseRequest(target_status="under_review", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[c_dump, None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        req = TransitionCaseRequest(target_status="under_review", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).transition(MOCK_USER, "bad-id", req)

    @pytest.mark.asyncio
    async def test_timeline_created(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = TransitionCaseRequest(target_status="under_review", expected_version=2)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)
        mock_timeline.assert_awaited_once()
        args = mock_timeline.await_args[0][0]
        assert args.event_type == "case.under_review"

    @pytest.mark.asyncio
    async def test_outbox_created(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = TransitionCaseRequest(target_status="under_review", expected_version=2)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await CaseService(mock_db).transition(MOCK_USER, c.case_id, req)
        mock_outbox.assert_awaited_once()
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "case.under_review"


class TestDecision:
    @pytest.mark.asyncio
    async def test_record_decision_awaiting_compliance(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="High risk pattern detected",
                                    expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value=None)):
            result = await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        assert result.case.status == "awaiting_compliance_action"
        assert result.decision["decision_type"] == "warning"

    @pytest.mark.asyncio
    async def test_record_decision_no_action_resolves(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.NO_ACTION, rationale="No issues found",
                                    expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value=None)):
            result = await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        assert result.case.status == "resolved"
        assert result.case.resolved_at is not None
        assert result.case.resolved_by == "user1"

    @pytest.mark.asyncio
    async def test_record_decision_closure_recommended_resolves(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.CLOSURE_RECOMMENDED, rationale="Closure warranted",
                                    expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value=None)):
            result = await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        assert result.case.status == "resolved"

    @pytest.mark.asyncio
    async def test_decision_only_from_decision_pending(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="test", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_decision_creates_decision_record(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="Suspicious activity",
                                    expected_version=3)
        uow_mock = make_uow_mock()
        mock_decision_create = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", mock_decision_create), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value=None)):
            await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        mock_decision_create.assert_awaited_once()
        args = mock_decision_create.await_args[0][0]
        assert args.decision_type == "warning"
        assert args.rationale == "Suspicious activity"
        assert args.decided_by == "user1"
        assert args.case_id == c.case_id

    @pytest.mark.asyncio
    async def test_decision_notification(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", created_by="creator1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="test", expected_version=3)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value="admin1")):
            await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        mock_notify.assert_awaited_once()
        args = mock_notify.await_args[0][0]
        assert args.notification_type == "case_decision_recorded"
        assert args.user_id == "admin1"
        assert args.entity_type == "compliance_case"

    @pytest.mark.asyncio
    async def test_decision_resolution_events(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.NO_ACTION, rationale="No issues", expected_version=3)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        mock_notify = AsyncMock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value="admin1")):
            result = await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        assert result.case.status == "resolved"
        assert mock_timeline.await_args[0][0].event_type == "case.resolved"
        assert mock_notify.await_args[0][0].notification_type == "case_resolved"
        assert mock_outbox.await_args[0][0].event_type == "case.resolved"

    @pytest.mark.asyncio
    async def test_decision_audit_payload_envelope(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="secret detail", expected_version=3)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value=None)):
            await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        payload = mock_outbox.await_args[0][0].payload
        assert payload["event_type"] == "case.decision_recorded"
        assert payload["schema_version"] == 1
        assert payload["entity_type"] == "compliance_case"
        assert payload["entity_id"] == c.case_id
        assert payload["actor_id"] == "user1"
        assert "secret detail" not in json.dumps(payload)
        assert payload["metadata"]["rationale_sha256"] == HASH("secret detail")

    @pytest.mark.asyncio
    async def test_report_to_authority_requires_approval(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            with pytest.raises(ApprovalRequired):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_report_to_authority_consumes_approval(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        approval = ApprovalRequest(
            approval_request_id="ap1", action_type="decision_report_to_authority",
            entity_type="compliance_case", entity_id=c.case_id, requested_by="user1",
            rationale="report", required_approvals=1, approval_count=1,
            status="approved", expires_at=NOW)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", approval_request_id="ap1", expected_version=3)
        uow_mock = make_uow_mock()
        mock_consume = AsyncMock(return_value=approval)
        mock_decision_create = AsyncMock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id", AsyncMock(return_value=approval)), \
             patch("workbench.repos.ApprovalRepo.consume", mock_consume), \
             patch("workbench.repos.DecisionRepo.create", mock_decision_create), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox), \
             patch("workbench.services.case_service._fetch_admin_for_scope", AsyncMock(return_value=None)):
            result = await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        assert result.case.status == "awaiting_compliance_action"
        mock_consume.assert_awaited_once()
        assert mock_consume.await_args[0][0] == "ap1"
        assert mock_consume.await_args[0][1] is uow_mock.__aenter__.return_value.conn
        args = mock_decision_create.await_args[0][0]
        assert args.approval_id == "ap1"
        assert mock_outbox.await_args[0][0].event_type == "case.decision_recorded"
        assert mock_outbox.await_args[0][0].payload["metadata"]["approval_id"] == "ap1"

    @pytest.mark.asyncio
    async def test_report_to_authority_approval_wrong_entity(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        approval = ApprovalRequest(
            approval_request_id="ap1", action_type="decision_report_to_authority",
            entity_type="compliance_case", entity_id="other-case", requested_by="user1",
            rationale="report", required_approvals=1, approval_count=1,
            status="approved", expires_at=NOW)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", approval_request_id="ap1", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id", AsyncMock(return_value=approval)):
            with pytest.raises(InvalidTransition):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_report_to_authority_approval_not_approved(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        approval = ApprovalRequest(
            approval_request_id="ap1", action_type="decision_report_to_authority",
            entity_type="compliance_case", entity_id=c.case_id, requested_by="user1",
            rationale="report", required_approvals=1, approval_count=0,
            status="pending", expires_at=NOW)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", approval_request_id="ap1", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id", AsyncMock(return_value=approval)):
            with pytest.raises(ApprovalRequired):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_report_to_authority_approval_already_consumed(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        approval = ApprovalRequest(
            approval_request_id="ap1", action_type="decision_report_to_authority",
            entity_type="compliance_case", entity_id=c.case_id, requested_by="user1",
            rationale="report", required_approvals=1, approval_count=1,
            status="approved", expires_at=NOW, executed_at=NOW)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", approval_request_id="ap1", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id", AsyncMock(return_value=approval)):
            with pytest.raises(ApprovalConsumed):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_report_to_authority_approval_not_found(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", approval_request_id="ap1", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_report_to_authority_concurrent_consume_race(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        approval = ApprovalRequest(
            approval_request_id="ap1", action_type="decision_report_to_authority",
            entity_type="compliance_case", entity_id=c.case_id, requested_by="user1",
            rationale="report", required_approvals=1, approval_count=1,
            status="approved", expires_at=NOW)
        req = RecordDecisionRequest(decision_type=DecisionType.REPORT_TO_AUTHORITY_RECOMMENDED,
                                    rationale="Must report", approval_request_id="ap1", expected_version=3)
        uow_mock = make_uow_mock()
        mock_consume = AsyncMock(return_value=None)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.ApprovalRepo.fetch_by_id", AsyncMock(return_value=approval)), \
             patch("workbench.repos.ApprovalRepo.consume", mock_consume):
            with pytest.raises(ApprovalConsumed):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)
        mock_consume.assert_awaited_once_with("ap1", uow_mock.__aenter__.return_value.conn)

    @pytest.mark.asyncio
    async def test_decision_idempotency_replay(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="test", expected_version=3)
        fake_resp = CaseDecisionResponse(
            case=CaseAdminView(**c.model_dump()), decision={"decision_type": "warning"}, version=3)
        stored_body = fake_resp.model_dump_json()
        body_hash = HASH({"decision_type": "warning", "rationale": "test",
                          "approval_request_id": None, "expected_version": 3})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="POST",
                 request_path=f"/api/v1/cases/{c.case_id}/decisions",
                 request_body_sha256=body_hash,
                 response_status=201, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await CaseService(mock_db).record_decision(
                MOCK_USER, c.case_id, req, idempotency_key="dup-key")
        assert result.case.case_id == c.case_id


class TestListDecisions:
    def make_decisions(self, case_id):
        return [
            Decision(decision_id=f"d1", case_id=case_id, decision_type="warning",
                     rationale="first", decided_by="user1", decided_at=NOW,
                     is_final=False, version=1, created_at=NOW),
            Decision(decision_id=f"d2", case_id=case_id, decision_type="no_action",
                     rationale="second", decided_by="user1", decided_at=NOW,
                     is_final=False, version=1, created_at=NOW),
        ]

    @pytest.mark.asyncio
    async def test_assigned_owner_lists(self, mock_db):
        c = make_case(assigned_to="user1", status="resolved")
        mock_auth = AsyncMock()
        mock_list = AsyncMock(return_value=self.make_decisions(c.case_id))
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, mock_auth), \
             patch("workbench.repos.DecisionRepo.list_by_case", mock_list):
            result = await CaseService(mock_db).list_decisions(MOCK_USER, c.case_id)
        assert len(result) == 2
        mock_auth.assert_awaited_once()
        assert mock_auth.await_args[0][1] == "case:read_assigned"
        mock_list.assert_awaited_once_with(c.case_id)

    @pytest.mark.asyncio
    async def test_admin_read_fallback(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(assigned_to="user1", status="resolved")
        admin = ApplicationUser(user_id="admin1", role="admin", permissions=["case:read"])
        mock_list = AsyncMock(return_value=self.make_decisions(c.case_id))
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("case:read_assigned"), AsyncMock(),
             ])), \
             patch("workbench.repos.DecisionRepo.list_by_case", mock_list):
            result = await CaseService(mock_db).list_decisions(admin, c.case_id)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_non_owner_read_assigned_denied(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(assigned_to="user1", status="resolved")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 AsyncMock(), PermissionDeniedError("case:read"),
             ])):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).list_decisions(OTHER_USER, c.case_id)

    @pytest.mark.asyncio
    async def test_no_permission_returns_not_found(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(assigned_to="user1", status="resolved")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("case:read_assigned"),
                 PermissionDeniedError("case:read"),
             ])):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).list_decisions(NO_PERM_USER, c.case_id)

    @pytest.mark.asyncio
    async def test_missing_case_404(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).list_decisions(MOCK_USER, "bad-id")

    @pytest.mark.asyncio
    async def test_decision_version_conflict(self, mock_db):
        c = make_case(status="decision_pending", assigned_to="user1", version=3)
        c_dump = c.model_dump()
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="test", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[c_dump, None])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")), \
             patch("workbench.repos.DecisionRepo.create", AsyncMock()):
            with pytest.raises(VersionConflict):
                await CaseService(mock_db).record_decision(MOCK_USER, c.case_id, req)

    @pytest.mark.asyncio
    async def test_decision_not_found(self, mock_db):
        req = RecordDecisionRequest(decision_type=DecisionType.WARNING, rationale="test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CaseService(mock_db).record_decision(MOCK_USER, "bad-id", req)


class TestCaseAdminView:
    def test_strips_internal_fields(self):
        view = CaseAdminView(
            case_id="c1", title="Test", scope_id="hq_main",
            status="open", priority="medium", created_by="user1",
            version=1, created_at=NOW, updated_at=NOW,
        )
        assert not hasattr(view, "current_disposition_id")
        assert not hasattr(view, "closure_approval_id")


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_replay_returns_stored_response(self, mock_db):
        c = make_case(status="assigned", assigned_to="user1", version=2)
        req = TransitionCaseRequest(target_status="under_review", expected_version=2)
        fake_resp = CaseAdminResponse(
            case=CaseAdminView(**c.model_dump()), version=2)
        stored_body = fake_resp.model_dump_json()
        body_hash = HASH({"target_status": "under_review", "expected_version": 2, "resolution": None})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path=f"/api/v1/cases/{c.case_id}/transition",
                 request_body_sha256=body_hash,
                 response_status=200, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await CaseService(mock_db).transition(
                MOCK_USER, c.case_id, req, idempotency_key="dup-key")
        assert result.case.case_id == c.case_id

    @pytest.mark.asyncio
    async def test_mismatched_body_raises(self, mock_db):
        other_hash = HASH({"target_status": "resolved", "expected_version": 99, "resolution": None})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path="/api/v1/cases/any/transition",
                 request_body_sha256=other_hash,
                 response_status=200, response_body="{}",
                 created_at=NOW,
             ))):
            with pytest.raises(IdempotencyMismatch):
                await CaseService(mock_db).transition(
                    MOCK_USER, "any",
                    TransitionCaseRequest(target_status="under_review", expected_version=2),
                    idempotency_key="dup-key")


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


class TestRouteRegistration:
    def test_approved_routes_present(self):
        from workbench.routers.cases import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/cases/assigned", ("GET",)) in routes
        assert ("/api/v1/cases/{case_id}", ("GET",)) in routes
        assert ("/api/v1/cases/{case_id}/assign", ("PATCH",)) in routes
        assert ("/api/v1/cases/{case_id}/transition", ("PATCH",)) in routes
        assert ("/api/v1/cases/{case_id}/decisions", ("GET",)) in routes
        assert ("/api/v1/cases/{case_id}/decisions", ("POST",)) in routes
        assert ("/api/v1/cases/{case_id}/close", ("POST",)) in routes
        assert ("/api/v1/cases/{case_id}/reopen", ("POST",)) in routes

    def test_obsolete_routes_absent(self):
        from workbench.routers.cases import router
        paths = {r.path for r in router.routes}
        assert "/api/v1/cases/{case_id}/status" not in paths

    def test_exact_count_eight(self):
        from workbench.routers.cases import router
        assert len(router.routes) == 8
