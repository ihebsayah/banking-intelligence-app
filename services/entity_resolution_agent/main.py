"""
services/entity_resolution_agent/main.py
Entity Resolution Agent — FastAPI app on port 8004.
Finds semantic join paths for multi-table queries.

Phase 6B: On startup, loads glossary + join_registry into memory cache
when SEMANTIC_LAYER_ENABLED=True.
"""
import sys
import logging
import os
from contextlib import asynccontextmanager

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from models import EntityResolutionRequest, EntityResolutionResponse
from entity_resolver import EntityResolver, initialize_entity_cache, SEMANTIC_LAYER_ENABLED
import entity_resolver as _er_module

# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [entity_resolution] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Readiness state (populated in lifespan)
_fallback_reason: str = "not yet initialized"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize semantic cache on startup if feature flag is enabled."""
    global _fallback_reason
    if SEMANTIC_LAYER_ENABLED:
        try:
            import psycopg2
            db_url = os.getenv(
                "DATABASE_URL",
                "postgresql://banking_user:securepass123@postgres-main:5432/banking_dev"
            )
            conn = psycopg2.connect(db_url)
            initialize_entity_cache(conn)
            conn.close()
            if _er_module._cache_ready:
                _fallback_reason = ""
            else:
                _fallback_reason = "glossary or join_registry empty after load"
        except Exception as exc:
            _fallback_reason = f"DB connection failed: {exc}"
            logger.warning(
                "[startup] Could not initialize entity semantic cache: %s", exc
            )
    else:
        _fallback_reason = "SEMANTIC_LAYER_ENABLED=false"
        logger.info("[startup] SEMANTIC_LAYER_ENABLED=False — using hardcoded resolver")
    yield


app = FastAPI(
    title="Entity Resolution Agent",
    description="Finds semantic join paths using business-key correlation. Phase 6B.",
    version="0.6b.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

resolver = EntityResolver()


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    cache_ready = _er_module._cache_ready
    return {
        "status": "healthy",
        "service": "entity_resolution_agent",
        "port": 8004,
        "version": "0.6b.0",
        "semantic_layer_enabled": SEMANTIC_LAYER_ENABLED,
        "semantic_cache_ready": cache_ready,
        "fallback_active": not cache_ready,
        "fallback_reason": _fallback_reason if not cache_ready else None,
        "metadata_counts": {
            "business_glossary": len(_er_module._glossary_cache),
            "join_registry_nodes": len(_er_module._join_graph),
        },
    }


@app.get("/semantic/health")
async def semantic_health():
    """Detailed semantic layer health."""
    cache_ready = _er_module._cache_ready
    return {
        "semantic_layer_enabled": SEMANTIC_LAYER_ENABLED,
        "semantic_cache_ready": cache_ready,
        "fallback_active": not cache_ready,
        "fallback_reason": _fallback_reason if not cache_ready else None,
        "metadata_counts": {
            "business_glossary": len(_er_module._glossary_cache),
            "join_registry_nodes": len(_er_module._join_graph),
        },
        "readiness_requirements": {
            "business_glossary": "must be non-empty",
            "join_registry": "must be non-empty",
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# RESOLVE ENTITIES
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/resolve_entities", response_model=EntityResolutionResponse)
async def resolve_entities(request: EntityResolutionRequest):
    """
    Resolve entity relationships and build semantic join structure.

    Input:
        primary_entity: "customer" | "account" | "transaction" | "branch" | ...
        tables: list of tables to join (returned by Schema Agent)

    Output:
        primary_key, primary_table, join_structure with conditions
    """
    try:
        logger.info(
            "Resolving entity='%s' tables=%s",
            request.primary_entity, request.tables
        )
        result = resolver.resolve(request)
        logger.info(
            "Resolved: pk='%s' joins=%d",
            result.primary_key, len(result.join_structure)
        )
        return result
    except Exception as exc:
        logger.error("Entity resolution failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# BATCH TEST ENDPOINT (10 test cases)
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/test_resolution")
async def test_resolution():
    """Run all 10 acceptance test cases and return pass/fail."""
    test_cases = [
        # 1
        {"primary_entity": "customer", "tables": ["customers", "accounts"],
         "expect_key": "customer_id", "expect_joins": 1},
        # 2
        {"primary_entity": "customer", "tables": ["customers", "accounts", "transactions"],
         "expect_key": "customer_id", "expect_joins": 2},
        # 3
        {"primary_entity": "customer", "tables": ["customers", "risk_flags"],
         "expect_key": "customer_id", "expect_joins": 1},
        # 4
        {"primary_entity": "account", "tables": ["accounts", "transactions"],
         "expect_key": "account_id", "expect_joins": 1},
        # 5
        {"primary_entity": "account", "tables": ["accounts", "products"],
         "expect_key": "account_id", "expect_joins": 1},
        # 6
        {"primary_entity": "transaction", "tables": ["transactions"],
         "expect_key": "transaction_id", "expect_joins": 0},
        # 7
        {"primary_entity": "branch", "tables": ["branches"],
         "expect_key": "branch_id", "expect_joins": 0},
        # 8
        {"primary_entity": "branch", "tables": ["branches", "accounts"],
         "expect_key": "branch_id", "expect_joins": 1},
        # 9
        {"primary_entity": "customer", "tables": ["customers", "accounts", "transactions", "risk_flags"],
         "expect_key": "customer_id", "expect_joins": 3},
        # 10
        {"primary_entity": "loan", "tables": ["loans", "customers", "accounts", "branches"],
         "expect_key": "loan_id", "expect_joins": 3},
    ]

    results = []
    passed = 0

    for i, tc in enumerate(test_cases, 1):
        req = EntityResolutionRequest(
            primary_entity=tc["primary_entity"],
            tables=tc["tables"],
        )
        try:
            res = resolver.resolve(req)
            key_ok = res.primary_key == tc["expect_key"]
            joins_ok = len(res.join_structure) == tc["expect_joins"]
            ok = key_ok and joins_ok
            if ok:
                passed += 1
            results.append({
                "test": i,
                "entity": tc["primary_entity"],
                "tables": tc["tables"],
                "expected_key": tc["expect_key"],
                "got_key": res.primary_key,
                "expected_joins": tc["expect_joins"],
                "got_joins": len(res.join_structure),
                "passed": ok,
                "joins": [j.model_dump() for j in res.join_structure],
            })
        except Exception as exc:
            results.append({"test": i, "passed": False, "error": str(exc)})

    return {
        "total": len(test_cases),
        "passed": passed,
        "failed": len(test_cases) - passed,
        "success_rate": f"{passed}/{len(test_cases)}",
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8004, reload=False)
