"""Test harness for the outbox worker."""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from workbench.outbox_worker import run_cycle
from workbench.repos import OutboxRepo
from workbench.models import AuditOutboxEvent


class FakeResponse:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


class FakeClient:
    """Minimal httpx.AsyncClient stand-in."""

    def __init__(self, response):
        self.response = response
        self.posted = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        self.posted = (url, json, headers)
        return self.response


def _make_event():
    return AuditOutboxEvent(
        outbox_id="test-outbox-id",
        idempotency_key="idem-1",
        event_type="alert.created",
        entity_type="alert",
        entity_id=str(uuid.uuid4()),
        actor_id="test-user",
        actor_role="analyst",
        occurred_at=datetime.now(timezone.utc),
        payload={},
    )


@pytest.mark.asyncio
async def test_outbox_worker_delivery():
    """Test that the outbox worker delivers events to the Audit Agent."""
    mock_repo = MagicMock(spec=OutboxRepo)
    mock_repo.reconcile_stuck = AsyncMock(return_value=[])
    mock_repo.count_poison = AsyncMock(return_value=0)
    mock_repo.claim_next_batch = AsyncMock(return_value=[_make_event()])
    mock_repo.mark_delivered = AsyncMock()
    mock_repo.mark_failed = AsyncMock()

    client = FakeClient(FakeResponse(status_code=200))
    with patch("workbench.outbox_worker.httpx.AsyncClient", return_value=client):
        await run_cycle(mock_repo, "http://mock-audit-agent:8008")

    mock_repo.claim_next_batch.assert_called_once()
    mock_repo.mark_delivered.assert_called_once_with("test-outbox-id")
    mock_repo.mark_failed.assert_not_called()
    url, payload, headers = client.posted
    assert url == "http://mock-audit-agent:8008/log_access"
    assert headers.get("X-Idempotency-Key") == "idem-1"
    assert payload["action"] == "alert.created"


@pytest.mark.asyncio
async def test_outbox_worker_failure():
    """Test that the outbox worker marks events as failed on delivery failure."""
    mock_repo = MagicMock(spec=OutboxRepo)
    mock_repo.reconcile_stuck = AsyncMock(return_value=[])
    mock_repo.count_poison = AsyncMock(return_value=0)
    mock_repo.claim_next_batch = AsyncMock(return_value=[_make_event()])
    mock_repo.mark_delivered = AsyncMock()
    mock_repo.mark_failed = AsyncMock()

    client = FakeClient(FakeResponse(status_code=500, text="boom"))
    with patch("workbench.outbox_worker.httpx.AsyncClient", return_value=client):
        await run_cycle(mock_repo, "http://mock-audit-agent:8008")

    mock_repo.claim_next_batch.assert_called_once()
    mock_repo.mark_delivered.assert_not_called()
    assert mock_repo.mark_failed.call_count == 1
    assert mock_repo.mark_failed.call_args.args[0] == "test-outbox-id"
