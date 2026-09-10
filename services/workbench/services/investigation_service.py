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
    Comment, ComplianceCase, IdempotencyRecord, Investigation,
    InvestigationReportSubmission, InvestigationReviewDecision, Notification,
)
from workbench.repos import (
    AlertRepo, AttachmentRepo, AssignmentHistoryRepo, CaseRepo, CommentRepo,
    IdempotencyRepo, InvestigationRepo, NotificationRepo, OutboxRepo,
    ReportSubmissionRepo, ReviewDecisionRepo, TimelineRepo,
)
from workbench.schemas.investigations import (
    CancelInvestigationRequest, EscalateInvestigationRequest,
    EscalateInvestigationResponse, InvestigationMutationResponse,
    InvestigationResponse, ReviewNotHarmfulRequest,
    SubmissionSnapshot, TransitionInvestigationRequest,
    UpdateInvestigationRequest,
)
from workbench.uow import UnitOfWork



ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "open": ["active"],
    "active": ["awaiting_information"],
    "awaiting_information": ["active"],
    "submitted": ["completed"],
    "completed": [],
    "cancelled": [],
}

TRANSITION_REQUIRED_ACTION: Dict[Tuple[str, str], str] = {
    ("open", "active"): "investigation:transition",
    ("active", "awaiting_information"): "investigation:transition",
    ("awaiting_information", "active"): "investigation:transition",
    ("submitted", "completed"): "investigation:review",
}

# `returned` is retained only as a legacy status. Post-submission analyst input
# is intentionally routed through the Information Request loop (see
# information_request_service) — there is NO return-for-revision re-open path,
# so `returned` is treated as frozen/read-only in the canonical C4 flow.
CANCEL_ALLOWED_FROM: set = {"open", "active", "awaiting_information", "submitted"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_real_user(row: Dict[str, Any]) -> bool:
    """Return whether an officer row is a real user rather than a test fixture.

    Test/seed compliance accounts use `@test.local` / `@test.com` email domains.
    """
    email = (row.get("email") or "").lower()
    return not (email.endswith("@test.local") or email.endswith("@test.com"))


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
        compliance_officer_id=inv.compliance_officer_id,
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

    async def _finalize_source_alert(self, investigation: Investigation,
                                     actor_id: str, conn: Any) -> Optional[str]:
        """Resolve the source alert when an investigation reaches a final
        compliance outcome (not harmful or escalated to case). No-op when the
        investigation has no linked alert. Returns the alert_id resolved."""
        if not investigation.alert_id:
            return None
        alert = await AlertRepo(self._db).fetch_by_id(investigation.alert_id, conn)
        if alert is None:
            return None
        if alert.status in ("dismissed", "resolved"):
            return alert.alert_id
        old_status = alert.status
        alert.status = "resolved"
        alert.resolved_by = actor_id
        alert.resolved_at = _now()
        alert.updated_at = _now()
        alert.version += 1
        await AlertRepo(self._db).update(alert, alert.version - 1, conn)
        await TimelineRepo(self._db).insert(
            _make_timeline("alert", alert.alert_id, "alert.resolved_from_investigation",
                          actor_id, {"status": old_status}, {"status": "resolved"}),
            conn)
        await OutboxRepo(self._db).insert(
            _make_outbox("alert.resolved_from_investigation", "alert",
                        alert.alert_id, actor_id, "compliance",
                        {"alert_id": alert.alert_id,
                         "investigation_id": investigation.investigation_id,
                         "old_status": old_status, "new_status": "resolved"}),
            conn)
        return alert.alert_id

    async def _notify_report_analyst(self, investigation: Investigation,
                                     ntype: str, title: str, body: str,
                                     conn: Any) -> None:
        recipient = investigation.assigned_to or investigation.created_by
        if not recipient:
            return
        await NotificationRepo(self._db).insert(
            _make_notification(recipient, ntype, title, body,
                              "investigation", investigation.investigation_id),
            conn)

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

    async def list_submitted(
        self, user: ApplicationUser, scope: str,
        priority: Optional[str] = None,
        page: int = 1, per_page: int = 50,
    ) -> Tuple[List[InvestigationResponse], int]:
        await authorise(
            user, "investigation:review",
            Resource(id="submitted", status="active", entity_type="collection"),
            self._db, RequestContext())
        # Compliance sees only investigations assigned to them
        officer_filter = user.user_id if user.role == "compliance" else None
        investigations = await InvestigationRepo(self._db).list(
            scope_id=scope, status="submitted",
            compliance_officer_id=officer_filter,
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
            return await self._response_with_snapshot(inv)
        except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
            pass

        try:
            await authorise(user, "investigation:read",
                            _resource_from_inv(inv), self._db, RequestContext())
            if inv.compliance_officer_id and inv.compliance_officer_id != user.user_id:
                raise ResourceNotFound("Investigation", investigation_id)
            return await self._response_with_snapshot(inv)
        except AuthPermissionDenied:
            raise ResourceNotFound("Investigation", investigation_id)

    async def _response_with_snapshot(
        self, inv: Investigation, conn=None,
    ) -> InvestigationResponse:
        resp = InvestigationResponse(**inv.model_dump())
        sub = await ReportSubmissionRepo(self._db).fetch_for_investigation(
            inv.investigation_id, conn)
        if sub is not None:
            resp.submission_snapshot = SubmissionSnapshot(
                submission_id=sub.submission_id,
                analyst_id=sub.analyst_id,
                compliance_officer_id=sub.compliance_officer_id,
                findings_text=sub.findings_text,
                findings_refs=sub.findings_refs,
                conclusion=sub.conclusion,
                submitted_at=sub.submitted_at,
                evidence_manifest=sub.evidence_manifest,
                report_hash=sub.report_hash,
            )
        return resp

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

            if inv.status != "active":
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

            if target == "returned" and not req.return_reason:
                raise InvalidAssignee("return_reason required when transitioning to returned")

            await authorise(user, action, _resource_from_inv(inv),
                            self._db, RequestContext(request_id=request_id))

            old_status = inv.status
            inv.status = target
            inv.version += 1
            inv.updated_at = _now()

            if target == "returned":
                inv.return_reason = req.return_reason
            if target == "active" and old_status == "returned":
                inv.return_reason = None
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

    async def review_not_harmful(
        self, user: ApplicationUser, investigation_id: str,
        req: ReviewNotHarmfulRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InvestigationMutationResponse:
        path = f"/api/v1/investigations/{investigation_id}/review/not-harmful"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InvestigationMutationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            await authorise(user, "investigation:review",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))

            if inv.compliance_officer_id and inv.compliance_officer_id != user.user_id:
                raise AuthOwnershipDenied()

            if inv.status != "submitted":
                raise InvalidTransition(inv.status, "review_not_harmful")

            # Persistent immutable decision record (replaces comment-prefix storage)
            decision = InvestigationReviewDecision(
                review_decision_id=_uuid(),
                investigation_id=investigation_id,
                compliance_officer_id=user.user_id,
                decision_type="NOT_HARMFUL",
                rationale=req.rationale.strip(),
                resulting_case_id=None,
                decided_at=_now(), created_at=_now(),
            )
            await ReviewDecisionRepo(self._db).insert(decision, uow.conn)

            old_status = inv.status
            inv.status = "completed"
            inv.completed_at = _now()
            inv.version += 1
            inv.updated_at = _now()

            updated = await InvestigationRepo(self._db).update(
                inv, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            resolved_alert = await self._finalize_source_alert(inv, user.user_id, uow.conn)
            await self._notify_report_analyst(
                inv, "investigation_reviewed",
                "Investigation closed as Not Harmful",
                f"{inv.title} was closed with a Not Harmful decision.", uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              "investigation.review_not_harmful", user.user_id,
                              {"status": old_status},
                              {"status": "completed",
                               "outcome": "not_harmful",
                               "reviewer": user.user_id,
                               "decision_id": decision.review_decision_id}),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.review_not_harmful", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "outcome": "not_harmful",
                             "reviewer": user.user_id,
                             "decision_id": decision.review_decision_id,
                             "resolved_alert_id": resolved_alert,
                             "old_status": old_status,
                             "new_status": "completed"}),
                uow.conn)

            resp = InvestigationMutationResponse(
                investigation=InvestigationResponse(**inv.model_dump()),
                version=inv.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def escalate_to_case(
        self, user: ApplicationUser, investigation_id: str,
        req: EscalateInvestigationRequest,
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> EscalateInvestigationResponse:
        path = f"/api/v1/investigations/{investigation_id}/review/escalate"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return EscalateInvestigationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            # Requires both investigation:review AND case:create
            await authorise(user, "investigation:review",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))
            await authorise(user, "case:create",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))

            if inv.compliance_officer_id and inv.compliance_officer_id != user.user_id:
                raise AuthOwnershipDenied()

            if inv.status != "submitted":
                raise InvalidTransition(inv.status, "escalate_to_case")

            # C4 immutable submission snapshot must exist (authoritative report
            # reference for the resulting case's provenance).
            snapshot = await ReportSubmissionRepo(self._db).fetch_for_investigation(
                investigation_id, uow.conn)
            if snapshot is None:
                raise WorkbenchError(
                    "NO_SUBMISSION_SNAPSHOT",
                    "Cannot escalate: the immutable report submission snapshot is missing.",
                    409,
                )

            # Duplicate escalation guard (app-level)
            existing_case = await CaseRepo(self._db).fetch_active_for_investigation(
                investigation_id, uow.conn)
            if existing_case:
                raise WorkbenchError(
                    "DUPLICATE_ESCALATION",
                    f"An active Compliance Case already exists for this investigation: {existing_case.case_id}",
                    409,
                )

            # Create the Compliance Case. The escalating officer is the initial
            # responsible officer (officer continuity — no unassigned pool).
            case = ComplianceCase(
                case_id=_uuid(),
                title=req.title,
                alert_id=inv.alert_id,
                investigation_id=investigation_id,
                scope_id=inv.scope_id,
                priority=req.priority,
                created_by=user.user_id,
                assigned_to=user.user_id,
                version=1, created_at=_now(), updated_at=_now(),
            )
            await CaseRepo(self._db).create(case, uow.conn)

            # Persistent immutable decision record (replaces comment-prefix storage)
            decision = InvestigationReviewDecision(
                review_decision_id=_uuid(),
                investigation_id=investigation_id,
                compliance_officer_id=user.user_id,
                decision_type="ESCALATE_TO_CASE",
                rationale=req.rationale.strip(),
                resulting_case_id=case.case_id,
                decided_at=_now(), created_at=_now(),
            )
            await ReviewDecisionRepo(self._db).insert(decision, uow.conn)

            # Finalize investigation
            old_status = inv.status
            inv.status = "completed"
            inv.completed_at = _now()
            inv.version += 1
            inv.updated_at = _now()

            updated = await InvestigationRepo(self._db).update(
                inv, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            resolved_alert = await self._finalize_source_alert(inv, user.user_id, uow.conn)
            await self._notify_report_analyst(
                inv, "investigation_escalated",
                "Investigation escalated to a Compliance Case",
                f"{inv.title} was escalated. A Compliance Case has been opened.",
                uow.conn)

            # Timeline on investigation
            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              "investigation.escalated_to_case", user.user_id,
                              {"status": old_status},
                              {"status": "completed",
                               "outcome": "escalated_to_case",
                               "case_id": case.case_id,
                               "reviewer": user.user_id,
                               "decision_id": decision.review_decision_id}),
                uow.conn)

            # Timeline on case
            await TimelineRepo(self._db).insert(
                _make_timeline("compliance_case", case.case_id,
                              "case.created", user.user_id,
                              None,
                              {"title": req.title, "priority": req.priority,
                               "investigation_id": investigation_id,
                               "alert_id": inv.alert_id}),
                uow.conn)

            # Outbox events
            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.escalated_to_case", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "outcome": "escalated_to_case",
                             "case_id": case.case_id,
                             "reviewer": user.user_id,
                             "decision_id": decision.review_decision_id,
                             "resolved_alert_id": resolved_alert,
                             "old_status": old_status,
                             "new_status": "completed"}),
                uow.conn)
            await OutboxRepo(self._db).insert(
                _make_outbox("case.created", "compliance_case",
                            case.case_id, user.user_id, user.role,
                            {"case_id": case.case_id,
                             "investigation_id": investigation_id,
                             "alert_id": inv.alert_id,
                             "created_by": user.user_id,
                             "assigned_to": user.user_id}),
                uow.conn)

            resp = EscalateInvestigationResponse(
                investigation=InvestigationResponse(**inv.model_dump()),
                case_id=case.case_id,
                version=inv.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def submit_to_compliance(
        self, user: ApplicationUser, investigation_id: str,
        req: "SubmitInvestigationRequest",
        idempotency_key: Optional[str] = None,
        request_id: str = "",
    ) -> InvestigationMutationResponse:
        from workbench.schemas.investigations import (
            SubmitInvestigationRequest, InvestigationResponse,
            InvestigationMutationResponse,
        )
        path = f"/api/v1/investigations/{investigation_id}/submit"
        async with UnitOfWork(self._db) as uow:
            idem = await _check_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), uow.conn)
            if idem:
                return InvestigationMutationResponse.model_validate_json(idem[1])

            inv = await InvestigationRepo(self._db).fetch_by_id(investigation_id, uow.conn)
            if inv is None:
                raise ResourceNotFound("Investigation", investigation_id)

            await authorise(user, "investigation:transition",
                            _resource_from_inv(inv), self._db,
                            RequestContext(request_id=request_id))

            if inv.assigned_to != user.user_id:
                raise AuthOwnershipDenied()

            if inv.status not in ("active",):
                raise InvalidTransition(inv.status, "submit_to_compliance")

            if not (inv.findings_text or inv.findings_refs):
                raise WorkbenchError(
                    "FINDINGS_REQUIRED",
                    "findings must be recorded before submitting the investigation",
                    400,
                )

            if not (inv.conclusion and inv.conclusion.strip()):
                raise WorkbenchError(
                    "CONCLUSION_REQUIRED",
                    "a conclusion must be recorded before submitting the investigation",
                    400,
                )

            officer_row = await self._db.fetch_one(
                "SELECT user_id, status, role, name, email FROM users WHERE user_id = $1",
                [req.compliance_officer_id], conn=uow.conn)
            if officer_row is None:
                raise InvalidAssignee(f"User not found: {req.compliance_officer_id}")
            if officer_row.get("status") != "active":
                raise InvalidAssignee(f"User is not active: {req.compliance_officer_id}")
            if officer_row.get("role") != "compliance":
                raise InvalidAssignee(
                    f"User is not an eligible Compliance Officer: {req.compliance_officer_id}")

            officer_perm_row = await self._db.fetch_one(
                "SELECT role_id FROM role_permissions WHERE role_id = $1 AND permission_key = 'investigation:review' LIMIT 1",
                [officer_row.get("role")], conn=uow.conn)
            if officer_perm_row is None or not _is_real_user(officer_row):
                raise InvalidAssignee(
                    f"User is not an eligible Compliance Officer: {req.compliance_officer_id}")

            old_status = inv.status
            inv.status = "submitted"
            inv.submitted_at = _now()
            inv.compliance_officer_id = req.compliance_officer_id
            inv.version += 1
            inv.updated_at = _now()

            updated = await InvestigationRepo(self._db).update(
                inv, req.expected_version, uow.conn)
            if updated is None:
                raise VersionConflict()

            attachments = await AttachmentRepo(self._db).list_by_investigation(
                investigation_id, uow.conn)
            evidence_manifest = [
                {"filename": a.original_filename, "sha256": a.sha256_hash,
                 "uploaded_by": a.uploaded_by, "uploaded_at": a.uploaded_at.isoformat()}
                for a in attachments
            ]
            report_hash = _sha256({
                "findings_text": inv.findings_text,
                "findings_refs": inv.findings_refs or [],
                "conclusion": inv.conclusion,
                "evidence_manifest": evidence_manifest,
            })
            submission = InvestigationReportSubmission(
                submission_id=_uuid(),
                investigation_id=investigation_id,
                analyst_id=user.user_id,
                compliance_officer_id=req.compliance_officer_id,
                findings_text=inv.findings_text,
                findings_refs=inv.findings_refs,
                conclusion=inv.conclusion,
                submitted_at=inv.submitted_at,
                evidence_manifest=evidence_manifest,
                report_hash=report_hash,
                created_at=_now(),
            )
            await ReportSubmissionRepo(self._db).insert(submission, uow.conn)

            await TimelineRepo(self._db).insert(
                _make_timeline("investigation", investigation_id,
                              "investigation.submitted_to_compliance", user.user_id,
                              {"status": old_status,
                               "assigned_compliance_officer": None},
                              {"status": "submitted",
                               "assigned_compliance_officer": req.compliance_officer_id}),
                uow.conn)

            await NotificationRepo(self._db).insert(
                _make_notification(req.compliance_officer_id,
                                  "investigation_assigned",
                                  "New investigation assigned for review",
                                  inv.title, "investigation", investigation_id),
                uow.conn)

            await OutboxRepo(self._db).insert(
                _make_outbox("investigation.submitted_to_compliance", "investigation",
                            investigation_id, user.user_id, user.role,
                            {"investigation_id": investigation_id,
                             "old_status": old_status,
                             "new_status": "submitted",
                             "compliance_officer_id": req.compliance_officer_id}),
                uow.conn)

            resp = InvestigationMutationResponse(
                investigation=await self._response_with_snapshot(inv, uow.conn),
                version=inv.version)
            await _store_idempotency(
                IdempotencyRepo(self._db), idempotency_key, "POST", path,
                req.model_dump(), 200, resp.model_dump_json(), uow.conn)
            return resp

    async def list_eligible_compliance_officers(
        self, user: ApplicationUser, scope: str,
    ) -> List["EligibleComplianceOfficer"]:
        from workbench.schemas.investigations import EligibleComplianceOfficer
        rows = await self._db.fetch_all(
            """
            SELECT u.user_id, u.name, u.email
            FROM users u
            INNER JOIN role_permissions rp ON rp.role_id = u.role
            WHERE u.status = 'active'
              AND u.role = 'compliance'
              AND rp.permission_key = 'investigation:review'
              AND u.email NOT ILIKE '%@test.local'
              AND u.email NOT ILIKE '%@test.com'
            ORDER BY u.name
            """,
            [], )
        return [EligibleComplianceOfficer(
            user_id=r["user_id"], name=r["name"], email=r["email"])
            for r in rows]

