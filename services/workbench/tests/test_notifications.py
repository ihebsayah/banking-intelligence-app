"""Notification service tests (N1-N3)."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser

from workbench.exceptions import IdempotencyMismatch, ResourceNotFound
from workbench.models import Notification
from workbench.schemas.notifications import (
    NotificationMutationResponse, NotificationResponse,
)
from workbench.services.notification_service import NotificationService

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

USER = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "notification:read", "notification:update",
])

UOW_TARGET = "workbench.services.notification_service.UnitOfWork"
AUTH_TARGET = "workbench.services.notification_service.authorise"

HASH = lambda body: hashlib.sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def make_notification(**kw):
    defaults = dict(notification_id=UID(), user_id="user1",
                    notification_type="alert_assigned", title="New alert",
                    body="Alert assigned", is_read=False, read_at=None,
                    created_at=NOW)
    defaults.update(kw)
    return Notification(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


class TestList:
    @pytest.mark.asyncio
    async def test_returns_items_total_and_unread_count(self, mock_db):
        n = make_notification()
        mock_list = AsyncMock(return_value=[n])
        with patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.NotificationRepo.list_for_user", mock_list), \
             patch("workbench.repos.NotificationRepo.unread_count",
                   AsyncMock(return_value=3)), \
             patch("workbench.repos.NotificationRepo.count_for_user",
                   AsyncMock(return_value=5)):
            items, total, unread = await NotificationService(mock_db).list(USER)
        assert total == 5
        assert unread == 3
        assert items[0].notification_id == n.notification_id
        assert mock_auth.await_args.args[1] == "notification:read"
        assert mock_auth.await_args.args[2].entity_type == "notification"

    @pytest.mark.asyncio
    async def test_is_read_filter_and_pagination_passed_through(self, mock_db):
        mock_list = AsyncMock(return_value=[])
        with patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.NotificationRepo.list_for_user", mock_list), \
             patch("workbench.repos.NotificationRepo.unread_count",
                   AsyncMock(return_value=0)), \
             patch("workbench.repos.NotificationRepo.count_for_user",
                   AsyncMock(return_value=0)):
            await NotificationService(mock_db).list(
                USER, is_read=True, page=2, per_page=25)
        assert mock_list.await_args.kwargs["is_read"] is True
        assert mock_list.await_args.kwargs["limit"] == 25
        assert mock_list.await_args.kwargs["offset"] == 25


class TestMarkRead:
    @pytest.mark.asyncio
    async def test_marks_unread_notification(self, mock_db):
        n = make_notification()
        uow = MagicMock()
        uow.conn = MagicMock()
        uow_mock = make_uow_mock()
        uow_mock.__aenter__ = AsyncMock(return_value=uow)
        mock_mark = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=None)), \
             patch("workbench.repos.NotificationRepo.fetch_by_id",
                   AsyncMock(return_value=n)), \
             patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.NotificationRepo.mark_read", mock_mark):
            result = await NotificationService(mock_db).mark_read(
                USER, n.notification_id)
        mock_mark.assert_awaited_once_with(n.notification_id, uow.conn)
        assert result.notification.is_read is True
        assert mock_auth.await_args.args[1] == "notification:update"
        assert mock_auth.await_args.args[2].status == "unread"

    @pytest.mark.asyncio
    async def test_foreign_notification_is_404(self, mock_db):
        n = make_notification(user_id="someone_else")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=None)), \
             patch("workbench.repos.NotificationRepo.fetch_by_id",
                   AsyncMock(return_value=n)):
            with pytest.raises(ResourceNotFound):
                await NotificationService(mock_db).mark_read(USER, n.notification_id)

    @pytest.mark.asyncio
    async def test_missing_notification_is_404(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=None)), \
             patch("workbench.repos.NotificationRepo.fetch_by_id",
                   AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await NotificationService(mock_db).mark_read(USER, "ghost")

    @pytest.mark.asyncio
    async def test_already_read_is_idempotent(self, mock_db):
        n = make_notification(is_read=True, read_at=NOW)
        uow_mock = make_uow_mock()
        mock_mark = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=None)), \
             patch("workbench.repos.NotificationRepo.fetch_by_id",
                   AsyncMock(return_value=n)), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.NotificationRepo.mark_read", mock_mark):
            result = await NotificationService(mock_db).mark_read(
                USER, n.notification_id)
        mock_mark.assert_not_awaited()
        assert result.notification.is_read is True

    @pytest.mark.asyncio
    async def test_idempotent_replay(self, mock_db):
        n = make_notification(is_read=True)
        resp = NotificationMutationResponse(
            notification=NotificationResponse(**n.model_dump()))
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=MagicMock(
                       request_body_sha256=HASH({}),
                       response_status=200,
                       response_body=resp.model_dump_json()))):
            result = await NotificationService(mock_db).mark_read(
                USER, n.notification_id, idempotency_key="key1")
        assert result.notification.notification_id == n.notification_id

    @pytest.mark.asyncio
    async def test_idempotency_mismatch(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=MagicMock(
                       request_body_sha256="deadbeef"))):
            with pytest.raises(IdempotencyMismatch):
                await NotificationService(mock_db).mark_read(
                    USER, UID(), idempotency_key="key1")


class TestMarkAllRead:
    @pytest.mark.asyncio
    async def test_marks_all_and_returns_count(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=None)), \
             patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.NotificationRepo.mark_all_read",
                   AsyncMock(return_value=2)):
            result = await NotificationService(mock_db).mark_all_read(USER)
        assert result.marked_read == 2
        assert mock_auth.await_args.args[1] == "notification:update"

    @pytest.mark.asyncio
    async def test_idempotency_mismatch(self, mock_db):
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=MagicMock(
                       request_body_sha256="deadbeef"))):
            with pytest.raises(IdempotencyMismatch):
                await NotificationService(mock_db).mark_all_read(
                    USER, idempotency_key="key1")


class TestRouteRegistration:
    def test_exact_count_three(self):
        from workbench.routers.notifications import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/notifications", ("GET",)) in routes
        assert ("/api/v1/notifications/{notification_id}/read", ("PATCH",)) in routes
        assert ("/api/v1/notifications/read-all", ("PATCH",)) in routes
        assert len(router.routes) == 3
