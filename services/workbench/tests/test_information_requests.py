"""Information request service tests (IR1-IR8)."""
import json
import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser, PermissionDeniedError

from workbench.exceptions import (
    IdempotencyMismatch, InvalidAssignee, InvalidTransition,
    ResourceNotFound, VersionConflict, WorkbenchError,
)
from workbench.models import ComplianceCase, InformationRequest
from workbench.schemas.information_requests import (
    AcceptInformationRequest, AcknowledgeInformationRequest,
    CancelInformationRequest, CreateInformationRequest,
    InformationRequestAdminView, InformationRequestMutationResponse,
    InformationRequestResponse, RespondInformationRequest,
    ReturnInformationRequest,
)
from workbench.services.information_request_service import (
    InformationRequestService, _validate_assignee,
)

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

ANALYST = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "info_request:read_assigned", "info_request:respond",
])
COMPLIANCE = ApplicationUser(user_id="user1", role="compliance", permissions=[
    "info_request:create", "info_request:read", "info_request:accept",
    "info_request:return", "info_request:cancel", "case:read_assigned",
])
OTHER_COMPLIANCE = ApplicationUser(user_id="user2", role="compliance", permissions=[
    "info_request:read",
])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "info_request:read", "info_request:cancel",
])


def make_case(**kw):
    defaults = dict(case_id=UID(), title="Test Case",
                    description=None, alert_id=None, investigation_id=None,
                    scope_id="hq_main", status="under_review", priority="medium",
                    risk_level=None, regulatory_frameworks=None,
                    assigned_to="user1", created_by="user1",
                    target_date=None, resolution=None, resolved_at=None,
                    resolved_by=None, closed_at=None, closed_by=None,
                    current_disposition_id=None, closure_approval_id=None,
                    reopen_reason=None,
                    version=2, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ComplianceCase(**defaults)


def make_ir(**kw):
    defaults = dict(ir_id=UID(), case_id="case1", investigation_id=None,
                    created_by="user1", assigned_to="user1",
                    question="Please provide transaction records", due_date=None,
                    status="open", response_text=None, responded_at=None,
                    acceptance_note=None, return_reason=None,
                    accepted_at=None, returned_at=None,
                    accepted_by=None, returned_by=None,
                    cancelled_at=None, cancelled_by=None, cancel_reason=None,
                    version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return InformationRequest(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


UOW_TARGET = "workbench.services.information_request_service.UnitOfWork"
AUTH_TARGET = "workbench.services.information_request_service.authorise"
HASH = lambda body: __import__("hashlib").sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def resp_body(ir, role="analyst"):
    view = InformationRequestAdminView if role == "admin" else InformationRequestResponse
    return InformationRequestMutationResponse(
        information_request=view(**ir.model_dump()), version=ir.version).model_dump_json()


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_open_ir(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.information_request_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)
        assert result.information_request.status == "open"
        assert result.information_request.assigned_to == "user2"
        assert result.information_request.created_by == "user1"
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_create_requires_under_review(self, mock_db):
        c = make_case(status="open", version=1)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(InvalidTransition):
                await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)

    @pytest.mark.asyncio
    async def test_create_case_not_found(self, mock_db):
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await InformationRequestService(mock_db).create(COMPLIANCE, "bad-id", req)

    @pytest.mark.asyncio
    async def test_create_past_due_date_rejected(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       due_date=date(2020, 1, 1), expected_case_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())):
            with pytest.raises(WorkbenchError) as ei:
                await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)
        assert ei.value.code == "INVALID_DUE_DATE"
        assert ei.value.http_status == 400

    @pytest.mark.asyncio
    async def test_create_duplicate_active_ir_rejected(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        active = make_ir(case_id=c.case_id, assigned_to="user2", status="acknowledged")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[active.model_dump()])):
            with pytest.raises(InvalidTransition, match="already exists"):
                await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)

    @pytest.mark.asyncio
    async def test_create_stale_case_version(self, mock_db):
        c = make_case(status="under_review", version=2)
        c_dump = c.model_dump()
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[c_dump, None])), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")), \
             patch("workbench.services.information_request_service._validate_assignee", AsyncMock()):
            with pytest.raises(VersionConflict):
                await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)

    @pytest.mark.asyncio
    async def test_create_invalid_assignee(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="ghost", question="Docs?",
                                       expected_case_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.services.information_request_service._validate_assignee",
                   AsyncMock(side_effect=InvalidAssignee("User not found: ghost"))):
            with pytest.raises(InvalidAssignee):
                await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)

    @pytest.mark.asyncio
    async def test_create_advances_case_and_writes_timeline(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.information_request_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)
        assert mock_timeline.await_count == 2
        events = [a.args[0].event_type for a in mock_timeline.await_args_list]
        assert "case.awaiting_information" in events
        assert "ir.created" in events
        case_events = [a.args[0] for a in mock_timeline.await_args_list
                       if a.args[0].event_type == "case.awaiting_information"]
        assert case_events[0].new_value["status"] == "awaiting_information"
        assert case_events[0].old_value == {"status": "under_review"}

    @pytest.mark.asyncio
    async def test_create_notifies_assignee(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.information_request_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)
        mock_notify.assert_awaited_once()
        args = mock_notify.await_args[0][0]
        assert args.notification_type == "ir_created"
        assert args.user_id == "user2"
        assert args.entity_type == "information_request"

    @pytest.mark.asyncio
    async def test_create_writes_outbox(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.services.information_request_service._validate_assignee", AsyncMock()), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InformationRequestService(mock_db).create(COMPLIANCE, c.case_id, req)
        assert mock_outbox.await_count == 2
        events = [a.args[0].event_type for a in mock_outbox.await_args_list]
        assert "ir.created" in events
        assert "case.awaiting_info" in events
        ir_event = [a.args[0] for a in mock_outbox.await_args_list
                    if a.args[0].event_type == "ir.created"][0]
        assert ir_event.actor_id == "user1"
        assert ir_event.actor_role == "compliance"
        assert ir_event.payload["schema_version"] == 1
        assert "question_sha256" in ir_event.payload["after"]

    @pytest.mark.asyncio
    async def test_create_replay_returns_stored_response(self, mock_db):
        c = make_case(status="under_review", version=2)
        req = CreateInformationRequest(assigned_to="user2", question="Docs?",
                                       expected_case_version=2)
        ir = make_ir(case_id=c.case_id, assigned_to="user2", status="open", version=1)
        stored_body = resp_body(ir, role="analyst")
        body_hash = HASH(req.model_dump())
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="POST",
                 request_path=f"/api/v1/cases/{c.case_id}/information-requests",
                 request_body_sha256=body_hash,
                 response_status=201, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await InformationRequestService(mock_db).create(
                COMPLIANCE, c.case_id, req, idempotency_key="dup-key")
        assert result.information_request.ir_id == ir.ir_id
        assert result.version == 1


class TestList:
    @pytest.mark.asyncio
    async def test_admin_lists_all_as_admin_views(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(status="under_review", assigned_to="user1", created_by="user3")
        irs = [make_ir(case_id=c.case_id, assigned_to="user1"),
               make_ir(case_id=c.case_id, assigned_to="user4")]
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos.InfoRequestRepo.list_by_case",
                   AsyncMock(return_value=irs)), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])):
            items, total = await InformationRequestService(mock_db).list_for_case(
                ADMIN, c.case_id)
        assert total == 2
        assert all(isinstance(i, InformationRequestAdminView) for i in items)

    @pytest.mark.asyncio
    async def test_assigned_analyst_sees_only_own(self, mock_db):
        c = make_case(status="under_review", assigned_to="user1")
        mine = make_ir(case_id=c.case_id, assigned_to="user1")
        others = make_ir(case_id=c.case_id, assigned_to="user5")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos.InfoRequestRepo.list_by_case",
                   AsyncMock(return_value=[mine, others])), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await InformationRequestService(mock_db).list_for_case(
                ANALYST, c.case_id)
        assert total == 1
        assert items[0].ir_id == mine.ir_id
        assert isinstance(items[0], InformationRequestResponse)

    @pytest.mark.asyncio
    async def test_compliance_sees_own_created_or_case_assignee(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(status="under_review", assigned_to="user9", created_by="user3")
        own = make_ir(case_id=c.case_id, assigned_to="user6", created_by="user1")
        foreign = make_ir(case_id=c.case_id, assigned_to="user8", created_by="user4")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos.InfoRequestRepo.list_by_case",
                   AsyncMock(return_value=[own, foreign])), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])):
            items, total = await InformationRequestService(mock_db).list_for_case(
                COMPLIANCE, c.case_id)
        assert total == 1
        assert items[0].ir_id == own.ir_id

    @pytest.mark.asyncio
    async def test_compliance_sees_irs_on_assigned_case(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(status="under_review", assigned_to="user1", created_by="user3")
        others = make_ir(case_id=c.case_id, assigned_to="user6", created_by="user4")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos.InfoRequestRepo.list_by_case",
                   AsyncMock(return_value=[others])), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])):
            items, total = await InformationRequestService(mock_db).list_for_case(
                COMPLIANCE, c.case_id)
        assert total == 1
        assert items[0].ir_id == others.ir_id

    @pytest.mark.asyncio
    async def test_list_case_not_found(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await InformationRequestService(mock_db).list_for_case(ADMIN, "bad-id")

    @pytest.mark.asyncio
    async def test_pagination_args(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(status="under_review")
        mock_list = AsyncMock(return_value=[])
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos.InfoRequestRepo.list_by_case", mock_list), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])):
            await InformationRequestService(mock_db).list_for_case(
                COMPLIANCE, c.case_id, status="responded", page=2, per_page=25)
        kwargs = mock_list.call_args.kwargs
        assert kwargs["status"] == "responded"
        assert kwargs["limit"] == 25
        assert kwargs["offset"] == 25

    @pytest.mark.asyncio
    async def test_per_page_capped_at_100(self, mock_db):
        from shared.authorise import PermissionDeniedError
        c = make_case(status="under_review")
        mock_list = AsyncMock(return_value=[])
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch("workbench.repos.InfoRequestRepo.list_by_case", mock_list), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])):
            await InformationRequestService(mock_db).list_for_case(
                COMPLIANCE, c.case_id, page=1, per_page=500)
        assert mock_list.call_args.kwargs["limit"] == 100


class TestGetById:
    @pytest.mark.asyncio
    async def test_assigned_analyst_success(self, mock_db):
        ir = make_ir(assigned_to="user1", status="open")
        c = make_case(case_id=ir.case_id, status="under_review")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).get_by_id(ANALYST, ir.ir_id)
        assert result.ir_id == ir.ir_id
        assert result.question == ir.question

    @pytest.mark.asyncio
    async def test_nonexistent(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await InformationRequestService(mock_db).get_by_id(ANALYST, "bad-id")

    @pytest.mark.asyncio
    async def test_foreign_compliance_denied(self, mock_db):
        from shared.authorise import PermissionDeniedError
        ir = make_ir(assigned_to="user5", created_by="user6", status="open")
        c = make_case(case_id=ir.case_id, assigned_to="user5", created_by="user6")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(ResourceNotFound):
                await InformationRequestService(mock_db).get_by_id(OTHER_COMPLIANCE, ir.ir_id)

    @pytest.mark.asyncio
    async def test_admin_gets_admin_view(self, mock_db):
        from shared.authorise import PermissionDeniedError
        ir = make_ir(assigned_to="user1", created_by="user3", status="open")
        c = make_case(case_id=ir.case_id, assigned_to="user1", created_by="user3")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock(side_effect=[
                 PermissionDeniedError("info_request:read_assigned"), None,
             ])), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).get_by_id(ADMIN, ir.ir_id)
        assert isinstance(result, InformationRequestAdminView)
        assert not hasattr(result, "question")
        assert not hasattr(result, "assigned_to")


class TestAcknowledge:
    @pytest.mark.asyncio
    async def test_open_to_acknowledged(self, mock_db):
        ir = make_ir(assigned_to="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).acknowledge(
                ANALYST, ir.ir_id, req)
        assert result.information_request.status == "acknowledged"
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_returned_reacknowledged(self, mock_db):
        ir = make_ir(assigned_to="user1", status="returned", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=2)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).acknowledge(
                ANALYST, ir.ir_id, req)
        assert result.information_request.status == "acknowledged"
        assert mock_timeline.await_args[0][0].event_type == "ir.re_acknowledged"

    @pytest.mark.asyncio
    async def test_re_acknowledge_no_notification(self, mock_db):
        ir = make_ir(assigned_to="user1", status="returned", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=2)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).acknowledge(ANALYST, ir.ir_id, req)
        mock_notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_already_acknowledged_idempotent(self, mock_db):
        ir = make_ir(assigned_to="user1", status="acknowledged", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).acknowledge(
                ANALYST, ir.ir_id, req)
        assert result.information_request.status == "acknowledged"
        assert result.version == 3

    @pytest.mark.asyncio
    async def test_responded_cannot_acknowledge(self, mock_db):
        ir = make_ir(assigned_to="user1", status="responded", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(InvalidTransition):
                await InformationRequestService(mock_db).acknowledge(ANALYST, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        ir = make_ir(assigned_to="user1", status="open", version=1)
        ir_dump = ir.model_dump()
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir_dump, c.model_dump(), None,
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await InformationRequestService(mock_db).acknowledge(ANALYST, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_creator_notified_from_open(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user9", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=1)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).acknowledge(ANALYST, ir.ir_id, req)
        mock_notify.assert_awaited_once()
        args = mock_notify.await_args[0][0]
        assert args.notification_type == "ir_acknowledged"
        assert args.user_id == "user9"

    @pytest.mark.asyncio
    async def test_outbox_event(self, mock_db):
        ir = make_ir(assigned_to="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcknowledgeInformationRequest(expected_version=1)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InformationRequestService(mock_db).acknowledge(ANALYST, ir.ir_id, req)
        mock_outbox.assert_awaited_once()
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "ir.acknowledged"
        assert args.payload["before"] == {"status": "open", "version": 1}
        assert args.payload["after"] == {"status": "acknowledged", "version": 2}


class TestRespond:
    @pytest.mark.asyncio
    async def test_acknowledged_to_responded(self, mock_db):
        ir = make_ir(assigned_to="user1", status="acknowledged", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = RespondInformationRequest(response_text="Here are the records", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).respond(ANALYST, ir.ir_id, req)
        assert result.information_request.status == "responded"
        assert result.information_request.response_text == "Here are the records"
        assert result.information_request.responded_at is not None
        assert result.version == 3

    @pytest.mark.asyncio
    async def test_already_responded_idempotent(self, mock_db):
        ir = make_ir(assigned_to="user1", status="responded", version=3,
                     response_text="done")
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = RespondInformationRequest(response_text="done", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).respond(ANALYST, ir.ir_id, req)
        assert result.information_request.status == "responded"
        assert result.version == 3

    @pytest.mark.asyncio
    async def test_open_cannot_respond(self, mock_db):
        ir = make_ir(assigned_to="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = RespondInformationRequest(response_text="docs", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(InvalidTransition):
                await InformationRequestService(mock_db).respond(ANALYST, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_creator_notified(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user9", status="acknowledged", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = RespondInformationRequest(response_text="records attached", expected_version=2)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).respond(ANALYST, ir.ir_id, req)
        mock_notify.assert_awaited_once()
        args = mock_notify.await_args[0][0]
        assert args.notification_type == "ir_responded"
        assert args.user_id == "user9"
        assert args.body == "records attached"

    @pytest.mark.asyncio
    async def test_outbox_hashes_response(self, mock_db):
        ir = make_ir(assigned_to="user1", status="acknowledged", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = RespondInformationRequest(response_text="sensitive data", expected_version=2)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InformationRequestService(mock_db).respond(ANALYST, ir.ir_id, req)
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "ir.responded"
        assert args.payload["after"]["response_text_sha256"] == HASH("sensitive data")
        assert "sensitive data" not in json.dumps(args.payload)

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        ir = make_ir(assigned_to="user1", status="acknowledged", version=2)
        ir_dump = ir.model_dump()
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = RespondInformationRequest(response_text="docs", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir_dump, c.model_dump(), None,
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await InformationRequestService(mock_db).respond(ANALYST, ir.ir_id, req)


class TestAccept:
    @pytest.mark.asyncio
    async def test_responded_to_accepted(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="responded",
                     response_text="docs", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcceptInformationRequest(acceptance_note="Good enough", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).accept(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "accepted"
        assert result.information_request.accepted_by == "user1"
        assert result.version == 4

    @pytest.mark.asyncio
    async def test_already_accepted_idempotent(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="accepted", version=4,
                     accepted_by="user1")
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcceptInformationRequest(expected_version=4)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).accept(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "accepted"
        assert result.version == 4

    @pytest.mark.asyncio
    async def test_open_cannot_accept(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcceptInformationRequest(expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(InvalidTransition):
                await InformationRequestService(mock_db).accept(COMPLIANCE, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_non_creator_permission_denied(self, mock_db):
        from shared.authorise import PermissionDeniedError
        ir = make_ir(assigned_to="user5", created_by="user5", status="responded", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcceptInformationRequest(expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock(side_effect=PermissionDeniedError("info_request:accept"))), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(PermissionDeniedError):
                await InformationRequestService(mock_db).accept(COMPLIANCE, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_case_assignee_and_analyst_notified(self, mock_db):
        ir = make_ir(assigned_to="user5", created_by="user1", status="responded",
                     response_text="docs", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information", assigned_to="user9")
        req = AcceptInformationRequest(acceptance_note="ok", expected_version=3)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).accept(COMPLIANCE, ir.ir_id, req)
        assert mock_notify.await_count == 2
        recipients = {a.args[0].user_id for a in mock_notify.await_args_list}
        assert recipients == {"user9", "user5"}
        types = {a.args[0].notification_type for a in mock_notify.await_args_list}
        assert types == {"ir_accepted"}

    @pytest.mark.asyncio
    async def test_outbox_hashes_acceptance_note(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="responded", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = AcceptInformationRequest(acceptance_note="approved by me", expected_version=3)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InformationRequestService(mock_db).accept(COMPLIANCE, ir.ir_id, req)
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "ir.accepted"
        assert args.payload["after"]["acceptance_note_sha256"] == HASH("approved by me")
        assert args.payload["after"]["accepted_by"] == "user1"
        assert args.payload["after"]["case_resumed_triggered"] is True


class TestReturn:
    @pytest.mark.asyncio
    async def test_responded_to_returned(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="responded",
                     response_text="weak", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = ReturnInformationRequest(return_reason="Needs evidence", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).return_(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "returned"
        assert result.information_request.return_reason == "Needs evidence"
        assert result.information_request.returned_by == "user1"
        assert result.version == 4

    @pytest.mark.asyncio
    async def test_already_returned_idempotent(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="returned", version=4,
                     returned_by="user1", return_reason="n/a")
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = ReturnInformationRequest(return_reason="n/a", expected_version=4)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).return_(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "returned"
        assert result.version == 4

    @pytest.mark.asyncio
    async def test_acknowledged_cannot_return(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="acknowledged", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = ReturnInformationRequest(return_reason="no", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(InvalidTransition):
                await InformationRequestService(mock_db).return_(COMPLIANCE, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_analyst_notified_for_rework(self, mock_db):
        ir = make_ir(assigned_to="user5", created_by="user1", status="responded", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = ReturnInformationRequest(return_reason="rework", expected_version=3)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).return_(COMPLIANCE, ir.ir_id, req)
        mock_notify.assert_awaited_once()
        args = mock_notify.await_args[0][0]
        assert args.notification_type == "ir_returned"
        assert args.user_id == "user5"
        assert args.body == "rework"

    @pytest.mark.asyncio
    async def test_outbox_hashes_return_reason(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="responded", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = ReturnInformationRequest(return_reason="missing docs", expected_version=3)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InformationRequestService(mock_db).return_(COMPLIANCE, ir.ir_id, req)
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "ir.returned"
        assert args.payload["after"]["return_reason_sha256"] == HASH("missing docs")
        assert args.payload["after"]["returned_by"] == "user1"


class TestCancel:
    @pytest.mark.asyncio
    async def test_open_to_cancelled(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="Resolved in system", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "cancelled"
        assert result.information_request.cancelled_by == "user1"
        assert result.information_request.cancel_reason == "Resolved in system"
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_acknowledged_to_cancelled(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="acknowledged", version=2)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="dup", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "cancelled"

    @pytest.mark.asyncio
    async def test_responded_cannot_cancel(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="responded", version=3)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="late", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            with pytest.raises(InvalidTransition):
                await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)

    @pytest.mark.asyncio
    async def test_already_cancelled_idempotent(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="cancelled", version=2,
                     cancelled_by="user1", cancel_reason="n/a")
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="n/a", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])):
            result = await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)
        assert result.information_request.status == "cancelled"
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_no_notification_on_cancel(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="superseded", expected_version=1)
        uow_mock = make_uow_mock()
        mock_notify = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)
        mock_notify.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_admin_cancels_other_creator(self, mock_db):
        ir = make_ir(assigned_to="user5", created_by="user5", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="admin override", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await InformationRequestService(mock_db).cancel(ADMIN, ir.ir_id, req)
        assert result.information_request.status == "cancelled"
        assert result.information_request.cancelled_by == "admin1"

    @pytest.mark.asyncio
    async def test_outbox_hashes_cancel_reason(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="open", version=1)
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="closed elsewhere", expected_version=1)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir.model_dump(), c.model_dump(),
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.NotificationRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "ir.cancelled"
        assert args.payload["after"]["cancel_reason_sha256"] == HASH("closed elsewhere")
        assert args.payload["after"]["cancelled_by"] == "user1"

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        ir = make_ir(assigned_to="user1", created_by="user1", status="open", version=1)
        ir_dump = ir.model_dump()
        c = make_case(case_id=ir.case_id, status="awaiting_information")
        req = CancelInformationRequest(cancel_reason="dup", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 ir_dump, c.model_dump(), None,
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await InformationRequestService(mock_db).cancel(COMPLIANCE, ir.ir_id, req)


class TestAdminView:
    def test_strips_content_fields(self):
        view = InformationRequestAdminView(
            ir_id="ir1", case_id="c1", investigation_id=None,
            created_by="user1", due_date=None, status="open",
            responded_at=None, accepted_at=None, returned_at=None,
            accepted_by=None, returned_by=None, cancelled_at=None,
            cancelled_by=None, version=1, created_at=NOW, updated_at=NOW,
        )
        assert not hasattr(view, "question")
        assert not hasattr(view, "assigned_to")
        assert not hasattr(view, "response_text")
        assert not hasattr(view, "acceptance_note")
        assert not hasattr(view, "return_reason")
        assert not hasattr(view, "cancel_reason")


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_replay_returns_stored_response(self, mock_db):
        ir = make_ir(assigned_to="user1", status="acknowledged", version=2)
        req = RespondInformationRequest(response_text="docs", expected_version=2)
        fake_resp = InformationRequestMutationResponse(
            information_request=InformationRequestResponse(**ir.model_dump()), version=2)
        stored_body = fake_resp.model_dump_json()
        body_hash = HASH({"response_text": "docs", "expected_version": 2})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path=f"/api/v1/information-requests/{ir.ir_id}/respond",
                 request_body_sha256=body_hash,
                 response_status=200, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await InformationRequestService(mock_db).respond(
                ANALYST, ir.ir_id, req, idempotency_key="dup-key")
        assert result.information_request.ir_id == ir.ir_id
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_mismatched_body_raises(self, mock_db):
        other_hash = HASH({"response_text": "different", "expected_version": 99})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path="/api/v1/information-requests/any/respond",
                 request_body_sha256=other_hash,
                 response_status=200, response_body="{}",
                 created_at=NOW,
             ))):
            with pytest.raises(IdempotencyMismatch):
                await InformationRequestService(mock_db).respond(
                    ANALYST, "any",
                    RespondInformationRequest(response_text="docs", expected_version=2),
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

    @pytest.mark.asyncio
    async def test_user_lacks_scope(self, mock_db):
        conn_mock = MagicMock()
        mock_db.fetch_one = AsyncMock(return_value={"status": "active"})
        mock_db.fetch_all = AsyncMock(return_value=[{"scope_id": "eu_main"}])
        with pytest.raises(InvalidAssignee, match="lacks scope"):
            await _validate_assignee(mock_db, "user_x", "hq_main", conn_mock)


class TestRouteRegistration:
    def test_approved_routes_present(self):
        from workbench.routers.information_requests import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/cases/{case_id}/information-requests", ("POST",)) in routes
        assert ("/api/v1/cases/{case_id}/information-requests", ("GET",)) in routes
        assert ("/api/v1/information-requests/assigned", ("GET",)) in routes
        assert ("/api/v1/information-requests/{ir_id}", ("GET",)) in routes
        assert ("/api/v1/information-requests/{ir_id}/acknowledge", ("PATCH",)) in routes
        assert ("/api/v1/information-requests/{ir_id}/respond", ("PATCH",)) in routes
        assert ("/api/v1/information-requests/{ir_id}/accept", ("PATCH",)) in routes
        assert ("/api/v1/information-requests/{ir_id}/return", ("PATCH",)) in routes
        assert ("/api/v1/information-requests/{ir_id}/cancel", ("POST",)) in routes

    def test_static_assigned_precedes_dynamic_detail(self):
        from workbench.routers.information_requests import router
        paths = [r.path for r in router.routes]
        assert paths.index("/api/v1/information-requests/assigned") < \
            paths.index("/api/v1/information-requests/{ir_id}")

    def test_obsolete_routes_absent(self):
        from workbench.routers.information_requests import router
        paths = {r.path for r in router.routes}
        assert "/api/v1/information-requests/{ir_id}/reopen" not in paths
        assert "/api/v1/information-requests/{ir_id}/submit" not in paths
        assert "/api/v1/cases/{case_id}/information-requests/{ir_id}" not in paths

    def test_exact_count_nine(self):
        from workbench.routers.information_requests import router
        assert len(router.routes) == 9


class TestListAssigned:
    @pytest.mark.asyncio
    async def test_own_assigned_returned_with_full_dto(self, mock_db):
        ir = make_ir(assigned_to="user1", status="open",
                     due_date=date(2026, 1, 31), question="Send statements")
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[ir.model_dump()])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 1})), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")
        assert total == 1
        assert items[0].ir_id == ir.ir_id
        assert items[0].question == "Send statements"
        assert items[0].due_date == date(2026, 1, 31)

    @pytest.mark.asyncio
    async def test_query_restricts_to_current_user(self, mock_db):
        mock_fetch_all = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch_all), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 0})), \
             patch(AUTH_TARGET, AsyncMock()):
            await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")
        sql, params = mock_fetch_all.call_args[0][1], mock_fetch_all.call_args[0][2]
        assert "ir.assigned_to = $1" in sql
        assert params[0] == "user1"

    @pytest.mark.asyncio
    async def test_status_filter_and_pagination(self, mock_db):
        mock_fetch_all = AsyncMock(return_value=[])
        mock_fetch_one = AsyncMock(return_value={"count": 7})
        with patch("workbench.repos._fetch_all", mock_fetch_all), \
             patch("workbench.repos._fetch_one", mock_fetch_one), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await InformationRequestService(mock_db).list_assigned(
                ANALYST, "hq_main", status="returned", page=2, per_page=10)
        assert total == 7
        assert items == []
        list_params = mock_fetch_all.call_args[0][2]
        assert list_params[0] == "user1"
        assert list_params[2] == "returned"
        assert list_params[3:] == [10, 10]
        assert mock_fetch_one.call_args[0][2][2] == "returned"

    @pytest.mark.asyncio
    async def test_real_total_count(self, mock_db):
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 42})), \
             patch(AUTH_TARGET, AsyncMock()):
            _, total = await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")
        assert total == 42

    @pytest.mark.asyncio
    async def test_empty_inbox(self, mock_db):
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 0})), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_authorise_called_with_read_assigned(self, mock_db):
        mock_auth = AsyncMock()
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 0})), \
             patch(AUTH_TARGET, mock_auth):
            await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")
        mock_auth.assert_awaited_once()
        assert mock_auth.await_args[0][1] == "info_request:read_assigned"

    @pytest.mark.asyncio
    async def test_permission_denied_propagates(self, mock_db):
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 0})), \
             patch(AUTH_TARGET, AsyncMock(
                 side_effect=PermissionDeniedError("info_request:read_assigned"))):
            with pytest.raises(PermissionDeniedError):
                await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")

    @pytest.mark.asyncio
    async def test_no_mutation_side_effects(self, mock_db):
        """Read-only: only SELECT list/count run; no outbox/timeline/idempotency writes."""
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value={"count": 0})), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.services.information_request_service.UnitOfWork") as uow, \
             patch("workbench.repos.TimelineRepo.insert") as tl, \
             patch("workbench.repos.OutboxRepo.insert") as ob, \
             patch("workbench.repos.NotificationRepo.insert") as nt:
            await InformationRequestService(mock_db).list_assigned(ANALYST, "hq_main")
        uow.assert_not_called()
        tl.assert_not_called()
        ob.assert_not_called()
        nt.assert_not_called()
