"""Outbox delivery worker — ships audit_outbox events to the audit agent.

Run as a standalone process or container. Do NOT start inside API workers
unless ENABLE_BACKGROUND_WORKERS=true is set (exactly one process).

Usage:
    python -m services.workbench.outbox_worker
    # or via Docker with WORKBENCH_OUTBOX_WORKER=true env var
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from shared.config import get_settings
from shared.database import DatabaseConnector
from shared.logger import get_logger

from .repos import OutboxRepo

logger = get_logger(__name__, "outbox-worker")

_WORKER_ID: str = f"worker-{uuid.uuid4().hex[:8]}"
_DEFAULT_POLL_INTERVAL: int = 5
_DEFAULT_BATCH_SIZE: int = 10
_DEFAULT_MAX_ATTEMPTS: int = 5
_DEFAULT_STALE_MINUTES: int = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


class OutboxDeliveryError(Exception):
    """Raised when delivery to the audit agent fails."""


async def deliver_event(event: Any, audit_url: str, client: httpx.AsyncClient) -> None:
    """Deliver one outbox event to the audit agent."""
    payload = {
        "audit_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, event.idempotency_key)),
        "timestamp": event.occurred_at.isoformat(),
        "user_id": event.actor_id,
        "user_role": event.actor_role,
        "action": event.event_type,
        "endpoint": f"/{event.entity_type}/{event.entity_id}",
        "metadata": event.payload,
    }
    headers = {
        "Content-Type": "application/json",
        "X-Idempotency-Key": event.idempotency_key,
    }
    resp = await client.post(f"{audit_url}/log_access", json=payload, headers=headers)
    if resp.status_code >= 500:
        raise OutboxDeliveryError(f"Audit agent returned {resp.status_code}: {resp.text[:200]}")


async def run_cycle(repo: OutboxRepo, audit_url: str, max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
                    stale_minutes: int = _DEFAULT_STALE_MINUTES) -> None:
    """One poll cycle: reconcile stuck, claim, deliver."""
    try:
        await repo.reconcile_stuck(stale_minutes=stale_minutes)
    except Exception as exc:
        logger.warning("Reconciliation failed", extra={"error": str(exc)})

    async with httpx.AsyncClient(timeout=30.0) as client:
        events = await repo.claim_next_batch(_WORKER_ID, batch_size=_DEFAULT_BATCH_SIZE)
        if not events:
            return

        for event in events:
            try:
                await deliver_event(event, audit_url, client)
                await repo.mark_delivered(event.outbox_id)
                logger.info("Delivered", extra={"outbox_id": event.outbox_id})
            except Exception as exc:
                logger.warning("Delivery failed", extra={
                    "outbox_id": event.outbox_id, "error": str(exc),
                })
                await repo.mark_failed(event.outbox_id, str(exc), max_attempts=max_attempts)

    poison_count = await repo.count_poison()
    if poison_count > 0:
        logger.warning("Poison records detected", extra={"count": poison_count})


async def main_loop(poll_interval: int = _DEFAULT_POLL_INTERVAL,
                    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
                    stale_minutes: int = _DEFAULT_STALE_MINUTES) -> None:
    db_url = os.environ.get(
        "INTEGRATION_DATABASE_URL",
        os.environ.get("DATABASE_URL", ""),
    )
    if not db_url:
        raise RuntimeError("INTEGRATION_DATABASE_URL or DATABASE_URL not set")
    db = DatabaseConnector(db_url)
    await db.initialize()
    repo = OutboxRepo(db)

    audit_url = os.environ.get("AUDIT_AGENT_URL", "http://audit-agent:8008")
    logger.info("Outbox worker starting", extra={
        "worker_id": _WORKER_ID, "poll_interval": poll_interval, "audit_url": audit_url,
    })

    try:
        while True:
            await run_cycle(repo, audit_url, max_attempts=max_attempts, stale_minutes=stale_minutes)
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        logger.info("Outbox worker stopped")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main_loop())
