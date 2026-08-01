"""Admin outbox endpoint tests (AD1-AD2)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser, PermissionDeniedError

from workbench.exceptions import ResourceNotFound
from workbench.models import AuditOutboxEvent
from workbench.schemas.admin_outbox import OutboxRetryResponse
from workbench.services.admin_outbox_service import AdminOutboxService

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "admin:outbox_monitor", "admin:outbox_retry",
])
COMPLIANCE = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "admin:outbox_monitor",
])
ANALYST = ApplicationUser(user_id="a1", role="analyst", permissions=[])

UOW_TARGET = "workbench.services.admin_outbox_service.UnitOfWork"
AUTH_TARGET = "workbench.services.admin_outbox_service.authorise"


def make_event(**kw):
    defaults = dict(outbox_id=UID(), idempotency_key=UID(), event_type="alert.created",
                    entity_type="alert", entity_id=UID(), actor_id="user1",
                    actor_role="analyst", occurred_at=NOW, payload={"after": {}},
                    status="poison", attempt_count=5, last_error="boom",
                    poison_reason="Failed after 5 attempts", created_at=NOW)
    defaults.update(kw)
    return AuditOutboxEvent(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


class TestList:
    @pytest.mark.asyncio
    async def test_admin_lists_with_status_filter_and_pagination(self, mock_db):
        event = make_event()
        mock_list = AsyncMock(return_value=[event])
        mock_count = AsyncMock(return_value=1)
        with patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.OutboxRepo.list", mock_list), \
             patch("workbench.repos.OutboxRepo.count", mock_count):
            items, total = await AdminOutboxService(mock_db).list(
                ADMIN, status="poison", page=2, per_page=25)
        assert total == 1
        assert items[0].outbox_id == event.outbox_id
        assert mock_auth.await_args.args[1] == "admin:outbox_monitor"
        assert mock_auth.await_args.args[2].entity_type == "audit_outbox"
        assert mock_list.await_args.kwargs["status"] == "poison"
        assert mock_list.await_args.kwargs["limit"] == 25
        assert mock_list.await_args.kwargs["offset"] == 25

    @pytest.mark.asyncio
    async def test_lacking_permission_denied(self, mock_db):
        with patch("workbench.repos.OutboxRepo.list", AsyncMock(return_value=[])), \
             patch("workbench.repos.OutboxRepo.count", AsyncMock(return_value=0)):
            with pytest.raises(PermissionDeniedError):
                await AdminOutboxService(mock_db).list(ANALYST)


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_resets_and_emits_audit(self, mock_db):
        event = make_event()
        uow = MagicMock()
        uow.conn = MagicMock()
        uow_mock = make_uow_mock()
        uow_mock.__aenter__ = AsyncMock(return_value=uow)
        mock_retry = AsyncMock()
        mock_insert = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.OutboxRepo.fetch_by_id",
                   AsyncMock(return_value=event)), \
             patch("workbench.repos.OutboxRepo.retry", mock_retry), \
             patch("workbench.repos.OutboxRepo.insert", mock_insert):
            result = await AdminOutboxService(mock_db).retry(
                ADMIN, event.outbox_id)
        assert isinstance(result, OutboxRetryResponse)
        assert result.queued is True
        assert result.outbox_id == event.outbox_id
        mock_retry.assert_awaited_once_with(event.outbox_id, uow.conn)
        assert mock_auth.await_args.args[1] == "admin:outbox_retry"
        inserted = mock_insert.await_args.args[0]
        assert inserted.event_type == "admin.outbox_retry"
        assert inserted.entity_id == event.outbox_id
        assert inserted.payload["before"]["status"] == "poison"
        assert inserted.payload["after"] == {"status": "pending", "attempt_count": 0}

    @pytest.mark.asyncio
    async def test_missing_event_is_404(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.OutboxRepo.fetch_by_id",
                   AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await AdminOutboxService(mock_db).retry(ADMIN, "ghost")

    @pytest.mark.asyncio
    async def test_lacking_permission_denied(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.OutboxRepo.fetch_by_id",
                   AsyncMock(return_value=make_event())):
            with pytest.raises(PermissionDeniedError):
                await AdminOutboxService(mock_db).retry(COMPLIANCE, UID())


class TestRouteRegistration:
    def test_exact_count_two(self):
        from workbench.routers.admin_outbox import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/admin/outbox", ("GET",)) in routes
        assert ("/api/v1/admin/outbox/{outbox_id}/retry", ("POST",)) in routes
        assert len(router.routes) == 2
