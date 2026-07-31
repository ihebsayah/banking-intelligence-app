from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.cases import (
    AssignCaseRequest, CaseAdminResponse, CaseDecisionListResponse,
    CaseDecisionResponse, CaseListResponse, CaseResponse,
    RecordDecisionRequest, TransitionCaseRequest,
)
from workbench.services.case_service import CaseService

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


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


def _service(request: Request) -> CaseService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return CaseService(db)


@router.get("/assigned", response_model=CaseListResponse)
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
    return CaseListResponse(total=total, page=page, page_size=per_page, items=items)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str, request: Request):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.get_by_id(u, case_id)
    return result


@router.patch("/{case_id}/assign", response_model=CaseAdminResponse)
async def assign_case(
    case_id: str, req: AssignCaseRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.assign(u, case_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


@router.patch("/{case_id}/transition", response_model=CaseAdminResponse)
async def transition_case(
    case_id: str, req: TransitionCaseRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.transition(u, case_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


@router.post("/{case_id}/decisions", response_model=CaseDecisionResponse,
             status_code=201)
async def record_decision(
    case_id: str, req: RecordDecisionRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.record_decision(u, case_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


@router.get("/{case_id}/decisions", response_model=CaseDecisionListResponse)
async def list_decisions(
    case_id: str, request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.list_decisions(u, case_id, x_request_id or "")
    return CaseDecisionListResponse(data=result)
