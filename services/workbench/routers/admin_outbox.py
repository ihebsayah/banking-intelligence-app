from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.admin_outbox import OutboxListResponse, OutboxRetryResponse
from workbench.services.admin_outbox_service import AdminOutboxService

router = APIRouter(prefix="/api/v1", tags=["admin-outbox"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _service(request: Request) -> AdminOutboxService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return AdminOutboxService(db)


# ── AD1 — GET /admin/outbox ───────────────────────────────────────────────────

@router.get("/admin/outbox", response_model=OutboxListResponse)
async def list_outbox(
    request: Request,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list(u, status, page, per_page)
    return OutboxListResponse(total=total, page=page, page_size=per_page, items=items)


# ── AD2 — POST /admin/outbox/{outbox_id}/retry ────────────────────────────────

@router.post("/admin/outbox/{outbox_id}/retry",
             response_model=OutboxRetryResponse)
async def retry_outbox_event(
    outbox_id: str, request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    return await svc.retry(u, outbox_id, x_request_id or "")
