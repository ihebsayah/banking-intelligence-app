import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from config import Settings
from data_lineage_tracker import DataLineageTracker
from compliance_reporter import ComplianceReporter
from models import (
    LineageRequest, LineageResponse,
    GDPRReportRequest, SOXReportRequest, ReportResponse,
)

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

config = Settings()
lineage_tracker: DataLineageTracker = None
reporter: ComplianceReporter = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global lineage_tracker, reporter
    logger.info("Initialising Audit Enhancement Service…")

    lineage_tracker = DataLineageTracker(config)
    await lineage_tracker.initialize()

    reporter = ComplianceReporter(config)
    await reporter.initialize()

    logger.info("✅ Audit Enhancement Service ready on port 8012")
    yield

    # teardown
    for pool in [
        lineage_tracker.pool,
        reporter.main_pool,
        reporter.audit_pool,
    ]:
        if pool:
            await pool.close()


app = FastAPI(
    title="Audit Enhancement Service",
    description="Data lineage tracking + GDPR/SOX compliance reporting.",
    version="2.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# Lineage
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/track_lineage", response_model=LineageResponse)
async def track_lineage(request: LineageRequest):
    """
    Record which tables/columns were accessed for a given query.

    Body:
        query_id         : str
        user_id          : str
        source_tables    : list[str]
        accessed_columns : list[str]
    """
    if not lineage_tracker:
        raise HTTPException(503, "Audit Enhancement not initialised")
    return await lineage_tracker.track(
        query_id=request.query_id,
        user_id=request.user_id,
        source_tables=request.source_tables,
        accessed_columns=request.accessed_columns,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reports
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/report/gdpr", response_model=ReportResponse)
async def gdpr_report(request: GDPRReportRequest):
    """Generate GDPR Right-to-Access report for a specific user."""
    if not reporter:
        raise HTTPException(503, "Reporter not initialised")
    return await reporter.generate_gdpr_report(request.user_id, request.days)


@app.post("/report/sox", response_model=ReportResponse)
async def sox_report(request: SOXReportRequest):
    """Generate SOX access-log report for the given time window."""
    if not reporter:
        raise HTTPException(503, "Reporter not initialised")
    return await reporter.generate_sox_report(request.days)


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "audit_enhancement",
        "port": 8012,
    }
