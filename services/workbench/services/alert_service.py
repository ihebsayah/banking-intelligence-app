"""Alert service — workflow logic for all alert mutation endpoints.

Coordinates repos, authorise(), and UoW for each alert operation.
Never calls HTTP directly. Returns typed models; caller maps to HTTP.
"""
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
    ApprovalRequiredError as AuthApprovalRequired,
)
from shared.database import DatabaseConnector
from shared.errors import DatabaseError

from workbench.exceptions import (
    ApprovalConsumed, ApprovalRequired, IdempotencyMismatch, InvalidAssignee,
    InvalidTransition, PermissionDenied, ResourceNotFound, VersionConflict,
)
from workbench.models import (
    Alert, AssignmentHistoryEntry, AuditOutboxEvent,
    ComplianceCase, IdempotencyRecord, Investigation, Notification,
    ActivityTimelineEntry,
)
from workbench.repos import (
    AlertRepo, ApprovalRepo, AssignmentHistoryRepo, CaseRepo,
    IdempotencyRepo, InvestigationRepo, NotificationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.alerts import (
    AlertAdminResponse, AlertResponse, AssignAlertRequest,
    DismissAlertRequest, EscalateResponse, InvestigateResponse, MutationResponse,
)
from workbench.uow import UnitOfWork


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


def _resource_from_alert(a: Alert) -> Resource:
    return Resource(
        id=a.alert_id, status=a.status, assigned_to=a.assigned_to,
        scope_id=a.scope_id, version=a.version, entity_type="alert",
        severity=a.severity,
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


# ── Service ────────────────────────────────────────────────────────────────────

class AlertService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── GET /alerts/assigned ──────────────────────────────────────────────────

    async def list_assigned(
        self, user: ApplicationUser, scope: str,
        status: Optional[str] = None, severity: Optional[str] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[AlertResponse], int]:
        await authorise(user, "alert:read_assigned", Resource(id="", status="", entity_type="alert"),
                        self._db, RequestContext())
        alerts = await AlertRepo(self._db).list(
            scope_id=scope, status=status, assigned_to=user.user_id,
            limit=min(per_page, 100), offset=(page - 1) * min(per_page, 100),
        )
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        return [AlertResponse(**a.model_dump()) for a in alerts], len(alerts)

    # ── GET /alerts/{alert_id} ────────────────────────────────────────────────

    async def get_by_id(
        self, user: ApplicationUser, alert_id: str,
    ) -> AlertResponse | AlertAdminResponse:
        alert = await AlertRepo(self._db).fetch_by_id(alert_id)
        if alert is None:
            raise ResourceNotFound("Alert", alert_id)

        try:
            await authorise(user, "alert:read_assigned", _resource_from_alert(alert),
                            self._db, RequestContext())
            return AlertResponse(**alert.model_dump())
        except (AuthOwnershipDenied, AuthScopeDenied):
            pass

        try:
            await authorise(user, "alert:read", _resource_from_alert(alert),
                            self._db, RequestContext())
            return AlertAdminResponse(
                alert_id=alert.alert_id, alert_type=alert.alert_type,
                severity=alert.severity, status=alert.status,
                assigned_to=alert.assigned_to, scope_id=alert.scope_id,
                created_at=alert.created_at, version=alert.version,
            )
        except AuthPermissionDenied:
            raise ResourceNotFound("Alert", alert_id)

    # ── PATCH /alerts/{alert_id}/assign ───────────────────────────────────────

    async def assign(
        self, user: ApplicationUser, alert_id: str, req: AssignAlertRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> MutationResponse:
        path = f"/api/v1/alerts/{alert_id}/assign"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                status_code, body = idem
                return MutationResponse.model_validate_json(body)

            alert = await AlertRepo(self._db).fetch_by_id(alert_id, uow.conn)
            if alert is None:
                raise ResourceNotFound("Alert", alert_id)

            await authorise(user, "alert:assign", _resource_from_alert(alert),
                            self._db, RequestContext(request_id=request_id))

            if alert.assigned_to == req.assigned_to and alert.status in ("assigned", "acknowledged", "under_investigation"):
                return MutationResponse(alert=AlertResponse(**alert.model_dump()), version=alert.version)

            await _validate_assignee(self._db, req.assigned_to, alert.scope_id, uow.conn)

            old_assigned = alert.assigned_to
            old_status = alert.status
            if old_status == "new":
                alert.status = "assigned"
            elif old_status in ("dismissed", "resolved"):
                alert.status = "assigned"
            else:
                if old_status not in ("assigned", "acknowledged", "under_investigation"):
                    raise InvalidTransition(old_status, "assign")
                if old_assigned == req.assigned_to:
                    raise InvalidTransition(old_status, "reassign_same")

            if old_assigned and old_assigned != req.assigned_to:
                if not req.reason:
                    raise InvalidAssignee("Reason required for reassignment")
            if old_status in ("dismissed", "resolved") and not req.reason:
                raise InvalidAssignee("Reason required for reopening")

            alert.assigned_to = req.assigned_to
            alert.version += 1
            alert.updated_at = _now()

            updated = await AlertRepo(self._db).update(alert, old_version := alert.version - 1, uow.conn)
            if updated is None:
                raise VersionConflict()

            await AssignmentHistoryRepo(self._db).insert(
                _make_assignment("alert", alert_id, old_assigned,
                                req.assigned_to, user.user_id, req.reason),
                uow.conn)

            event = "alert.reopened" if old_status in ("dismissed", "resolved") else "alert.assigned"
            await TimelineRepo(self._db).insert(
                _make_timeline("alert", alert_id, event, user.user_id,
                              {"assigned_to": old_assigned, "status": old_status},
                              {"assigned_to": req.assigned_to, "status": alert.status}),
                uow.conn)

            await NotificationRepo(self._db).insert(
                _make_notification(req.assigned_to, "alert_assigned",
                                  f"Alert assigned to you", alert.title,
                                  "alert", alert_id),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox(event, "alert", alert_id, user.user_id,
                            user.role, {"alert_id": alert_id, "assigned_to": req.assigned_to}),
                uow.conn)

            resp = MutationResponse(alert=AlertResponse(**alert.model_dump()), version=alert.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── PATCH /alerts/{alert_id}/acknowledge ──────────────────────────────────

    async def acknowledge(
        self, user: ApplicationUser, alert_id: str,
        expected_version: int, idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> MutationResponse:
        path = f"/api/v1/alerts/{alert_id}/acknowledge"
        body = {"expected_version": expected_version}
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path, body, uow.conn)
            if idem:
                return MutationResponse.model_validate_json(idem[1])

            alert = await AlertRepo(self._db).fetch_by_id(alert_id, uow.conn)
            if alert is None:
                raise ResourceNotFound("Alert", alert_id)

            await authorise(user, "alert:acknowledge", _resource_from_alert(alert),
                            self._db, RequestContext(request_id=request_id))

            if alert.status == "acknowledged":
                return MutationResponse(alert=AlertResponse(**alert.model_dump()), version=alert.version)

            if alert.status != "assigned":
                raise InvalidTransition(alert.status, "acknowledge")

            old_status = alert.status
            alert.status = "acknowledged"
            alert.version += 1
            alert.updated_at = _now()

            updated = await AlertRepo(self._db).update(alert, expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("alert", alert_id, "alert.acknowledged", user.user_id,
                              {"status": old_status}, {"status": "acknowledged"}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("alert.acknowledged", "alert", alert_id, user.user_id,
                            user.role, {"alert_id": alert_id}),
                uow.conn)

            resp = MutationResponse(alert=AlertResponse(**alert.model_dump()), version=alert.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path, body,
                200, resp.model_dump_json(), uow.conn)
            return resp

    # ── PATCH /alerts/{alert_id}/dismiss ──────────────────────────────────────

    async def dismiss(
        self, user: ApplicationUser, alert_id: str, req: DismissAlertRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> MutationResponse:
        path = f"/api/v1/alerts/{alert_id}/dismiss"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return MutationResponse.model_validate_json(idem[1])

            alert = await AlertRepo(self._db).fetch_by_id(alert_id, uow.conn)
            if alert is None:
                raise ResourceNotFound("Alert", alert_id)

            await authorise(user, "alert:dismiss", _resource_from_alert(alert),
                            self._db, RequestContext(request_id=request_id))

            if alert.status not in ("acknowledged", "under_investigation"):
                raise InvalidTransition(alert.status, "dismiss")

            if alert.severity in ("critical", "high"):
                if not req.approval_request_id:
                    raise ApprovalRequired("alert:dismiss")
                approval = await ApprovalRepo(self._db).fetch_by_id(req.approval_request_id, uow.conn)
                if approval is None:
                    raise ResourceNotFound("ApprovalRequest", req.approval_request_id)
                if approval.entity_type != "alert" or approval.entity_id != alert_id:
                    raise InvalidTransition(alert.status, "dismiss_wrong_entity")
                if approval.status != "approved":
                    raise ApprovalRequired("alert:dismiss")
                if approval.executed_at is not None:
                    raise ApprovalConsumed()
                consumed = await ApprovalRepo(self._db).consume(approval.approval_request_id, uow.conn)
                if consumed is None:
                    raise ApprovalConsumed()

            old_status = alert.status
            alert.status = "dismissed"
            alert.dismissed_reason = req.dismissed_reason
            alert.dismissed_by = user.user_id
            alert.dismissed_at = _now()
            alert.version += 1
            alert.updated_at = _now()

            updated = await AlertRepo(self._db).update(alert, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("alert", alert_id, "alert.dismissed", user.user_id,
                              {"status": old_status}, {"status": "dismissed", "reason": req.dismissed_reason}),
                uow.conn)

            if alert.severity in ("critical", "high"):
                await NotificationRepo(self._db).insert(
                    _make_notification("compliance", "alert_dismissed",
                                      f"Critical/high alert dismissed: {alert.title}",
                                      f"Dismissed by {user.user_id}: {req.dismissed_reason}",
                                      "alert", alert_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("alert.dismissed", "alert", alert_id, user.user_id,
                            user.role, {"alert_id": alert_id, "reason": req.dismissed_reason}),
                uow.conn)

            resp = MutationResponse(alert=AlertResponse(**alert.model_dump()), version=alert.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── POST /alerts/{alert_id}/investigate ──────────────────────────────────

    async def investigate(
        self, user: ApplicationUser, alert_id: str, req: InvestigateAlertRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InvestigateResponse:
        path = f"/api/v1/alerts/{alert_id}/investigate"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InvestigateResponse.model_validate_json(idem[1])

            alert = await AlertRepo(self._db).fetch_by_id(alert_id, uow.conn)
            if alert is None:
                raise ResourceNotFound("Alert", alert_id)

            await authorise(user, "alert:investigate", _resource_from_alert(alert),
                            self._db, RequestContext(request_id=request_id))

            if alert.status != "acknowledged":
                raise InvalidTransition(alert.status, "investigate")

            inv = await InvestigationRepo(self._db).fetch_by_alert(alert_id, uow.conn)
            if inv:
                return InvestigateResponse(
                    alert=AlertResponse(**alert.model_dump()),
                    investigation_id=inv.investigation_id,
                    version=alert.version,
                )

            alert.status = "under_investigation"
            alert.version += 1
            alert.updated_at = _now()

            investigation = Investigation(
                investigation_id=_uuid(), title=req.title,
                description=req.description, alert_id=alert_id,
                scope_id=alert.scope_id, assigned_to=alert.assigned_to,
                created_by=user.user_id,
                version=1, created_at=_now(), updated_at=_now(),
            )

            updated = await AlertRepo(self._db).update(alert, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()
            await InvestigationRepo(self._db).create(investigation, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("alert", alert_id, "alert.investigation_started", user.user_id,
                              {"status": "acknowledged"}, {"status": "under_investigation"}),
                uow.conn)
            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation.investigation_id,
                              "investigation.created", user.user_id,
                              None, {"title": req.title}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("alert.investigation_started", "alert", alert_id,
                            user.user_id, user.role,
                            {"alert_id": alert_id, "investigation_id": investigation.investigation_id}),
                uow.conn)

            resp = InvestigateResponse(
                alert=AlertResponse(**alert.model_dump()),
                investigation_id=investigation.investigation_id,
                version=alert.version,
            )
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── POST /alerts/{alert_id}/escalate ──────────────────────────────────────

    async def escalate(
        self, user: ApplicationUser, alert_id: str, req: EscalateAlertRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> EscalateResponse:
        path = f"/api/v1/alerts/{alert_id}/escalate"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return EscalateResponse.model_validate_json(idem[1])

            alert = await AlertRepo(self._db).fetch_by_id(alert_id, uow.conn)
            if alert is None:
                raise ResourceNotFound("Alert", alert_id)

            await authorise(user, "alert:transition", _resource_from_alert(alert),
                            self._db, RequestContext(request_id=request_id))

            if alert.status != "under_investigation":
                raise InvalidTransition(alert.status, "escalate")

            inv = await InvestigationRepo(self._db).fetch_by_alert(alert_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", f"linked to alert {alert_id}")

            existing_case = await CaseRepo(self._db).fetch_active_for_alert(alert_id, uow.conn)
            if existing_case:
                return EscalateResponse(
                    alert=AlertResponse(**alert.model_dump()),
                    case_id=existing_case.case_id,
                    version=alert.version,
                )

            case = ComplianceCase(
                case_id=_uuid(), title=req.title, description=req.description,
                alert_id=alert_id, investigation_id=inv.investigation_id,
                scope_id=alert.scope_id, priority=req.priority.value,
                created_by=user.user_id,
                version=1, created_at=_now(), updated_at=_now(),
            )
            await CaseRepo(self._db).create(case, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("alert", alert_id, "alert.escalated", user.user_id,
                              {"status": "under_investigation", "investigation_id": inv.investigation_id},
                              {"case_id": case.case_id, "priority": req.priority.value}),
                uow.conn)
            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case.case_id, "case.created", user.user_id,
                              None, {"title": req.title, "priority": req.priority.value}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("alert.escalated", "alert", alert_id,
                            user.user_id, user.role,
                            {"alert_id": alert_id, "case_id": case.case_id}),
                uow.conn)
            await OutboxRepo(self._db).insert(
                _make_outbox("case.created", "compliance_case", case.case_id,
                            user.user_id, user.role,
                            {"case_id": case.case_id, "alert_id": alert_id}),
                uow.conn)

            resp = EscalateResponse(
                alert=AlertResponse(**alert.model_dump()),
                case_id=case.case_id, version=alert.version,
            )
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp



