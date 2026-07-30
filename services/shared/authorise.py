"""Shared authorisation policy engine for Phase 2B.

Pure policy — no HTTP, no framework imports.
All checks use passed db and user objects.
Raises authorisation errors as plain exceptions; caller translates to HTTP.
"""
from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Protocol


# ── Exceptions ─────────────────────────────────────────────────────────────────


class AuthorisationError(Exception):
    """Base for all authorisation denials."""

    def __init__(self, code: str, message: str, http_status: int = 403) -> None:
        self.code = code
        self.http_status = http_status
        super().__init__(message)

    def to_dict(self) -> dict:
        return {"error": self.code, "message": str(self)}


class ActionUnknownError(AuthorisationError):
    def __init__(self, action: str) -> None:
        super().__init__("UNKNOWN_ACTION", f"Unknown action: {action}", 400)


class ProhibitedComboError(AuthorisationError):
    def __init__(self, role: str, action: str) -> None:
        super().__init__("PROHIBITED", f"Action {action} is prohibited for role {role}", 403)


class PermissionDeniedError(AuthorisationError):
    def __init__(self, action: str) -> None:
        super().__init__("PERMISSION_DENIED", f"Permission not granted: {action}", 403)


class ScopeDeniedError(AuthorisationError):
    def __init__(self) -> None:
        super().__init__("SCOPE_DENIED", "Resource not found or not in scope", 404)


class OwnershipDeniedError(AuthorisationError):
    def __init__(self) -> None:
        super().__init__("OWNERSHIP_DENIED", "Resource not assigned to user", 404)


class WorkflowStateError(AuthorisationError):
    def __init__(self, status: str, action: str) -> None:
        super().__init__("WORKFLOW_STATE", f"Action {action} not permitted in status {status}", 409)


class ConflictOfInterestError(AuthorisationError):
    def __init__(self) -> None:
        super().__init__("CONFLICT_OF_INTEREST", "Cannot perform this action on own request", 403)


class ApprovalRequiredError(AuthorisationError):
    def __init__(self, action: str) -> None:
        super().__init__("APPROVAL_REQUIRED", f"Approval required for action: {action}", 428)


# ── Data types ─────────────────────────────────────────────────────────────────


@dataclass
class ApplicationUser:
    user_id: str
    role: str
    permissions: List[str] = field(default_factory=list)
    scopes: List[str] = field(default_factory=list)


@dataclass
class Resource:
    id: str
    status: str
    assigned_to: Optional[str] = None
    scope_id: Optional[str] = None
    version: Optional[int] = None
    entity_type: str = "unknown"
    severity: Optional[str] = None
    risk_level: Optional[str] = None


@dataclass
class RequestContext:
    request_id: str = ""
    ip_address: str = ""
    override_id: Optional[str] = None


class Database(Protocol):
    """Minimal DB interface needed by authorise()."""

    async def fetch_one(self, sql: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
        ...

    async def fetch_all(self, sql: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        ...


# ── Constants ──────────────────────────────────────────────────────────────────


ALL_PERMISSION_CODES: frozenset[str] = frozenset({
    "workbench:access",
    "alert:read_assigned", "alert:read", "alert:assign",
    "alert:acknowledge", "alert:dismiss", "alert:investigate",
    "alert:transition",
    "investigation:read_own", "investigation:read",
    "investigation:update", "investigation:modify_findings",
    "investigation:transition", "investigation:review",
    "investigation:assign",
    "case:create", "case:read_assigned", "case:read",
    "case:transition", "case:decision", "case:close",
    "case:assign", "case:reopen",
    "info_request:create", "info_request:read_assigned", "info_request:read",
    "info_request:respond", "info_request:accept", "info_request:return",
    "info_request:cancel",
    "approval:request", "approval:approve", "approval:read",
    "comment:create", "comment:read",
    "comment:view_internal_content", "comment:view_metadata",
    "comment:redact",
    "timeline:read",
    "notification:read", "notification:update",
    "admin:outbox_monitor", "admin:outbox_retry",
})

PROHIBITED: frozenset[tuple[str, str]] = frozenset({
    # Admin SoD
    ("admin", "case:decision"),
    ("admin", "case:close"),
    ("admin", "investigation:review"),
    ("admin", "investigation:modify_findings"),
    ("admin", "remediation:verify"),
    ("admin", "evidence:destroy"),
    # Analyst SoD
    ("analyst", "case:decision"),
    ("analyst", "case:close"),
    ("analyst", "case:assign"),
    ("analyst", "approval:approve"),
    # Legacy role
    ("manager", "workbench:access"),
    ("manager", "alert:acknowledge"),
    ("manager", "investigation:transition"),
    ("manager", "case:transition"),
    ("manager", "case:decision"),
    ("manager", "case:close"),
})

OWNERSHIP_ACTIONS: frozenset[str] = frozenset({
    "alert:acknowledge", "alert:dismiss", "alert:investigate",
    "investigation:update", "investigation:modify_findings",
    "investigation:transition",
    "info_request:respond",
})

ASSIGNED_READ_ACTIONS: frozenset[str] = frozenset({
    "alert:read_assigned", "investigation:read_own",
    "case:read_assigned", "info_request:read_assigned",
})

APPROVAL_VOTE_ACTIONS: frozenset[str] = frozenset({
    "approval:approve",
})

APPROVAL_GATED_ACTIONS: Dict[str, str] = {
    "alert:dismiss": "alert_dismissal_critical_high",
    "case:close": "case_closure_critical_high",
    "case:reopen": "case_reopen",
}

SENSITIVE_PERMISSIONS: frozenset[str] = frozenset({
    "case:decision", "case:close",
    "investigation:modify_findings",
    "remediation:verify", "evidence:destroy",
})

OVERRIDEABLE_ACTIONS: frozenset[str] = frozenset()  # Phase 2H


# ── State machine transition map ──────────────────────────────────────────────
# entity_type -> status -> set of allowed actions

ALERT_TRANSITIONS: Dict[str, set] = {
    "new": {"alert:assign", "alert:read_assigned", "alert:read"},
    "assigned": {"alert:acknowledge", "alert:assign", "alert:read_assigned", "alert:read"},
    "acknowledged": {"alert:investigate", "alert:dismiss", "alert:assign", "alert:read_assigned", "alert:read"},
    "under_investigation": {"alert:transition", "alert:assign", "alert:read_assigned", "alert:read"},
    "resolved": {"alert:read"},
    "dismissed": {"alert:read"},
}

INVESTIGATION_TRANSITIONS: Dict[str, set] = {
    "open": {"investigation:assign", "investigation:transition",
             "investigation:read_own", "investigation:read"},
    "active": {"investigation:update", "investigation:modify_findings",
               "investigation:transition", "investigation:assign",
               "investigation:read_own", "investigation:read"},
    "awaiting_information": {"investigation:read_own", "investigation:read"},
    "submitted": {"investigation:review", "investigation:assign",
                  "investigation:read_own", "investigation:read"},
    "returned": {"investigation:update", "investigation:modify_findings",
                 "investigation:transition", "investigation:read_own", "investigation:read"},
    "completed": {"investigation:read_own", "investigation:read"},
    "cancelled": {"investigation:read"},
}

CASE_TRANSITIONS: Dict[str, set] = {
    "open": {"case:assign", "case:read_assigned", "case:read"},
    "assigned": {"case:transition", "case:read_assigned", "case:read"},
    "under_review": {"case:transition", "case:decision",
                     "case:read_assigned", "case:read"},
    "awaiting_information": {"case:read_assigned", "case:read"},
    "decision_pending": {"case:transition", "case:read_assigned", "case:read"},
    "awaiting_compliance_action": {"case:transition", "case:read_assigned", "case:read"},
    "resolved": {"case:transition", "case:close", "case:read_assigned", "case:read"},
    "closed": {"case:reopen", "case:read"},
    "cancelled": {"case:read"},
}

IR_TRANSITIONS: Dict[str, set] = {
    "open": {"info_request:read_assigned", "info_request:read"},
    "acknowledged": {"info_request:respond", "info_request:read_assigned", "info_request:read"},
    "responded": {"info_request:accept", "info_request:return",
                  "info_request:read_assigned", "info_request:read"},
    "accepted": {"info_request:read"},
    "returned": {"info_request:read_assigned", "info_request:read"},
    "cancelled": {"info_request:read"},
}

ENTITY_TRANSITIONS: Dict[str, Dict[str, set]] = {
    "alert": ALERT_TRANSITIONS,
    "investigation": INVESTIGATION_TRANSITIONS,
    "compliance_case": CASE_TRANSITIONS,
    "information_request": IR_TRANSITIONS,
}


# ── Core function ─────────────────────────────────────────────────────────────


async def authorise(
    user: ApplicationUser,
    action: str,
    resource: Resource,
    db: Optional[Database] = None,
    request_context: Optional[RequestContext] = None,
) -> None:
    """Evaluate all 10 policy steps. Raises AuthorisationError on deny.

    Args:
        user: Authenticated user with role and permissions.
        action: Permission code for the attempted operation.
        resource: The target resource with status, scope, assignment.
        db: Database connector for approval/override lookups.
        request_context: Request metadata.
    """
    ctx = request_context or RequestContext()

    # Step 1 — Action known?
    if action not in ALL_PERMISSION_CODES:
        raise ActionUnknownError(action)

    # Step 2 — Prohibited combo?
    if (user.role, action) in PROHIBITED:
        raise ProhibitedComboError(user.role, action)

    # Step 3 — Permission granted?
    if action not in user.permissions:
        raise PermissionDeniedError(action)

    # Step 4 — Scope check
    if resource.scope_id:
        if resource.scope_id not in user.scopes and "global" not in user.scopes:
            raise ScopeDeniedError()

    # Step 5 — Ownership/assignment check
    if action in OWNERSHIP_ACTIONS:
        if resource.assigned_to != user.user_id:
            raise OwnershipDeniedError()

    # Step 6 — Workflow state permits action?
    entity_type = resource.entity_type
    status = resource.status
    valid_actions = ENTITY_TRANSITIONS.get(entity_type, {}).get(status, set())
    if action not in valid_actions:
        raise WorkflowStateError(status, action)

    # Step 7 — Conflict of interest
    if action in APPROVAL_VOTE_ACTIONS:
        if resource.assigned_to == user.user_id:
            raise ConflictOfInterestError()

    # Step 8 — Approval prerequisite
    if action in APPROVAL_GATED_ACTIONS:
        if action == "alert:dismiss" and resource.severity not in ("critical", "high"):
            pass  # only gated for critical/high
        elif action == "case:close" and resource.risk_level not in ("critical", "high"):
            pass  # only gated for critical/high
        else:
            approval_action_type = APPROVAL_GATED_ACTIONS[action]
            approval = await _fetch_active_approval(db, resource.id, approval_action_type) if db else None
            if approval is None:
                raise ApprovalRequiredError(action)

    # Step 9 — Emergency override (Phase 2H — not implemented)
    if action in OVERRIDEABLE_ACTIONS:
        pass

    # Step 10 — Default deny (reached only if no guard triggered = allow)


async def _fetch_active_approval(
    db: Optional[Database],
    entity_id: str,
    action_type: str,
) -> Optional[Dict[str, Any]]:
    if db is None:
        return None
    return await db.fetch_one(
        """
        SELECT approval_request_id, status, executed_at
        FROM approval_requests
        WHERE entity_id = $1::uuid
          AND action_type = $2
          AND status = 'approved'
          AND executed_at IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [entity_id, action_type],
    )
