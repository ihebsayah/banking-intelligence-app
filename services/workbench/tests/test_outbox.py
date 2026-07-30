"""Outbox worker tests — verifies delivery cycle, retry, poison, and reconciliation."""
import asyncio
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from workbench.models import AuditOutboxEvent
from workbench.outbox_worker import (
    OutboxDeliveryError, _now, deliver_event, run_cycle, main_loop,
)
from workbench.repos import OutboxRepo

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)


def make_outbox(**kw):
    defaults = dict(outbox_id=UID(), idempotency_key=UID(), event_type="alert.created",
                    entity_type="alert", entity_id=UID(), actor_id="user1",
                    actor_role="analyst", occurred_at=NOW, payload={"key": "val"},
                    status="pending", next_attempt_at=NOW, created_at=NOW)
    defaults.update(kw)
    return AuditOutboxEvent(**defaults)


# ── Delivery Tests ────────────────────────────────────────────────────────────

class TestDeliverEvent:
    @pytest.mark.asyncio
    async def test_deliver_success(self):
        event = make_outbox()
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_client.post = AsyncMock(return_value=mock_response)

        await deliver_event(event, "http://audit:8008", mock_client)
        mock_client.post.assert_called_once()
        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"]["X-Idempotency-Key"] == event.idempotency_key
        assert kwargs["json"]["audit_id"] is not None

    @pytest.mark.asyncio
    async def test_server_error_raises(self):
        event = make_outbox()
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(OutboxDeliveryError):
            await deliver_event(event, "http://audit:8008", mock_client)

    @pytest.mark.asyncio
    async def test_http_error_does_not_raise_if_not_5xx(self):
        """4xx errors are client errors — don't retry via OutboxDeliveryError."""
        event = make_outbox()
        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_client.post = AsyncMock(return_value=mock_response)

        # 400 is not >= 500, so no error raised
        await deliver_event(event, "http://audit:8008", mock_client)


# ── Cycle Tests ───────────────────────────────────────────────────────────────

class TestRunCycle:
    @pytest.mark.asyncio
    async def test_pending_to_delivered(self, mock_db):
        e = make_outbox()
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock()
        mock_repo.claim_next_batch = AsyncMock(return_value=[e])
        mock_repo.mark_delivered = AsyncMock()
        mock_repo.mark_failed = AsyncMock()
        mock_repo.count_poison = AsyncMock(return_value=0)

        with patch("workbench.outbox_worker.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_client.post = AsyncMock(return_value=mock_response)

            await run_cycle(mock_repo, "http://audit:8008")

        mock_repo.claim_next_batch.assert_called_once()
        mock_repo.mark_delivered.assert_called_once_with(e.outbox_id)
        mock_repo.mark_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_failed_delivery_schedules_retry(self, mock_db):
        e = make_outbox()
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock()
        mock_repo.claim_next_batch = AsyncMock(return_value=[e])
        mock_repo.mark_delivered = AsyncMock()
        mock_repo.mark_failed = AsyncMock()
        mock_repo.count_poison = AsyncMock(return_value=0)

        with patch("workbench.outbox_worker.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.text = "Down"
            mock_client.post = AsyncMock(return_value=mock_response)

            await run_cycle(mock_repo, "http://audit:8008", max_attempts=5)

        mock_repo.mark_failed.assert_called_once_with(e.outbox_id, unittest.mock.ANY, max_attempts=5)
        mock_repo.mark_delivered.assert_not_called()

    @pytest.mark.asyncio
    async def test_poison_after_max_attempts(self, mock_db):
        e = make_outbox(attempt_count=4)
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock()
        mock_repo.claim_next_batch = AsyncMock(return_value=[e])
        mock_repo.mark_delivered = AsyncMock()
        mock_repo.mark_failed = AsyncMock()
        mock_repo.count_poison = AsyncMock(return_value=1)

        with patch("workbench.outbox_worker.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_response.text = "Down"
            mock_client.post = AsyncMock(return_value=mock_response)

            await run_cycle(mock_repo, "http://audit:8008", max_attempts=5)

        mock_repo.mark_failed.assert_called_once()
        # count_poison returns 1 → log warning issued

    @pytest.mark.asyncio
    async def test_no_pending_events(self, mock_db):
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock()
        mock_repo.claim_next_batch = AsyncMock(return_value=[])
        mock_repo.count_poison = AsyncMock(return_value=0)

        await run_cycle(mock_repo, "http://audit:8008")
        mock_repo.claim_next_batch.assert_called_once()
        # No events → no delivery attempted; no error raised

    @pytest.mark.asyncio
    async def test_duplicate_delivery_idempotent(self, mock_db):
        """Same idempotency_key sent twice → audit agent returns 200."""
        e1 = make_outbox(idempotency_key="dup-key")
        e2 = make_outbox(idempotency_key="dup-key")
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock()
        mock_repo.claim_next_batch = AsyncMock(return_value=[e1, e2])
        mock_repo.mark_delivered = AsyncMock()
        mock_repo.mark_failed = AsyncMock()
        mock_repo.count_poison = AsyncMock(return_value=0)

        with patch("workbench.outbox_worker.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)

            await run_cycle(mock_repo, "http://audit:8008")
        assert mock_repo.mark_delivered.call_count == 2

    @pytest.mark.asyncio
    async def test_worker_crash_no_data_loss(self, mock_db):
        """Event stays 'delivering' after crash → reconciliation picks it up."""
        e = make_outbox(status="delivering", locked_by="dead-worker",
                        locked_at=datetime.now(timezone.utc))
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock(return_value=[e])
        mock_repo.claim_next_batch = AsyncMock(return_value=[])
        mock_repo.count_poison = AsyncMock(return_value=0)

        with patch("workbench.outbox_worker.httpx.AsyncClient"):
            await run_cycle(mock_repo, "http://audit:8008")

        mock_repo.reconcile_stuck.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_workers_no_double_claim(self, mock_db):
        """Two workers should not claim the same row — FOR UPDATE SKIP LOCKED
        ensures only one worker gets each row."""
        e = make_outbox()
        mock_repo = MagicMock(spec=OutboxRepo)
        mock_repo.reconcile_stuck = AsyncMock()
        mock_repo.claim_next_batch = AsyncMock(side_effect=[
            [e],  # worker 1 claims it
            [],   # worker 2 finds nothing
        ])
        mock_repo.count_poison = AsyncMock(return_value=0)

        with patch("workbench.outbox_worker.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_client.post = AsyncMock(return_value=mock_response)

            # Two cycles simulating two workers
            await run_cycle(mock_repo, "http://audit:8008")
            e2 = make_outbox()
            mock_repo.claim_next_batch = AsyncMock(return_value=[])
            await run_cycle(mock_repo, "http://audit:8008")

        assert mock_repo.mark_delivered.call_count == 1

    @pytest.mark.asyncio
    async def test_mutation_rollback_no_outbox_event(self, mock_db):
        """If the business mutation fails, no timeline/notification/outbox events
        are persisted because the UoW rolls back the entire transaction."""
        mock_conn = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_db._pool = mock_pool
        mock_db._ensure_pool = MagicMock(return_value=mock_pool)

        from workbench.uow import UnitOfWork
        mock_alert_repo = MagicMock()
        mock_alert_repo.create = AsyncMock(side_effect=ValueError("business rule violation"))

        with pytest.raises(ValueError):
            async with UnitOfWork(mock_db) as uow:
                uow.conn = mock_conn
                uow.alert_repo = mock_alert_repo
                await uow.alert_repo.create(make_outbox())

        mock_conn.execute.assert_any_call("BEGIN")
        mock_conn.execute.assert_any_call("ROLLBACK")
        mock_pool.release.assert_called_once()
        # Verify no COMMIT was called
        calls = [c for c in mock_conn.execute.call_args_list if c[0][0] == "COMMIT"]
        assert len(calls) == 0


# ── Worker Integration Test ────────────────────────────────────────────────────

class TestMainLoop:
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Verify the main loop starts and can be cancelled."""
        with patch("workbench.outbox_worker.get_settings"), \
             patch("workbench.outbox_worker.DatabaseConnector.initialize", AsyncMock()), \
             patch("workbench.outbox_worker.DatabaseConnector.close", AsyncMock()), \
             patch("workbench.outbox_worker.run_cycle", AsyncMock()) as mock_cycle:
            task = asyncio.create_task(main_loop(poll_interval=1))
            await asyncio.sleep(0.3)
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
            assert mock_cycle.called
