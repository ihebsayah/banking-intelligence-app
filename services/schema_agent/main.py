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

# Readiness state — separate from is_initialized on matcher
_semantic_cache_ready: bool = False
_fallback_reason: str = ""


@app.on_event("startup")
async def startup() -> None:
    global matcher, _semantic_cache_ready, _fallback_reason
    try:
        from shared.database import get_connector
        semantic_enabled = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"
        if semantic_enabled:
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://banking_user:securepass123@postgres-main:5432/banking_dev"
            )
            db_connector = await get_connector(db_url)
            matcher = SchemaMatcher(db=db_connector, semantic_layer_enabled=True)
            await matcher.initialize_db_cache()

            # Validate minimum required metadata — ready only if data actually loaded
            t_count = len(matcher._table_metadata_cache)
            c_count = len(matcher._column_metadata_cache)
            j_count = len(matcher._join_registry_cache)

            if t_count == 0:
                _fallback_reason = "table_metadata is empty"
                logger.warning(
                    "[SchemaAgent] %s — semantic cache NOT ready; using static fallback", _fallback_reason
                )
            elif c_count == 0:
                _fallback_reason = "column_metadata is empty"
                logger.warning(
                    "[SchemaAgent] %s — semantic cache NOT ready; using static fallback", _fallback_reason
                )
            elif j_count == 0:
                _fallback_reason = "join_registry is empty"
                logger.warning(
                    "[SchemaAgent] %s — semantic cache NOT ready; using static fallback", _fallback_reason
                )
            else:
                _semantic_cache_ready = True
                logger.info(
                    "[SchemaAgent] Semantic cache ready: %d tables, %d columns, %d joins",
                    t_count, c_count, j_count
                )
        else:
            _fallback_reason = "SEMANTIC_LAYER_ENABLED=false"
    except Exception as exc:
        _fallback_reason = f"startup error: {exc}"
        logger.warning("[SchemaAgent] Failed to initialize database cache: %s", exc)


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
    semantic_enabled = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"

    return {
        "status": "healthy",
        "service": "schema_agent",
        "semantic_layer_enabled": semantic_enabled,
        "semantic_cache_ready": _semantic_cache_ready,
        "fallback_active": not _semantic_cache_ready,
        "fallback_reason": _fallback_reason if not _semantic_cache_ready else None,
        "metadata_counts": {
            "table_metadata": len(matcher._table_metadata_cache),
            "column_metadata": len(matcher._column_metadata_cache),
            "join_registry": len(matcher._join_registry_cache),
        },
    }


@app.get("/semantic/health")
async def semantic_health() -> dict:
    """Detailed semantic layer health — safe to expose (no credentials or formulas)."""
    semantic_enabled = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"

    return {
        "semantic_layer_enabled": semantic_enabled,
        "semantic_cache_ready": _semantic_cache_ready,
        "fallback_active": not _semantic_cache_ready,
        "fallback_reason": _fallback_reason if not _semantic_cache_ready else None,
        "metadata_counts": {
            "table_metadata": len(matcher._table_metadata_cache),
            "column_metadata": len(matcher._column_metadata_cache),
            "join_registry": len(matcher._join_registry_cache),
        },
        "readiness_requirements": {
            "table_metadata": "must be non-empty",
            "column_metadata": "must be non-empty",
            "join_registry": "must be non-empty",
        },
    }
