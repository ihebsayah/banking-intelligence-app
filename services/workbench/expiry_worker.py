"""Approval expiry worker — transitions pending approvals past due to expired (AP5).

Run as a standalone process or container. Do NOT start inside API workers
unless ENABLE_BACKGROUND_WORKERS=true is set (exactly one process).

Usage:
    python -m services.workbench.expiry_worker
"""
from __future__ import annotations

import asyncio
import os
from typing import List

from shared.config import get_settings
from shared.database import DatabaseConnector
from shared.logger import get_logger

from .models import ApprovalRequest
from .services.approval_service import (
    _audit_payload, _make_notification, _make_outbox, _make_timeline,
)
from .uow import UnitOfWork

logger = get_logger(__name__, "approval-expiry-worker")

# Canonical actor for AP5 (increment-2B-state-machines.md: Actor=Worker,
# Perm=(system)). Seeded by migrations/versions/0008_add_system_actor.py so the
# timeline FK (activity_timeline.actor_id -> users(user_id)) resolves.
# audit_outbox.actor_id is free-form (no FK) and records the same stable ID.
SYSTEM_ACTOR_ID = "system_001"
SYSTEM_ACTOR_ROLE = "system"

DEFAULT_INTERVAL_SECONDS = 60
DEFAULT_BATCH_SIZE = 50


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


async def expire_due(db: DatabaseConnector, batch_size: int = DEFAULT_BATCH_SIZE) -> List[ApprovalRequest]:
    """Expire one batch of due approvals with atomic side effects.

    One UnitOfWork transaction per batch: the repo claim is atomic
    (UPDATE ... FOR UPDATE SKIP LOCKED) so concurrent workers can never
    expire the same row twice; the whole batch rolls back on any error and
    is retried on the next cycle. Side effects per expired approval:
    status transition, timeline event, notification to requester, audit
    outbox event — all committed together.
    """
    async with UnitOfWork(db) as uow:
        due = await uow.approval_repo.expire_due(batch_size, conn=uow.conn)
        for ar in due:
            await uow.timeline_repo.insert(
                _make_timeline("approval_request", ar.approval_request_id,
                               "approval_expired", SYSTEM_ACTOR_ID,
                               {"status": "pending"},
                               {"status": "expired", "version": ar.version}),
                conn=uow.conn)
            await uow.notification_repo.insert(
                _make_notification(
                    ar.requested_by, "approval_expired",
                    "Approval request expired",
                    f"Your approval request for {ar.action_type} expired before it was approved",
                    "approval_request", ar.approval_request_id),
                conn=uow.conn)
            await uow.outbox_repo.insert(
                _make_outbox(
                    "approval.expired", "approval_request", ar.approval_request_id,
                    SYSTEM_ACTOR_ID, SYSTEM_ACTOR_ROLE,
                    _audit_payload(
                        "approval.expired", "approval_request", ar.approval_request_id,
                        SYSTEM_ACTOR_ID, SYSTEM_ACTOR_ROLE,
                        before={"status": "pending"},
                        after={"status": "expired", "version": ar.version})),
                conn=uow.conn)
        return due


async def main_loop(interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
                    batch_size: int = DEFAULT_BATCH_SIZE) -> None:
    db_url = os.environ.get(
        "INTEGRATION_DATABASE_URL",
        os.environ.get("DATABASE_URL", ""),
    )
    if not db_url:
        raise RuntimeError("INTEGRATION_DATABASE_URL or DATABASE_URL not set")
    db = DatabaseConnector(db_url)
    await db.initialize()
    logger.info("Approval expiry worker starting", extra={
        "interval_seconds": interval_seconds, "batch_size": batch_size,
    })
    try:
        while True:
            try:
                expired = await expire_due(db, batch_size=batch_size)
                if expired:
                    logger.info("Expired approval requests", extra={"count": len(expired)})
            except Exception as exc:
                logger.error("Approval expiry cycle failed", extra={"error": str(exc)})
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("Approval expiry worker stopped")
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main_loop(
        interval_seconds=_env_int("APPROVAL_EXPIRY_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS),
        batch_size=_env_int("APPROVAL_EXPIRY_BATCH_SIZE", DEFAULT_BATCH_SIZE),
    ))
