"""
services/audit_agent/main.py
FastAPI application for the Audit Agent.

Responsibilities:
  - Receive POST /log_access from all other services
  - Write to the immutable audit_log table in postgres-audit
  - Expose GET /logs for compliance review (read-only)
  - Expose GET /health for Docker health checks

Port: 8008
DB:   postgres-audit (audit_logs database)
"""
import sys

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from shared.config import get_settings
from shared.database import DatabaseConnector
from shared.errors import AuditLoggingError, BankingBaseError
from shared.logger import get_logger
from shared.models import AuditLogEntry, AuditLogResponse, HealthResponse

from audit_logger import AuditLogger

logger = get_logger(__name__, "audit-agent")
settings = get_settings()

# Module-level singletons (initialized in lifespan)
_db: DatabaseConnector = None
_audit_logger: AuditLogger = None


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db, _audit_logger

    logger.info("Audit Agent starting up")

    # Connect to postgres-audit
    _db = DatabaseConnector(settings.AUDIT_DATABASE_URL)
    await _db.initialize()
    _audit_logger = AuditLogger(_db)

    logger.info("Audit Agent ready — connected to postgres-audit")
    yield

    logger.info("Audit Agent shutting down")
    await _db.close()


# ─── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Banking Intelligence – Audit Agent",
    description="Immutable compliance audit logging service.",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Exception Handlers ───────────────────────────────────────────────────────
@app.exception_handler(BankingBaseError)
async def banking_error_handler(request: Request, exc: BankingBaseError):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", extra={"error": str(exc)}, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "INTERNAL_ERROR", "message": str(exc)},
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    tags=["monitoring"],
)
async def health() -> HealthResponse:
    """Docker health check — verifies DB connectivity."""
    db_ok = await _db.health_check() if _db else False
    return HealthResponse(
        service="audit-agent",
        checks={"postgres_audit": "ok" if db_ok else "unreachable"},
    )


@app.post(
    "/log_access",
    response_model=AuditLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Write an audit log entry",
    tags=["audit"],
)
async def log_access(entry: AuditLogEntry) -> AuditLogResponse:
    """
    Accept an audit log entry from any service and write it to the
    immutable audit_log table.

    Called by:
      - api-gateway (every HTTP request)
      - execution-agent (every query execution)
      - any other agent that needs to record an auditable action

    Returns:
        AuditLogResponse confirming the write with the audit_id.
    """
    if _audit_logger is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audit logger not initialized",
        )

    try:
        result = await _audit_logger.log_access(entry)
        return result
    except AuditLoggingError as exc:
        logger.error("Audit write failed", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=exc.to_dict(),
        )


@app.get(
    "/logs",
    summary="Retrieve recent audit logs (compliance view)",
    tags=["audit"],
)
async def get_logs(
    user_id: str = Query(default=None, description="Filter by user_id"),
    limit: int = Query(default=50, ge=1, le=1000, description="Max rows to return"),
) -> dict:
    """
    Read-only access to the audit log (for compliance analysts).
    The DB RULE prevents updates/deletes regardless of who calls this.
    """
    if _audit_logger is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    rows = await _audit_logger.get_recent_logs(user_id=user_id, limit=limit)
    return {
        "count": len(rows),
        "logs": rows,
    }
