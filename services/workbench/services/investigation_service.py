from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, Resource, RequestContext, authorise,
    OwnershipDeniedError as AuthOwnershipDenied,
    PermissionDeniedError as AuthPermissionDenied,
    ScopeDeniedError as AuthScopeDenied,
    WorkflowStateError as AuthWorkflowState,
)
from shared.database import DatabaseConnector

from workbench.exceptions import (
    IdempotencyMismatch, InvalidAssignee, InvalidTransition,
    ResourceNotFound, VersionConflict, WorkbenchError,
)
from workbench.models import (
    ActivityTimelineEntry, AssignmentHistoryEntry, AuditOutboxEvent,
    Comment, IdempotencyRecord, Investigation, Notification,
)
from workbench.repos import (
    AssignmentHistoryRepo, CommentRepo, IdempotencyRepo,
    InvestigationRepo, NotificationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.investigations import (
    CancelInvestigationRequest, InvestigationMutationResponse,
    InvestigationResponse, TransitionInvestigationRequest,
    UpdateInvestigationRequest,
)
from workbench.uow import UnitOfWork


ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "open": ["active"],
    "active": ["awaiting_information", "submitted"],
    "awaiting_information": ["active"],
    "submitted": ["completed", "returned"],
    "returned": ["active"],
    "completed": [],
    "cancelled": [],
}

TRANSITION_REQUIRED_ACTION: Dict[Tuple[str, str], str] = {
    ("open", "active"): "investigation:transition",
    ("active", "awaiting_information"): "investigation:transition",
    ("active", "submitted"): "investigation:transition",
    ("awaiting_information", "active"): "investigation:transition",
    ("submitted", "completed"): "investigation:review",
    ("submitted", "returned"): "investigation:review",
    ("returned", "active"): "investigation:transition",
}

CANCEL_ALLOWED_FROM: set = {"open", "active", "awaiting_information", "submitted", "returned"}


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


def _make_notification(user_id: str, ntype: str, title: str, body: str,
                       entity_type: str, entity_id: str) -> Notification:
    return Notification(
        notification_id=_uuid(), user_id=user_id, notification_type=ntype,
        title=title, body=body, entity_type=entity_type, entity_id=entity_id,
        created_at=_now(),
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


def _make_assignment(entity_type: str, entity_id: str, assigned_from: Optional[str],
                     assigned_to: Optional[str], assigned_by: str,
                     reason: Optional[str] = None) -> AssignmentHistoryEntry:
    return AssignmentHistoryEntry(
        history_id=_uuid(), entity_type=entity_type, entity_id=entity_id,
        assigned_from=assigned_from, assigned_to=assigned_to,
        assigned_by=assigned_by, reason=reason, assigned_at=_now(),
    )


def _resource_from_inv(inv: Investigation) -> Resource:
    return Resource(
        id=inv.investigation_id, status=inv.status,
        assigned_to=inv.assigned_to, scope_id=inv.scope_id,
        version=inv.version, entity_type="investigation",
    )


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


async def _validate_assignee(db: DatabaseConnector, user_id: str,
                             scope_id: str, conn: Any) -> None:
    row = await db.fetch_one(
        "SELECT status FROM users WHERE user_id = $1", [user_id], conn=conn)
    if row is None:
        raise InvalidAssignee(f"User not found: {user_id}")
    if row.get("status") != "active":
        raise InvalidAssignee(f"User is not active: {user_id}")
    scope_rows = await db.fetch_all(
        "SELECT scope_id FROM user_scopes WHERE user_id = $1", [user_id], conn=conn)
    scopes = [r["scope_id"] for r in scope_rows]
    if scope_id not in scopes and scopes:
        raise InvalidAssignee(f"User lacks scope: {scope_id}")


class InvestigationService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def list_assigned(
        self, user: ApplicationUser, scope: str,
        status: Optional[str] = None, priority: Optional[str] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[InvestigationResponse], int]:
        await authorise(
            user, "investigation:read_own",
            Resource(id="assigned", status="active", entity_type="collection"),
            self._db, RequestContext())
        investigations = await InvestigationRepo(self._db).list(
            scope_id=scope, status=status, assigned_to=user.user_id,
            limit=min(per_page, 100), offset=(page - 1) * min(per_page, 100),
        )
        if priority:
            investigations = [i for i in investigations if i.priority == priority]
        return [InvestigationResponse(**i.model_dump()) for i in investigations], len(investigations)

    async def get_by_id(
        self, user: ApplicationUser, investigation_id: str,
    ) -> InvestigationResponse:
        inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id)
        if inv is None:
            raise ResourceNotFound("Investigation", investigation_id)

        try:
            await authorise(user, "investigation:read_own",
                            _resource_from_inv(inv), self._db, RequestContext())
            if inv.assigned_to != user.user_id:
                raise AuthOwnershipDenied()
            return InvestigationResponse(**inv.model_dump())
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            pass

        try:
            await authorise(user, "investigation:read",
                            _resource_from_inv(inv), self._db, RequestContext())
            return InvestigationResponse(**inv.model_dump())
        except AuthPermissionDenied:
            raise ResourceNotFound("Investigation", investigation_id)

    async def update(
        self, user: ApplicationUser, investigation_id: str,
        req: UpdateInvestigationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InvestigationMutationResponse:
        path = f"/api/v1/investigations/{investigation_id}"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return InvestigationMutationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            await authorise(user, "investigation:modify_findings",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))

            if inv.status not in ("active", "returned"):
                raise InvalidTransition(inv.status, "modify_findings")

            old_findings = inv.findings_text
            old_conclusion = inv.conclusion
            old_refs = inv.findings_refs

            if req.findings_text is not None:
                inv.findings_text = req.findings_text
            if req.findings_refs is not None:
                inv.findings_refs = req.findings_refs
            if req.conclusion is not None:
                inv.conclusion = req.conclusion

            inv.version += 1
            inv.updated_at = _now()

            updated = await InvestigationRepo(self._db).update(
                inv, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              "investigation.findings_updated", user.user_id,
                              {"findings_text": old_findings,
                               "conclusion": old_conclusion,
                               "findings_refs": old_refs},
                              {"findings_text": inv.findings_text,
                               "conclusion": inv.conclusion,
                               "findings_refs": inv.findings_refs}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.findings_updated", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "findings_updated": req.findings_text is not None,
                             "conclusion_updated": req.conclusion is not None}),
                uow.conn)

            resp = InvestigationMutationResponse(
                investigation=InvestigationResponse(**inv.model_dump()),
                version=inv.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def transition(
        self, user: ApplicationUser, investigation_id: str,
        req: TransitionInvestigationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InvestigationMutationResponse:
        path = f"/api/v1/investigations/{investigation_id}/transition"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return InvestigationMutationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            target = req.target_status
            allowed = ALLOWED_TRANSITIONS.get(inv.status, [])
            if target not in allowed:
                raise InvalidTransition(inv.status, target)

            action = TRANSITION_REQUIRED_ACTION.get((inv.status, target))
            if action is None:
                raise InvalidTransition(inv.status, target)

            if target == "submitted" and not (inv.findings_text or inv.findings_refs):
                raise WorkbenchError(
                    "FINDINGS_REQUIRED",
                    "findings must be recorded before submitting the investigation",
                    400,
                )

            await authorise(user, action, _resource_from_inv(inv),
                            self._db, RequestContext(request_id=request_id))

            if target == "returned" and not req.return_reason:
                raise InvalidAssignee("return_reason required when transitioning to returned")

            old_status = inv.status
            inv.status = target
            inv.version += 1
            inv.updated_at = _now()

            if target == "returned":
                inv.return_reason = req.return_reason
            if target == "active" and old_status == "returned":
                inv.return_reason = None
            if target == "submitted":
                inv.submitted_at = _now()
            if target == "completed":
                inv.completed_at = _now()

            updated = await InvestigationRepo(self._db).update(
                inv, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              f"investigation.{target}", user.user_id,
                              {"status": old_status}, {"status": target}),
                uow.conn)

            if target == "returned" and inv.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(inv.assigned_to, "investigation_returned",
                                      f"Investigation returned for rework",
                                      inv.title, "investigation", investigation_id),
                    uow.conn)

            if target == "completed":
                await NotificationRepo(self._db).insert(
                    _make_notification(inv.created_by, "investigation_completed",
                                      f"Investigation completed",
                                      inv.title, "investigation", investigation_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox(f"investigation.{target}", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "old_status": old_status, "new_status": target}),
                uow.conn)

            resp = InvestigationMutationResponse(
                investigation=InvestigationResponse(**inv.model_dump()),
                version=inv.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def cancel(
        self, user: ApplicationUser, investigation_id: str,
        req: CancelInvestigationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InvestigationMutationResponse:
        path = f"/api/v1/investigations/{investigation_id}/cancel"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InvestigationMutationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            if inv.status == "cancelled":
                return InvestigationMutationResponse(
                    investigation=InvestigationResponse(**inv.model_dump()),
                    version=inv.version)

            if inv.status == "completed":
                raise InvalidTransition(inv.status, "cancel")

            if inv.status not in CANCEL_ALLOWED_FROM:
                raise InvalidTransition(inv.status, "cancel")

            await authorise(user, "investigation:assign", _resource_from_inv(inv),
                            self._db, RequestContext(request_id=request_id))

            old_status = inv.status
            inv.status = "cancelled"
            inv.version += 1
            inv.updated_at = _now()

            updated = await InvestigationRepo(self._db).update(
                inv, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            comment = Comment(
                comment_id=_uuid(), entity_type="investigation",
                entity_id=investigation_id, content=req.cancel_reason,
                author_id=user.user_id, is_internal=True, is_redacted=False,
                version=1, created_at=_now(), updated_at=_now(),
            )
            await CommentRepo(self._db).create(comment, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              "investigation.cancelled", user.user_id,
                              {"status": old_status, "reason": req.cancel_reason},
                              {"status": "cancelled"}),
                uow.conn)

            if inv.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(inv.assigned_to, "investigation_cancelled",
                                      f"Investigation cancelled",
                                      req.cancel_reason,
                                      "investigation", investigation_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.cancelled", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "reason": req.cancel_reason,
                             "old_status": old_status}),
                uow.conn)

            resp = InvestigationMutationResponse(
                investigation=InvestigationResponse(**inv.model_dump()),
                version=inv.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp
