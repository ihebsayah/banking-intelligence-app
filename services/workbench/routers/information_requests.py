from __future__ import annotations

from typing import Optional, Union

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.information_requests import (
    AcknowledgeInformationRequest, AcceptInformationRequest,
    CancelInformationRequest, CreateInformationRequest,
    InformationRequestAdminView, InformationRequestListResponse,
    InformationRequestMutationResponse, InformationRequestResponse,
    RespondInformationRequest, ReturnInformationRequest,
)
from workbench.services.information_request_service import InformationRequestService

router = APIRouter(prefix="/api/v1", tags=["information-requests"])


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


def _service(request: Request) -> InformationRequestService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return InformationRequestService(db)


# ── IR1 — POST /cases/{case_id}/information-requests ──────────────────────────

@router.post("/cases/{case_id}/information-requests",
             response_model=InformationRequestMutationResponse)
async def create_information_request(
    case_id: str, req: CreateInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.create(u, case_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), status_code=201,
                        headers={"X-Version": str(result.version)})


# ── IR2 — GET /cases/{case_id}/information-requests ───────────────────────────

@router.get("/cases/{case_id}/information-requests",
            response_model=InformationRequestListResponse)
async def list_information_requests(
    case_id: str, request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_for_case(u, case_id, status_filter, page, per_page)
    return InformationRequestListResponse(total=total, page=page, page_size=per_page, items=items)


# ── IR3 — GET /information-requests/{ir_id} ───────────────────────────────────

@router.get("/information-requests/{ir_id}",
            response_model=Union[InformationRequestResponse, InformationRequestAdminView])
async def get_information_request(ir_id: str, request: Request):
    u = _get_user(request)
    svc = _service(request)
    return await svc.get_by_id(u, ir_id)


# ── IR4 — PATCH /information-requests/{ir_id}/acknowledge ─────────────────────

@router.patch("/information-requests/{ir_id}/acknowledge",
              response_model=InformationRequestMutationResponse)
async def acknowledge_information_request(
    ir_id: str, req: AcknowledgeInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.acknowledge(u, ir_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── IR5 — PATCH /information-requests/{ir_id}/respond ─────────────────────────

@router.patch("/information-requests/{ir_id}/respond",
              response_model=InformationRequestMutationResponse)
async def respond_information_request(
    ir_id: str, req: RespondInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.respond(u, ir_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── IR6 — PATCH /information-requests/{ir_id}/accept ──────────────────────────

@router.patch("/information-requests/{ir_id}/accept",
              response_model=InformationRequestMutationResponse)
async def accept_information_request(
    ir_id: str, req: AcceptInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.accept(u, ir_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── IR7 — PATCH /information-requests/{ir_id}/return ──────────────────────────

@router.patch("/information-requests/{ir_id}/return",
              response_model=InformationRequestMutationResponse)
async def return_information_request(
    ir_id: str, req: ReturnInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.return_(u, ir_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── IR8 — POST /information-requests/{ir_id}/cancel ───────────────────────────

@router.post("/information-requests/{ir_id}/cancel",
             response_model=InformationRequestMutationResponse)
async def cancel_information_request(
    ir_id: str, req: CancelInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.cancel(u, ir_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})
