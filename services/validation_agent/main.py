"""
services/validation_agent/main.py
Validation Agent — FastAPI app on port 8006.
Validates SQL queries for security (injection prevention) + HMAC signing.
"""
import sys
import logging
import os

sys.path.insert(0, "/app/shared")
sys.path.insert(0, "/app")

from fastapi import FastAPI, HTTPException
import uvicorn

from models import QueryValidationRequest, QueryValidationResponse
from query_validator import QueryValidator
from injection_tester import InjectionTester

# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [validation_agent] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Validation Agent",
    description=(
        "Validates SQL queries for safety (injection prevention) + signs safe queries. "
        "Blocks DELETE, DROP, UNION, OR 1=1, SLEEP and 20+ attack vectors. Week 3."
    ),
    version="0.3.0",
)

validator = QueryValidator()
tester = InjectionTester(validator)


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "validation_agent",
        "port": 8006,
        "version": "0.3.0",
        "security": "5-check validation + HMAC signing",
    }


# ──────────────────────────────────────────────────────────────────────────────
# VALIDATE QUERY
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/validate_query", response_model=QueryValidationResponse)
async def validate_query(request: QueryValidationRequest):
    """
    Validate a SQL query for safety.

    Checks:
      1. syntax_check    — valid SQL syntax
      2. select_only     — must be SELECT statement
      3. keyword_check   — no dangerous keywords (DROP/DELETE/INSERT/...)
      4. limit_check     — LIMIT clause required
      5. pattern_check   — no injection patterns (UNION/OR 1=1/SLEEP/...)

    Returns:
      safe: bool, confidence, issues, signature (if safe)
    """
    try:
        logger.info(
            "Validating query: user_role=%s sql_len=%d",
            request.user_role, len(request.sql)
        )
        result = validator.validate(request)
        if result.safe:
            logger.info("Query APPROVED — confidence=%.2f", result.confidence)
        else:
            logger.warning(
                "Query REJECTED — issues=%s", result.issues
            )
        return result
    except Exception as exc:
        logger.error("Validation error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# VERIFY SIGNATURE
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/verify_signature")
async def verify_signature(payload: dict):
    """Verify that a signed query has not been tampered with."""
    try:
        sql = payload.get("sql", "")
        parameters = payload.get("parameters", [])
        signature = payload.get("signature", "")
        valid = validator.verify_signature(sql, parameters, signature)
        return {"valid": valid, "sql": sql[:100]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ──────────────────────────────────────────────────────────────────────────────
# INJECTION TESTS — CRITICAL ENDPOINT
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/test_injections")
async def test_injections():
    """
    Run all 22 SQL injection attack tests.
    
    Expected result: blocked=22, vulnerable=0
    
    If vulnerable > 0: CRITICAL SECURITY FAILURE — fix validator immediately!
    """
    logger.info("Running injection test suite...")
    result = tester.test_all_injections()

    if result["vulnerable"] > 0:
        logger.critical(
            "SECURITY FAILURE: %d injection(s) NOT blocked!",
            result["vulnerable"]
        )
    else:
        logger.info(
            "All %d injections BLOCKED ✓", result["blocked"]
        )

    return result


# ──────────────────────────────────────────────────────────────────────────────
# DEMO — good query passes
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/test_good_queries")
async def test_good_queries():
    """Verify that legitimate queries pass validation."""
    good_queries = [
        {
            "name": "Simple customer lookup",
            "sql": "SELECT customer_id, first_name, last_name FROM customers WHERE customer_id = ? LIMIT 100",
        },
        {
            "name": "Account balance query",
            "sql": "SELECT account_id, balance FROM accounts WHERE balance > ? LIMIT 50",
        },
        {
            "name": "Join customers and accounts",
            "sql": (
                "SELECT customers.customer_id, customers.first_name, accounts.balance\n"
                "FROM customers\n"
                "INNER JOIN accounts ON customers.customer_id = accounts.customer_id\n"
                "WHERE accounts.status = ?\n"
                "LIMIT 100"
            ),
        },
        {
            "name": "Aggregation query",
            "sql": "SELECT branch_id, COUNT(*) FROM accounts GROUP BY branch_id LIMIT 100",
        },
    ]

    results = []
    passed = 0
    for gq in good_queries:
        req = QueryValidationRequest(sql=gq["sql"], parameters=["test_value"])
        res = validator.validate(req)
        if res.safe:
            passed += 1
        results.append({
            "name": gq["name"],
            "safe": res.safe,
            "confidence": res.confidence,
            "checks_passed": res.checks_passed,
            "checks_failed": res.checks_failed,
            "has_signature": res.signature is not None,
        })

    return {
        "total": len(good_queries),
        "passed": passed,
        "all_passed": passed == len(good_queries),
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8006, reload=False)
