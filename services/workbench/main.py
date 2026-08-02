"""Workbench service — FastAPI entry point for staging deployment.

Mounts the composed integration app (all workbench routers) on port 8014
and runs the expiry worker and outbox worker as background tasks within
the same process. Production deploys may split these into separate
containers; this is the staging-minimal variant.
"""
import asyncio
import os
import sys

# Add parent directories to path for package imports
# When running in Docker: /app is services/workbench, so we need services/ in path
_app_dir = os.path.dirname(os.path.abspath(__file__))
_services_dir = os.path.dirname(_app_dir)  # services/
sys.path.insert(0, _services_dir)
sys.path.insert(0, _app_dir)

from fastapi import FastAPI
from shared.database import DatabaseConnector
from workbench.integration_app import build_integration_app

WORKBENCH_PORT = int(os.environ.get("WORKBENCH_PORT", "8014"))
WORKBENCH_AUDIT_AGENT_URL = os.environ.get(
    "AUDIT_AGENT_URL", "http://audit-agent:8008"
)


def _build_app() -> FastAPI:
    url = os.environ.get("INTEGRATION_DATABASE_URL", "")
    app = build_integration_app()

    @app.on_event("startup")
    async def _startup() -> None:
        connector = DatabaseConnector(url)
        await connector.initialize()
        app.state.db = connector

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        connector = getattr(app.state, "db", None)
        if connector is not None:
            await connector.close()

    return app


app = _build_app()


async def _run_outbox() -> None:
    """Background outbox delivery loop."""
    while True:
        try:
            from workbench.repos import OutboxRepo
            db = app.state.db
            repo = OutboxRepo(db)
            await repo.reconcile_stuck(stale_minutes=5)
            async with __import__("httpx").AsyncClient(timeout=30.0) as client:
                events = await repo.claim_next_batch(
                    f"workbench-{os.getpid()}", batch_size=10
                )
                for event in events:
                    try:
                        payload = {
                            "audit_id": __import__("uuid").uuid5(
                                __import__("uuid").NAMESPACE_DNS,
                                event.idempotency_key,
                            ).hex,
                            "timestamp": event.occurred_at.isoformat(),
                            "user_id": event.actor_id,
                            "user_role": event.actor_role,
                            "action": event.event_type,
                            "endpoint": f"/{event.entity_type}/{event.entity_id}",
                            "metadata": event.payload,
                        }
                        resp = await client.post(
                            f"{WORKBENCH_AUDIT_AGENT_URL}/log_access",
                            json=payload,
                            headers={
                                "Content-Type": "application/json",
                                "X-Idempotency-Key": event.idempotency_key,
                            },
                        )
                        if resp.status_code >= 500:
                            raise RuntimeError(
                                f"Audit agent returned {resp.status_code}"
                            )
                        await repo.mark_delivered(event.outbox_id)
                    except Exception as exc:
                        await repo.mark_failed(event.outbox_id, str(exc))
        except Exception as exc:
            print(f"[outbox-worker] cycle error: {exc}")
        await asyncio.sleep(5)


async def _run_expiry() -> None:
    """Background approval expiry loop."""
    while True:
        try:
            from workbench.expiry_worker import expire_due
            db = app.state.db
            expired = await expire_due(db, batch_size=50)
            if expired:
                print(f"[expiry-worker] expired {len(expired)} approvals")
        except Exception as exc:
            print(f"[expiry-worker] cycle error: {exc}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def _start_workers() -> None:
    asyncio.create_task(_run_outbox())
    asyncio.create_task(_run_expiry())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "__main__:app",
        host="0.0.0.0",
        port=WORKBENCH_PORT,
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )
