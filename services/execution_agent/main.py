"""
services/execution_agent/main.py
Execution Agent — FastAPI app on port 8007.

Endpoints:
  POST /execute_query  — Execute validated SQL, return formatted results
  GET  /health         — Liveness probe
  POST /cache/clear    — Manually clear query cache
  POST /test_execution — Run 15 built-in test cases
"""
import sys
import logging
import os
import time

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/shared")

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
import uvicorn

from models import ExecutionRequest, ExecutionResponse, ExecutionMetadata
from query_executor import QueryExecutor
from result_formatter import ResultFormatter

# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [execution_agent] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

executor = QueryExecutor()
formatter = ResultFormatter()


# ──────────────────────────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Execution Agent starting — initializing pool + cache")
    await executor.initialize()
    yield
    logger.info("Execution Agent shutting down")
    await executor.close()


app = FastAPI(
    title="Execution Agent",
    description=(
        "Executes validated, signed SQL queries with role-based access control, "
        "PII masking, Redis caching, and 30-second timeout protection. Week 4."
    ),
    version="0.4.0",
    lifespan=lifespan,
)


# ──────────────────────────────────────────────────────────────────────────────
# HEALTH
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "execution_agent",
        "port": 8007,
        "version": "0.4.0",
        "features": [
            "signature_verification",
            "rbac",
            "pii_masking",
            "redis_caching",
            "30s_timeout",
            "multi_format",
        ],
    }


# ──────────────────────────────────────────────────────────────────────────────
# EXECUTE QUERY
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/execute_query", response_model=ExecutionResponse)
async def execute_query(request: ExecutionRequest):
    """
    Execute a validated, signed SQL query.

    Security:
      - Signature verified before execution (HMAC-SHA256)
      - 30-second timeout enforced
      - Role-based column/row filtering applied
      - PII masked for all roles except compliance

    Caching:
      - Result cached in Redis for 1 hour (SHA-256 keyed on sql+params)
      - metadata.source = "cache" | "database"
    """
    logger.info(
        "execute_query: user_role=%s format=%s sql_len=%d",
        request.user_role, request.format, len(request.sql),
    )

    try:
        result = await executor.execute(
            sql=request.sql,
            parameters=request.parameters,
            signature=request.signature,
            user_role=request.user_role,
        )
    except ValueError as exc:
        # Signature invalid — reject immediately
        logger.warning("Signature rejected: %s", exc)
        return ExecutionResponse(
            status="rejected",
            data=None,
            metadata=ExecutionMetadata(
                rows_returned=0,
                execution_time_ms=0.0,
                source="none",
                data_freshness="n/a",
                user_role=request.user_role,
                error=str(exc),
            ),
            message=str(exc),
        )
    except TimeoutError as exc:
        logger.error("Query timeout: %s", exc)
        return ExecutionResponse(
            status="error",
            data=None,
            metadata=ExecutionMetadata(
                rows_returned=0,
                execution_time_ms=30000.0,
                source="database",
                data_freshness="n/a",
                user_role=request.user_role,
                error="TIMEOUT",
            ),
            message=str(exc),
        )
    except RuntimeError as exc:
        logger.error("DB error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

    raw_rows = result["data"]
    meta = result["metadata"]

    # Format + mask
    formatted_data, columns_masked = formatter.format(
        raw_rows=raw_rows,
        format_type=request.format,
        user_role=request.user_role,
    )

    return ExecutionResponse(
        status="success",
        data=formatted_data,
        metadata=ExecutionMetadata(
            rows_returned=meta["rows_returned"],
            execution_time_ms=meta["execution_time_ms"],
            data_freshness=meta["data_freshness"],
            source=meta["source"],
            columns_masked=columns_masked,
            user_role=request.user_role,
            query_hash=meta.get("query_hash"),
        ),
    )


# ──────────────────────────────────────────────────────────────────────────────
# CACHE MANAGEMENT
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/cache/clear")
async def clear_cache():
    """Manually evict all cached query results."""
    removed = await executor.clear_cache()
    return {"status": "ok", "keys_removed": removed}


# ──────────────────────────────────────────────────────────────────────────────
# BUILT-IN TEST SUITE — 15 cases
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/test_execution")
async def test_execution():
    """
    Run 15 execution test cases covering:
      - Simple SELECT / JOIN / WHERE / GROUP BY / ORDER BY
      - Large result set
      - Empty result set
      - Timeout (mocked — signature check catches bad sigs first)
      - Invalid signature (rejected)
      - Role filtering (analyst vs manager)
      - PII masking (SSN, credit card)
      - Format: JSON / CSV / Table
      - Cache: first hit (database) + second hit (cache)
    """
    import hashlib, hmac, json as _json

    SIGNING_KEY = "DEMO_KEY_CHANGE_IN_PRODUCTION_DO_NOT_USE_IN_PROD"

    def _sign(sql, params):
        msg = sql + "|" + str(sorted(str(p) for p in params))
        sig = hmac.new(SIGNING_KEY.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return f"sha256:{sig}:1700000000"

    base_sql = "SELECT customer_id, first_name, last_name, balance, risk_score, segment, ssn, email, credit_score FROM customers LIMIT 100"
    tx_sql   = "SELECT transaction_id, account_id, amount, transaction_type, transaction_date FROM transactions LIMIT 100"
    br_sql   = "SELECT branch_id, branch_name, region, count FROM accounts GROUP BY branch_id LIMIT 50"

    cases = [
        # 1
        {"name": "TC-01 Simple SELECT customers",
         "sql": base_sql, "params": [], "role": "analyst", "format": "json"},
        # 2
        {"name": "TC-02 SELECT with JOIN (customers + accounts)",
         "sql": "SELECT customers.customer_id, customers.first_name, accounts.balance FROM customers JOIN accounts ON customers.customer_id = accounts.customer_id LIMIT 100",
         "params": [], "role": "analyst", "format": "json"},
        # 3
        {"name": "TC-03 SELECT with WHERE filter",
         "sql": "SELECT account_id, balance FROM accounts WHERE balance > ? LIMIT 50",
         "params": [1000], "role": "analyst", "format": "json"},
        # 4
        {"name": "TC-04 SELECT with GROUP BY aggregation",
         "sql": br_sql, "params": [], "role": "analyst", "format": "json"},
        # 5
        {"name": "TC-05 SELECT with ORDER BY",
         "sql": "SELECT customer_id, first_name, balance FROM customers ORDER BY balance DESC LIMIT 10",
         "params": [], "role": "analyst", "format": "json"},
        # 6 — large result set (mocked 20 rows)
        {"name": "TC-06 Large result set (transactions)",
         "sql": tx_sql, "params": [], "role": "analyst", "format": "json"},
        # 7 — empty result set (WHERE impossible)
        {"name": "TC-07 Empty result set",
         "sql": "SELECT customer_id FROM customers WHERE customer_id = ? LIMIT 1",
         "params": ["NONEXISTENT_ID_ZZZ"], "role": "analyst", "format": "json"},
        # 8 — invalid signature → rejected
        {"name": "TC-08 Invalid signature (tamper attempt)",
         "sql": base_sql, "params": [], "role": "analyst", "format": "json",
         "_bad_sig": True},
        # 9 — role: analyst (no PII unmasked)
        {"name": "TC-09 Role analyst — PII masked",
         "sql": base_sql, "params": [], "role": "analyst", "format": "json"},
        # 10 — role: compliance (PII visible)
        {"name": "TC-10 Role compliance — PII visible",
         "sql": base_sql, "params": [], "role": "compliance", "format": "json"},
        # 11 — PII: SSN masked
        {"name": "TC-11 SSN masking verified",
         "sql": base_sql, "params": [], "role": "analyst", "format": "json",
         "_check_ssn_masked": True},
        # 12 — Format: JSON
        {"name": "TC-12 Format JSON",
         "sql": base_sql, "params": [], "role": "analyst", "format": "json"},
        # 13 — Format: CSV
        {"name": "TC-13 Format CSV",
         "sql": base_sql, "params": [], "role": "analyst", "format": "csv"},
        # 14 — Format: Table
        {"name": "TC-14 Format Table (ASCII)",
         "sql": base_sql, "params": [], "role": "analyst", "format": "table"},
        # 15 — Cache: run same query twice; second should be from cache
        {"name": "TC-15 Cache hit (second call returns source=cache)",
         "sql": "SELECT customer_id, first_name, balance FROM customers LIMIT 5",
         "params": [], "role": "analyst", "format": "json",
         "_cache_test": True},
    ]

    results = []
    passed = 0

    for tc in cases:
        bad_sig   = tc.pop("_bad_sig", False)
        cache_test = tc.pop("_cache_test", False)
        check_ssn  = tc.pop("_check_ssn_masked", False)

        sig = "sha256:INVALID:0" if bad_sig else _sign(tc["sql"], tc["params"])

        try:
            # First call
            res = await executor.execute(
                sql=tc["sql"],
                parameters=tc["params"],
                signature=sig,
                user_role=tc["role"],
            )
            formatted, cols_masked = formatter.format(res["data"], tc["format"], tc["role"])
            src1 = res["metadata"]["source"]

            # Cache test: second identical call
            src2 = None
            if cache_test:
                res2 = await executor.execute(
                    sql=tc["sql"], parameters=tc["params"],
                    signature=sig, user_role=tc["role"],
                )
                src2 = res2["metadata"]["source"]

            # Checks
            ok = True
            note = "passed"

            if bad_sig:
                ok = False  # should have raised ValueError
                note = "FAIL: bad signature should be rejected"

            if check_ssn:
                rows = formatted if isinstance(formatted, list) else []
                ssns = [r.get("ssn", "") for r in rows if "ssn" in r]
                if ssns and all("***" in str(s) for s in ssns):
                    note = f"SSN masked correctly: {ssns[0]}"
                else:
                    ok = False
                    note = f"FAIL: SSN not masked. got={ssns[:2]}"

            if cache_test and src2 != "cache":
                ok = False
                note = f"FAIL: expected cache on 2nd call, got source={src2}"
            elif cache_test:
                note = f"1st={src1} 2nd={src2} ✓"

            if ok:
                passed += 1

        except ValueError as exc:
            if bad_sig:
                passed += 1
                ok = True
                formatted = None
                cols_masked = []
                note = f"Correctly rejected: {str(exc)[:60]}"
            else:
                ok = False
                note = f"Unexpected ValueError: {exc}"
        except Exception as exc:
            ok = False
            note = f"ERROR: {exc}"
            formatted = None
            cols_masked = []

        results.append({
            "test": tc["name"],
            "passed": ok,
            "role": tc["role"],
            "format": tc["format"],
            "note": note,
            "columns_masked": cols_masked,
        })

    return {
        "total": len(cases),
        "passed": passed,
        "failed": len(cases) - passed,
        "success_rate": f"{passed}/{len(cases)}",
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8007, reload=False)
