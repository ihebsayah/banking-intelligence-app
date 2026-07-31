from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, Resource, RequestContext, authorise,
    PermissionDeniedError as AuthPermissionDenied,
    ScopeDeniedError as AuthScopeDenied,
    OwnershipDeniedError as AuthOwnershipDenied,
)
from shared.database import DatabaseConnector

from workbench.exceptions import (
    IdempotencyMismatch, InvalidAssignee, InvalidTransition,
    ResourceNotFound, VersionConflict,
)
from workbench.models import (
    ActivityTimelineEntry, AssignmentHistoryEntry, AuditOutboxEvent,
    ComplianceCase, Decision, IdempotencyRecord, Notification,
)
from workbench.repos import (
    AssignmentHistoryRepo, CaseRepo, DecisionRepo, IdempotencyRepo,
    NotificationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.cases import (
    AssignCaseRequest, CaseAdminResponse, CaseAdminView,
    CaseDecisionResponse, CaseResponse,
    RecordDecisionRequest, TransitionCaseRequest,
)
from workbench.uow import UnitOfWork


ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "assigned": ["under_review"],
    "under_review": ["decision_pending"],
    "decision_pending": [],
    "awaiting_compliance_action": ["resolved"],
    "resolved": [],
    "closed": [],
    "cancelled": [],
}

DECISION_TYPE_TARGET: Dict[str, str] = {
    "no_action": "resolved",
    "closure_recommended": "resolved",
    "warning": "awaiting_compliance_action",
    "enhanced_due_diligence_recommended": "awaiting_compliance_action",
    "report_to_authority_recommended": "awaiting_compliance_action",
    "account_action_recommended": "awaiting_compliance_action",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


def _sha256(body: Any) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


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


def _resource_from_case(c: ComplianceCase) -> Resource:
    return Resource(
        id=c.case_id, status=c.status,
        assigned_to=c.assigned_to, scope_id=c.scope_id,
        version=c.version, entity_type="compliance_case",
        risk_level=c.risk_level,
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


class CaseService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def list_assigned(
        self, user: ApplicationUser, scope: str,
        status: Optional[str] = None, priority: Optional[str] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[CaseResponse], int]:
        await authorise(
            user, "case:read_assigned",
            Resource(id="", status="", entity_type="compliance_case"),
            self._db, RequestContext())
        cases = await CaseRepo(self._db).list(
            scope_id=scope, status=status, assigned_to=user.user_id,
            limit=min(per_page, 100), offset=(page - 1) * min(per_page, 100),
        )
        if priority:
            cases = [c for c in cases if c.priority == priority]
        return [CaseResponse(**c.model_dump()) for c in cases], len(cases)

    async def get_by_id(
        self, user: ApplicationUser, case_id: str,
    ) -> CaseResponse:
        c = await CaseRepo(self._db).fetch_by_id(case_id)
        if c is None:
            raise ResourceNotFound("Case", case_id)

        try:
            await authorise(user, "case:read_assigned",
                            _resource_from_case(c), self._db, RequestContext())
            return CaseResponse(**c.model_dump())
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            pass

        try:
            await authorise(user, "case:read",
                            _resource_from_case(c), self._db, RequestContext())
            return CaseResponse(**c.model_dump())
        except AuthPermissionDenied:
            raise ResourceNotFound("Case", case_id)

    async def assign(
        self, user: ApplicationUser, case_id: str,
        req: AssignCaseRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CaseAdminResponse:
        path = f"/api/v1/cases/{case_id}/assign"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return CaseAdminResponse.model_validate_json(idem[1])

            c = await CaseRepo(self._db).fetch_by_id(case_id, uow.conn)
            if c is None:
                raise ResourceNotFound("Case", case_id)

            await authorise(user, "case:assign",
                            _resource_from_case(c), self._db,
                            RequestContext(request_id=request_id))

            if c.status not in ("open", "assigned"):
                raise InvalidTransition(c.status, "assign")

            if req.assigned_to == c.assigned_to:
                resp = CaseAdminResponse(
                    case=CaseAdminView(**c.model_dump()),
                    version=c.version)
                await _store_idempotency(
                    IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                    req.model_dump(), 200, resp.model_dump_json(), uow.conn)
                return resp

            await _validate_assignee(self._db, req.assigned_to, c.scope_id, uow.conn)

            old_assigned_to = c.assigned_to
            c.assigned_to = req.assigned_to
            c.version += 1
            c.updated_at = _now()

            if c.status == "open":
                c.status = "assigned"

            updated = await CaseRepo(self._db).update(c, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id,
                              "case.assigned", user.user_id,
                              {"assigned_to": old_assigned_to},
                              {"assigned_to": req.assigned_to}),
                uow.conn)

            await AssignmentHistoryRepo(self._db).insert(
                _make_assignment("compliance_case", case_id,
                                old_assigned_to, req.assigned_to,
                                user.user_id, req.reason),
                uow.conn)

            if req.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(req.assigned_to, "case_assigned",
                                      f"Case assigned to you", c.title,
                                      "compliance_case", case_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("case.assigned", "compliance_case",
                            case_id, user.user_id, user.role,
                            {"case_id": case_id,
                             "assigned_to": req.assigned_to,
                             "reason": req.reason}),
                uow.conn)

            resp = CaseAdminResponse(
                case=CaseAdminView(**c.model_dump()),
                version=c.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def transition(
        self, user: ApplicationUser, case_id: str,
        req: TransitionCaseRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CaseAdminResponse:
        path = f"/api/v1/cases/{case_id}/transition"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return CaseAdminResponse.model_validate_json(idem[1])

            c = await CaseRepo(self._db).fetch_by_id(case_id, uow.conn)
            if c is None:
                raise ResourceNotFound("Case", case_id)

            target = req.target_status
            allowed = ALLOWED_TRANSITIONS.get(c.status, [])
            if target not in allowed:
                raise InvalidTransition(c.status, target)

            await authorise(user, "case:transition",
                            _resource_from_case(c), self._db,
                            RequestContext(request_id=request_id))

            if target == "resolved" and not req.resolution:
                raise InvalidTransition(c.status, target,
                                         detail="resolution is required when transitioning to resolved")

            old_status = c.status
            c.status = target
            c.version += 1
            c.updated_at = _now()

            if target == "resolved":
                c.resolution = req.resolution
                c.resolved_at = _now()
                c.resolved_by = user.user_id

            updated = await CaseRepo(self._db).update(c, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id,
                              f"case.{target}", user.user_id,
                              {"status": old_status}, {"status": target}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox(f"case.{target}", "compliance_case",
                            case_id, user.user_id, user.role,
                            {"case_id": case_id,
                             "old_status": old_status, "new_status": target}),
                uow.conn)

            resp = CaseAdminResponse(
                case=CaseAdminView(**c.model_dump()),
                version=c.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def record_decision(
        self, user: ApplicationUser, case_id: str,
        req: RecordDecisionRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CaseDecisionResponse:
        path = f"/api/v1/cases/{case_id}/decisions"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return CaseDecisionResponse.model_validate_json(idem[1])

            c = await CaseRepo(self._db).fetch_by_id(case_id, uow.conn)
            if c is None:
                raise ResourceNotFound("Case", case_id)

            if c.status != "decision_pending":
                raise InvalidTransition(c.status, "decision")

            await authorise(user, "case:decision",
                            _resource_from_case(c), self._db,
                            RequestContext(request_id=request_id))

            decision = Decision(
                decision_id=_uuid(), case_id=case_id,
                decision_type=req.decision_type.value, rationale=req.rationale,
                decided_by=user.user_id, decided_at=_now(),
                is_final=req.is_final,
                supersedes_decision_id=req.supersedes_decision_id,
            )
            await DecisionRepo(self._db).create(decision, uow.conn)

            target_status = DECISION_TYPE_TARGET.get(req.decision_type.value, "awaiting_compliance_action")

            old_status = c.status
            c.status = target_status
            c.current_disposition_id = decision.decision_id
            c.version += 1
            c.updated_at = _now()

            if target_status == "resolved":
                c.resolved_at = _now()
                c.resolved_by = user.user_id

            updated = await CaseRepo(self._db).update(c, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id,
                              "case.decision_recorded", user.user_id,
                              {"status": old_status, "decision_type": req.decision_type.value},
                              {"status": target_status, "decision_id": decision.decision_id}),
                uow.conn)

            await NotificationRepo(self._db).insert(
                _make_notification(c.created_by, "case_decision",
                                  f"Decision recorded on case",
                                  f"{req.decision_type.value}: {req.rationale}",
                                  "compliance_case", case_id),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("case.decision_recorded", "compliance_case",
                            case_id, user.user_id, user.role,
                            {"case_id": case_id,
                             "decision_id": decision.decision_id,
                             "decision_type": req.decision_type.value,
                             "rationale": req.rationale,
                             "is_final": req.is_final,
                             "target_status": target_status}),
                uow.conn)

            admin_view = CaseAdminView(**c.model_dump())
            resp = CaseDecisionResponse(
                case=admin_view,
                decision=decision.model_dump(),
                version=c.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp
