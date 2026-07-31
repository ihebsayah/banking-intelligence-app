"""Notification service — workflow logic for N1, N2, N3.

Notifications are user-owned and carry no workflow status, so the authorisation
Resource maps is_read onto the synthetic "unread"/"read" states registered in
shared/authorise (NOTIFICATION_TRANSITIONS). Ownership (user_id == user.id) is
enforced before any mutation; foreign notifications resolve to 404.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
)
from shared.database import DatabaseConnector

from workbench.exceptions import IdempotencyMismatch, ResourceNotFound
from workbench.models import IdempotencyRecord, Notification
from workbench.repos import IdempotencyRepo, NotificationRepo
from workbench.schemas.notifications import (
    MarkAllReadResponse, NotificationMutationResponse, NotificationResponse,
)
from workbench.uow import UnitOfWork


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


async def _check_idempotency(repo: IdempotencyRepo, key: str, method: str,
                             path: str, body: Any,
                             conn: Any) -> Optional[Tuple[int, str]]:
    if not key:
        return None
    body_hash = _sha256(body)
    existing = await repo.lookup(key, conn)
    if existing is None:
        return None
    if existing.request_body_sha256 != body_hash:
        raise IdempotencyMismatch()
    return existing.response_status, existing.response_body


async def _store_idempotency(repo: IdempotencyRepo, key: str, method: str,
                             path: str, body: Any, status: int, resp_body: str,
                             conn: Any) -> None:
    if not key:
        return
    rec = IdempotencyRecord(
        idempotency_key=key, request_method=method, request_path=path,
        request_body_sha256=_sha256(body),
        response_status=status, response_body=resp_body,
        created_at=_now(),
    )
    await repo.store(rec, conn)


def _notification_resource(user_id: str, is_read: Optional[bool] = None) -> Resource:
    """Resource for notification actions.

    N1/N3 (no specific notification) pass is_read=None -> "unread".
    N2 passes the actual is_read of the targeted notification.
    """
    return Resource(
        id=user_id,
        status="read" if is_read else "unread",
        entity_type="notification",
    )


class NotificationService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── N1 — GET /notifications ───────────────────────────────────────────────

    async def list(
        self, user: ApplicationUser, is_read: Optional[bool] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[NotificationResponse], int, int]:
        await authorise(user, "notification:read",
                        _notification_resource(user.user_id), self._db)

        limit = min(per_page, 100)
        items = await NotificationRepo(self._db).list_for_user(
            user.user_id, is_read=is_read,
            limit=limit, offset=(page - 1) * limit)
        unread = await NotificationRepo(self._db).unread_count(user.user_id)
        total = await NotificationRepo(self._db).count_for_user(
            user.user_id, is_read=is_read)
        return (
            [NotificationResponse(**n.model_dump()) for n in items],
            total, unread,
        )

    # ── N2 — PATCH /notifications/{notification_id}/read ──────────────────────

    async def mark_read(
        self, user: ApplicationUser, notification_id: str,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> NotificationMutationResponse:
        path = f"/api/v1/notifications/{notification_id}/read"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                {}, uow.conn)
            if idem:
                return NotificationMutationResponse.model_validate_json(idem[1])

            n = await NotificationRepo(self._db).fetch_by_id(notification_id, uow.conn)
            if n is None or n.user_id != user.user_id:
                raise ResourceNotFound("Notification", notification_id)

            await authorise(user, "notification:update",
                            _notification_resource(user.user_id, n.is_read),
                            self._db, RequestContext(request_id=request_id))

            if not n.is_read:
                await NotificationRepo(self._db).mark_read(notification_id, uow.conn)
                n.is_read = True
                n.read_at = _now()

            resp = NotificationMutationResponse(
                notification=NotificationResponse(**n.model_dump()))
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                {}, 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── N3 — PATCH /notifications/read-all ────────────────────────────────────

    async def mark_all_read(
        self, user: ApplicationUser, idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> MarkAllReadResponse:
        path = "/api/v1/notifications/read-all"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                {}, uow.conn)
            if idem:
                return MarkAllReadResponse.model_validate_json(idem[1])

            await authorise(user, "notification:update",
                            _notification_resource(user.user_id),
                            self._db, RequestContext(request_id=request_id))

            marked = await NotificationRepo(self._db).mark_all_read(user.user_id, uow.conn)
            resp = MarkAllReadResponse(marked_read=marked)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                {}, 200, resp.model_dump_json(), uow.conn)
            return resp
