"""Investigation service tests."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser

from workbench.exceptions import (
    IdempotencyMismatch, InvalidAssignee, InvalidTransition,
    ResourceNotFound, VersionConflict,
)
from workbench.models import Investigation
from workbench.schemas.investigations import (
    CancelInvestigationRequest, InvestigationMutationResponse,
    InvestigationResponse, TransitionInvestigationRequest,
    UpdateInvestigationRequest,
)
from workbench.services.investigation_service import InvestigationService, _validate_assignee

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

MOCK_USER = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "investigation:read_own", "investigation:assign",
    "investigation:transition", "investigation:modify_findings",
])
ADMIN_USER = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "investigation:read", "investigation:assign",
    "investigation:modify_findings",
])
OTHER_USER = ApplicationUser(user_id="user3", role="analyst", permissions=[
    "investigation:read_own",
])
NO_PERM_USER = ApplicationUser(user_id="analyst1", role="analyst", permissions=[
    "investigation:read_own", "investigation:transition",
])
COMPLIANCE_USER = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "investigation:read_own", "investigation:read",
])


def make_inv(**kw):
    defaults = dict(investigation_id=UID(), title="Test Investigation",
                    description=None, alert_id=None, scope_id="hq_main",
                    status="open", priority="medium", assigned_to=None,
                    created_by="user1", findings_text=None, findings_refs=None,
                    conclusion=None, started_at=None, submitted_at=None,
                    completed_at=None, return_reason=None,
                    version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Investigation(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


UOW_TARGET = "workbench.services.investigation_service.UnitOfWork"
AUTH_TARGET = "workbench.services.investigation_service.authorise"
HASH = lambda body: __import__("hashlib").sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class TestListAssigned:
    @pytest.mark.asyncio
    async def test_own_investigations_only(self, mock_db):
        inv = make_inv(assigned_to="user1", status="active")
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[inv.model_dump()])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            items, total = await InvestigationService(mock_db).list_assigned(MOCK_USER, "hq_main")
        assert len(items) == 1
        assert items[0].investigation_id == inv.investigation_id

    @pytest.mark.asyncio
    async def test_filtering(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()):
            await InvestigationService(mock_db).list_assigned(MOCK_USER, "hq_main", status="active", priority="high")
        assert "assigned_to" in mock_fetch.call_args[0][1]

    @pytest.mark.asyncio
    async def test_authorise_called(self, mock_db):
        mock_auth = AsyncMock()
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, mock_auth):
            await InvestigationService(mock_db).list_assigned(MOCK_USER, "hq_main")
        mock_auth.assert_awaited_once()


class TestGetById:
    @pytest.mark.asyncio
    async def test_assigned_user_success(self, mock_db):
        inv = make_inv(assigned_to="user1", status="active")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch(AUTH_TARGET, AsyncMock()):
            result = await InvestigationService(mock_db).get_by_id(MOCK_USER, inv.investigation_id)
        assert result.investigation_id == inv.investigation_id

    @pytest.mark.asyncio
    async def test_nonexistent(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await InvestigationService(mock_db).get_by_id(MOCK_USER, "no-such-id")

    @pytest.mark.asyncio
    async def test_no_permission(self, mock_db):
        inv = make_inv(assigned_to="user1", status="active")
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._fetch_all", AsyncMock(return_value=[])):
            with pytest.raises(ResourceNotFound):
                await InvestigationService(mock_db).get_by_id(OTHER_USER, inv.investigation_id)


class TestUpdate:
    @pytest.mark.asyncio
    async def test_update_findings_active(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = UpdateInvestigationRequest(findings_text="New analysis", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).update(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.findings_text == "New analysis"

    @pytest.mark.asyncio
    async def test_update_conclusion_only(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = UpdateInvestigationRequest(conclusion="Concluded", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).update(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.conclusion == "Concluded"

    @pytest.mark.asyncio
    async def test_update_findings_returned(self, mock_db):
        inv = make_inv(status="returned", assigned_to="user1", version=3,
                       return_reason="needs evidence")
        req = UpdateInvestigationRequest(findings_text="Updated evidence", conclusion="Now conclusive",
                                         expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).update(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.findings_text == "Updated evidence"
        assert result.investigation.conclusion == "Now conclusive"

    @pytest.mark.asyncio
    async def test_wrong_state_for_update(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = UpdateInvestigationRequest(findings_text="test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(InvalidTransition):
                await InvestigationService(mock_db).update(MOCK_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_no_investigation_raises(self, mock_db):
        req = UpdateInvestigationRequest(findings_text="test", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await InvestigationService(mock_db).update(MOCK_USER, "bad-id", req)


class TestTransition:
    @pytest.mark.asyncio
    async def test_open_to_active(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = TransitionInvestigationRequest(target_status="active", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "active"

    @pytest.mark.asyncio
    async def test_active_to_submitted(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = TransitionInvestigationRequest(target_status="submitted", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "submitted"
        assert result.investigation.submitted_at is not None

    @pytest.mark.asyncio
    async def test_submitted_to_completed(self, mock_db):
        inv = make_inv(status="submitted", assigned_to="user1", version=3)
        req = TransitionInvestigationRequest(target_status="completed", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "completed"
        assert result.investigation.completed_at is not None

    @pytest.mark.asyncio
    async def test_submitted_to_returned(self, mock_db):
        inv = make_inv(status="submitted", assigned_to="user1", version=3)
        req = TransitionInvestigationRequest(target_status="returned", return_reason="needs work",
                                             expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "returned"
        assert result.investigation.return_reason == "needs work"

    @pytest.mark.asyncio
    async def test_returned_to_active_clears_reason(self, mock_db):
        inv = make_inv(status="returned", assigned_to="user1", version=3,
                       return_reason="needs more evidence")
        req = TransitionInvestigationRequest(target_status="active", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "active"
        assert result.investigation.return_reason is None

    @pytest.mark.asyncio
    async def test_returned_requires_reason(self, mock_db):
        inv = make_inv(status="submitted", assigned_to="user1", version=3)
        req = TransitionInvestigationRequest(target_status="returned", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(InvalidAssignee, match="return_reason required"):
                await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_invalid_transition(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = TransitionInvestigationRequest(target_status="completed", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(InvalidTransition):
                await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        inv = make_inv(status="open", version=1)
        inv_dump = inv.model_dump()
        req = TransitionInvestigationRequest(target_status="active", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 inv_dump, None,
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_active_to_cancelled_not_allowed_in_transition(self, mock_db):
        inv = make_inv(status="active", version=2)
        req = TransitionInvestigationRequest(target_status="cancelled", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(InvalidTransition):
                await InvestigationService(mock_db).transition(MOCK_USER, inv.investigation_id, req)


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_from_open(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = CancelInvestigationRequest(cancel_reason="not needed", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_from_active(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = CancelInvestigationRequest(cancel_reason="abandoned", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_from_submitted(self, mock_db):
        inv = make_inv(status="submitted", assigned_to="user1", version=3)
        req = CancelInvestigationRequest(cancel_reason="withdrawn", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_from_returned(self, mock_db):
        inv = make_inv(status="returned", assigned_to="user1", version=3,
                       return_reason="needs evidence")
        req = CancelInvestigationRequest(cancel_reason="closing", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "cancelled"

    @pytest.mark.asyncio
    async def test_completed_cancellation_rejected(self, mock_db):
        inv = make_inv(status="completed", assigned_to="user1", version=4)
        req = CancelInvestigationRequest(cancel_reason="late", expected_version=4)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(InvalidTransition):
                await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_cancelled_is_idempotent(self, mock_db):
        inv = make_inv(status="cancelled", assigned_to="user1", version=4)
        req = CancelInvestigationRequest(cancel_reason="already done", expected_version=4)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            result = await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        assert result.investigation.status == "cancelled"
        assert result.investigation.version == 4

    @pytest.mark.asyncio
    async def test_analyst_without_permission_denied(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = CancelInvestigationRequest(cancel_reason="nope", expected_version=1)
        uow_mock = make_uow_mock()
        from shared.authorise import PermissionDeniedError
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock(side_effect=PermissionDeniedError("investigation:assign"))), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(PermissionDeniedError):
                await InvestigationService(mock_db).cancel(NO_PERM_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_compliance_cancellation_denied(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = CancelInvestigationRequest(cancel_reason="nope", expected_version=1)
        uow_mock = make_uow_mock()
        from shared.authorise import PermissionDeniedError
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock(side_effect=PermissionDeniedError("investigation:assign"))), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())):
            with pytest.raises(PermissionDeniedError):
                await InvestigationService(mock_db).cancel(COMPLIANCE_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_admin_cancellation_succeeds(self, mock_db):
        inv = make_inv(status="open", version=1)
        req = CancelInvestigationRequest(cancel_reason="admin override", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")):
            result = await InvestigationService(mock_db).cancel(ADMIN_USER, inv.investigation_id, req)
        assert result.investigation.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_reason_required(self, mock_db):
        with pytest.raises(Exception):
            CancelInvestigationRequest(cancel_reason="", expected_version=1)

    @pytest.mark.asyncio
    async def test_stale_version_returns_409(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        inv_dump = inv.model_dump()
        req = CancelInvestigationRequest(cancel_reason="done", expected_version=2)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(side_effect=[
                 inv_dump, None,
             ])), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 0")):
            with pytest.raises(VersionConflict):
                await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)

    @pytest.mark.asyncio
    async def test_cancellation_comment_created(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = CancelInvestigationRequest(cancel_reason="abandoned", expected_version=2)
        uow_mock = make_uow_mock()
        mock_comment_create = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.CommentRepo.create", mock_comment_create):
            await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        mock_comment_create.assert_awaited_once()
        args = mock_comment_create.await_args[0][0]
        assert args.content == "abandoned"
        assert args.entity_type == "investigation"
        assert args.author_id == "user1"

    @pytest.mark.asyncio
    async def test_cancellation_notification_created(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = CancelInvestigationRequest(cancel_reason="done", expected_version=2)
        uow_mock = make_uow_mock()
        mock_notify_create = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.NotificationRepo.insert", mock_notify_create):
            await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        mock_notify_create.assert_awaited_once()
        args = mock_notify_create.await_args[0][0]
        assert args.notification_type == "investigation_cancelled"
        assert args.user_id == "user1"

    @pytest.mark.asyncio
    async def test_cancellation_timeline_created(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = CancelInvestigationRequest(cancel_reason="done", expected_version=2)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline):
            await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        mock_timeline.assert_awaited_once()
        args = mock_timeline.await_args[0][0]
        assert args.event_type == "investigation.cancelled"

    @pytest.mark.asyncio
    async def test_cancellation_outbox_created(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = CancelInvestigationRequest(cancel_reason="done", expected_version=2)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        mock_outbox.assert_awaited_once()
        args = mock_outbox.await_args[0][0]
        assert args.event_type == "investigation.cancelled"

    @pytest.mark.asyncio
    async def test_rollback_on_failure(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = CancelInvestigationRequest(cancel_reason="done", expected_version=2)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=inv.model_dump())), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock(side_effect=RuntimeError("db fail"))):
            with pytest.raises(RuntimeError):
                await InvestigationService(mock_db).cancel(MOCK_USER, inv.investigation_id, req)
        uow_mock.__aexit__.assert_awaited()


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_replay_returns_stored_response(self, mock_db):
        inv = make_inv(status="active", assigned_to="user1", version=2)
        req = TransitionInvestigationRequest(target_status="submitted", expected_version=2)
        fake_resp = InvestigationMutationResponse(
            investigation=InvestigationResponse(**inv.model_dump()), version=2)
        stored_body = fake_resp.model_dump_json()
        body_hash = HASH({"target_status": "submitted", "return_reason": None, "expected_version": 2})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path=f"/api/v1/investigations/{inv.investigation_id}/transition",
                 request_body_sha256=body_hash,
                 response_status=200, response_body=stored_body,
                 created_at=NOW,
             ))):
            result = await InvestigationService(mock_db).transition(
                MOCK_USER, inv.investigation_id, req, idempotency_key="dup-key")
        assert result.investigation.investigation_id == inv.investigation_id

    @pytest.mark.asyncio
    async def test_mismatched_body_raises(self, mock_db):
        other_hash = HASH({"target_status": "completed", "return_reason": None, "expected_version": 99})
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=dict(
                 idempotency_key="dup-key", request_method="PATCH",
                 request_path="/api/v1/investigations/any/transition",
                 request_body_sha256=other_hash,
                 response_status=200, response_body="{}",
                 created_at=NOW,
             ))):
            with pytest.raises(IdempotencyMismatch):
                await InvestigationService(mock_db).transition(
                    MOCK_USER, "any",
                    TransitionInvestigationRequest(target_status="submitted", expected_version=2),
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
        from workbench.routers.investigations import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/investigations/assigned", ("GET",)) in routes
        assert ("/api/v1/investigations/{investigation_id}", ("GET",)) in routes
        assert ("/api/v1/investigations/{investigation_id}", ("PATCH",)) in routes
        assert ("/api/v1/investigations/{investigation_id}/transition", ("PATCH",)) in routes
        assert ("/api/v1/investigations/{investigation_id}/cancel", ("POST",)) in routes

    def test_obsolete_routes_absent(self):
        from workbench.routers.investigations import router
        paths = {r.path for r in router.routes}
        assert "/api/v1/investigations/{investigation_id}/assign" not in paths
        assert "/api/v1/investigations/{investigation_id}/status" not in paths
        assert "/api/v1/investigations/{investigation_id}/findings" not in paths

    def test_exact_count_five(self):
        from workbench.routers.investigations import router
        assert len(router.routes) == 5
