"""Information request service — workflow logic for all IR endpoints (IR1-IR8).

Coordinates repos, authorise(), and UnitOfWork for each IR operation.
Follows the case/investigation service pattern: router validates/auth/http,
service holds business workflow, repo does SQL only.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
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
    ActivityTimelineEntry, AuditOutboxEvent, ComplianceCase,
    IdempotencyRecord, InformationRequest, InformationRequestAttachment,
    Investigation, Notification,
)
from workbench.repos import (
    CaseRepo, IdempotencyRepo, InfoRequestRepo, IrAttachmentRepo,
    InvestigationRepo, NotificationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.information_requests import (
    AcknowledgeInformationRequest, AcceptInformationRequest,
    CancelInformationRequest, CreateInformationRequest,
    InformationRequestAdminView, InformationRequestMutationResponse,
    InformationRequestResponse, IrAttachmentListResponse,
    IrAttachmentResponse, RespondInformationRequest,
    ReturnInformationRequest,
)
from workbench.storage import EvidenceStorage, validate_file_type
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


def _notification_parent(ir: "InformationRequest", case: Optional["ComplianceCase"] = None,
                         inv: Optional["Investigation"] = None) -> tuple[str, str]:
    """Point IR notifications at the owning workstream so compliance can reach the response."""
    if inv is not None:
        return "investigation", inv.investigation_id
    if case is not None:
        return "compliance_case", case.case_id
    return "information_request", ir.ir_id


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
    """Audit outbox payload v1 envelope.

    Sensitive content is hashed in before/after, never included verbatim.
    """
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


def _resource_from_case(c: ComplianceCase) -> Resource:
    return Resource(
        id=c.case_id, status=c.status,
        assigned_to=c.assigned_to, scope_id=c.scope_id,
        version=c.version, entity_type="compliance_case",
        risk_level=c.risk_level, created_by=c.created_by,
    )


def _resource_from_inv(inv: Investigation) -> Resource:
    return Resource(
        id=inv.investigation_id, status=inv.status,
        assigned_to=inv.assigned_to, scope_id=inv.scope_id,
        version=inv.version, entity_type="investigation",
        compliance_officer_id=inv.compliance_officer_id,
    )


def _resource_from_ir(ir: InformationRequest, scope_id: str) -> Resource:
    return Resource(
        id=ir.ir_id, status=ir.status, assigned_to=ir.assigned_to,
        scope_id=scope_id, version=ir.version,
        entity_type="information_request", created_by=ir.created_by,
    )


def _full_response(ir: InformationRequest) -> InformationRequestResponse:
    return InformationRequestResponse(**ir.model_dump())


def _admin_view(ir: InformationRequest) -> InformationRequestAdminView:
    return InformationRequestAdminView(
        ir_id=ir.ir_id, case_id=ir.case_id,
        investigation_id=ir.investigation_id, created_by=ir.created_by,
        due_date=ir.due_date, status=ir.status,
        responded_at=ir.responded_at, accepted_at=ir.accepted_at,
        returned_at=ir.returned_at, accepted_by=ir.accepted_by,
        returned_by=ir.returned_by, cancelled_at=ir.cancelled_at,
        cancelled_by=ir.cancelled_by, version=ir.version,
        created_at=ir.created_at, updated_at=ir.updated_at,
    )


def _mutation_response(ir: InformationRequest, role: str) -> InformationRequestMutationResponse:
    if role == "admin":
        return InformationRequestMutationResponse(
            information_request=_admin_view(ir), version=ir.version)
    return InformationRequestMutationResponse(
        information_request=_full_response(ir), version=ir.version)


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


class InformationRequestService:
    def __init__(self, db: DatabaseConnector, storage: Optional[EvidenceStorage] = None) -> None:
        self._db = db
        self._storage = storage or EvidenceStorage()

    async def _resolve_ir_parent(
        self, ir: InformationRequest, conn: Any = None
    ) -> Tuple[str, Resource, Optional[ComplianceCase], Optional[Investigation]]:
        if ir.case_id:
            case = await CaseRepo(self._db).fetch_by_id(ir.case_id, conn)
            if case is None:
                raise ResourceNotFound("Case", ir.case_id)
            return case.scope_id, _resource_from_ir(ir, case.scope_id), case, None
        elif ir.investigation_id:
            inv = await InvestigationRepo(self._db).fetch_by_id(ir.investigation_id, conn)
            if inv is None:
                raise ResourceNotFound("Investigation", ir.investigation_id)
            return inv.scope_id, _resource_from_ir(ir, inv.scope_id), None, inv
        else:
            raise WorkbenchError("INVALID_IR", "Information request has no parent entity", 400)

    async def _authorise_ir_read(
        self, user: ApplicationUser, ir: InformationRequest,
        scope_id: str, parent_assigned_to: Optional[str],
    ) -> bool:
        """Authorise reading an IR (and its attachments).

        Assigned users reach the IR via ``info_request:read_assigned``; other
        readers need ``info_request:read`` and must own the IR or be assigned
        to its parent entity. Fails closed (404 at the endpoint level).
        """
        resource = _resource_from_ir(ir, scope_id)
        try:
            await authorise(user, "info_request:read_assigned", resource,
                            self._db, RequestContext())
            return ir.assigned_to == user.user_id
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied,
                AuthWorkflowState, ResourceNotFound):
            pass

        try:
            await authorise(user, "info_request:read", resource,
                            self._db, RequestContext())
        except AuthPermissionDenied:
            return False

        if user.role != "admin":
            return ir.created_by == user.user_id or parent_assigned_to == user.user_id
        return True

    # ── IR1 — POST /cases/{case_id}/information-requests ─────────────────────

    async def create(
        self, user: ApplicationUser, case_id: str, req: CreateInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/cases/{case_id}/information-requests"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            case = await CaseRepo(self._db).fetch_by_id(case_id, uow.conn)
            if case is None:
                raise ResourceNotFound("Case", case_id)

            if case.status != "under_review":
                raise InvalidTransition(case.status, "create_information_request")

            await authorise(user, "info_request:create", _resource_from_case(case),
                            self._db, RequestContext(request_id=request_id))

            if req.due_date and req.due_date < date.today():
                raise WorkbenchError("INVALID_DUE_DATE",
                                     "due_date must be today or later", 400)

            active = await InfoRequestRepo(self._db).fetch_active_by_case_assignee(
                case_id, req.assigned_to, uow.conn)
            if active:
                raise InvalidTransition(
                    case.status, "create_information_request",
                    detail="An active information request already exists for this analyst")

            await _validate_assignee(self._db, req.assigned_to, case.scope_id, uow.conn)

            old_status = case.status
            case.status = "awaiting_information"
            case.version += 1
            case.updated_at = _now()

            ir = InformationRequest(
                ir_id=_uuid(), case_id=case_id,
                investigation_id=case.investigation_id,
                created_by=user.user_id, assigned_to=req.assigned_to,
                question=req.question, due_date=req.due_date,
                status="open", version=1, created_at=_now(), updated_at=_now(),
            )

            updated = await CaseRepo(self._db).update(case, req.expected_case_version, uow.conn)
            if updated is None:
                raise VersionConflict()
            await InfoRequestRepo(self._db).create(ir, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case_id,
                               "case.awaiting_information", user.user_id,
                               {"status": old_status},
                               {"status": "awaiting_information", "ir_id": ir.ir_id}),
                uow.conn)
            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir.ir_id,
                               "ir.created", user.user_id,
                               None,
                               {"question_sha256": _sha256(ir.question),
                                "assigned_to": ir.assigned_to,
                                "due_date": str(ir.due_date) if ir.due_date else None}),
                uow.conn)

            await NotificationRepo(self._db).insert(
                _make_notification(ir.assigned_to, "ir_created",
                                   f"Information request assigned to you",
                                   ir.question,
                                   *_notification_parent(ir, case, None)),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.created", "information_request", ir.ir_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "ir.created", "information_request", ir.ir_id,
                                 user.user_id, user.role,
                                 before=None,
                                 after={"status": "open", "version": 1,
                                        "assigned_to": ir.assigned_to,
                                        "question_sha256": _sha256(ir.question),
                                        "due_date": str(ir.due_date) if ir.due_date else None},
                                 request_id=request_id,
                                 metadata={"case_id": case_id})),
                uow.conn)
            await OutboxRepo(self._db).insert(
                _make_outbox("case.awaiting_info", "compliance_case", case_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "case.awaiting_info", "compliance_case", case_id,
                                 user.user_id, user.role,
                                 before={"status": old_status},
                                 after={"status": "awaiting_information",
                                        "version": case.version},
                                 request_id=request_id,
                                 metadata={"ir_id": ir.ir_id})),
                uow.conn)

            resp = InformationRequestMutationResponse(
                information_request=_full_response(ir), version=ir.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 201, resp.model_dump_json(), uow.conn)
            return resp

    # ── IR1.5 — POST /investigations/{investigation_id}/information-requests ──

    async def create_for_investigation(
        self, user: ApplicationUser, investigation_id: str, req: CreateInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/investigations/{investigation_id}/information-requests"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            if inv.status != "submitted":
                raise InvalidTransition(inv.status, "create_information_request")

            await authorise(user, "info_request:create", _resource_from_inv(inv),
                            self._db, RequestContext(request_id=request_id))

            if req.due_date and req.due_date < date.today():
                raise WorkbenchError("INVALID_DUE_DATE",
                                     "due_date must be today or later", 400)

            active = await InfoRequestRepo(self._db).fetch_active_by_investigation_assignee(
                investigation_id, req.assigned_to, uow.conn)
            if active:
                raise InvalidTransition(
                    inv.status, "create_information_request",
                    detail="An active information request already exists for this analyst")

            await _validate_assignee(self._db, req.assigned_to, inv.scope_id, uow.conn)

            old_status = inv.status
            inv.status = "awaiting_information"
            inv.version += 1
            inv.updated_at = _now()

            ir = InformationRequest(
                ir_id=_uuid(), case_id=None,
                investigation_id=investigation_id,
                created_by=user.user_id, assigned_to=req.assigned_to,
                question=req.question, due_date=req.due_date,
                status="open", version=1, created_at=_now(), updated_at=_now(),
            )

            expected_ver = req.expected_investigation_version or (inv.version - 1)
            updated = await InvestigationRepo(self._db).update(inv, expected_ver, uow.conn)
            if updated is None:
                raise VersionConflict()
            await InfoRequestRepo(self._db).create(ir, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                               "investigation.awaiting_information", user.user_id,
                               {"status": old_status},
                               {"status": "awaiting_information", "ir_id": ir.ir_id}),
                uow.conn)
            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir.ir_id,
                               "ir.created", user.user_id,
                               None,
                               {"question_sha256": _sha256(ir.question),
                                "assigned_to": ir.assigned_to,
                                "due_date": str(ir.due_date) if ir.due_date else None}),
                uow.conn)

            await NotificationRepo(self._db).insert(
                _make_notification(ir.assigned_to, "ir_created",
                                   f"Information request assigned to you",
                                   ir.question,
                                   *_notification_parent(ir, None, inv)),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.created", "information_request", ir.ir_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "ir.created", "information_request", ir.ir_id,
                                 user.user_id, user.role,
                                 before=None,
                                 after={"status": "open", "version": 1,
                                        "assigned_to": ir.assigned_to,
                                        "question_sha256": _sha256(ir.question),
                                        "due_date": str(ir.due_date) if ir.due_date else None},
                                 request_id=request_id,
                                 metadata={"investigation_id": investigation_id})),
                uow.conn)
            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.awaiting_info", "investigation", investigation_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "investigation.awaiting_info", "investigation", investigation_id,
                                 user.user_id, user.role,
                                 before={"status": old_status},
                                 after={"status": "awaiting_information",
                                        "version": inv.version},
                                 request_id=request_id,
                                 metadata={"ir_id": ir.ir_id})),
                uow.conn)

            resp = InformationRequestMutationResponse(
                information_request=_full_response(ir), version=ir.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 201, resp.model_dump_json(), uow.conn)
            return resp

    # ── IR2 — GET /cases/{case_id}/information-requests ──────────────────────

    async def list_for_case(
        self, user: ApplicationUser, case_id: str,
        status: Optional[str] = None, page: int = 1, per_page: int = 50,
    ) -> Tuple[List[Any], int]:
        case = await CaseRepo(self._db).fetch_by_id(case_id)
        if case is None:
            raise ResourceNotFound("Case", case_id)
        resource = _resource_from_case(case)

        assigned_path = False
        try:
            await authorise(user, "info_request:read_assigned", resource,
                            self._db, RequestContext())
            assigned_path = True
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            try:
                await authorise(user, "info_request:read", resource,
                                self._db, RequestContext())
            except AuthPermissionDenied:
                raise ResourceNotFound("Case", case_id)

        limit = min(per_page, 100)
        irs = await InfoRequestRepo(self._db).list_by_case(
            case_id, status=status, limit=limit, offset=(page - 1) * limit)

        if assigned_path:
            irs = [ir for ir in irs if ir.assigned_to == user.user_id]
        elif user.role != "admin":
            irs = [ir for ir in irs
                   if ir.created_by == user.user_id or case.assigned_to == user.user_id]

        if user.role == "admin":
            return [_admin_view(ir) for ir in irs], len(irs)
        return [_full_response(ir) for ir in irs], len(irs)

    # ── IR2.1 — GET /investigations/{investigation_id}/information-requests ──

    async def list_for_investigation(
        self, user: ApplicationUser, investigation_id: str,
        status: Optional[str] = None, page: int = 1, per_page: int = 50,
    ) -> Tuple[List[Any], int]:
        inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id)
        if inv is None:
            raise ResourceNotFound("Investigation", investigation_id)
        resource = _resource_from_inv(inv)

        assigned_path = False
        try:
            await authorise(user, "info_request:read_assigned", resource,
                            self._db, RequestContext())
            assigned_path = True
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            try:
                await authorise(user, "info_request:read", resource,
                                self._db, RequestContext())
            except AuthPermissionDenied:
                raise ResourceNotFound("Investigation", investigation_id)

        limit = min(per_page, 100)
        irs = await InfoRequestRepo(self._db).list_by_investigation(
            investigation_id, status=status, limit=limit, offset=(page - 1) * limit)

        if assigned_path:
            irs = [ir for ir in irs if ir.assigned_to == user.user_id]
        elif user.role != "admin":
            irs = [ir for ir in irs
                   if ir.created_by == user.user_id
                   or inv.assigned_to == user.user_id
                   or inv.compliance_officer_id == user.user_id]

        if user.role == "admin":
            return [_admin_view(ir) for ir in irs], len(irs)
        return [_full_response(ir) for ir in irs], len(irs)

    # ── IR2.5 — GET /information-requests/assigned ────────────────────────────

    async def list_assigned(
        self, user: ApplicationUser, scope: str,
        status: Optional[str] = None, page: int = 1, per_page: int = 50,
    ) -> Tuple[List[InformationRequestResponse], int]:
        await authorise(
            user, "info_request:read_assigned",
            Resource(id="assigned", status="active", entity_type="collection"),
            self._db, RequestContext())
        limit = min(per_page, 100)
        scopes = user.scopes or [scope]
        irs = await InfoRequestRepo(self._db).list_assigned(
            user.user_id, scopes, status=status, limit=limit,
            offset=(page - 1) * limit)
        total = await InfoRequestRepo(self._db).count_assigned(
            user.user_id, scopes, status=status)
        return [_full_response(ir) for ir in irs], total

    # ── IR3 — GET /information-requests/{ir_id} ───────────────────────────────

    async def get_by_id(
        self, user: ApplicationUser, ir_id: str,
    ) -> Any:
        ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id)
        if ir is None:
            raise ResourceNotFound("InformationRequest", ir_id)
        scope_id, resource, case, inv = await self._resolve_ir_parent(ir)
        parent_assigned_to = case.assigned_to if case else (inv.assigned_to if inv else None)

        if not await self._authorise_ir_read(user, ir, scope_id, parent_assigned_to):
            raise ResourceNotFound("InformationRequest", ir_id)
        return _admin_view(ir) if user.role == "admin" else _full_response(ir)

    # ── IR4 — PATCH /information-requests/{ir_id}/acknowledge ─────────────────

    async def acknowledge(
        self, user: ApplicationUser, ir_id: str, req: AcknowledgeInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/information-requests/{ir_id}/acknowledge"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)

            await authorise(user, "info_request:respond", resource,
                            self._db, RequestContext(request_id=request_id))

            if ir.status == "acknowledged":
                return _mutation_response(ir, user.role)
            if ir.status not in ("open", "returned"):
                raise InvalidTransition(ir.status, "acknowledge")

            old_status = ir.status
            ir.status = "acknowledged"
            ir.version += 1
            ir.updated_at = _now()

            updated = await InfoRequestRepo(self._db).update(ir, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            event = "ir.acknowledged" if old_status == "open" else "ir.re_acknowledged"
            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir_id, event, user.user_id,
                               {"status": old_status}, {"status": "acknowledged"}),
                uow.conn)

            if old_status == "open" and ir.created_by:
                await NotificationRepo(self._db).insert(
                    _make_notification(ir.created_by, "ir_acknowledged",
                                       f"Information request acknowledged",
                                       ir.question,
                                       *_notification_parent(ir, case, inv)),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox(event, "information_request", ir_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 event, "information_request", ir_id,
                                 user.user_id, user.role,
                                 before={"status": old_status, "version": req.expected_version},
                                 after={"status": "acknowledged", "version": ir.version},
                                 request_id=request_id,
                                 metadata={"case_id": ir.case_id, "investigation_id": ir.investigation_id})),
                uow.conn)

            resp = _mutation_response(ir, user.role)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── IR5 — PATCH /information-requests/{ir_id}/respond ─────────────────────

    async def respond(
        self, user: ApplicationUser, ir_id: str, req: RespondInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
        *,
        original_filename: Optional[str] = None,
        content_type: Optional[str] = None,
        file_obj: Optional[BinaryIO] = None,
        description: Optional[str] = None,
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/information-requests/{ir_id}/respond"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)

            await authorise(user, "info_request:respond", resource,
                            self._db, RequestContext(request_id=request_id))

            if ir.status == "responded":
                return _mutation_response(ir, user.role)
            if ir.status != "acknowledged":
                raise InvalidTransition(ir.status, "respond")

            old_status = ir.status
            ir.status = "responded"
            ir.response_text = req.response_text
            ir.responded_at = _now()
            ir.version += 1
            ir.updated_at = _now()

            stored_filename: Optional[str] = None
            try:
                if file_obj is not None:
                    validate_file_type(original_filename or "attachment.bin",
                                       content_type or "application/octet-stream")
                    attachment_id = _uuid()
                    stored_filename, sha256_hash, size_bytes = self._storage.save(
                        scope_id=scope_id, investigation_id=ir.ir_id,
                        attachment_id=attachment_id, file_obj=file_obj,
                    )
                    att = InformationRequestAttachment(
                        attachment_id=attachment_id, ir_id=ir.ir_id,
                        original_filename=original_filename or "attachment.bin",
                        stored_filename=stored_filename,
                        content_type=content_type or "application/octet-stream",
                        size_bytes=size_bytes, sha256_hash=sha256_hash,
                        description=description, uploaded_by=user.user_id,
                        uploaded_at=_now(),
                    )
                    try:
                        await IrAttachmentRepo(self._db).create(att, uow.conn)
                    except Exception:
                        # Compensation: DB write failed → remove the physical object.
                        self._storage.delete(scope_id, ir.ir_id, stored_filename)
                        raise
                    await TimelineRepo(self._db).insert(
                        _make_timeline("information_request", ir_id, "ir.attachment_uploaded",
                                       user.user_id, None,
                                       {"attachment_id": attachment_id,
                                        "content_type": content_type,
                                        "size_bytes": size_bytes,
                                        "sha256_hash": sha256_hash}),
                        uow.conn)
                    await OutboxRepo(self._db).insert(
                        _make_outbox("ir.attachment_uploaded", "information_request", ir_id,
                                     user.user_id, user.role,
                                     {"ir_id": ir_id, "attachment_id": attachment_id,
                                      "content_type": content_type, "size_bytes": size_bytes,
                                      "sha256_hash": sha256_hash}),
                        uow.conn)

                updated = await InfoRequestRepo(self._db).update(ir, req.expected_version, uow.conn)
                if updated is None:
                    raise VersionConflict()

                await TimelineRepo(self._db).insert(
                    _make_timeline("information_request", ir_id, "ir.responded", user.user_id,
                                   {"status": old_status}, {"status": "responded"}),
                    uow.conn)

                if ir.created_by:
                    await NotificationRepo(self._db).insert(
                        _make_notification(ir.created_by, "ir_responded",
                                           f"Information request responded",
                                           req.response_text,
                                           *_notification_parent(ir, case, inv)),
                        uow.conn)

                # If the parent investigation is awaiting_information and no
                # other active IRs remain (the just-responded IR stays in the
                # active set until compliance accepts/returns it), resume it back
                # into the review queue.
                inv_resumed = False
                if inv and inv.status == "awaiting_information":
                    active_irs = await InfoRequestRepo(self._db).fetch_active_by_investigation(
                        inv.investigation_id, uow.conn)
                    if len(active_irs) <= 1:
                        old_inv_status = inv.status
                        inv.status = "submitted"
                        inv.version += 1
                        inv.updated_at = _now()
                        await InvestigationRepo(self._db).update(inv, inv.version - 1, uow.conn)
                        inv_resumed = True
                        await TimelineRepo(self._db).insert(
                            _make_timeline("investigation", inv.investigation_id,
                                           "investigation.submitted", user.user_id,
                                           {"status": old_inv_status},
                                           {"status": "submitted", "reason": "ir_responded"}),
                            uow.conn)
                        if inv.assigned_to:
                            await NotificationRepo(self._db).insert(
                                _make_notification(inv.assigned_to, "investigation_submitted",
                                                   f"Information request responded — investigation returned to review",
                                                   f"IR {ir_id} responded",
                                                   "investigation", inv.investigation_id),
                                uow.conn)
                        await OutboxRepo(self._db).insert(
                            _make_outbox("investigation.submitted", "investigation", inv.investigation_id,
                                         user.user_id, user.role,
                                         _audit_payload(
                                             "investigation.submitted", "investigation", inv.investigation_id,
                                             user.user_id, user.role,
                                             before={"status": old_inv_status},
                                             after={"status": "submitted", "version": inv.version},
                                             request_id=request_id,
                                             metadata={"ir_id": ir_id})),
                            uow.conn)

                await OutboxRepo(self._db).insert(
                    _make_outbox("ir.responded", "information_request", ir_id,
                                 user.user_id, user.role,
                                 _audit_payload(
                                     "ir.responded", "information_request", ir_id,
                                     user.user_id, user.role,
                                     before={"status": old_status, "version": req.expected_version},
                                     after={"status": "responded", "version": ir.version,
                                            "response_text_sha256": _sha256(req.response_text),
                                            "responded_at": ir.responded_at.isoformat()},
                                     request_id=request_id,
                                     metadata={"case_id": ir.case_id, "investigation_id": ir.investigation_id,
                                               "investigation_resumed_triggered": inv_resumed})),
                    uow.conn)

                resp = _mutation_response(ir, user.role)
                await _store_idempotency(
                    IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                    req.model_dump(), 200, resp.model_dump_json(), uow.conn)
                return resp
            except Exception:
                if stored_filename:
                    # Compensation: response failed after physical write → remove the object.
                    self._storage.delete(scope_id, ir.ir_id, stored_filename)
                raise

    # ── IR5.1 — POST /information-requests/{ir_id}/attachments ───────────────

    async def upload_attachment(
        self, user: ApplicationUser, ir_id: str,
        original_filename: str, content_type: str, file_obj: BinaryIO,
        description: Optional[str] = None, request_id: str = "",
    ) -> IrAttachmentResponse:
        validate_file_type(original_filename, content_type)

        attachment_id = _uuid()
        stored_filename = None

        async with UnitOfWork(self._db) as uow:
            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)

            await authorise(user, "info_request:respond", resource,
                            self._db, RequestContext(request_id=request_id))

            if ir.status not in ("acknowledged", "returned"):
                raise InvalidTransition(ir.status, "upload_attachment")

            stored_filename, sha256_hash, size_bytes = self._storage.save(
                scope_id=scope_id, investigation_id=ir.ir_id,
                attachment_id=attachment_id, file_obj=file_obj,
            )

            att = InformationRequestAttachment(
                attachment_id=attachment_id, ir_id=ir.ir_id,
                original_filename=original_filename,
                stored_filename=stored_filename, content_type=content_type,
                size_bytes=size_bytes, sha256_hash=sha256_hash,
                description=description, uploaded_by=user.user_id,
                uploaded_at=_now(),
            )

            try:
                await IrAttachmentRepo(self._db).create(att, uow.conn)
            except Exception:
                # Compensation: delete physical storage object if DB record write fails
                if stored_filename:
                    self._storage.delete(scope_id, ir.ir_id, stored_filename)
                raise

            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir_id, "ir.attachment_uploaded",
                               user.user_id, None,
                               {"attachment_id": attachment_id,
                                "content_type": content_type,
                                "size_bytes": size_bytes,
                                "sha256_hash": sha256_hash}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.attachment_uploaded", "information_request", ir_id,
                             user.user_id, user.role,
                             {"ir_id": ir_id, "attachment_id": attachment_id,
                              "content_type": content_type, "size_bytes": size_bytes,
                              "sha256_hash": sha256_hash}),
                uow.conn)

            return IrAttachmentResponse(**att.model_dump())

    # ── IR5.2 — GET /information-requests/{ir_id}/attachments ────────────────

    async def list_attachments(
        self, user: ApplicationUser, ir_id: str, request_id: str = "",
    ) -> IrAttachmentListResponse:
        async with UnitOfWork(self._db) as uow:
            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)
            parent_assigned_to = case.assigned_to if case else (inv.assigned_to if inv else None)
            if not await self._authorise_ir_read(user, ir, scope_id, parent_assigned_to):
                raise ResourceNotFound("InformationRequest", ir_id)

            items = await IrAttachmentRepo(self._db).list_by_ir(ir_id, uow.conn)
            responses = [IrAttachmentResponse(**a.model_dump()) for a in items]
            return IrAttachmentListResponse(total=len(responses), items=responses)

    # ── IR5.3 — GET /information-requests/{ir_id}/attachments/{id}/download ──

    async def get_attachment_for_download(
        self, user: ApplicationUser, ir_id: str, attachment_id: str,
        request_id: str = "",
    ) -> Tuple[IrAttachmentResponse, str]:
        async with UnitOfWork(self._db) as uow:
            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)
            parent_assigned_to = case.assigned_to if case else (inv.assigned_to if inv else None)
            if not await self._authorise_ir_read(user, ir, scope_id, parent_assigned_to):
                raise ResourceNotFound("InformationRequest", ir_id)

            att = await IrAttachmentRepo(self._db).fetch_by_id_and_ir(attachment_id, ir_id, uow.conn)
            if att is None:
                raise ResourceNotFound("Attachment", attachment_id)

            file_path = self._storage.get_path(scope_id, ir.ir_id, att.stored_filename)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.attachment_downloaded", "information_request", ir_id,
                             user.user_id, user.role,
                             {"ir_id": ir_id, "attachment_id": attachment_id,
                              "downloaded_by": user.user_id}),
                uow.conn)

            return IrAttachmentResponse(**att.model_dump()), file_path

    # ── IR6 — PATCH /information-requests/{ir_id}/accept ──────────────────────

    async def accept(
        self, user: ApplicationUser, ir_id: str, req: AcceptInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/information-requests/{ir_id}/accept"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)

            await authorise(user, "info_request:accept", resource,
                            self._db, RequestContext(request_id=request_id))

            if ir.status == "accepted":
                return _mutation_response(ir, user.role)
            if ir.status != "responded":
                raise InvalidTransition(ir.status, "accept")

            old_status = ir.status
            ir.status = "accepted"
            ir.acceptance_note = req.acceptance_note
            ir.accepted_at = _now()
            ir.accepted_by = user.user_id
            ir.version += 1
            ir.updated_at = _now()

            updated = await InfoRequestRepo(self._db).update(ir, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir_id, "ir.accepted", user.user_id,
                               {"status": old_status}, {"status": "accepted"}),
                uow.conn)

            if case and case.status == "awaiting_information" and case.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(case.assigned_to, "ir_accepted",
                                       f"Information received — resume case review",
                                       f"IR {ir_id} accepted",
                                       "compliance_case", case.case_id),
                    uow.conn)

            inv_resumed = False
            if inv and inv.status == "awaiting_information":
                active_irs = await InfoRequestRepo(self._db).fetch_active_by_investigation(inv.investigation_id, uow.conn)
                if not active_irs:
                    old_inv_status = inv.status
                    inv.status = "submitted"
                    inv.version += 1
                    inv.updated_at = _now()
                    await InvestigationRepo(self._db).update(inv, inv.version - 1, uow.conn)
                    inv_resumed = True
                    await TimelineRepo(self._db).insert(
                        _make_timeline("investigation", inv.investigation_id,
                                       "investigation.submitted", user.user_id,
                                       {"status": old_inv_status},
                                       {"status": "submitted", "reason": "ir_accepted"}),
                        uow.conn)
                    if inv.assigned_to:
                        await NotificationRepo(self._db).insert(
                            _make_notification(inv.assigned_to, "investigation_submitted",
                                               f"Information received — investigation returned to review",
                                               f"IR {ir_id} accepted",
                                               "investigation", inv.investigation_id),
                            uow.conn)
                    await OutboxRepo(self._db).insert(
                        _make_outbox("investigation.submitted", "investigation", inv.investigation_id,
                                     user.user_id, user.role,
                                     _audit_payload(
                                         "investigation.submitted", "investigation", inv.investigation_id,
                                         user.user_id, user.role,
                                         before={"status": old_inv_status},
                                         after={"status": "submitted", "version": inv.version},
                                         request_id=request_id,
                                         metadata={"ir_id": ir_id})),
                        uow.conn)

            if ir.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(ir.assigned_to, "ir_accepted",
                                       f"Information request accepted",
                                       ir.question,
                                       *_notification_parent(ir, case, inv)),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.accepted", "information_request", ir_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "ir.accepted", "information_request", ir_id,
                                 user.user_id, user.role,
                                 before={"status": old_status, "version": req.expected_version},
                                 after={"status": "accepted", "version": ir.version,
                                        "accepted_by": ir.accepted_by,
                                        "acceptance_note_sha256": (
                                            _sha256(req.acceptance_note) if req.acceptance_note else None),
                                        "case_resumed_triggered": case.status == "awaiting_information" if case else False,
                                        "investigation_resumed_triggered": inv_resumed},
                                 request_id=request_id,
                                 metadata={"case_id": ir.case_id, "investigation_id": ir.investigation_id})),
                uow.conn)

            resp = _mutation_response(ir, user.role)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── IR7 — PATCH /information-requests/{ir_id}/return ──────────────────────

    async def return_(
        self, user: ApplicationUser, ir_id: str, req: ReturnInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/information-requests/{ir_id}/return"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)

            await authorise(user, "info_request:return", resource,
                            self._db, RequestContext(request_id=request_id))

            if ir.status == "returned":
                return _mutation_response(ir, user.role)
            if ir.status != "responded":
                raise InvalidTransition(ir.status, "return")

            old_status = ir.status
            ir.status = "returned"
            ir.return_reason = req.return_reason
            ir.returned_at = _now()
            ir.returned_by = user.user_id
            ir.version += 1
            ir.updated_at = _now()

            updated = await InfoRequestRepo(self._db).update(ir, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir_id, "ir.returned", user.user_id,
                               {"status": old_status}, {"status": "returned"}),
                uow.conn)

            if ir.assigned_to:
                await NotificationRepo(self._db).insert(
                    _make_notification(ir.assigned_to, "ir_returned",
                                       f"Information request returned for rework",
                                       req.return_reason,
                                       *_notification_parent(ir, case, inv)),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.returned", "information_request", ir_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "ir.returned", "information_request", ir_id,
                                 user.user_id, user.role,
                                 before={"status": old_status, "version": req.expected_version},
                                 after={"status": "returned", "version": ir.version,
                                        "returned_by": ir.returned_by,
                                        "return_reason_sha256": _sha256(req.return_reason)},
                                 request_id=request_id,
                                 metadata={"case_id": ir.case_id, "investigation_id": ir.investigation_id})),
                uow.conn)

            resp = _mutation_response(ir, user.role)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "PATCH", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    # ── IR8 — POST /information-requests/{ir_id}/cancel ───────────────────────

    async def cancel(
        self, user: ApplicationUser, ir_id: str, req: CancelInformationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InformationRequestMutationResponse:
        path = f"/api/v1/information-requests/{ir_id}/cancel"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InformationRequestMutationResponse.model_validate_json(idem[1])

            ir = await InfoRequestRepo(self._db).fetch_by_id(ir_id, uow.conn)
            if ir is None:
                raise ResourceNotFound("InformationRequest", ir_id)
            scope_id, resource, case, inv = await self._resolve_ir_parent(ir, uow.conn)

            await authorise(user, "info_request:cancel", resource,
                            self._db, RequestContext(request_id=request_id))

            if ir.status == "cancelled":
                return _mutation_response(ir, user.role)
            if ir.status not in ("open", "acknowledged"):
                raise InvalidTransition(ir.status, "cancel")

            old_status = ir.status
            ir.status = "cancelled"
            ir.cancel_reason = req.cancel_reason
            ir.cancelled_at = _now()
            ir.cancelled_by = user.user_id
            ir.version += 1
            ir.updated_at = _now()

            updated = await InfoRequestRepo(self._db).update(ir, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            await TimelineRepo(self._db).insert(
                _make_timeline("information_request", ir_id, "ir.cancelled", user.user_id,
                               {"status": old_status, "reason": req.cancel_reason},
                               {"status": "cancelled"}),
                uow.conn)

            # If inv is awaiting_information and no active IRs remain, resume inv
            inv_resumed = False
            if inv and inv.status == "awaiting_information":
                active_irs = await InfoRequestRepo(self._db).fetch_active_by_investigation(inv.investigation_id, uow.conn)
                if not active_irs:
                    old_inv_status = inv.status
                    inv.status = "submitted"
                    inv.version += 1
                    inv.updated_at = _now()
                    await InvestigationRepo(self._db).update(inv, inv.version - 1, uow.conn)
                    inv_resumed = True
                    await TimelineRepo(self._db).insert(
                        _make_timeline("investigation", inv.investigation_id,
                                       "investigation.submitted", user.user_id,
                                       {"status": old_inv_status},
                                       {"status": "submitted", "reason": "ir_cancelled"}),
                        uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("ir.cancelled", "information_request", ir_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 "ir.cancelled", "information_request", ir_id,
                                 user.user_id, user.role,
                                 before={"status": old_status, "version": req.expected_version},
                                 after={"status": "cancelled", "version": ir.version,
                                        "cancelled_by": ir.cancelled_by,
                                        "cancel_reason_sha256": _sha256(req.cancel_reason)},
                                 request_id=request_id,
                                 metadata={"case_id": ir.case_id, "investigation_id": ir.investigation_id})),
                uow.conn)

            resp = _mutation_response(ir, user.role)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp
