"""Composed FastAPI integration app for the Phase 2B.17b scenario suite.

Mounts every canonical workbench router against the dedicated integration
PostgreSQL database and injects authenticated test users via an
integration-only request header (``X-Test-User``).

This is NOT a production entrypoint. Keycloak/JWT token validation is
intentionally bypassed; user lookup, role, status, scope, permission,
ownership, and workflow authorisation all run through the real engine
(``shared.authorise``) with permissions loaded from the database.

The app refuses to start if ``INTEGRATION_DATABASE_URL`` is not set or if the
resolved URL points at the main/dev database (port 5432).
"""
from __future__ import annotations

import json
import os
from urllib.parse import urlparse
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from shared.authorise import ApplicationUser, AuthorisationError
from shared.database import DatabaseConnector

from workbench.exceptions import WorkbenchError
from workbench.routers import (
    admin_orphans,
    admin_outbox,
    alerts,
    approvals,
    cases,
    comments,
    information_requests,
    investigations,
    notifications,
    timeline,
)

TEST_USER_HEADER = "X-Test-User"

_DEFAULT_SCOPE = "hq_main"


def _assert_integration_database(url: str) -> None:
    if not url:
        raise RuntimeError(
            "INTEGRATION_DATABASE_URL is not set. The Phase 2B.17b scenario "
            "suite must run against the dedicated integration database."
        )
    parsed = urlparse(url)
    # Accept any database URL that is NOT the main/dev database.
    # The main dev DB is identified by its database name 'banking_dev'
    # (not by port, since internal Docker ports differ from host ports).
    db_name = parsed.path.lstrip("/")
    if db_name in ("banking_dev", "banking"):
        raise RuntimeError(
            f"Refusing to serve the 2B.17b scenario suite against the "
            f"main/dev database ({url}). INTEGRATION_DATABASE_URL must point "
            f"at the integration database."
        )


async def _resolve_application_user(request: Request) -> ApplicationUser:
    """Resolve the authenticated user for an integration request.

    Reads ``X-Test-User``, loads the user row, enforces the canonical active
    status gate, and hydrates role permissions + scopes from the database
    (mirroring ``api_gateway/auth.py``). Inactive or suspended users are
    rejected exactly like a failed Keycloak token exchange: 401.
    """
    user_id = request.headers.get(TEST_USER_HEADER)
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"error": "AUTH_REQUIRED", "message": "Missing X-Test-User header"},
        )

    db: DatabaseConnector = request.app.state.db
    row = await db.fetch_one(
        "SELECT user_id, role, status, permissions FROM users WHERE user_id = $1",
        [user_id],
    )
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "AUTH_REQUIRED", "message": "Unknown test user"},
        )

    if row["status"] != "active":
        raise HTTPException(
            status_code=401,
            detail={"error": "AUTH_REQUIRED", "message": "User is not active"},
        )

    permission_rows = await db.fetch_all(
        "SELECT permission_key FROM role_permissions WHERE role_id = $1",
        [row["role"]],
    )
    permissions = [r["permission_key"] for r in permission_rows]

    custom = row.get("permissions") or []
    if isinstance(custom, str):
        try:
            custom = json.loads(custom)
        except Exception:
            custom = [custom]
    if custom:
        permissions = list(dict.fromkeys(permissions + [p for p in custom if p]))

    scope_rows = await db.fetch_all(
        "SELECT scope_id FROM user_scopes WHERE user_id = $1", [user_id]
    )
    scopes = [r["scope_id"] for r in scope_rows]

    return ApplicationUser(user_id=user_id, role=row["role"], permissions=permissions, scopes=scopes)


async def _inject_test_user(request: Request, call_next):
    """Integration-only auth middleware: never bypasses policy checks."""
    path = request.url.path
    if path in ("/health", "/healthz", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    user = await _resolve_application_user(request)
    request.state.application_user = user
    request.state.scope_id = user.scopes[0] if user.scopes else _DEFAULT_SCOPE

    response = await call_next(request)
    return response


async def _authorisation_error_handler(request: Request, exc: AuthorisationError):
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


async def _workbench_error_handler(request: Request, exc: WorkbenchError):
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


async def _unhandled_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."},
    )


def build_integration_app(db: Optional[DatabaseConnector] = None) -> FastAPI:
    """Build the composed integration app.

    ``db`` may be a pre-initialised connector. When omitted the app reads
    ``INTEGRATION_DATABASE_URL`` and creates its own connector during startup
    (and closes it on shutdown).
    """
    url = os.environ.get("INTEGRATION_DATABASE_URL", "")
    _assert_integration_database(url)

    app = FastAPI(
        title="Workbench Integration App (Phase 2B.17b)",
        description="Composed workbench routers on the integration database. Test-only.",
        version="2.17.0",
    )

    if db is not None:
        app.state.db = db

    @app.on_event("startup")
    async def _startup() -> None:
        if not hasattr(app.state, "db") or app.state.db is None:
            connector = DatabaseConnector(url)
            await connector.initialize()
            app.state.db = connector

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        connector = getattr(app.state, "db", None)
        if connector is not None:
            await connector.close()

    @app.get("/health", include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok"}

    @app.middleware("http")
    async def test_user_middleware(request: Request, call_next):
        return await _inject_test_user(request, call_next)

    for router in (
        alerts.router,
        cases.router,
        investigations.router,
        information_requests.router,
        approvals.router,
        comments.router,
        notifications.router,
        timeline.router,
        admin_outbox.router,
        admin_orphans.router,
    ):
        app.include_router(router)

    app.add_exception_handler(AuthorisationError, _authorisation_error_handler)
    app.add_exception_handler(WorkbenchError, _workbench_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)

    return app
