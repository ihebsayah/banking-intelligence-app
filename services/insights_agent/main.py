import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from config import Settings
from insights_generator import InsightsGenerator
from models import InsightsRequest, InsightsResponse

logging.basicConfig(level="INFO")
logger = logging.getLogger(__name__)

config = Settings()
insights_generator: InsightsGenerator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global insights_generator
    logger.info("Initializing Insights Agent…")
    insights_generator = InsightsGenerator(config)
    await insights_generator.context_gatherer.initialize()
    logger.info("✅ Insights Agent ready on port 8013")
    yield
    # teardown
    if insights_generator.context_gatherer.pool:
        await insights_generator.context_gatherer.pool.close()


app = FastAPI(
    title="Insights Agent",
    description="Natural language analysis of banking query results.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.post("/generate_insights", response_model=InsightsResponse)
async def generate_insights(request: InsightsRequest):
    """
    Receive query results + intent → return executive summary + trends.

    Body:
        query_intent  : str  — e.g. "customer_analysis"
        query_text    : str  — original user question
        results       : list — raw rows from Execution Agent
        metadata      : dict — rows_returned, execution_time_ms, tables, …
    """
    if not insights_generator:
        raise HTTPException(503, "Insights Agent not initialised")
    try:
        return await insights_generator.generate(request)
    except Exception as exc:
        logger.error(f"generate_insights error: {exc}")
        raise HTTPException(500, str(exc))


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "insights_agent", "port": 8013}
