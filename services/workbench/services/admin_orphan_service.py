"""Admin orphan-assignment service — workflow logic for AD3.

Read-only diagnostic endpoint. Runs the canonical contract query
(increment-2B-api-contracts.md AD3) and groups results by entity type.
No audit event, no mutation, no reassignment (contract: "Audit: None
(read-only)").
"""
from __future__ import annotations

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
)
from shared.database import DatabaseConnector

from workbench.repos import OrphanRepo
from workbench.schemas.admin_orphans import (
    OrphanAssignee, OrphanAssignmentItem, OrphanAssignmentsResponse,
)


def _orphan_resource() -> Resource:
    return Resource(id="orphan-assignments", status="active",
                    entity_type="orphan_assignment")


class AdminOrphanService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def list(self, user: ApplicationUser) -> OrphanAssignmentsResponse:
        await authorise(user, "admin:orphan_monitor", _orphan_resource(),
                        self._db, RequestContext())
        rows = await OrphanRepo(self._db).orphan_assignments()
        groups: dict[str, list[OrphanAssignmentItem]] = {
            "alert": [], "investigation": [], "compliance_case": [],
        }
        for r in rows:
            groups[r["entity_type"]].append(OrphanAssignmentItem(
                entity_id=r["entity_id"],
                title=r["title"],
                status=r["status"],
                assigned_to=OrphanAssignee(
                    user_id=r["assigned_user_id"],
                    status=r["assigned_user_status"],
                ),
            ))
        return OrphanAssignmentsResponse(
            alerts=groups["alert"],
            investigations=groups["investigation"],
            cases=groups["compliance_case"],
        )
