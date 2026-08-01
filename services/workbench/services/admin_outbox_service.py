"""Admin outbox service — workflow logic for AD1 and AD2.

Both endpoints are admin-only. `admin:outbox_monitor`/`admin:outbox_retry` carry
no workflow status, so they run through authorise() via a synthetic
"audit_outbox"/"active" resource (OUTBOX_TRANSITIONS), mirroring the
notification/timeline synthetic-resource pattern.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
)
from shared.database import DatabaseConnector

from workbench.exceptions import ResourceNotFound
from workbench.models import AuditOutboxEvent
from workbench.repos import OutboxRepo
from workbench.schemas.admin_outbox import OutboxRetryResponse
from workbench.uow import UnitOfWork


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_outbox(actor_id: str, actor_role: str, outbox_id: str,
                 payload: Dict[str, Any]) -> AuditOutboxEvent:
    return AuditOutboxEvent(
        outbox_id=str(uuid.uuid4()),
        idempotency_key=f"audit_outbox.{outbox_id}.admin.outbox_retry.{uuid.uuid4()}",
        event_type="admin.outbox_retry", entity_type="audit_outbox",
        entity_id=outbox_id, actor_id=actor_id, actor_role=actor_role,
        occurred_at=_now(), payload=payload,
    )


def _outbox_resource() -> Resource:
    return Resource(id="outbox", status="active", entity_type="audit_outbox")


class AdminOutboxService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── AD1 — GET /admin/outbox ───────────────────────────────────────────────

    async def list(
        self, user: ApplicationUser, status: Optional[str] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[AuditOutboxEvent], int]:
        await authorise(user, "admin:outbox_monitor", _outbox_resource(),
                        self._db, RequestContext())
        limit = min(per_page, 100)
        items = await OutboxRepo(self._db).list(
            status=status, limit=limit, offset=(page - 1) * limit)
        total = await OutboxRepo(self._db).count(status=status)
        return items, total

    # ── AD2 — POST /admin/outbox/{outbox_id}/retry ────────────────────────────

    async def retry(
        self, user: ApplicationUser, outbox_id: str, request_id: str = "",
    ) -> OutboxRetryResponse:
        async with UnitOfWork(self._db) as uow:
            await authorise(user, "admin:outbox_retry", _outbox_resource(),
                            self._db, RequestContext(request_id=request_id))
            event = await OutboxRepo(self._db).fetch_by_id(outbox_id, uow.conn)
            if event is None:
                raise ResourceNotFound("OutboxEvent", outbox_id)
            await OutboxRepo(self._db).retry(outbox_id, uow.conn)
            await OutboxRepo(self._db).insert(
                _make_outbox(
                    user.user_id, user.role, outbox_id,
                    {
                        "schema_version": 1,
                        "event_type": "admin.outbox_retry",
                        "entity_type": "audit_outbox",
                        "entity_id": outbox_id,
                        "actor_id": user.user_id,
                        "actor_role": user.role,
                        "occurred_at": _now().isoformat(),
                        "request_id": request_id,
                        "before": {"status": event.status,
                                   "attempt_count": event.attempt_count},
                        "after": {"status": "pending", "attempt_count": 0},
                        "metadata": {},
                    }),
                uow.conn)
        return OutboxRetryResponse(outbox_id=outbox_id)
