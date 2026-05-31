import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from compliance_checker import ComplianceChecker
from config import Settings
from models import ComplianceRequest, ComplianceResponse

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

config = Settings()
checker: ComplianceChecker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global checker
    logger.info("Initialising Compliance Agent…")
    checker = ComplianceChecker(config)
    await checker.initialize()
    logger.info("✅ Compliance Agent ready on port 8011")
    yield
    if checker.pool:
        await checker.pool.close()


app = FastAPI(
    title="Compliance Agent",
    description="GDPR / PCI-DSS / SOX / AML / KYC compliance enforcement.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.post("/check_compliance", response_model=ComplianceResponse)
async def check_compliance(request: ComplianceRequest):
    """
    Evaluate a query against all compliance regulations.

    Body:
        user_id       : str
        user_role     : str   — analyst, admin, compliance, …
        query_intent  : str
        tables        : list  — tables the query will touch
        columns       : list  — columns the query will select
    """
    if not checker:
        raise HTTPException(503, "Compliance Agent not initialised")
    try:
        return await checker.check_compliance(
            user_id=request.user_id,
            user_role=request.user_role,
            query_intent=request.query_intent,
            tables=request.tables,
            columns=request.columns,
        )
    except Exception as exc:
        logger.error(f"check_compliance error: {exc}")
        raise HTTPException(500, str(exc))


@app.get("/regulations")
async def list_regulations():
    """Return the list of regulations this agent enforces."""
    return {
        "regulations": ["GDPR", "PCI-DSS", "SOX", "AML", "KYC"],
        "rule_count": 12,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "compliance_agent", "port": 8011}
