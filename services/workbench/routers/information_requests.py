from __future__ import annotations

import re
from typing import Optional, Union

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.information_requests import (
    AcknowledgeInformationRequest, AcceptInformationRequest,
    CancelInformationRequest, CreateInformationRequest,
    InformationRequestAdminView, InformationRequestListResponse,
    InformationRequestMutationResponse, InformationRequestResponse,
    IrAttachmentListResponse, IrAttachmentResponse,
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
    return JSONResponse(content=result.model_dump(mode="json"), status_code=201,
                        headers={"X-Version": str(result.version)})


# ── IR1.5 — POST /investigations/{investigation_id}/information-requests ──────

@router.post("/investigations/{investigation_id}/information-requests",
             response_model=InformationRequestMutationResponse)
async def create_investigation_information_request(
    investigation_id: str, req: CreateInformationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.create_for_investigation(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), status_code=201,
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


# ── IR2.1 — GET /investigations/{investigation_id}/information-requests ──────

@router.get("/investigations/{investigation_id}/information-requests",
            response_model=InformationRequestListResponse)
async def list_investigation_information_requests(
    investigation_id: str, request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_for_investigation(u, investigation_id, status_filter, page, per_page)
    return InformationRequestListResponse(total=total, page=page, page_size=per_page, items=items)


# ── IR2.5 — GET /information-requests/assigned (analyst inbox) ────────────────
# Registered before IR3's dynamic /{ir_id} route so "assigned" can never be
# captured as an ir_id (FastAPI matches routes in registration order).

@router.get("/information-requests/assigned",
            response_model=InformationRequestListResponse)
async def list_assigned_information_requests(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_assigned(
        u, _get_scope(request), status_filter, page, per_page)
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
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


# ── IR5 — PATCH /information-requests/{ir_id}/respond ─────────────────────────

@router.patch("/information-requests/{ir_id}/respond",
              response_model=InformationRequestMutationResponse)
async def respond_information_request(
    ir_id: str, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)

    response_text: Optional[str] = None
    expected_version: Optional[Union[int, str]] = None
    description: Optional[str] = None
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    file_obj = None

    content_type_header = request.headers.get("content-type", "") or ""
    if content_type_header.startswith("multipart/form-data"):
        form = await request.form()
        response_text = form.get("response_text")
        expected_version = form.get("expected_version")
        description = form.get("description") or None
        uploaded = form.get("file")
        if uploaded is not None:
            original_filename = uploaded.filename or "attachment.bin"
            content_type = uploaded.content_type or "application/octet-stream"
            file_obj = uploaded.file
    else:
        body = await request.json()
        response_text = body.get("response_text")
        expected_version = body.get("expected_version")
        description = body.get("description")

    req = RespondInformationRequest(response_text=response_text,
                                    expected_version=expected_version)
    result = await svc.respond(
        u, ir_id, req, x_idempotency_key, x_request_id or "",
        original_filename=original_filename, content_type=content_type,
        file_obj=file_obj, description=description)
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


# ── IR5.1 — POST /information-requests/{ir_id}/attachments ────────────────────

@router.post("/information-requests/{ir_id}/attachments",
             response_model=IrAttachmentResponse, status_code=201)
async def upload_information_request_attachment(
    ir_id: str, request: Request,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    return await svc.upload_attachment(
        user=u,
        ir_id=ir_id,
        original_filename=file.filename or "attachment.bin",
        content_type=file.content_type or "application/octet-stream",
        file_obj=file.file,
        description=description,
        request_id=x_request_id or "",
    )


# ── IR5.2 — GET /information-requests/{ir_id}/attachments ─────────────────────

@router.get("/information-requests/{ir_id}/attachments",
            response_model=IrAttachmentListResponse)
async def list_information_request_attachments(
    ir_id: str, request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    return await svc.list_attachments(u, ir_id, x_request_id or "")


# ── IR5.3 — GET /information-requests/{ir_id}/attachments/{id}/download ───────

@router.get("/information-requests/{ir_id}/attachments/{attachment_id}/download")
async def download_information_request_attachment(
    ir_id: str, attachment_id: str, request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    att, file_path = await svc.get_attachment_for_download(
        u, ir_id, attachment_id, x_request_id or "")

    safe_name = re.sub(r'[\r\n"\\]', '_', att.original_filename)
    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}
    return FileResponse(file_path, media_type=att.content_type, headers=headers)


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
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


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
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


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
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})
