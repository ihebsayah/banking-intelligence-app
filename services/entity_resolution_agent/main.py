"""
services/entity_resolution_agent/main.py
Entity Resolution Agent — FastAPI app on port 8004.
Finds semantic join paths for multi-table queries.
"""
import sys
import logging
import os

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

from models import EntityResolutionRequest, EntityResolutionResponse
from entity_resolver import EntityResolver

# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [entity_resolution] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Entity Resolution Agent",
    description="Finds semantic join paths using business-key correlation. Week 3.",
    version="0.3.0",
)

resolver = EntityResolver()


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "entity_resolution_agent",
        "port": 8004,
        "version": "0.3.0",
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
