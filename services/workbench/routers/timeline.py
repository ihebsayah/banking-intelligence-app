from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, Request

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.timeline import TimelineListResponse
from workbench.services.timeline_service import TimelineService

router = APIRouter(prefix="/api/v1", tags=["timeline"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _service(request: Request) -> TimelineService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return TimelineService(db)


# ── TL1 — GET /{entity_type}/{entity_id}/timeline ─────────────────────────────

@router.get("/{entity_type}/{entity_id}/timeline",
            response_model=TimelineListResponse)
async def list_entity_timeline(
    entity_type: str, entity_id: str, request: Request,
    event_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_for_entity(
        u, entity_type, entity_id, event_type, page, per_page)
    return TimelineListResponse(total=total, page=page, page_size=per_page, items=items)


# ── TL2 — GET /timeline (own entities only) ───────────────────────────────────

@router.get("/timeline", response_model=TimelineListResponse)
async def list_own_timeline(
    request: Request,
    entity_type: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_for_user(
        u, entity_type, since, page, per_page)
    return TimelineListResponse(total=total, page=page, page_size=per_page, items=items)
