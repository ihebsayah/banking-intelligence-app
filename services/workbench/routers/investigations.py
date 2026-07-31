from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.investigations import (
    CancelInvestigationRequest, InvestigationListResponse,
    InvestigationMutationResponse, InvestigationResponse,
    TransitionInvestigationRequest, UpdateInvestigationRequest,
)
from workbench.services.investigation_service import InvestigationService

router = APIRouter(prefix="/api/v1/investigations", tags=["investigations"])


def _get_db(request: Request) -> DatabaseConnector:
    return getattr(request.app.state, "db", None)


def _get_user(request: Request) -> ApplicationUser:
    user = getattr(request.state, "application_user", None)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail={"error": "AUTH_REQUIRED", "message": "Not authenticated"})
    return user


def _get_scope(request: Request) -> str:
    return getattr(request.state, "scope_id", "hq_main")


def _service(request: Request) -> InvestigationService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return InvestigationService(db)


@router.get("/assigned", response_model=InvestigationListResponse)
async def list_assigned(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_assigned(
        u, _get_scope(request), status_filter, priority, page, per_page)
    return InvestigationListResponse(total=total, page=page, page_size=per_page, items=items)


@router.get("/{investigation_id}", response_model=InvestigationResponse)
async def get_investigation(investigation_id: str, request: Request):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.get_by_id(u, investigation_id)
    return result


@router.patch("/{investigation_id}", response_model=InvestigationMutationResponse)
async def update_investigation(
    investigation_id: str, req: UpdateInvestigationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.update(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


@router.patch("/{investigation_id}/transition", response_model=InvestigationMutationResponse)
async def transition_investigation(
    investigation_id: str, req: TransitionInvestigationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.transition(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


@router.post("/{investigation_id}/cancel", response_model=InvestigationMutationResponse)
async def cancel_investigation(
    investigation_id: str, req: CancelInvestigationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.cancel(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})
