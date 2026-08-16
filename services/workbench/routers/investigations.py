import re
from typing import Optional

from fastapi import APIRouter, File, Form, Header, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from shared.authorise import ApplicationUser
from shared.database import DatabaseConnector

from workbench.schemas.attachments import AttachmentListResponse, AttachmentResponse
from workbench.schemas.investigations import (
    CancelInvestigationRequest, EscalateInvestigationRequest,
    EscalateInvestigationResponse, InvestigationListResponse,
    InvestigationMutationResponse, InvestigationResponse,
    ReviewNotHarmfulRequest, TransitionInvestigationRequest,
    UpdateInvestigationRequest,
)
from workbench.services.attachment_service import AttachmentService
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


@router.get("/submitted", response_model=InvestigationListResponse)
async def list_submitted(
    request: Request,
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    u = _get_user(request)
    svc = _service(request)
    items, total = await svc.list_submitted(
        u, _get_scope(request), priority, page, per_page)
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
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


@router.patch("/{investigation_id}/transition", response_model=InvestigationMutationResponse)
async def transition_investigation(
    investigation_id: str, req: TransitionInvestigationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.transition(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


@router.post("/{investigation_id}/cancel", response_model=InvestigationMutationResponse)
async def cancel_investigation(
    investigation_id: str, req: CancelInvestigationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.cancel(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


@router.post("/{investigation_id}/review/not-harmful",
             response_model=InvestigationMutationResponse, status_code=200)
async def review_not_harmful(
    investigation_id: str, req: ReviewNotHarmfulRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.review_not_harmful(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


@router.post("/{investigation_id}/review/escalate",
             response_model=EscalateInvestigationResponse, status_code=200)
async def escalate_to_case(
    investigation_id: str, req: EscalateInvestigationRequest, request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _service(request)
    result = await svc.escalate_to_case(u, investigation_id, req, x_idempotency_key, x_request_id or "")
    return JSONResponse(content=result.model_dump(mode="json"), headers={"X-Version": str(result.version)})


def _attachment_service(request: Request) -> AttachmentService:
    db = _get_db(request)
    if db is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"error": "DB_UNAVAILABLE", "message": "Database not available"})
    return AttachmentService(db)


@router.post("/{investigation_id}/attachments", response_model=AttachmentResponse, status_code=201)
async def upload_attachment(
    investigation_id: str,
    request: Request,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _attachment_service(request)
    res = await svc.upload_attachment(
        user=u,
        investigation_id=investigation_id,
        original_filename=file.filename or "evidence.bin",
        content_type=file.content_type or "application/octet-stream",
        file_obj=file.file,
        description=description,
        request_id=x_request_id or "",
    )
    return res


@router.get("/{investigation_id}/attachments", response_model=AttachmentListResponse)
async def list_attachments(
    investigation_id: str,
    request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _attachment_service(request)
    return await svc.list_attachments(u, investigation_id, x_request_id or "")


@router.get("/{investigation_id}/attachments/{attachment_id}/download")
async def download_attachment(
    investigation_id: str,
    attachment_id: str,
    request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _attachment_service(request)
    att, file_path = await svc.get_attachment_for_download(u, investigation_id, attachment_id, x_request_id or "")

    safe_name = re.sub(r'[\r\n"\\]', '_', att.original_filename)
    headers = {"Content-Disposition": f'attachment; filename="{safe_name}"'}
    return FileResponse(file_path, media_type=att.content_type, headers=headers)


@router.delete("/{investigation_id}/attachments/{attachment_id}")
async def delete_attachment(
    investigation_id: str,
    attachment_id: str,
    request: Request,
    x_request_id: Optional[str] = Header(None, alias="X-Request-ID"),
):
    u = _get_user(request)
    svc = _attachment_service(request)
    success = await svc.delete_attachment(u, investigation_id, attachment_id, x_request_id or "")
    return {"success": success}

