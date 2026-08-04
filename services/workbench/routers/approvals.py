from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.approvals import (
    ApprovalRequestDetailResponse, ApprovalRequestListResponse,
    ApprovalRequestMutationResponse, CreateApprovalRequest,
    VoteApprovalRequest,
)
from workbench.services.approval_service import ApprovalService

router = APIRouter(prefix="/api/v1", tags=["approvals"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _service(request: Request) -> ApprovalService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return ApprovalService(db)


# ── AP1 — POST /approval-requests ─────────────────────────────────────────────

@router.post("/approval-requests",
             response_model=ApprovalRequestMutationResponse)
async def create_approval_request(
    req: CreateApprovalRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.create(u, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), status_code=201,
                        headers={"X-Version": str(result.version)})


# ── AP2 — GET /approval-requests ──────────────────────────────────────────────

@router.get("/approval-requests",
            response_model=ApprovalRequestListResponse)
async def list_approval_requests(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    action_type: Optional[str] = Query(None, alias="action_type"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list(u, status_filter, action_type, page, per_page)
    return ApprovalRequestListResponse(total=total, page=page, page_size=per_page, items=items)


# ── AP3 — GET /approval-requests/{approval_request_id} ────────────────────────

@router.get("/approval-requests/{approval_request_id}",
            response_model=ApprovalRequestDetailResponse)
async def get_approval_request(approval_request_id: str, request: Request):
    u = _get_user(request)
    svc = _service(request)
    return await svc.get_by_id(u, approval_request_id)


# ── AP4 — POST /approval-requests/{approval_request_id}/vote ─────────────────

@router.post("/approval-requests/{approval_request_id}/vote",
             response_model=ApprovalRequestMutationResponse)
async def vote_approval_request(
    approval_request_id: str, req: VoteApprovalRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.vote(u, approval_request_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})
