"""Approval request service — workflow logic for all approval endpoints (AP1-AP4).

Coordinates repos, authorise(), and UnitOfWork for each approval operation.
Follows the information-request/case service pattern: router validates/auth/http,
service holds business workflow, repo does SQL only.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
)
from shared.database import DatabaseConnector

from workbench.exceptions import (
    IdempotencyMismatch, InvalidTransition, PermissionDenied,
    ResourceNotFound, WorkbenchError,
)
from workbench.models import (
    ActivityTimelineEntry, ApprovalDecision, ApprovalRequest,
    AuditOutboxEvent, IdempotencyRecord, Notification,
)
from workbench.repos import (
    AlertRepo, ApprovalDecisionRepo, ApprovalRepo, CaseRepo,
    IdempotencyRepo, NotificationRepo, OutboxRepo, TimelineRepo,
)
from workbench.schemas.approvals import (
    ApprovalDecisionResponse, ApprovalRequestDetailResponse,
    ApprovalRequestMutationResponse, ApprovalRequestResponse,
    CreateApprovalRequest, VoteApprovalRequest,
)
from workbench.uow import UnitOfWork

# Action -> (allowed entity_type, allowed entity states)
ACTION_STATES: Dict[str, Tuple[str, set]] = {
    "alert_dismissal_critical_high": ("alert", {"acknowledged", "under_investigation"}),
    "case_closure_critical_high": ("compliance_case", {"resolved"}),
    "decision_report_to_authority": ("compliance_case", {"decision_pending"}),
    "case_reopen": ("compliance_case", {"closed"}),
}

# Role -> action types it may request (frozen role matrix).
ROLE_ACTION_TYPES: Dict[str, set] = {
    "analyst": {"alert_dismissal_critical_high"},
    "compliance": {"case_closure_critical_high", "decision_report_to_authority"},
    "admin": {"case_reopen"},
}

APPROVAL_EXPIRY_HOURS = 72
REQUIRED_APPROVALS = 1


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


def _resource_from_alert(a: Any) -> Resource:
    return Resource(
        id=a.alert_id, status=a.status,
        assigned_to=a.assigned_to, scope_id=a.scope_id,
        version=a.version, entity_type="alert",
        severity=a.severity,
    )


def _resource_from_case(c: Any) -> Resource:
    return Resource(
        id=c.case_id, status=c.status,
        assigned_to=c.assigned_to, scope_id=c.scope_id,
        version=c.version, entity_type="compliance_case",
        risk_level=c.risk_level, created_by=c.created_by,
    )


def _resource_from_approval(ar: ApprovalRequest, scope_id: str) -> Resource:
    return Resource(
        id=ar.approval_request_id, status=ar.status,
        assigned_to=ar.requested_by, scope_id=scope_id,
        version=ar.version, entity_type="approval_request",
    )


def _decision_response(d: ApprovalDecision) -> ApprovalDecisionResponse:
    return ApprovalDecisionResponse(
        approval_decision_id=d.approval_decision_id, approver_id=d.approver_id,
        decision=d.decision, rationale=d.rationale, decided_at=d.decided_at,
    )


def _detail_response(ar: ApprovalRequest,
                     decisions: List[ApprovalDecision]) -> ApprovalRequestDetailResponse:
    return ApprovalRequestDetailResponse(
        **ar.model_dump(),
        decisions=[_decision_response(d) for d in decisions],
    )


def _base_response(ar: ApprovalRequest) -> ApprovalRequestResponse:
    return ApprovalRequestResponse(**ar.model_dump())


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


async def _fetch_eligible_approvers(db: DatabaseConnector, scope_id: str,
                                    requester_id: str, conn: Any) -> List[str]:
    """All active compliance officers in scope, excluding the requester."""
    rows = await db.fetch_all(
        """
        SELECT u.user_id FROM users u
        JOIN user_scopes us ON us.user_id = u.user_id
        WHERE u.role = 'compliance' AND us.scope_id = $1
          AND u.user_id != $2 AND u.status = 'active'
        """, [scope_id, requester_id], conn=conn)
    return [r["user_id"] for r in rows]


class ApprovalService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── AP1 — POST /approval-requests ─────────────────────────────────────────

    async def create(
        self, user: ApplicationUser, req: CreateApprovalRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> ApprovalRequestMutationResponse:
        path = "/api/v1/approval-requests"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return ApprovalRequestMutationResponse.model_validate_json(idem[1])

            action_type = req.action_type.value if hasattr(req.action_type, "value") else req.action_type
            if action_type not in ROLE_ACTION_TYPES.get(user.role, set()):
                raise PermissionDenied(f"Action {action_type} not permitted for role {user.role}")

            expected_entity_type, allowed_states = ACTION_STATES[action_type]
            if req.entity_type.value != expected_entity_type:
                raise WorkbenchError(
                    "INVALID_APPROVAL_REQUEST",
                    f"{action_type} requires entity_type {expected_entity_type}", 400)

            if expected_entity_type == "alert":
                entity = await AlertRepo(self._db).fetch_by_id(req.entity_id, uow.conn)
                if entity is None:
                    raise ResourceNotFound("Alert", req.entity_id)
                resource = _resource_from_alert(entity)
            else:
                entity = await CaseRepo(self._db).fetch_by_id(req.entity_id, uow.conn)
                if entity is None:
                    raise ResourceNotFound("Case", req.entity_id)
                resource = _resource_from_case(entity)

            if entity.status not in allowed_states:
                raise WorkbenchError(
                    "INVALID_APPROVAL_REQUEST",
                    f"{action_type} not permitted for {expected_entity_type} in status {entity.status}",
                    400)

            await authorise(user, "approval:request", resource,
                            self._db, RequestContext(request_id=request_id))

            if action_type == "decision_report_to_authority":
                payload = req.proposed_payload or {}
                if payload.get("decision_type") != "report_to_authority_recommended":
                    raise WorkbenchError(
                        "INVALID_PROPOSED_PAYLOAD",
                        "proposed_payload must be {decision_type: report_to_authority_recommended}",
                        400)

            active = await ApprovalRepo(self._db).fetch_active_for_entity(
                expected_entity_type, req.entity_id, action_type, uow.conn)
            if active:
                raise InvalidTransition(
                    entity.status, "request_approval",
                    detail="An active approval request already exists for this entity")

            ar = ApprovalRequest(
                approval_request_id=_uuid(), action_type=action_type,
                entity_type=expected_entity_type, entity_id=req.entity_id,
                requested_by=user.user_id, rationale=req.rationale,
                required_approvals=REQUIRED_APPROVALS, approval_count=0,
                status="pending",
                expires_at=_now() + timedelta(hours=APPROVAL_EXPIRY_HOURS),
                version=1, created_at=_now(), updated_at=_now(),
            )
            await ApprovalRepo(self._db).create(ar, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("approval_request", ar.approval_request_id,
                               "approval_requested", user.user_id,
                               None,
                               {"status": "pending", "action_type": action_type,
                                "entity_type": expected_entity_type,
                                "entity_id": req.entity_id,
                                "required_approvals": ar.required_approvals}),
                uow.conn)

            approvers = await _fetch_eligible_approvers(
                self._db, resource.scope_id, user.user_id, uow.conn)
            for approver in approvers:
                await NotificationRepo(self._db).insert(
                    _make_notification(
                        approver, "approval_requested",
                        f"Approval requested",
                        f"{action_type} for {expected_entity_type} {req.entity_id}: {req.rationale}",
                        "approval_request", ar.approval_request_id),
                    uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("approval.created", "approval_request",
                             ar.approval_request_id, user.user_id, user.role,
                             _audit_payload(
                                 "approval.created", "approval_request",
                                 ar.approval_request_id, user.user_id, user.role,
                                 after={"status": "pending", "version": 1,
                                        "action_type": action_type,
                                        "entity_type": expected_entity_type,
                                        "entity_id": req.entity_id,
                                        "required_approvals": ar.required_approvals,
                                        "rationale_sha256": _sha256(ar.rationale)},
                                 request_id=request_id,
                                 metadata={"proposed_payload_sha256": _sha256(req.proposed_payload or {})})),
                uow.conn)

            resp = ApprovalRequestMutationResponse(
                approval_request=_detail_response(ar, []), version=ar.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 201, resp.model_dump_json(), uow.conn)
            return resp

    # ── AP2 — GET /approval-requests ──────────────────────────────────────────

    async def list(
        self, user: ApplicationUser,
        status: Optional[str] = None, action_type: Optional[str] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[ApprovalRequestResponse], int]:
        limit = min(per_page, 100)
        offset = (page - 1) * limit
        scopes = user.scopes or ["hq_main"]
        items = await ApprovalRepo(self._db).list(
            user.user_id, user.role, scopes, status, action_type, limit, offset)
        return [_base_response(ar) for ar in items], len(items)

    # ── AP3 — GET /approval-requests/{approval_request_id} ────────────────────

    async def get_by_id(self, user: ApplicationUser, approval_request_id: str) -> ApprovalRequestDetailResponse:
        ar = await ApprovalRepo(self._db).fetch_by_id(approval_request_id)
        if ar is None:
            raise ResourceNotFound("ApprovalRequest", approval_request_id)
        entity = await self._fetch_entity(ar)
        if entity is None:
            raise ResourceNotFound(ar.entity_type.title(), ar.entity_id)
        resource = _resource_from_approval(ar, entity.scope_id)
        await authorise(user, "approval:read", resource,
                        self._db, RequestContext())
        if user.role == "analyst" and ar.requested_by != user.user_id:
            raise ResourceNotFound("ApprovalRequest", approval_request_id)
        decisions = await ApprovalDecisionRepo(self._db).list_for_request(approval_request_id)
        return _detail_response(ar, decisions)

    # ── AP4 — POST /approval-requests/{approval_request_id}/vote ──────────────

    async def vote(
        self, user: ApplicationUser, approval_request_id: str,
        req: VoteApprovalRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> ApprovalRequestMutationResponse:
        path = f"/api/v1/approval-requests/{approval_request_id}/vote"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return ApprovalRequestMutationResponse.model_validate_json(idem[1])

            ar = await ApprovalRepo(self._db).fetch_by_id(approval_request_id, uow.conn)
            if ar is None:
                raise ResourceNotFound("ApprovalRequest", approval_request_id)
            entity = await self._fetch_entity(ar, uow.conn)
            if entity is None:
                raise ResourceNotFound(ar.entity_type.title(), ar.entity_id)

            decision = req.decision.value if hasattr(req.decision, "value") else req.decision
            resource = _resource_from_approval(ar, entity.scope_id)
            await authorise(user, "approval:approve", resource,
                            self._db, RequestContext(request_id=request_id))

            if ar.status != "pending":
                raise InvalidTransition(ar.status, "vote")
            if decision == "rejected" and not req.rationale:
                raise WorkbenchError("RATIONALE_REQUIRED",
                                     "rationale is required for a rejection vote", 400)

            existing = await ApprovalDecisionRepo(self._db).list_for_request(
                approval_request_id, uow.conn)
            if any(d.approver_id == user.user_id for d in existing):
                raise InvalidTransition(ar.status, "vote",
                                        detail="You have already voted on this request")

            updated = await ApprovalRepo(self._db).cast_vote(approval_request_id, decision, uow.conn)
            if updated is None:
                raise InvalidTransition(ar.status, "vote",
                                        detail="Approval request is no longer pending")

            ad = ApprovalDecision(
                approval_decision_id=_uuid(), approval_request_id=approval_request_id,
                approver_id=user.user_id, decision=decision,
                rationale=req.rationale, decided_at=_now(),
            )
            await ApprovalDecisionRepo(self._db).create(ad, uow.conn)
            decisions = existing + [ad]

            event = "approval_vote" if decision == "approved" else "approval_rejected"
            await TimelineRepo(self._db).insert(
                _make_timeline("approval_request", approval_request_id,
                               event, user.user_id,
                               {"status": "pending", "approval_count": ar.approval_count},
                               {"status": updated.status,
                                "approval_count": updated.approval_count}),
                uow.conn)

            if updated.status in ("approved", "rejected"):
                await NotificationRepo(self._db).insert(
                    _make_notification(
                        ar.requested_by, "approval_decided",
                        f"Approval request {updated.status}",
                        f"Your request for {ar.action_type} was {updated.status}",
                        "approval_request", approval_request_id),
                    uow.conn)

            if updated.status == "approved":
                event_type = "approval.approved"
            elif updated.status == "rejected":
                event_type = "approval.rejected"
            else:
                event_type = "approval.vote"
            await OutboxRepo(self._db).insert(
                _make_outbox(event_type, "approval_request", approval_request_id,
                             user.user_id, user.role,
                             _audit_payload(
                                 event_type, "approval_request", approval_request_id,
                                 user.user_id, user.role,
                                 before={"status": "pending",
                                         "approval_count": ar.approval_count},
                                 after={"status": updated.status,
                                        "approval_count": updated.approval_count,
                                        "version": updated.version,
                                        "approver_id": user.user_id,
                                        "decision": decision},
                                 request_id=request_id,
                                 metadata={"rationale_sha256": _sha256(req.rationale or "")})),
                uow.conn)

            resp = ApprovalRequestMutationResponse(
                approval_request=_detail_response(updated, decisions),
                version=updated.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def _fetch_entity(self, ar: ApprovalRequest, conn: Any = None) -> Any:
        if ar.entity_type == "alert":
            return await AlertRepo(self._db).fetch_by_id(ar.entity_id, conn)
        return await CaseRepo(self._db).fetch_by_id(ar.entity_id, conn)
