"""Alert CRUD and workflow endpoints.

All mutations use a single transaction (UoW) and emit timeline + audit_outbox events.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.exceptions import WorkbenchError
from workbench.schemas.alerts import (
    AcknowledgeAlertRequest, AlertListResponse, AlertResponse,
    AssignAlertRequest, DismissAlertRequest, EscalateAlertRequest,
    EscalateResponse, InvestigateAlertRequest, InvestigateResponse,
    MutationResponse,
)
from workbench.services.alert_service import AlertService

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


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


def _service(request: Request) -> AlertService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return AlertService(db)


# ── GET /alerts/assigned ──────────────────────────────────────────────────────

@router.get("/assigned", response_model=AlertListResponse)
async def list_assigned(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_assigned(
        u, _get_scope(request), status_filter, severity, page, per_page)
    return AlertListResponse(total=total, page=page, page_size=per_page, items=items)


# ── GET /alerts/{alert_id} ───────────────────────────────────────────────────

@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: str, request: Request):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.get_by_id(u, alert_id)
    return result


# ── PATCH /alerts/{alert_id}/assign ──────────────────────────────────────────

@router.patch("/{alert_id}/assign", response_model=MutationResponse)
async def assign_alert(
    alert_id: str, req: AssignAlertRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.assign(u, alert_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── PATCH /alerts/{alert_id}/acknowledge ─────────────────────────────────────

@router.patch("/{alert_id}/acknowledge", response_model=MutationResponse)
async def acknowledge_alert(
    alert_id: str, req: AcknowledgeAlertRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.acknowledge(u, alert_id, req.expected_version, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── PATCH /alerts/{alert_id}/dismiss ─────────────────────────────────────────

@router.patch("/{alert_id}/dismiss", response_model=MutationResponse)
async def dismiss_alert(
    alert_id: str, req: DismissAlertRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.dismiss(u, alert_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── POST /alerts/{alert_id}/investigate ──────────────────────────────────────

@router.post("/{alert_id}/investigate", response_model=InvestigateResponse)
async def investigate_alert(
    alert_id: str, req: InvestigateAlertRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.investigate(u, alert_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})


# ── POST /alerts/{alert_id}/escalate ─────────────────────────────────────────

@router.post("/{alert_id}/escalate", response_model=EscalateResponse)
async def escalate_alert(
    alert_id: str, req: EscalateAlertRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.escalate(u, alert_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(), headers={"X-Version": str(result.version)})



