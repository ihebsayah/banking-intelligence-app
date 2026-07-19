"""
services/execution_agent/query_executor.py
Safe query executor with:
  - Signature verification (HMAC — blocks tampered queries)
  - Connection pooling via asyncpg
  - 30-second execution timeout
  - Redis caching (cache-aside pattern)
  - Row-count + execution-time metadata

Increment 3: Added verification pipeline:
  - ResultVerifier validates dataset against ExpectedAnswer
  - PGRepairEngine auto-repairs common PG errors
  - PlanRefiner suggests plan adjustments on verification failure

Increment 3.1: Recovery split:
  - ExecutionRetryPolicy: deadlocks, transients → retry once
  - SQLMechanicalRepair: semantics-preserving fixes (GROUP BY, syntax)
  - PlanRepairRequest: structural issues → replan request
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Config (matches validation_agent's SIGNING_KEY)
# ──────────────────────────────────────────────────────────────────────────────
SIGNING_KEY = os.getenv(
    "QUERY_SIGNING_KEY",
    "DEMO_KEY_CHANGE_IN_PRODUCTION_DO_NOT_USE_IN_PROD"
)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://banking_user:securepass123@postgres-main:5432/banking_dev"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
QUERY_TIMEOUT_SECONDS = 30
CACHE_TTL = 3600  # 1 hour


# ──────────────────────────────────────────────────────────────────────────────
# Signature verification (mirrors validation_agent/query_validator.py)
# ──────────────────────────────────────────────────────────────────────────────

def _verify_signature(sql: str, parameters: list, signature: str) -> bool:
    """
    HMAC-SHA256 verification (backward compatibility fallback).
    """
    try:
        import sys
        import os
        shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared"))
        if shared_path not in sys.path:
            sys.path.insert(0, shared_path)
        from query_signing import verify_query_signature
        return verify_query_signature(
            sql=sql,
            parameters=parameters,
            signature=signature,
            key=SIGNING_KEY,
            max_age_seconds=int(os.getenv("QUERY_SIGNATURE_MAX_AGE_SECONDS", "60"))
        )
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Query hash for cache key
# ──────────────────────────────────────────────────────────────────────────────

def _query_hash(sql: str, parameters: list) -> str:
    message = f"{sql.strip()}:{json.dumps(parameters, sort_keys=True, default=str)}"
    return hashlib.sha256(message.encode()).hexdigest()


# ──────────────────────────────────────────────────────────────────────────────
# QueryExecutor
# ──────────────────────────────────────────────────────────────────────────────

class QueryExecutor:
    """
    Executes validated, signed SQL queries against PostgreSQL.
    Uses asyncpg connection pool + Redis cache.
    """

    def __init__(self):
        self._pool: Optional[asyncpg.Pool] = None
        self._redis: Optional[aioredis.Redis] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """Create DB pool + Redis connection. Called once at startup."""
        # Postgres pool
        try:
            self._pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=2,
                max_size=10,
                command_timeout=QUERY_TIMEOUT_SECONDS,
            )
            logger.info("asyncpg pool ready")
        except Exception as exc:
            logger.warning("DB pool unavailable — will use mock data: %s", exc)
            self._pool = None

        # Redis
        try:
            self._redis = aioredis.from_url(
                REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
            )
            await self._redis.ping()
            logger.info("Redis connected")
        except Exception as exc:
            logger.warning("Redis unavailable — caching disabled: %s", exc)
            self._redis = None

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
        if self._redis:
            await self._redis.aclose()

    # ── Cache helpers ─────────────────────────────────────────────────────────

    async def _cache_get(self, key: str) -> Optional[Any]:
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(f"query:{key}")
            return json.loads(raw) if raw else None
        except Exception:
            return None

    async def _cache_set(self, key: str, value: Any) -> None:
        if not self._redis:
            return
        try:
            await self._redis.setex(f"query:{key}", CACHE_TTL, json.dumps(value, default=str))
        except Exception:
            pass

    async def _cache_delete(self, key: str) -> None:
        if not self._redis:
            return
        try:
            await self._redis.delete(f"query:{key}")
        except Exception:
            pass

    async def clear_cache(self) -> int:
        """Delete all query:* keys. Returns count removed."""
        if not self._redis:
            return 0
        try:
            keys = await self._redis.keys("query:*")
            if keys:
                return await self._redis.delete(*keys)
            return 0
        except Exception:
            return 0

    # ── Main execute ──────────────────────────────────────────────────────────

    async def execute(
        self,
        sql: str,
        parameters: list,
        signature: str,
        user_role: str,
    ) -> Dict[str, Any]:
        """
        Execute a validated query.

        Returns:
          {
            "data":   [{"col": val, ...}, ...],
            "metadata": {
              "rows_returned": int,
              "execution_time_ms": float,
              "source": "database" | "cache",
              "data_freshness": str,
              "query_hash": str,
            }
          }

        Raises:
          ValueError   — invalid signature
          TimeoutError — exceeded 30-second limit
          RuntimeError — DB error
        """
        # 1. Verify signature — CRITICAL security check
        import sys
        import os
        shared_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "shared"))
        if shared_path not in sys.path:
            sys.path.insert(0, shared_path)
        from query_signing import verify_query_signature
        verify_query_signature(
            sql=sql,
            parameters=parameters,
            signature=signature,
            key=SIGNING_KEY,
            max_age_seconds=int(os.getenv("QUERY_SIGNATURE_MAX_AGE_SECONDS", "60"))
        )

        q_hash = _query_hash(sql, parameters)

        # 2. Cache lookup
        cached = await self._cache_get(q_hash)
        if cached is not None:
            logger.info("Cache HIT for hash=%s", q_hash[:16])
            return {
                "data": cached,
                "metadata": {
                    "rows_returned": len(cached) if isinstance(cached, list) else 1,
                    "execution_time_ms": 0.0,
                    "source": "cache",
                    "data_freshness": "cached",
                    "query_hash": q_hash,
                },
            }

        # 3. Execute against DB (with timeout)
        t0 = time.monotonic()
        rows = await self._execute_with_timeout(sql, parameters)
        elapsed_ms = round((time.monotonic() - t0) * 1000, 2)

        # 4. Cache result
        await self._cache_set(q_hash, rows)

        logger.info("DB query OK rows=%d time=%.1fms hash=%s", len(rows), elapsed_ms, q_hash[:16])

        return {
            "data": rows,
            "metadata": {
                "rows_returned": len(rows),
                "execution_time_ms": elapsed_ms,
                "source": "database",
                "data_freshness": "real-time",
                "query_hash": q_hash,
            },
        }

    async def _execute_with_timeout(self, sql: str, parameters: list) -> List[Dict]:
        """Run query with 30-second timeout. Falls back to mock data if DB unavailable."""
        try:
            return await asyncio.wait_for(
                self._run_query(sql, parameters),
                timeout=QUERY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Query exceeded {QUERY_TIMEOUT_SECONDS}s timeout — aborted for safety")

    # ── Verification pipeline (Increment 3) ────────────────────────────────

    def verify_result(
        self,
        data: List[Dict],
        expected_answer: Optional[Dict] = None,
        plan_metrics: Optional[List[str]] = None,
        plan_dimensions: Optional[List[str]] = None,
        plan_grain: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Run ResultVerifier against the returned dataset."""
        from result_verifier import ResultVerifier
        verifier = ResultVerifier()
        return verifier.verify(
            data=data,
            expected_answer=expected_answer,
            plan_metrics=plan_metrics,
            plan_dimensions=plan_dimensions,
            plan_grain=plan_grain,
        )

    def diagnose_error(self, error_message: str) -> Dict[str, Any]:
        """Run PGRepairEngine diagnosis on an error."""
        from pg_repair_engine import PGRepairEngine
        engine = PGRepairEngine()
        return engine.diagnose(error_message)

    def attempt_repair(self, sql: str, error_message: str) -> Optional[str]:
        """Attempt to repair SQL based on error diagnosis (legacy interface)."""
        from pg_repair_engine import PGRepairEngine
        engine = PGRepairEngine()
        diagnosis = engine.diagnose(error_message)
        return engine.repair_sql(sql, diagnosis["error_type"], diagnosis.get("matched_value", ""))

    def attempt_recovery(
        self,
        sql: str,
        error_message: str,
        attempt: int = 0,
    ) -> Dict[str, Any]:
        """Increment 3.1: Three-way recovery split."""
        from pg_repair_engine import PGRepairEngine
        engine = PGRepairEngine()
        return engine.attempt_recovery(sql, error_message, attempt)

    def refine_plan(
        self,
        plan_summary: Dict[str, Any],
        verification_result: Optional[Dict] = None,
        execution_error: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run PlanRefiner to suggest plan adjustments."""
        from plan_refiner import PlanRefiner
        refiner = PlanRefiner()
        return refiner.refine(plan_summary, verification_result, execution_error)

    async def _run_query(self, sql: str, parameters: list) -> List[Dict]:
        """Execute against real DB or return mock rows if pool unavailable."""
        if self._pool is None:
            return self._mock_results(sql)

        # asyncpg uses $1, $2 placeholders; convert ? → $N
        pg_sql, pg_params = _convert_placeholders(sql, parameters)

        try:
            async with self._pool.acquire() as conn:
                records = await conn.fetch(pg_sql, *pg_params)
                return [dict(r) for r in records]
        except Exception as exc:
            logger.error("DB query failed: %s", exc)
            raise RuntimeError(f"DB_ERROR: {exc}") from exc

    def _mock_results(self, sql: str) -> List[Dict]:
        """
        Deterministic mock rows used when DB is unavailable (local testing).
        Uses real schema column names from postgres-main-init.sql.
        """
        sql_upper = sql.upper()
        if "CUSTOMER" in sql_upper:
            return [
                {"customer_id": f"CUST00{i}", "name": f"User{i} Smith",
                 "email": f"user{i}@example.com", "phone": f"555-010{i}",
                 "risk_score": round(0.1 * (i % 10), 2), "kyc_verified": i % 2 == 0,
                 "segment": ["premium", "standard", "high_risk"][i % 3],
                 "balance": round(1000 * i + 500.50, 2)}
                for i in range(1, 6)
            ]
        if "TRANSACTION" in sql_upper:
            return [
                {"transaction_id": f"TXN{i:03d}", "account_id": f"ACC{i:03d}",
                 "customer_id": f"CUST{i:03d}",
                 "amount": round(50.0 * i, 2), "transaction_type": ["debit", "credit"][i % 2],
                 "status": "completed", "transaction_date": f"2024-0{(i%9)+1}-{(i%28)+1:02d}"}
                for i in range(1, 21)
            ]
        if "BRANCH" in sql_upper:
            return [
                {"branch_id": f"BR{i:03d}", "name": f"Branch {i}",
                 "state": ["NY", "CA", "IL", "TX", "MA"][i % 5],
                 "city": ["New York", "Los Angeles", "Chicago", "Houston", "Boston"][i % 5]}
                for i in range(1, 6)
            ]
        if "ACCOUNT" in sql_upper:
            return [
                {"account_id": f"ACC{i:03d}", "customer_id": f"CUST{i:03d}",
                 "account_type": ["checking", "savings"][i % 2],
                 "status": "active", "balance": round(10000.0 * i, 2),
                 "available_balance": round(9500.0 * i, 2), "currency": "USD",
                 "branch_id": f"BR{i:03d}"}
                for i in range(1, 6)
            ]
        # Generic fallback
        return [
            {"id": i, "value": f"row_{i}", "amount": round(100.0 * i, 2)}
            for i in range(1, 6)
        ]


def _convert_placeholders(sql: str, parameters: list):
    """
    Convert ? placeholders to $1, $2, ... for asyncpg.
    If SQL already uses $N notation, pass through unchanged.
    """
    import re
    from datetime import datetime
    
    def _parse_val(val):
        if isinstance(val, str) and re.match(r"^\d{4}-\d{2}-\d{2}", val):
            try:
                # if it has time, parse time, else just date
                if len(val) > 10:
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                else:
                    return datetime.strptime(val[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        return val

    # Already postgres-style? Just unwrap any ParameterValue objects
    if re.search(r'\$\d+', sql):
        pg_params = []
        for p in parameters:
            val = p.value if hasattr(p, 'value') else p
            pg_params.append(_parse_val(val))
        return sql, pg_params

    idx = 0
    pg_params = []
    result = []
    for char in sql:
        if char == "?":
            if idx < len(parameters):
                p = parameters[idx]
                val = p.value if hasattr(p, "value") else p
                pg_params.append(_parse_val(val))
                idx += 1
                result.append(f"${idx}")
            else:
                result.append(char)
        else:
            result.append(char)
    return "".join(result), pg_params
