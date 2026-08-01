from __future__ import annotations

from fastapi import APIRouter, Request

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.admin_orphans import OrphanAssignmentsResponse
from workbench.services.admin_orphan_service import AdminOrphanService

router = APIRouter(prefix="/api/v1", tags=["admin-orphans"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _service(request: Request) -> AdminOrphanService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return AdminOrphanService(db)


# ── AD3 — GET /admin/orphan-assignments ────────────────────────────────────────

@router.get("/admin/orphan-assignments", response_model=OrphanAssignmentsResponse)
async def list_orphan_assignments(request: Request):
    u = _get_user(request)
    svc = _service(request)
    return await svc.list(u)
