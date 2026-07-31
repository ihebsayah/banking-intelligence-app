"""Shared parent-entity resolution for comment/timeline endpoints (2B.9).

CM1/CM2/TL1 operate against a polymorphic parent (alert, investigation,
compliance_case, information_request). This module resolves the parent from the
URL entity_type segment, builds its authorisation Resource, and enforces the
entity read-access fallback chain used across the workbench services:
try the assigned/own read permission, then the broad read permission, otherwise
raise 404 so the entity appears nonexistent (object-level leakage policy).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
    OwnershipDeniedError as AuthOwnershipDenied,
    PermissionDeniedError as AuthPermissionDenied,
    ScopeDeniedError as AuthScopeDenied,
)
from shared.database import DatabaseConnector

from workbench.exceptions import ResourceNotFound, WorkbenchError
from workbench.models import (
    Alert, ComplianceCase, InformationRequest, Investigation,
)
from workbench.repos import (
    AlertRepo, CaseRepo, InfoRequestRepo, InvestigationRepo,
)

# URL entity_type segment -> canonical DB entity_type (comments CHECK constraint).
ENTITY_TYPE_SEGMENTS = {
    "alerts": "alert",
    "investigations": "investigation",
    "cases": "compliance_case",
    "information-requests": "information_request",
}

# canonical entity_type -> (assigned/own read action, broad read action)
ENTITY_READ_ACTIONS = {
    "alert": ("alert:read_assigned", "alert:read"),
    "investigation": ("investigation:read_own", "investigation:read"),
    "compliance_case": ("case:read_assigned", "case:read"),
    "information_request": ("info_request:read_assigned", "info_request:read"),
}


def resolve_entity_type(segment: str) -> str:
    """Map a URL entity_type segment to its canonical value; 400 when unknown."""
    canonical = ENTITY_TYPE_SEGMENTS.get(segment)
    if canonical is None:
        raise WorkbenchError(
            "INVALID_ENTITY_TYPE",
            f"Unsupported entity_type: {segment}",
            400,
        )
    return canonical


@dataclass
class ParentContext:
    """Resolved parent entity plus its authorisation resource.

    `case` is populated only for information_request parents (IR scope lives on
    the owning compliance case).
    """

    entity: Any
    resource: Resource
    case: Optional[ComplianceCase] = None


async def fetch_parent(db: DatabaseConnector, entity_type: str, entity_id: str,
                       conn: Any = None) -> ParentContext:
    """Load the parent entity and build its Resource, or raise 404."""
    if entity_type == "alert":
        entity = await AlertRepo(db).fetch_by_id(entity_id, conn)
    elif entity_type == "investigation":
        entity = await InvestigationRepo(db).fetch_by_id(entity_id, conn)
    elif entity_type == "compliance_case":
        entity = await CaseRepo(db).fetch_by_id(entity_id, conn)
    elif entity_type == "information_request":
        entity = await InfoRequestRepo(db).fetch_by_id(entity_id, conn)
    else:
        entity = None

    if entity is None:
        raise ResourceNotFound(entity_type, entity_id)

    case: Optional[ComplianceCase] = None
    if entity_type == "information_request":
        case = await CaseRepo(db).fetch_by_id(entity.case_id, conn)
        scope_id = case.scope_id if case else "hq_main"
    else:
        scope_id = entity.scope_id

    resource = _build_resource(entity_type, entity, scope_id)
    return ParentContext(entity=entity, resource=resource, case=case)


def _build_resource(entity_type: str, entity: Any, scope_id: str) -> Resource:
    if entity_type == "alert":
        return Resource(
            id=entity.alert_id, status=entity.status, assigned_to=entity.assigned_to,
            scope_id=scope_id, version=entity.version, entity_type="alert",
            severity=entity.severity, created_by=None,
        )
    if entity_type == "investigation":
        return Resource(
            id=entity.investigation_id, status=entity.status,
            assigned_to=entity.assigned_to, scope_id=scope_id,
            version=entity.version, entity_type="investigation",
            severity=None, created_by=entity.created_by,
        )
    if entity_type == "compliance_case":
        return Resource(
            id=entity.case_id, status=entity.status, assigned_to=entity.assigned_to,
            scope_id=scope_id, version=entity.version, entity_type="compliance_case",
            risk_level=entity.risk_level, created_by=entity.created_by,
        )
    return Resource(
        id=entity.ir_id, status=entity.status, assigned_to=entity.assigned_to,
        scope_id=scope_id, version=entity.version,
        entity_type="information_request", created_by=entity.created_by,
    )


async def assert_entity_readable(user: ApplicationUser, parent: ParentContext,
                                 db: DatabaseConnector,
                                 request_context: Optional[RequestContext] = None) -> None:
    """Authorise entity read via the assigned/own -> broad fallback chain.

    Raises 404 (leakage prevention) when neither path grants access. The
    information_request broad path additionally requires the user to be the IR
    creator or the owning case assignee, mirroring get_by_id OLP.
    """
    ctx = request_context or RequestContext()
    assigned_perm, broad_perm = ENTITY_READ_ACTIONS[parent.resource.entity_type]
    try:
        await authorise(user, assigned_perm, parent.resource, db, ctx)
        return
    except (AuthOwnershipDenied, AuthScopeDenied, AuthPermissionDenied):
        pass

    try:
        await authorise(user, broad_perm, parent.resource, db, ctx)
    except AuthPermissionDenied:
        raise ResourceNotFound(parent.resource.entity_type, parent.resource.id)

    if parent.resource.entity_type == "information_request" and user.role != "admin":
        ir: InformationRequest = parent.entity
        case_assignee = parent.case.assigned_to if parent.case else None
        if ir.created_by != user.user_id and case_assignee != user.user_id:
            raise ResourceNotFound("InformationRequest", ir.ir_id)
