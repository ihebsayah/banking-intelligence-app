"""Approval expiry worker tests — eligibility, atomic side effects, lifecycle (AP5)."""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.errors import DatabaseError
from workbench.expiry_worker import (
    SYSTEM_ACTOR_ID, SYSTEM_ACTOR_ROLE, _env_int, expire_due, main_loop,
)
from workbench.models import ApprovalRequest

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)


def make_approval(**kw):
    defaults = dict(approval_request_id=UID(), action_type="alert_dismissal_critical_high",
                    entity_type="alert", entity_id=UID(), requested_by="user1",
                    rationale="Needs sign-off", required_approvals=1,
                    approval_count=0, status="pending",
                    expires_at=NOW - timedelta(hours=1), executed_at=None,
                    version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ApprovalRequest(**defaults)


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow.approval_repo = MagicMock(expire_due=AsyncMock())
    uow.timeline_repo = MagicMock(insert=AsyncMock())
    uow.notification_repo = MagicMock(insert=AsyncMock())
    uow.outbox_repo = MagicMock(insert=AsyncMock())
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


class TestExpireDue:
    @pytest.mark.asyncio
    async def test_due_pending_approval_expired_with_side_effects(self, mock_db):
        ar = make_approval()
        uow_mock = make_uow_mock()
        uow = uow_mock.__aenter__.return_value
        uow.approval_repo.expire_due = AsyncMock(return_value=[ar])
        with patch("workbench.expiry_worker.UnitOfWork", return_value=uow_mock):
            expired = await expire_due(mock_db, batch_size=10)
        assert expired == [ar]
        uow.approval_repo.expire_due.assert_called_once_with(10, conn=uow.conn)
        uow.timeline_repo.insert.assert_called_once()
        timeline = uow.timeline_repo.insert.call_args[0][0]
        assert timeline.event_type == "approval_expired"
        assert timeline.entity_type == "approval_request"
        assert timeline.entity_id == ar.approval_request_id
        assert timeline.actor_id == SYSTEM_ACTOR_ID
        uow.notification_repo.insert.assert_called_once()
        notification = uow.notification_repo.insert.call_args[0][0]
        assert notification.notification_type == "approval_expired"
        assert notification.user_id == ar.requested_by
        assert "rationale" not in notification.body.lower()
        uow.outbox_repo.insert.assert_called_once()
        outbox = uow.outbox_repo.insert.call_args[0][0]
        assert outbox.event_type == "approval.expired"
        assert outbox.actor_id == SYSTEM_ACTOR_ID
        assert outbox.actor_role == SYSTEM_ACTOR_ROLE
        assert outbox.payload["before"] == {"status": "pending"}
        assert outbox.payload["after"]["status"] == "expired"

    @pytest.mark.asyncio
    async def test_no_due_approvals_no_side_effects(self, mock_db):
        uow_mock = make_uow_mock()
        uow = uow_mock.__aenter__.return_value
        uow.approval_repo.expire_due = AsyncMock(return_value=[])
        with patch("workbench.expiry_worker.UnitOfWork", return_value=uow_mock):
            expired = await expire_due(mock_db)
        assert expired == []
        uow.timeline_repo.insert.assert_not_called()
        uow.notification_repo.insert.assert_not_called()
        uow.outbox_repo.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_side_effect_failure_aborts_batch_for_retry(self, mock_db):
        """A failed side effect aborts the batch; UoW rolls back the whole
        transaction (including the status transition) so nothing is orphaned
        and the next cycle retries cleanly."""
        ar = make_approval()
        uow_mock = make_uow_mock()
        uow = uow_mock.__aenter__.return_value
        uow.approval_repo.expire_due = AsyncMock(return_value=[ar])
        uow.notification_repo.insert = AsyncMock(side_effect=DatabaseError("down"))
        with patch("workbench.expiry_worker.UnitOfWork", return_value=uow_mock):
            with pytest.raises(DatabaseError):
                await expire_due(mock_db)
        uow.outbox_repo.insert.assert_not_called()
        exc_type = uow_mock.__aexit__.call_args.args[0]
        assert exc_type is DatabaseError

    @pytest.mark.asyncio
    async def test_batch_size_configured(self, mock_db):
        ar = make_approval()
        uow_mock = make_uow_mock()
        uow = uow_mock.__aenter__.return_value
        uow.approval_repo.expire_due = AsyncMock(return_value=[ar])
        with patch("workbench.expiry_worker.UnitOfWork", return_value=uow_mock):
            await expire_due(mock_db, batch_size=100)
        uow.approval_repo.expire_due.assert_called_once_with(100, conn=uow.conn)

    @pytest.mark.asyncio
    async def test_failure_propagates(self, mock_db):
        uow_mock = make_uow_mock()
        uow_mock.__aenter__ = AsyncMock(side_effect=DatabaseError("boom"))
        with patch("workbench.expiry_worker.UnitOfWork", return_value=uow_mock):
            with pytest.raises(DatabaseError):
                await expire_due(mock_db)


class TestMainLoop:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        with patch("workbench.expiry_worker.get_settings"), \
             patch("workbench.expiry_worker.DatabaseConnector.initialize", AsyncMock()), \
             patch("workbench.expiry_worker.DatabaseConnector.close", AsyncMock()), \
             patch("workbench.expiry_worker.expire_due", AsyncMock()) as mock_expire:
            task = asyncio.create_task(main_loop(interval_seconds=0.05))
            await asyncio.sleep(0.12)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            assert mock_expire.called

    @pytest.mark.asyncio
    async def test_failure_does_not_terminate_loop(self):
        calls = 0

        async def flaky(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise DatabaseError("boom")
            return []

        with patch("workbench.expiry_worker.get_settings"), \
             patch("workbench.expiry_worker.DatabaseConnector.initialize", AsyncMock()), \
             patch("workbench.expiry_worker.DatabaseConnector.close", AsyncMock()), \
             patch("workbench.expiry_worker.expire_due", AsyncMock(side_effect=flaky)) as mock_expire:
            task = asyncio.create_task(main_loop(interval_seconds=0.01))
            await asyncio.sleep(0.15)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            assert mock_expire.call_count >= 2


class TestConfig:
    def test_env_interval_and_batch_size(self, monkeypatch):
        monkeypatch.setenv("APPROVAL_EXPIRY_INTERVAL_SECONDS", "123")
        monkeypatch.setenv("APPROVAL_EXPIRY_BATCH_SIZE", "7")
        assert _env_int("APPROVAL_EXPIRY_INTERVAL_SECONDS", 60) == 123
        assert _env_int("APPROVAL_EXPIRY_BATCH_SIZE", 50) == 7

    def test_env_invalid_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("APPROVAL_EXPIRY_INTERVAL_SECONDS", "abc")
        assert _env_int("APPROVAL_EXPIRY_INTERVAL_SECONDS", 60) == 60
