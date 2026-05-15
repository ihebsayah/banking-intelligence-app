"""
services/orchestrator/main.py
Orchestrator Agent — Full 6-agent pipeline. Week 4.

Pipeline:
  User NL query
    → Intent Agent (8002)
    → Schema Agent (8003)
    → Entity Resolution Agent (8004)
    → SQL Generation Agent (8005)
    → Validation Agent (8006)
    → Execution Agent (8007)
    → [Audit Agent (8008)]
    → Return results

Port: 8001
"""
import sys
sys.path.insert(0, "/app"); sys.path.insert(0, "/app/shared")

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional
from urllib.request import urlopen, Request as UrlRequest
from urllib.error import URLError
import urllib.request

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [orchestrator] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

HOST = "0.0.0.0"
PORT = int(os.getenv("PORT", 8001))

INTENT_URL      = os.getenv("INTENT_AGENT_URL",            "http://intent-agent:8002")
SCHEMA_URL      = os.getenv("SCHEMA_AGENT_URL",            "http://schema-agent:8003")
ENTITY_URL      = os.getenv("ENTITY_RESOLUTION_AGENT_URL", "http://entity-resolution-agent:8004")
SQL_URL         = os.getenv("SQL_AGENT_URL",               "http://sql-agent:8005")
VALIDATION_URL  = os.getenv("VALIDATION_AGENT_URL",        "http://validation-agent:8006")
EXECUTION_URL   = os.getenv("EXECUTION_AGENT_URL",         "http://execution-agent:8007")
AUDIT_URL       = os.getenv("AUDIT_AGENT_URL",             "http://audit-agent:8008")

STEP_TIMEOUT = 10  # seconds per agent call


# ──────────────────────────────────────────────────────────────────────────────
# HTTP helper (stdlib only — no requests/httpx in orchestrator image)
# ──────────────────────────────────────────────────────────────────────────────

def _post(url: str, payload: Dict, timeout: int = STEP_TIMEOUT) -> Dict:
    """Synchronous HTTP POST. Returns parsed JSON or raises."""
    data = json.dumps(payload, default=str).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return json.loads(body)
    except URLError as exc:
        raise RuntimeError(f"Agent call failed {url}: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Agent call error {url}: {exc}") from exc


def _post_safe(url: str, payload: Dict, timeout: int = STEP_TIMEOUT) -> Optional[Dict]:
    """Like _post but returns None on failure (for non-critical steps)."""
    try:
        return _post(url, payload, timeout)
    except Exception as exc:
        logger.warning("Non-critical agent call failed: %s", exc)
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────────

def run_pipeline(
    query: str,
    user_role: str = "analyst",
    user_id: str = "unknown",
    format_type: str = "json",
) -> Dict:
    """
    Full 6-agent pipeline. Synchronous (runs in thread from HTTP handler).

    Returns:
      {status, results, metadata, pipeline_steps}
    """
    pipeline_id = str(uuid.uuid4())[:8]
    t_start = time.monotonic()
    steps = []

    logger.info("[%s] Pipeline start: query=%r role=%s", pipeline_id, query[:60], user_role)

    # ── STEP 1: Intent Recognition ────────────────────────────────────────────
    try:
        step_t = time.monotonic()
        intent_res = _post(f"{INTENT_URL}/process_intent", {"query": query})
        steps.append({
            "step": 1, "agent": "intent_agent",
            "time_ms": round((time.monotonic() - step_t) * 1000, 1),
            "status": "ok",
            "output": {
                "primary_category": intent_res.get("primary_category"),
                "secondary_categories": intent_res.get("secondary_categories", []),
            },
        })
        intent_categories = [intent_res.get("primary_category", "retrieve")] + \
                             intent_res.get("secondary_categories", [])
        primary_intent = intent_res.get("primary_category", "retrieve")
    except Exception as exc:
        logger.warning("[%s] Intent agent unavailable, using fallback: %s", pipeline_id, exc)
        intent_categories = ["retrieve"]
        primary_intent = "retrieve"
        steps.append({"step": 1, "agent": "intent_agent", "status": "fallback", "note": str(exc)})

    # ── STEP 2: Schema Mapping ────────────────────────────────────────────────
    try:
        step_t = time.monotonic()
        schema_res = _post(f"{SCHEMA_URL}/map_schema", {"intent_categories": intent_categories})
        tables = []
        for domain in schema_res.get("relevant_domains", []):
            tables.extend(domain.get("tables", []))
        if not tables:
            tables = ["customers"]
        steps.append({
            "step": 2, "agent": "schema_agent",
            "time_ms": round((time.monotonic() - step_t) * 1000, 1),
            "status": "ok",
            "output": {"tables": tables[:5]},
        })
    except Exception as exc:
        logger.warning("[%s] Schema agent fallback: %s", pipeline_id, exc)
        # Infer tables from query text
        q_upper = query.upper()
        tables = []
        if "CUSTOMER" in q_upper:     tables.append("customers")
        if "ACCOUNT" in q_upper:      tables.append("accounts")
        if "TRANSACTION" in q_upper:  tables.append("transactions")
        if "BRANCH" in q_upper:       tables.append("branches")
        if "PRODUCT" in q_upper:      tables.append("products")
        if not tables:                tables = ["customers"]
        steps.append({"step": 2, "agent": "schema_agent", "status": "fallback", "tables": tables})

    # ── STEP 3: Entity Resolution ─────────────────────────────────────────────
    primary_entity = tables[0].rstrip("s") if tables else "customer"
    join_paths = []
    try:
        step_t = time.monotonic()
        entity_res = _post(f"{ENTITY_URL}/resolve_entities", {
            "primary_entity": primary_entity,
            "tables": tables,
        })
        join_paths = entity_res.get("join_structure", [])
        steps.append({
            "step": 3, "agent": "entity_resolution_agent",
            "time_ms": round((time.monotonic() - step_t) * 1000, 1),
            "status": "ok",
            "output": {"join_paths": len(join_paths)},
        })
    except Exception as exc:
        logger.warning("[%s] Entity agent fallback: %s", pipeline_id, exc)
        steps.append({"step": 3, "agent": "entity_resolution_agent", "status": "fallback"})

    # ── STEP 4: SQL Generation ────────────────────────────────────────────────
    try:
        step_t = time.monotonic()
        sql_payload = {
            "intent": primary_intent,
            "primary_entity": primary_entity,
            "tables": tables,
            "join_paths": join_paths,
            "limit": 100,
        }
        sql_res = _post(f"{SQL_URL}/generate_sql", sql_payload)
        sql      = sql_res.get("sql", "")
        params   = sql_res.get("parameters", [])
        steps.append({
            "step": 4, "agent": "sql_agent",
            "time_ms": round((time.monotonic() - step_t) * 1000, 1),
            "status": "ok",
            "output": {"sql": sql[:100], "param_count": len(params)},
        })
    except Exception as exc:
        logger.warning("[%s] SQL agent fallback: %s", pipeline_id, exc)
        # Safe generic fallback SQL
        tbl = tables[0] if tables else "customers"
        sql    = f"SELECT * FROM {tbl} LIMIT 100"
        params = []
        steps.append({"step": 4, "agent": "sql_agent", "status": "fallback", "sql": sql})

    # ── STEP 5: Validation ────────────────────────────────────────────────────
    try:
        step_t = time.monotonic()
        # Flatten parameter values for validation
        flat_params = [p.get("value", p) if isinstance(p, dict) else p for p in params]
        val_res = _post(f"{VALIDATION_URL}/validate_query", {
            "sql": sql,
            "parameters": flat_params,
            "user_role": user_role,
        })
        is_safe   = val_res.get("safe", False)
        signature = val_res.get("signature")
        steps.append({
            "step": 5, "agent": "validation_agent",
            "time_ms": round((time.monotonic() - step_t) * 1000, 1),
            "status": "ok",
            "output": {
                "safe": is_safe,
                "confidence": val_res.get("confidence"),
                "issues": val_res.get("issues", []),
            },
        })
    except Exception as exc:
        logger.warning("[%s] Validation fallback: %s", pipeline_id, exc)
        is_safe   = False
        signature = None
        steps.append({"step": 5, "agent": "validation_agent", "status": "fallback", "safe": False})

    # ── STEP 6a: Validation gate ──────────────────────────────────────────────
    if not is_safe or not signature:
        total_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.warning("[%s] Query blocked at validation", pipeline_id)
        _audit(pipeline_id, query, user_role, user_id, "rejected", total_ms)
        return {
            "status": "rejected",
            "message": "Query failed safety validation. See suggestions below.",
            "suggestions": [
                "Ensure query is a SELECT statement",
                "Add LIMIT clause",
                "Remove any injection patterns",
            ],
            "pipeline_steps": steps,
            "metadata": {
                "pipeline_id": pipeline_id,
                "total_time_ms": total_ms,
                "user_role": user_role,
            },
        }

    # ── STEP 6b: Execution ────────────────────────────────────────────────────
    try:
        step_t = time.monotonic()
        exec_res = _post(f"{EXECUTION_URL}/execute_query", {
            "sql": sql,
            "parameters": flat_params,
            "signature": signature,
            "user_role": user_role,
            "format": format_type,
            "user_id": user_id,
        })
        steps.append({
            "step": 6, "agent": "execution_agent",
            "time_ms": round((time.monotonic() - step_t) * 1000, 1),
            "status": "ok",
            "output": {
                "rows_returned": exec_res.get("metadata", {}).get("rows_returned", 0),
                "source": exec_res.get("metadata", {}).get("source"),
            },
        })
        exec_status = exec_res.get("status", "error")
        results     = exec_res.get("data")
        exec_meta   = exec_res.get("metadata", {})
    except Exception as exc:
        logger.error("[%s] Execution agent failed: %s", pipeline_id, exc)
        steps.append({"step": 6, "agent": "execution_agent", "status": "error", "note": str(exc)})
        exec_status = "error"
        results     = None
        exec_meta   = {}

    # ── STEP 7: Audit (fire-and-forget) ──────────────────────────────────────
    total_ms = round((time.monotonic() - t_start) * 1000, 1)
    _audit(pipeline_id, query, user_role, user_id, exec_status, total_ms)

    logger.info(
        "[%s] Pipeline done: status=%s rows=%s time=%.1fms",
        pipeline_id, exec_status,
        exec_meta.get("rows_returned", "?"), total_ms,
    )

    return {
        "status": exec_status,
        "results": results,
        "metadata": {
            "pipeline_id": pipeline_id,
            "rows_returned": exec_meta.get("rows_returned", 0),
            "execution_time_ms": exec_meta.get("execution_time_ms", 0),
            "total_pipeline_time_ms": total_ms,
            "data_freshness": exec_meta.get("data_freshness", "real-time"),
            "source": exec_meta.get("source", "database"),
            "columns_masked": exec_meta.get("columns_masked", []),
            "user_role": user_role,
            "format": format_type,
        },
        "pipeline_steps": steps,
    }


def _audit(pipeline_id, query, user_role, user_id, status, elapsed_ms):
    """Fire-and-forget audit log."""
    try:
        _post_safe(f"{AUDIT_URL}/log_access", {
            "user_id": user_id,
            "user_role": user_role,
            "action": "nl_query",
            "status": status,
            "endpoint": "/query",
            "http_method": "POST",
            "execution_time_ms": elapsed_ms,
            "metadata": {"query": query[:200], "pipeline_id": pipeline_id},
        }, timeout=3)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# HTTP Server
# ──────────────────────────────────────────────────────────────────────────────

class OrchestratorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default logs

    def _send_json(self, code: int, body: Dict):
        raw = json.dumps(body, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> Dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {
                "status": "healthy",
                "service": "orchestrator",
                "port": PORT,
                "version": "0.4.0",
                "pipeline": "6-agent: intent→schema→entity→sql→validation→execution",
            })
        else:
            self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path == "/process_query":
            try:
                payload    = self._read_body()
                query      = payload.get("query", "")
                user_role  = payload.get("user_role", "analyst")
                user_id    = payload.get("user_id", "unknown")
                fmt        = payload.get("format", "json")
                if not query:
                    self._send_json(400, {"error": "query field required"})
                    return
                result = run_pipeline(query, user_role, user_id, fmt)
                self._send_json(200, result)
            except Exception as exc:
                logger.error("Pipeline error: %s", exc, exc_info=True)
                self._send_json(500, {"status": "error", "message": str(exc)})
        else:
            self._send_json(404, {"error": "not_found"})


if __name__ == "__main__":
    logger.info("Orchestrator starting on port %d", PORT)
    server = HTTPServer((HOST, PORT), OrchestratorHandler)
    server.serve_forever()
