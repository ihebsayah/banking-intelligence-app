from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.comments import (
    CommentListResponse, CommentMutationResponse, CreateCommentRequest,
    RedactCommentRequest,
)
from workbench.services.comment_service import CommentService

router = APIRouter(prefix="/api/v1", tags=["comments"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _service(request: Request) -> CommentService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return CommentService(db)


# ── CM1 — GET /{entity_type}/{entity_id}/comments ─────────────────────────────

@router.get("/{entity_type}/{entity_id}/comments",
            response_model=CommentListResponse)
async def list_comments(
    entity_type: str, entity_id: str, request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_for_entity(u, entity_type, entity_id, page, per_page)
    return CommentListResponse(total=total, page=page, page_size=per_page, items=items)


# ── CM2 — POST /{entity_type}/{entity_id}/comments ────────────────────────────

@router.post("/{entity_type}/{entity_id}/comments",
             response_model=CommentMutationResponse)
async def create_comment(
    entity_type: str, entity_id: str, req: CreateCommentRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.create(u, entity_type, entity_id, req,
                              x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), status_code=201,
                        headers={"X-Version": str(result.version)})


# ── CM3 — PATCH /comments/{comment_id}/redact ─────────────────────────────────

@router.patch("/comments/{comment_id}/redact",
              response_model=CommentMutationResponse)
async def redact_comment(
    comment_id: str, req: RedactCommentRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.redact(u, comment_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(),
                        headers={"X-Version": str(result.version)})
