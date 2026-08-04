from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.notifications import (
    MarkAllReadResponse, NotificationListResponse, NotificationMutationResponse,
)
from workbench.services.notification_service import NotificationService

router = APIRouter(prefix="/api/v1", tags=["notifications"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _service(request: Request) -> NotificationService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return NotificationService(db)


# ── N1 — GET /notifications ───────────────────────────────────────────────────

@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    request: Request,
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total, unread = await svc.list(u, is_read, page, per_page)
    return NotificationListResponse(total=total, page=page, page_size=per_page,
                                    unread_count=unread, items=items)


# ── N2 — PATCH /notifications/{notification_id}/read ──────────────────────────

@router.patch("/notifications/{notification_id}/read",
              response_model=NotificationMutationResponse)
async def mark_notification_read(
    notification_id: str, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.mark_read(u, notification_id, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"))


# ── N3 — PATCH /notifications/read-all ────────────────────────────────────────

@router.patch("/notifications/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.mark_all_read(u, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"))
