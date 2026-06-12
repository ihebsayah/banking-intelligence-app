"""
services/api_gateway/main.py
FastAPI application entry point for the Banking Intelligence API Gateway.

Features:
  - CORS enabled for development
  - Rate limiting: 100 requests/minute per IP (slowapi)
  - Request audit middleware: every call logged to audit-agent
  - Global exception handler: all errors return structured JSON
  - JWT-protected routes via Depends(get_current_user)

Startup:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""
import sys
import os
import time
import uuid

# ─── Make shared/ importable inside the container ────────────────────────────
# Docker mounts shared/ at /app/shared; add /app to sys.path.
sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

try:
    from contextlib import asynccontextmanager

    import httpx
    from fastapi import FastAPI, Request, status
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    from shared.config import get_settings
    from shared.database import DatabaseConnector
    from shared.errors import (
        AuthenticationError,
        AuthorizationError,
        BankingBaseError,
        TokenExpiredError,
        InvalidTokenError,
    )
    from shared.logger import get_logger
    from shared.models import AuditLogEntry, AuditStatus

    from routes import router
except Exception as e:
    import traceback
    with open("/app/startup_error.log", "w") as f:
        f.write(traceback.format_exc())
    raise

async def apply_migrations(db: DatabaseConnector) -> None:
    """Execute the migration SQL file against the main database.
    Uses raw asyncpg pool so we can run a full multi-statement script at once.
    """
    migration_path = "/app/init/02-users-kpis.sql"
    if not os.path.exists(migration_path):
        migration_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../init/02-users-kpis.sql")
        )

    if not os.path.exists(migration_path):
        logger.warning(f"Migration file not found at {migration_path} — skipping")
        return

    try:
        logger.info(f"Applying database migrations from {migration_path}")
        with open(migration_path, "r") as f:
            sql = f.read()
        # Use the internal pool directly so we can execute a multi-statement script
        pool = db._pool
        if pool is None:
            logger.warning("Pool not ready — skipping migration")
            return
        async with pool.acquire() as conn:
            await conn.execute(sql)
        logger.info("Database migrations applied successfully")
    except Exception as exc:
        logger.error("Failed to apply database migrations", extra={"error": str(exc)})


try:
    logger = get_logger(__name__, "api-gateway")
    settings = get_settings()

    # ─── Rate Limiter ─────────────────────────────────────────────────────────────
    limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


    # ─── Lifespan (startup / shutdown) ───────────────────────────────────────────
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Initialize resources on startup, clean up on shutdown."""
        logger.info("API Gateway starting up")

        # Store DB connector in app state for health checks (optional)
        try:
            app.state.db = DatabaseConnector(settings.DATABASE_URL)
            await app.state.db.initialize()
            logger.info("Database connection pool ready")
            
            # Apply database migrations
            await apply_migrations(app.state.db)
        except Exception as exc:
            logger.warning("Database not available at startup", extra={"error": str(exc)})
            app.state.db = None

        # Store Audit DB connector in app state
        try:
            app.state.audit_db = DatabaseConnector(settings.AUDIT_DATABASE_URL)
            await app.state.audit_db.initialize()
            logger.info("Audit Database connection pool ready")
        except Exception as exc:
            logger.warning("Audit Database not available at startup", extra={"error": str(exc)})
            app.state.audit_db = None

        yield

        # Shutdown
        logger.info("API Gateway shutting down")
        if getattr(app.state, "db", None):
            await app.state.db.close()
        if getattr(app.state, "audit_db", None):
            await app.state.audit_db.close()


    # ─── Application ──────────────────────────────────────────────────────────────
    app = FastAPI(
        title="Banking Intelligence API Gateway",
        description=(
            "Secure API Gateway for the Banking Intelligence System. "
            "Handles authentication, rate limiting, audit logging, and request routing."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ─── Rate Limiting ─────────────────────────────────────────────────────────────
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ─── CORS ─────────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],   # Restrict to known origins in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ─── Include Routers ──────────────────────────────────────────────────────────
    app.include_router(router)
except Exception as e:
    import traceback
    with open("/app/startup_error2.log", "w") as f:
        f.write(traceback.format_exc())
    raise


# ─── Audit Middleware ─────────────────────────────────────────────────────────
async def _send_audit_log(entry: AuditLogEntry) -> None:
    """POST audit entry to audit-agent. Non-fatal if agent is unreachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(
                f"{settings.AUDIT_AGENT_URL}/log_access",
                json=entry.model_dump(mode="json"),
            )
    except Exception as exc:
        logger.error(
            "Audit log delivery failed",
            extra={"audit_id": entry.audit_id, "error": str(exc)},
        )


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    """
    Log every HTTP request to the audit service.

    Skips:
      - /health  (noisy, no security value)
      - /docs, /redoc, /openapi.json  (Swagger UI)
    """
    skip_paths = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
    if request.url.path in skip_paths:
        return await call_next(request)

    start_time = time.monotonic()
    audit_id = str(uuid.uuid4())
    request.state.audit_id = audit_id

    # Extract user context from state (populated by JWT dependency if called)
    # For unauthenticated paths like /auth/login, user_id will be "anonymous"
    user_id = getattr(request.state, "user_id", "anonymous")
    user_role = getattr(request.state, "user_role", "unknown")
    ip_address = request.client.host if request.client else "unknown"

    response = await call_next(request)

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    http_status = response.status_code
    audit_status = AuditStatus.SUCCESS if http_status < 400 else AuditStatus.ERROR

    await _send_audit_log(
        AuditLogEntry(
            audit_id=audit_id,
            user_id=user_id,
            user_role=user_role,
            action="api_call",
            status=audit_status,
            ip_address=ip_address,
            endpoint=str(request.url.path),
            http_method=request.method,
            execution_time_ms=elapsed_ms,
            metadata={"http_status": http_status},
        )
    )

    # Attach audit_id to response headers for traceability
    response.headers["X-Audit-ID"] = audit_id
    return response


# ─── Global Exception Handlers ────────────────────────────────────────────────

@app.exception_handler(BankingBaseError)
async def banking_error_handler(request: Request, exc: BankingBaseError):
    """Convert all BankingBaseError subclasses to structured JSON responses."""
    http_status = status.HTTP_400_BAD_REQUEST
    if isinstance(exc, (AuthenticationError, TokenExpiredError, InvalidTokenError)):
        http_status = status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, AuthorizationError):
        http_status = status.HTTP_403_FORBIDDEN

    logger.warning(
        "Banking error",
        extra={"error_code": exc.error_code, "message": exc.message, "path": request.url.path},
    )
    return JSONResponse(status_code=http_status, content=exc.to_dict())


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Catch-all: convert unexpected exceptions to JSON. Never return raw 500."""
    logger.error(
        "Unhandled exception",
        extra={"path": request.url.path, "error": str(exc)},
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred. Please contact support.",
            "audit_id": getattr(request.state, "audit_id", None),
        },
    )
