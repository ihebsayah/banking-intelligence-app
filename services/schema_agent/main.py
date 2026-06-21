"""
services/schema_agent/main.py
FastAPI entry-point for the Schema Understanding Agent (port 8003).
"""
from __future__ import annotations

import logging
import os

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../shared")))

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from models import SchemaMappingRequest, SchemaMappingResponse
from schema_matcher import SchemaMatcher, INTENT_TO_DOMAINS

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Schema Understanding Agent",
    description="Maps user intent categories to database domains, tables, and join paths",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

matcher = SchemaMatcher()


@app.on_event("startup")
async def startup() -> None:
    global matcher
    try:
        from shared.config import get_settings
        from shared.database import get_connector
        settings = get_settings()
        if settings.SEMANTIC_LAYER_ENABLED:
            db_connector = await get_connector(settings.DATABASE_URL)
            matcher = SchemaMatcher(db=db_connector, semantic_layer_enabled=True)
            await matcher.initialize_db_cache()
            logger.info("Schema Agent DB Cache initialized successfully")
    except Exception as exc:
        logger.warning("Failed to initialize database cache for Schema Agent: %s", exc)


@app.post("/map_schema", response_model=SchemaMappingResponse)
async def map_schema(request: SchemaMappingRequest) -> SchemaMappingResponse:
    """
    Map intent categories to the database schema.

    Input:  {"intent_categories": ["customer_analysis", "risk_analysis"],
              "primary_entity": "customer"}

    Output: relevant domains, tables, key columns, join paths.
    """
    if not request.intent_categories:
        raise HTTPException(status_code=400, detail="intent_categories must not be empty")

    try:
        domains = matcher.match_domains(request.intent_categories)
        tables  = matcher.get_tables(domains)

        entity = (request.primary_entity or "customer").lower()
        key_columns = matcher.get_key_columns(tables, entity)

        # Derive primary table: entity + "s" (simple pluralisation)
        # Override for known irregulars
        _plural_map = {
            "customer": "customers",
            "account":  "accounts",
            "transaction": "transactions",
            "branch":   "branches",
            "product":  "products",
            "region":   "regions",
        }
        primary_table = _plural_map.get(entity, entity + "s")

        join_paths = matcher.get_join_paths(tables, primary_table)
        explanations, confidences = matcher.get_table_enrichment(tables, request.intent_categories)

        return SchemaMappingResponse(
            relevant_domains=domains,
            tables=tables,
            key_columns=key_columns,
            join_paths=join_paths,
            table_explanations=explanations,
            confidence_scores=confidences,
        )

    except Exception as exc:
        logger.exception("Schema mapping failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/domains")
async def get_domains() -> dict:
    return {"domains": sorted(INTENT_TO_DOMAINS.keys())}


@app.get("/health")
async def health() -> dict:
    return {"status": "healthy", "service": "schema_agent"}
