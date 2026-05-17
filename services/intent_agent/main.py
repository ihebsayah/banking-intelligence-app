"""
services/intent_agent/main.py
FastAPI entry-point for the Intent Recognition Agent (port 8002).
"""
from __future__ import annotations

import logging
import os

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

    recognizer = IntentRecognizer(redis_client=redis_client)

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
    return {"status": "healthy", "service": "intent_agent"}


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
