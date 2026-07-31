"""Comment service — workflow logic for CM1, CM2, CM3.

Parent-entity access is enforced via shared/entity_access (assigned -> broad
read fallback), then the comment action itself runs through authorise() so the
workflow gate applies (e.g. comment:create is a 409 on a closed case).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, RequestContext, authorise,
)
from shared.database import DatabaseConnector

from workbench.exceptions import IdempotencyMismatch, ResourceNotFound, VersionConflict
from workbench.models import (
    ActivityTimelineEntry, AuditOutboxEvent, Comment, IdempotencyRecord,
)
from workbench.repos import (
    CommentRepo, IdempotencyRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.comments import (
    CommentMetadataView, CommentMutationResponse, CommentResponse,
)
from workbench.uow import UnitOfWork

from .entity_access import assert_entity_readable, fetch_parent, resolve_entity_type


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sha256(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def _uuid() -> str:
    return str(uuid.uuid4())


def _make_timeline(entity_type: str, entity_id: str, event_type: str,
                   actor_id: str, old_value: Any = None,
                   new_value: Any = None) -> ActivityTimelineEntry:
    return ActivityTimelineEntry(
        timeline_id=_uuid(), entity_type=entity_type, entity_id=entity_id,
        event_type=event_type, actor_id=actor_id,
        old_value=old_value, new_value=new_value, occurred_at=_now(),
    )


def _make_outbox(event_type: str, entity_type: str, entity_id: str,
                 actor_id: str, actor_role: str, payload: Dict[str, Any]) -> AuditOutboxEvent:
    return AuditOutboxEvent(
        outbox_id=_uuid(),
        idempotency_key=f"{entity_type}.{entity_id}.{event_type}.{_uuid()}",
        event_type=event_type, entity_type=entity_type, entity_id=entity_id,
        actor_id=actor_id, actor_role=actor_role,
        occurred_at=_now(), payload=payload,
    )


def _audit_payload(event_type: str, entity_type: str, entity_id: str,
                   actor_id: str, actor_role: str,
                   before: Optional[Dict[str, Any]] = None,
                   after: Optional[Dict[str, Any]] = None,
                   request_id: str = "",
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Audit outbox payload v1 envelope. Sensitive content is hashed, never verbatim."""
    return {
        "schema_version": 1,
        "event_type": event_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "actor_id": actor_id,
        "actor_role": actor_role,
        "occurred_at": _now().isoformat(),
        "request_id": request_id,
        "before": before or {},
        "after": after or {},
        "metadata": metadata or {},
    }


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


def _serialise(comment: Comment, user: ApplicationUser) -> Any:
    """Apply comment content-visibility OLP.

    Public comments: full content for anyone with comment:read.
    Internal comments: full content only with comment:view_internal_content
    (compliance); metadata-only view for comment:view_metadata (admin);
    excluded entirely for everyone else (analyst).
    """
    if not comment.is_internal:
        return CommentResponse(**comment.model_dump())
    if "comment:view_internal_content" in user.permissions:
        return CommentResponse(**comment.model_dump())
    return CommentMetadataView(
        comment_id=comment.comment_id, entity_type=comment.entity_type,
        entity_id=comment.entity_id, author_id=comment.author_id,
        is_internal=comment.is_internal, is_redacted=comment.is_redacted,
        redacted_at=comment.redacted_at, redacted_by=comment.redacted_by,
        version=comment.version, created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


class CommentService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── CM1 — GET /{entity_type}/{entity_id}/comments ─────────────────────────

    async def list_for_entity(
        self, user: ApplicationUser, entity_type: str, entity_id: str,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[Any], int]:
        canonical = resolve_entity_type(entity_type)
        parent = await fetch_parent(self._db, canonical, entity_id)
        await assert_entity_readable(user, parent, self._db)
        await authorise(user, "comment:read", parent.resource, self._db)

        include_internal = (
            "comment:view_internal_content" in user.permissions
            or "comment:view_metadata" in user.permissions
        )
        limit = min(per_page, 100)
        comments = await CommentRepo(self._db).list_for_entity(
            canonical, entity_id, limit=limit,
            offset=(page - 1) * limit, include_internal=include_internal)
        total = await CommentRepo(self._db).count_for_entity(
            canonical, entity_id, include_internal=include_internal)
        return [_serialise(c, user) for c in comments], total

    # ── CM2 — POST /{entity_type}/{entity_id}/comments ────────────────────────

    async def create(
        self, user: ApplicationUser, entity_type: str, entity_id: str,
        req: Any, idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CommentMutationResponse:
        canonical = resolve_entity_type(entity_type)
        path = f"/api/v1/{entity_type}/{entity_id}/comments"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return CommentMutationResponse.model_validate_json(idem[1])

            parent = await fetch_parent(self._db, canonical, entity_id, uow.conn)
            await assert_entity_readable(user, parent, self._db,
                                         RequestContext(request_id=request_id))
            await authorise(user, "comment:create", parent.resource,
                            self._db, RequestContext(request_id=request_id))

            comment = Comment(
                comment_id=_uuid(), entity_type=canonical, entity_id=entity_id,
                content=req.content, author_id=user.user_id,
                is_internal=req.is_internal, is_redacted=False,
                version=1, created_at=_now(), updated_at=_now(),
            )
            await CommentRepo(self._db).create(comment, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline(canonical, entity_id, "comment.created", user.user_id,
                               None,
                               {"comment_id": comment.comment_id,
                                "is_internal": comment.is_internal,
                                "content_sha256": _sha256(comment.content)}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("comment.created", canonical, entity_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "comment.created", canonical, entity_id,
                                 user.user_id, user.role,
                                 before=None,
                                 after={"comment_id": comment.comment_id,
                                        "is_internal": comment.is_internal,
                                        "content_sha256": _sha256(comment.content),
                                        "version": 1},
                                 request_id=request_id)),
                uow.conn)

            resp = CommentMutationResponse(
                comment=_serialise(comment, user), version=comment.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 201, resp.model_dump_json(), uow.conn)
            return resp

    # ── CM3 — PATCH /comments/{comment_id}/redact ─────────────────────────────

    async def redact(
        self, user: ApplicationUser, comment_id: str,
        req: Any, idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CommentMutationResponse:
        path = f"/api/v1/comments/{comment_id}/redact"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return CommentMutationResponse.model_validate_json(idem[1])

            comment = await CommentRepo(self._db).fetch_by_id(comment_id, uow.conn)
            if comment is None:
                raise ResourceNotFound("Comment", comment_id)

            parent = await fetch_parent(self._db, comment.entity_type,
                                        comment.entity_id, uow.conn)
            await authorise(user, "comment:redact", parent.resource,
                            self._db, RequestContext(request_id=request_id))

            if comment.is_redacted:
                resp = CommentMutationResponse(
                    comment=_serialise(comment, user), version=comment.version)
                await _store_idempotency(
                    IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                    req.model_dump(), 200, resp.model_dump_json(), uow.conn)
                return resp

            original = comment.content
            comment.content = f"[REDACTED — {req.redact_reason}]"
            comment.is_redacted = True
            comment.redacted_at = _now()
            comment.redacted_by = user.user_id
            comment.original_content_hash = _sha256(original)
            comment.redaction_reason = req.redact_reason
            comment.version += 1
            comment.updated_at = _now()

            updated = await CommentRepo(self._db).update(
                comment, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await OutboxRepo(self._db).insert(
                _make_outbox("comment.redacted", comment.entity_type,
                             comment.entity_id, user.user_id, user.role,
                             _audit_payload(
                                 "comment.redacted", comment.entity_type,
                                 comment.entity_id, user.user_id, user.role,
                                 before={"content_sha256": _sha256(original),
                                         "version": req.expected_version},
                                 after={"is_redacted": True,
                                        "version": comment.version,
                                        "redacted_by": comment.redacted_by,
                                        "redaction_reason_sha256": _sha256(req.redact_reason)},
                                 request_id=request_id,
                                 metadata={"comment_id": comment.comment_id})),
                uow.conn)

            resp = CommentMutationResponse(
                comment=_serialise(comment, user), version=comment.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp
