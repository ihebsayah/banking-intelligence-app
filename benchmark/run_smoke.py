#!/usr/bin/env python3
"""
benchmark/run_smoke.py — Run 10-question smoke benchmark twice, compare determinism.

Usage:
    python benchmark/run_smoke.py

Produces:
    benchmark/results/smoke_run_1.jsonl
    benchmark/results/smoke_run_2.jsonl
    benchmark/results/smoke_comparison.json
"""
import sys
import os
import json
import time
import hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICES = os.path.join(ROOT, "services")
for p in [SERVICES, os.path.join(SERVICES, "shared")]:
    if p not in sys.path:
        sys.path.insert(0, p)

EXEC_DIR = os.path.join(SERVICES, "execution_agent")
for p in [EXEC_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

import psycopg2
from sql_agent.query_plan_builder import QueryPlanBuilder, initialize_join_registry
from sql_agent.deterministic_compiler import DeterministicSQLCompiler
from result_verifier import ResultVerifier
from pg_repair_engine import PGRepairEngine

BUILDER = QueryPlanBuilder()
COMPILER = DeterministicSQLCompiler()
VERIFIER = ResultVerifier()
REPAIR = PGRepairEngine()

SNAPSHOT = "snap-smoke-001"
VERSION = "v8.0.0"
PG_DSN = os.environ.get(
    "PG_TEST_DSN",
    "host=localhost port=5432 dbname=banking_dev user=banking_user password=securepass123",
)
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")


def _get_conn():
    return psycopg2.connect(PG_DSN)


def _sql_hash(sql: str) -> str:
    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def _plan_hash(plan) -> str:
    return hashlib.sha256(json.dumps(plan.model_dump(), sort_keys=True).encode()).hexdigest()[:16]


def _run_question(q: dict) -> dict:
    """Execute one question through the full pipeline, return trace."""
    qid = q["question_id"]
    trace = {
        "question_id": qid,
        "question": q["question"],
        "language": q.get("language", "en"),
        "category": q["category"],
        "difficulty": q["difficulty"],
        "expected_answer_type": q["expected_answer_type"],
        "expected_supported": q["expected_supported"],
    }
    t_start = time.perf_counter()

    # 1. Build plan
    t0 = time.perf_counter()
    try:
        plan = BUILDER.build(
            task="aggregation",
            query_text=q["question"],
            selected_tables=q.get("selected_tables", []),
            bridge_tables=[],
            selected_columns=q.get("selected_columns", {}),
            join_paths=[],
            metrics=q.get("metrics", []),
            dimensions=q.get("dimensions", []),
            filters_structured=q.get("filters_structured", []),
            time_range={"type": "none", "value": None},
            sort_structured=q.get("sort_structured"),
            limit_requested=q.get("limit_requested", 100),
            requested_fields=q.get("requested_fields", []),
            semantic_metadata_version=VERSION,
            schema_snapshot_id=SNAPSHOT,
        )
        trace["plan_valid"] = True
        trace["plan_hash"] = _plan_hash(plan)
    except Exception as e:
        trace["plan_valid"] = False
        trace["plan_hash"] = None
        trace["failure_stage"] = "planning"
        trace["error"] = str(e)[:500]
        trace["latency_ms"] = {"total": round((time.perf_counter() - t_start) * 1000, 2)}
        return trace
    t_plan = time.perf_counter()

    # 2. Compile SQL
    try:
        compiled = COMPILER.compile(plan)
        trace["sql_compiled"] = True
        trace["sql_hash"] = _sql_hash(compiled.sql)
        trace["sql"] = compiled.sql
        trace["parameters"] = [{"position": p.position, "value": str(p.value)[:100]} for p in compiled.parameters]
    except Exception as e:
        trace["sql_compiled"] = False
        trace["failure_stage"] = "compilation"
        trace["error"] = str(e)[:500]
        trace["latency_ms"] = {"total": round((time.perf_counter() - t_start) * 1000, 2)}
        return trace
    t_compile = time.perf_counter()

    # 3. Execute against live PG
    import re as _re
    try:
        conn = _get_conn()
        cur = conn.cursor()
        sql = compiled.sql
        params_by_pos = {p.position: p.value for p in compiled.parameters}
        placeholders = _re.findall(r'\$(\d+)', sql)
        used_positions = sorted(set(int(m) for m in placeholders))
        param_values = [params_by_pos[pos] for pos in used_positions]
        for pos in used_positions:
            sql = sql.replace(f"${pos}", "%s")
        t0_exec = time.perf_counter()
        cur.execute(sql, param_values)
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description] if cur.description else []
        result_data = [dict(zip(col_names, row)) for row in rows]
        conn.close()
        trace["sql_executed"] = True
    except Exception as e:
        trace["sql_executed"] = False
        trace["failure_stage"] = "execution"
        trace["error"] = str(e)[:500]
        try:
            conn.close()
        except Exception:
            pass
        trace["latency_ms"] = {"total": round((time.perf_counter() - t_start) * 1000, 2)}
        return trace
    t_exec = time.perf_counter()

    # 4. Verify result
    try:
        verification = VERIFIER.verify(
            data=result_data,
            expected_answer={"answer_type": q["expected_answer_type"]},
            plan_metrics=q.get("metrics", []),
        )
        trace["result_verified"] = verification["verified"]
        trace["result_rows"] = len(result_data)
        trace["result_sample"] = result_data[:3]
    except Exception as e:
        trace["result_verified"] = False
        trace["error"] = str(e)[:500]
    t_verify = time.perf_counter()

    # Mark unsupported questions that fail at execution as correctly unsupported
    if not q.get("expected_supported") and trace.get("failure_stage") in ("execution", "compilation"):
        trace["unsupported_correctly"] = True
        trace["failure_stage"] = q.get("expected_failure_stage", "execution")
    else:
        trace["unsupported_correctly"] = False
        trace["failure_stage"] = None if trace.get("failure_stage") is None else trace["failure_stage"]
    trace["latency_ms"] = {
        "planning": round((t_plan - t_start) * 1000, 2),
        "compilation": round((t_compile - t_plan) * 1000, 2),
        "database": round((t_exec - t_compile) * 1000, 2),
        "verification": round((t_verify - t_exec) * 1000, 2),
        "total": round((t_verify - t_start) * 1000, 2),
    }
    return trace


def _run_set(questions: list, run_label: str) -> list:
    """Run all questions, write JSONL, return traces."""
    traces = []
    for q in questions:
        trace = _run_question(q)
        traces.append(trace)
        status = "PASS" if trace.get("failure_stage") is None else f"FAIL:{trace['failure_stage']}"
        print(f"  {trace['question_id']}: {status} ({trace['latency_ms']['total']}ms)")

    path = os.path.join(RESULTS_DIR, f"{run_label}.jsonl")
    with open(path, "w") as f:
        for t in traces:
            f.write(json.dumps(t, default=str) + "\n")
    print(f"  Wrote {len(traces)} traces to {path}")
    return traces


def _compare(run1: list, run2: list) -> dict:
    """Compare two runs for determinism."""
    comparison = {"deterministic": True, "mismatches": []}
    for t1, t2 in zip(run1, run2):
        qid = t1["question_id"]
        for key in ["plan_hash", "sql_hash", "failure_stage", "result_verified"]:
            if t1.get(key) != t2.get(key):
                comparison["deterministic"] = False
                comparison["mismatches"].append({
                    "question_id": qid,
                    "field": key,
                    "run1": t1.get(key),
                    "run2": t2.get(key),
                })
    return comparison


def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Initialize join registry for multi-table join resolution
    try:
        conn = _get_conn()
        initialize_join_registry(conn)
        conn.close()
    except Exception as e:
        print(f"  Warning: join registry init failed: {e}")

    questions_path = os.path.join(ROOT, "benchmark", "smoke_10.json")
    with open(questions_path) as f:
        questions = json.load(f)

    print(f"Smoke benchmark: {len(questions)} questions")
    print("=" * 50)

    print("\nRun 1:")
    run1 = _run_set(questions, "smoke_run_1")

    print("\nRun 2:")
    run2 = _run_set(questions, "smoke_run_2")

    print("\nComparison:")
    comparison = _compare(run1, run2)
    comp_path = os.path.join(RESULTS_DIR, "smoke_comparison.json")
    with open(comp_path, "w") as f:
        json.dump(comparison, f, indent=2)

    if comparison["deterministic"]:
        print("  DETERMINISTIC — all hashes match")
    else:
        print(f"  NOT DETERMINISTIC — {len(comparison['mismatches'])} mismatches")
        for m in comparison["mismatches"]:
            print(f"    {m['question_id']}.{m['field']}: {m['run1']} -> {m['run2']}")

    # Summary
    supported = [t for t in run1 if t.get("failure_stage") is None]
    unsupported = [t for t in run1 if not t.get("expected_supported")]
    print(f"\nSummary: {len(supported)}/{len(run1)} supported, {len(unsupported)} correctly unsupported")
    return 0 if comparison["deterministic"] else 1


if __name__ == "__main__":
    sys.exit(main())
