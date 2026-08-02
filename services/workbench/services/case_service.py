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
    ApprovalConsumed, ApprovalRequired, IdempotencyMismatch,
    InvalidAssignee, InvalidTransition, ResourceNotFound, VersionConflict,
    WorkbenchError,
)
from workbench.models import (
    ActivityTimelineEntry, Alert, ApprovalRequest, AssignmentHistoryEntry,
    AuditOutboxEvent, ComplianceCase, Decision, IdempotencyRecord,
    Notification,
)
from workbench.repos import (
    AlertRepo, ApprovalRepo, AssignmentHistoryRepo, CaseRepo, DecisionRepo,
    IdempotencyRepo, InvestigationRepo, NotificationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.cases import (
    AssignCaseRequest, CaseAdminReadResponse, CaseAdminResponse,
    CaseAdminView, CaseDecisionResponse, CaseResponse, CloseCaseRequest,
    RecordDecisionRequest, ReopenCaseRequest, TransitionCaseRequest,
)
from workbench.uow import UnitOfWork


ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "assigned": ["under_review"],
    "under_review": ["decision_pending"],
    "awaiting_information": ["under_review"],
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


def _audit_payload(event_type: str, entity_type: str, entity_id: str,
                   actor_id: str, actor_role: str,
                   before: Optional[Dict[str, Any]] = None,
                   after: Optional[Dict[str, Any]] = None,
                   request_id: str = "",
                   metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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


async def _fetch_admin_for_scope(db: DatabaseConnector, scope_id: str,
                                 conn: Any) -> Optional[str]:
    row = await db.fetch_one(
        "SELECT u.user_id FROM users u "
        "JOIN user_scopes us ON us.user_id = u.user_id "
        "WHERE u.role = 'admin' AND u.status = 'active' AND us.scope_id = $1 "
        "ORDER BY u.user_id LIMIT 1",
        [scope_id], conn=conn)
    return row["user_id"] if row else None


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
            Resource(id="assigned", status="active", entity_type="collection"),
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
            if c.assigned_to != user.user_id:
                raise AuthOwnershipDenied()
            return CaseResponse(**c.model_dump())
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            pass

        try:
            await authorise(user, "case:read",
                            _resource_from_case(c), self._db, RequestContext())
            return CaseAdminReadResponse(
                case_id=c.case_id, title=c.title, scope_id=c.scope_id,
                status=c.status, priority=c.priority, risk_level=c.risk_level,
                assigned_to=c.assigned_to, created_by=c.created_by,
                version=c.version, created_at=c.created_at,
                updated_at=c.updated_at,
            )
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

            resumed = old_status == "awaiting_information" and target == "under_review"
            timeline_event = "under_review_resumed" if resumed else f"case.{target}"
            audit_event = "case.resumed" if resumed else f"case.{target}"

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id,
                              timeline_event, user.user_id,
                              {"status": old_status}, {"status": target}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox(audit_event, "compliance_case",
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

    # ── C5 — POST /cases/{case_id}/close ──────────────────────────────────────

    async def close(
        self, user: ApplicationUser, case_id: str, req: CloseCaseRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CaseAdminResponse:
        path = f"/api/v1/cases/{case_id}/close"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return CaseAdminResponse.model_validate_json(idem[1])

            c = await CaseRepo(self._db).fetch_by_id(case_id, uow.conn)
            if c is None:
                raise ResourceNotFound("Case", case_id)

            await authorise(user, "case:close", _resource_from_case(c),
                            self._db, RequestContext(request_id=request_id))

            if c.status != "resolved":
                raise InvalidTransition(c.status, "close")

            resolution = req.resolution or c.resolution
            if not resolution:
                raise WorkbenchError(
                    "RESOLUTION_REQUIRED",
                    "resolution is required before closing the case", 400)

            approval_id = None
            if c.risk_level in ("critical", "high"):
                if not req.approval_request_id:
                    raise ApprovalRequired("case:close")
                approval = await ApprovalRepo(self._db).fetch_by_id(
                    req.approval_request_id, uow.conn)
                if approval is None:
                    raise ResourceNotFound("ApprovalRequest", req.approval_request_id)
                if (approval.entity_type != "compliance_case"
                        or approval.entity_id != case_id
                        or approval.action_type != "case_closure_critical_high"):
                    raise InvalidTransition(c.status, "close_approval_mismatch")
                if approval.status != "approved":
                    raise ApprovalRequired("case:close")
                if approval.executed_at is not None:
                    raise ApprovalConsumed()
                consumed = await ApprovalRepo(self._db).consume(
                    approval.approval_request_id, uow.conn)
                if consumed is None:
                    raise ApprovalConsumed()
                approval_id = approval.approval_request_id

            old_status = c.status
            c.status = "closed"
            c.resolution = resolution
            c.closed_at = _now()
            c.closed_by = user.user_id
            c.closure_approval_id = approval_id
            c.version += 1
            c.updated_at = _now()

            updated = await CaseRepo(self._db).update(c, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            if c.alert_id:
                alert = await AlertRepo(self._db).fetch_by_id(c.alert_id, uow.conn)
                if alert is not None and alert.status == "under_investigation":
                    old_alert_status = alert.status
                    alert.status = "resolved"
                    alert.resolved_at = _now()
                    alert.resolved_by = user.user_id
                    alert.version += 1
                    alert.updated_at = _now()
                    await AlertRepo(self._db).update(alert, alert.version - 1, uow.conn)
                    await TimelineRepo(self._db).insert(
                        _make_timeline("alert", alert.alert_id, "alert.resolved",
                                       user.user_id,
                                       {"status": old_alert_status},
                                       {"status": "resolved", "case_id": case_id}),
                        uow.conn)
                    await OutboxRepo(self._db).insert(
                        _make_outbox("alert.resolved", "alert", alert.alert_id,
                                     user.user_id, user.role,
                                     {"alert_id": alert.alert_id, "case_id": case_id}),
                        uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id, "case.closed", user.user_id,
                               {"status": old_status}, {"status": "closed"}),
                uow.conn)

            admin_user = await _fetch_admin_for_scope(self._db, c.scope_id, uow.conn)
            if admin_user is not None:
                await NotificationRepo(self._db).insert(
                    _make_notification(admin_user, "case_closed",
                                       f"Case closed", c.title,
                                       "compliance_case", case_id),
                    uow.conn)
            if c.investigation_id:
                inv = await InvestigationRepo(self._db).fetch_by_id(
                    c.investigation_id, uow.conn)
                if inv is not None and inv.assigned_to:
                    await NotificationRepo(self._db).insert(
                        _make_notification(inv.assigned_to, "case_closed",
                                           f"Case closed", c.title,
                                           "compliance_case", case_id),
                        uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("case.closed", "compliance_case",
                            case_id, user.user_id, user.role,
                            _audit_payload(
                                "case.closed", "compliance_case", case_id,
                                user.user_id, user.role,
                                before={"status": old_status,
                                        "version": req.expected_version},
                                after={"status": "closed", "version": c.version,
                                       "closed_by": c.closed_by,
                                       "closure_approval_id": approval_id,
                                       "resolution_sha256": _sha256(resolution)},
                                request_id=request_id,
                                metadata={"case_id": case_id})),
                uow.conn)

            resp = CaseAdminResponse(
                case=CaseAdminView(**c.model_dump()), version=c.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── C6 — POST /cases/{case_id}/reopen ─────────────────────────────────────

    async def reopen(
        self, user: ApplicationUser, case_id: str, req: ReopenCaseRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> CaseAdminResponse:
        path = f"/api/v1/cases/{case_id}/reopen"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return CaseAdminResponse.model_validate_json(idem[1])

            c = await CaseRepo(self._db).fetch_by_id(case_id, uow.conn)
            if c is None:
                raise ResourceNotFound("Case", case_id)

            await authorise(user, "case:reopen", _resource_from_case(c),
                            self._db, RequestContext(request_id=request_id))

            if c.status != "closed":
                raise InvalidTransition(c.status, "reopen")

            if not req.approval_request_id:
                raise ApprovalRequired("case:reopen")
            approval = await ApprovalRepo(self._db).fetch_by_id(
                req.approval_request_id, uow.conn)
            if approval is None:
                raise ResourceNotFound("ApprovalRequest", req.approval_request_id)
            if (approval.entity_type != "compliance_case"
                    or approval.entity_id != case_id
                    or approval.action_type != "case_reopen"):
                raise InvalidTransition(c.status, "reopen_approval_mismatch")
            if approval.status != "approved":
                raise ApprovalRequired("case:reopen")
            if approval.executed_at is not None:
                raise ApprovalConsumed()
            consumed = await ApprovalRepo(self._db).consume(
                approval.approval_request_id, uow.conn)
            if consumed is None:
                raise ApprovalConsumed()

            old_status = c.status
            c.status = "open"
            c.closed_at = None
            c.closed_by = None
            c.closure_approval_id = None
            c.reopen_reason = req.reopen_reason
            c.version += 1
            c.updated_at = _now()

            updated = await CaseRepo(self._db).update(c, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id, "case.reopened", user.user_id,
                               {"status": old_status}, {"status": "open"}),
                uow.conn)

            if c.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(c.assigned_to, "case_reopened",
                                       f"Case reopened", c.title,
                                       "compliance_case", case_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("case.reopened", "compliance_case",
                            case_id, user.user_id, user.role,
                            _audit_payload(
                                "case.reopened", "compliance_case", case_id,
                                user.user_id, user.role,
                                before={"status": old_status,
                                        "version": req.expected_version},
                                after={"status": "open", "version": c.version,
                                       "reopen_reason_sha256": _sha256(req.reopen_reason)},
                                request_id=request_id,
                                metadata={"case_id": case_id})),
                uow.conn)

            resp = CaseAdminResponse(
                case=CaseAdminView(**c.model_dump()), version=c.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
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

            decision_type = req.decision_type.value
            target_status = DECISION_TYPE_TARGET.get(decision_type, "awaiting_compliance_action")

            approval_id = None
            if decision_type == "report_to_authority_recommended":
                if not req.approval_request_id:
                    raise ApprovalRequired("case:decision")
                approval = await ApprovalRepo(self._db).fetch_by_id(
                    req.approval_request_id, uow.conn)
                if approval is None:
                    raise ResourceNotFound("ApprovalRequest", req.approval_request_id)
                if (approval.entity_type != "compliance_case"
                        or approval.entity_id != case_id
                        or approval.action_type != "decision_report_to_authority"):
                    raise InvalidTransition(c.status, "decision_approval_mismatch")
                if approval.status != "approved":
                    raise ApprovalRequired("case:decision")
                if approval.executed_at is not None:
                    raise ApprovalConsumed()
                consumed = await ApprovalRepo(self._db).consume(
                    approval.approval_request_id, uow.conn)
                if consumed is None:
                    raise ApprovalConsumed()
                approval_id = approval.approval_request_id

            decision = Decision(
                decision_id=_uuid(), case_id=case_id,
                decision_type=decision_type, rationale=req.rationale,
                decided_by=user.user_id, decided_at=_now(),
                approval_id=approval_id,
            )
            await DecisionRepo(self._db).create(decision, uow.conn)

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

            if target_status == "resolved":
                timeline_event = "case.resolved"
                audit_event = "case.resolved"
                notif_type = "case_resolved"
            else:
                timeline_event = "case.decision_recorded"
                audit_event = "case.decision_recorded"
                notif_type = "case_decision_recorded"

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id,
                              timeline_event, user.user_id,
                              {"status": old_status, "decision_type": decision_type},
                              {"status": target_status, "decision_id": decision.decision_id}),
                uow.conn)

            admin_user = await _fetch_admin_for_scope(self._db, c.scope_id, uow.conn)
            if admin_user is not None:
                await NotificationRepo(self._db).insert(
                    _make_notification(admin_user, notif_type,
                                      f"Decision recorded on case",
                                      f"{decision_type}: {req.rationale}",
                                      "compliance_case", case_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox(audit_event, "compliance_case",
                            case_id, user.user_id, user.role,
                            _audit_payload(
                                audit_event, "compliance_case", case_id,
                                user.user_id, user.role,
                                before={"status": old_status},
                                after={
                                    "status": target_status,
                                    "decision_id": decision.decision_id,
                                    "decision_type": decision_type,
                                    "version": c.version,
                                },
                                request_id=request_id,
                                metadata={
                                    "approval_id": approval_id,
                                    "rationale_sha256": _sha256(req.rationale),
                                })),
                uow.conn)

            admin_view = CaseAdminView(**c.model_dump())
            resp = CaseDecisionResponse(
                case=admin_view,
                decision=decision.model_dump(),
                version=c.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 201, resp.model_dump_json(), uow.conn)
            return resp

    async def list_decisions(
        self, user: ApplicationUser, case_id: str,
        request_id: str = "",
    ) -> List[Dict[str, Any]]:
        c = await CaseRepo(self._db).fetch_by_id(case_id)
        if c is None:
            raise ResourceNotFound("Case", case_id)
        resource = _resource_from_case(c)
        try:
            await authorise(user, "case:read_assigned", resource, self._db,
                            RequestContext(request_id=request_id))
            if c.assigned_to == user.user_id:
                decisions = await DecisionRepo(self._db).list_by_case(case_id)
                return [d.model_dump() for d in decisions]
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            pass
        try:
            await authorise(user, "case:read", resource, self._db,
                            RequestContext(request_id=request_id))
            decisions = await DecisionRepo(self._db).list_by_case(case_id)
            return [d.model_dump() for d in decisions]
        except AuthPermissionDenied:
            raise ResourceNotFound("Case", case_id)
        decisions = await DecisionRepo(self._db).list_by_case(case_id)
        return [d.model_dump() for d in decisions]
