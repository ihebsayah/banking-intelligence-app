"""
services/api_gateway/routes.py
Route definitions for the API Gateway.

Endpoints:
  POST /auth/login   → authenticate, return JWT
  GET  /health       → liveness probe
  POST /query        → submit NL query through full pipeline (Week 4)
"""
import time
import uuid
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from shared.config import get_settings
from shared.errors import AuthenticationError, TokenExpiredError, InvalidTokenError
from shared.logger import get_logger
from shared.models import (
    AuditLogEntry,
    AuditLogResponse,
    AuditStatus,
    HealthResponse,
    LoginResponse,
    User,
)
from auth import authenticate_user, create_access_token, verify_token

logger = get_logger(__name__, "api-gateway")
settings = get_settings()
router = APIRouter()
security = HTTPBearer(auto_error=False)

ORCHESTRATOR_URL = "http://orchestrator-agent:8001"


# ─── Request model ────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    format: str = "json"    # json | csv | table


# ─── Dependency: get_current_user ────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    FastAPI dependency that extracts and validates the Bearer JWT.
    Attach to any protected endpoint with: user: User = Depends(get_current_user)
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_REQUIRED", "message": "Authorization header missing"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id, user_role = verify_token(credentials.credentials)
        return User(user_id=user_id, user_role=user_role)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.to_dict(),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Internal helper: log to audit service ───────────────────────────────────

async def _send_audit_log(entry: AuditLogEntry) -> None:
    """
    Fire-and-forget HTTP POST to audit-agent /log_access.
    Non-fatal: if audit service is down we log locally and continue.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.AUDIT_AGENT_URL}/log_access",
                json=entry.model_dump(mode="json"),
            )
    except Exception as exc:
        # IMPORTANT: audit failure must never break the user's request
        logger.error(
            "Failed to send audit log",
            extra={"audit_id": entry.audit_id, "error": str(exc)},
        )


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["monitoring"],
)
async def health() -> HealthResponse:
    """
    Returns service health status.
    Does NOT require authentication — used by Docker health checks and load balancers.
    """
    return HealthResponse(service="api-gateway")


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="Authenticate and receive JWT",
    tags=["authentication"],
)
async def login(
    request: Request,
    username: str = Form(..., description="User's login name"),
    password: str = Form(..., description="User's password"),
) -> LoginResponse:
    """
    Authenticate user credentials and return a signed JWT access token.

    Mock users (MVP):
      - analyst_001 / password    → role: analyst
      - analyst_002 / password    → role: analyst
      - compliance_001 / password → role: compliance
      - manager_001 / password    → role: manager

    Returns:
        LoginResponse with access_token, user_id, user_role, expires_in.
    """
    start_time = time.monotonic()
    ip_address = request.client.host if request.client else "unknown"

    user = authenticate_user(username, password)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    if not user:
        # Log failed login attempt to audit
        await _send_audit_log(
            AuditLogEntry(
                user_id=username,
                user_role="unknown",
                action="login",
                status=AuditStatus.REJECTED,
                ip_address=ip_address,
                endpoint="/auth/login",
                http_method="POST",
                execution_time_ms=elapsed_ms,
                error_message="Invalid credentials",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "AUTH_FAILED",
                "message": "Invalid username or password",
            },
        )

    token, expires_in = create_access_token(user.user_id, user.user_role)

    # Log successful login
    await _send_audit_log(
        AuditLogEntry(
            user_id=user.user_id,
            user_role=user.user_role,
            action="login",
            status=AuditStatus.SUCCESS,
            ip_address=ip_address,
            endpoint="/auth/login",
            http_method="POST",
            execution_time_ms=elapsed_ms,
        )
    )

    logger.info(
        "User login successful",
        extra={"user_id": user.user_id, "role": user.user_role, "ip": ip_address},
    )

    return LoginResponse(
        access_token=token,
        user_id=user.user_id,
        user_role=user.user_role,
        expires_in=expires_in,
    )


# ─── /query — Full NL pipeline (Week 4) ──────────────────────────────────────

@router.post(
    "/query",
    summary="Submit natural language query",
    tags=["query"],
)
async def submit_query(
    request: Request,
    body: QueryRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """
    Submit a natural language query through the full 6-agent pipeline.

    Pipeline:
      Intent → Schema → Entity Resolution → SQL → Validation → Execution

    Input:
      {"query": "Show me high-risk customers in New York", "format": "json"}

    Output:
      {
        "status": "success",
        "results": [...],
        "metadata": {
          "rows_returned": 47,
          "execution_time_ms": 245,
          "data_freshness": "real-time",
          "source": "database",
          "user_role": "analyst"
        }
      }

    Formats: json | csv | table
    """
    start_time = time.monotonic()
    ip_address = request.client.host if request.client else "unknown"

    logger.info(
        "Query received",
        extra={"user_id": user.user_id, "role": user.user_role, "query": body.query[:80]},
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process_query",
                json={
                    "query":     body.query,
                    "user_role": user.user_role,
                    "user_id":   user.user_id,
                    "format":    body.format,
                },
            )
            pipeline_result = response.json()
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        await _send_audit_log(AuditLogEntry(
            user_id=user.user_id, user_role=user.user_role,
            action="nl_query", status=AuditStatus.ERROR,
            ip_address=ip_address, endpoint="/query", http_method="POST",
            execution_time_ms=elapsed_ms, error_message="Orchestrator timeout",
        ))
        raise HTTPException(status_code=504, detail={
            "error": "PIPELINE_TIMEOUT",
            "message": "Query pipeline timed out. Try a simpler query.",
        })
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Orchestrator error: %s", exc, exc_info=True)
        await _send_audit_log(AuditLogEntry(
            user_id=user.user_id, user_role=user.user_role,
            action="nl_query", status=AuditStatus.ERROR,
            ip_address=ip_address, endpoint="/query", http_method="POST",
            execution_time_ms=elapsed_ms, error_message=str(exc),
        ))
        raise HTTPException(status_code=503, detail={
            "error": "PIPELINE_UNAVAILABLE",
            "message": "Query pipeline is temporarily unavailable.",
        })

    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    # Audit success
    pipeline_status = pipeline_result.get("status", "unknown")
    audit_status = AuditStatus.SUCCESS if pipeline_status == "success" else AuditStatus.ERROR
    await _send_audit_log(AuditLogEntry(
        user_id=user.user_id, user_role=user.user_role,
        action="nl_query", status=audit_status,
        ip_address=ip_address, endpoint="/query", http_method="POST",
        execution_time_ms=elapsed_ms,
        metadata={
            "query": body.query[:200],
            "format": body.format,
            "pipeline_status": pipeline_status,
        },
    ))

    return {
        "status": pipeline_result.get("status"),
        "results": pipeline_result.get("results"),
        "metadata": pipeline_result.get("metadata", {}),
        "pipeline_steps": pipeline_result.get("pipeline_steps", []),
        "message": pipeline_result.get("message"),
        "error": pipeline_result.get("error"),
    }
