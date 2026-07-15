"""
services/intent_agent/main.py
FastAPI entry-point for the Intent Recognition Agent (port 8002).
"""
from __future__ import annotations

import logging
import os
import sys

# Add shared services path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../shared")))

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from intent_recognizer import IntentRecognizer
from models import IntentRequest, IntentResponse

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Intent Recognition Agent",
    description="Pattern-matching NLP service – classifies user query intent",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

recognizer: IntentRecognizer = None  # type: ignore


@app.on_event("startup")
async def startup() -> None:
    global recognizer

    # Optional Redis
    redis_client = None
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url:
        try:
            import aioredis
            redis_client = await aioredis.from_url(redis_url, decode_responses=True)
            logger.info("Redis connected: %s", redis_url)
        except Exception as exc:
            logger.warning("Redis unavailable (%s) — running without cache", exc)

    # Initialize Database Connector and load settings
    db_connector = None
    semantic_enabled = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"
    try:
        from shared.database import get_connector
        if semantic_enabled:
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://banking_user:securepass123@postgres-main:5432/banking_dev"
            )
            db_connector = await get_connector(db_url)
            logger.info("Semantic database connector initialized successfully")
    except Exception as exc:
        logger.warning("Failed to initialize database connector or settings for intent agent: %s", exc)

    recognizer = IntentRecognizer(
        redis_client=redis_client,
        db=db_connector,
        semantic_layer_enabled=semantic_enabled
    )

    # Warm up spaCy model
    logger.info("Loading spaCy model …")
    recognizer._get_nlp()
    logger.info("spaCy model ready")


@app.post("/process_intent", response_model=IntentResponse)
async def process_intent(request: IntentRequest) -> IntentResponse:
    """Classify the intent of a natural-language banking query."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")
    try:
        result = await recognizer.recognize(request.query)
        return IntentResponse(**result)
    except Exception as exc:
        logger.exception("Intent recognition failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/health")
async def health() -> dict:
    kpi_count = len(recognizer._kpi_cache) if recognizer and recognizer._kpi_cache is not None else 0
    semantic_enabled = recognizer._semantic_layer_enabled if recognizer else False
    # Intent agent uses lazy KPI loading: cache populated on first request
    # ready=True if flag enabled; kpi_count=0 means next request will load from DB
    return {
        "status": "healthy",
        "service": "intent_agent",
        "semantic_layer_enabled": semantic_enabled,
        "kpi_cache_loaded": recognizer._kpi_cache is not None if recognizer else False,
        "kpi_count": kpi_count,
    }


@app.get("/semantic/health")
async def semantic_health() -> dict:
    """Semantic layer health for intent agent."""
    if not recognizer:
        return {"semantic_layer_enabled": False, "semantic_cache_ready": False, "kpi_count": 0}
    semantic_enabled = recognizer._semantic_layer_enabled
    kpi_count = len(recognizer._kpi_cache) if recognizer._kpi_cache is not None else 0
    # Readiness: flag enabled AND db connector present
    cache_ready = semantic_enabled and recognizer._db is not None
    return {
        "semantic_layer_enabled": semantic_enabled,
        "semantic_cache_ready": cache_ready,
        "fallback_active": not cache_ready,
        "fallback_reason": (
            None if cache_ready
            else ("feature flag disabled" if not semantic_enabled else "db connector unavailable")
        ),
        "metadata_counts": {
            "metric_registry_kpis": kpi_count,
            "kpi_cache_loaded": recognizer._kpi_cache is not None,
        },
        "readiness_requirements": {
            "metric_registry": "loaded lazily on first request",
        },
    }


@app.get("/categories")
async def get_categories() -> dict:
    return {
        "categories": [
            "customer_analysis",
            "risk_analysis",
            "revenue_analysis",
            "operational_analysis",
            "geographic_analysis",
            "product_analysis",
            "compliance_analysis",
            "transaction_analysis",
        ]
    }
