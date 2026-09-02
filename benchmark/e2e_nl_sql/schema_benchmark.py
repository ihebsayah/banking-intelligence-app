"""Schema-retrieval golden evaluator (Step 15).

Runs ONLY the schema-retrieval stage of the deterministic pipeline against the
frozen E2E_NL_SQL benchmark and scores the returned table set against the golden
``expected.tables`` for every supported case, plus golden column coverage
(metrics / dimensions / filters / time).

Writes results/schema_retrieval_correctness.json and prints a summary.

Run with the project's testenv python:
    testenv/bin/python3 benchmark/e2e_nl_sql/schema_benchmark.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICES = os.path.join(ROOT, "services")
CASE_FILE = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "cases.json")
RESULTS_DIR = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "results")
RESULTS_FILE = os.path.join(RESULTS_DIR, "schema_retrieval_correctness.json")

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
for p in (SERVICES, os.path.join(SERVICES, "shared")):
    if p not in sys.path:
        sys.path.insert(0, p)

from benchmark.e2e_nl_sql.benchmark_runner import load_dependent  # noqa: E402

SchemaMatcher = load_dependent(
    "schema_agent.schema_matcher", "schema_agent", "schema_agent",
    also=["progressive_schema"],
).SchemaMatcher
from schema_agent.progressive_schema import _FALLBACK_COLUMNS  # noqa: E402
from intent_agent.structured_intent import build_structured_intent  # noqa: E402
from intent_agent.intent_recognizer import IntentRecognizer  # noqa: E402

_TABLE_DATE_COLS = set()
for _t, _cols in _FALLBACK_COLUMNS.items():
    if any("date" in c or c.endswith("_at") or c == "period" or c == "created_at" for c in _cols):
        _TABLE_DATE_COLS.add(_t)


def _col_ok(got_tables, col) -> bool:
    """col is 'table.column' (or None). True if table selected and column known."""
    if not col:
        return True
    tbl, _, cname = col.rpartition(".")
    if tbl not in got_tables:
        return False
    return cname in _FALLBACK_COLUMNS.get(tbl, [])


def run_schema_benchmark() -> dict:
    cases = json.load(open(CASE_FILE, encoding="utf-8"))
    supported = [
        c for c in cases
        if c["expected"]["supported"] and not c["expected"].get("requires_clarification")
    ]

    matcher = SchemaMatcher(semantic_layer_enabled=False)
    recognizer = IntentRecognizer()
    rows = []

    for c in supported:
        q = c["question"]
        expected = c["expected"]
        exp_tables = set(expected.get("tables", []))

        intent = recognizer.recognize_sync(q)
        si = build_structured_intent(q)

        resp = matcher.progressive_map(
            query=q,
            domain=si.get("domain") or "",
            task=si.get("task") or "",
            metrics=si.get("metrics") or [],
            dimensions=si.get("dimensions") or [],
            filters_structured=si.get("filters_structured") or [],
            limit_requested=si.get("limit_requested"),
            requested_fields=si.get("requested_fields") or [],
        )

        got_tables = list(dict.fromkeys(list(resp.selected_tables or []) + list(resp.bridge_tables or [])))
        got_set = set(got_tables)

        recall = len(got_set & exp_tables) / len(exp_tables) if exp_tables else 1.0
        precision = len(got_set & exp_tables) / len(got_set) if got_set else 0.0

        # Golden column coverage (against static column vocabulary).
        metric_cols = [(m.get("column")) for m in expected.get("metrics", []) if m.get("function") != "RATIO"]
        dim_cols = expected.get("dimensions", [])
        filter_cols = [f.get("column") for f in expected.get("filters", []) if f.get("column")]
        time_ok = True
        if (expected.get("time") or {}).get("type") == "relative":
            time_ok = bool(set(got_tables) & _TABLE_DATE_COLS)

        rows.append({
            "id": c["id"],
            "question": q,
            "expected_tables": sorted(exp_tables),
            "got_tables": got_tables,
            "selected_tables": list(resp.selected_tables or []),
            "bridge_tables": list(resp.bridge_tables or []),
            "recall": round(recall, 4),
            "precision": round(precision, 4),
            "exact": got_set == exp_tables,
            "missing": sorted(exp_tables - got_set),
            "extra": sorted(got_set - exp_tables),
            "metric_cols_ok": all(_col_ok(got_set, col) for col in metric_cols),
            "dim_cols_ok": all(_col_ok(got_set, col) for col in dim_cols),
            "filter_cols_ok": all(_col_ok(got_set, col) for col in filter_cols),
            "time_source_ok": time_ok,
            "reasons": {t: (resp.selection_reasons or {}).get(t, "") for t in got_tables},
        })

    n = len(rows)
    agg = {
        "total_supported_cases": n,
        "TABLE_RECALL": round(sum(r["recall"] for r in rows) / n, 4),
        "TABLE_PRECISION": round(sum(r["precision"] for r in rows) / n, 4),
        "EXACT_TABLE_MATCH": sum(1 for r in rows if r["exact"]),
        "EXACT_RATE": round(100.0 * sum(1 for r in rows if r["exact"]) / n, 2),
        "AVG_SELECTED_TABLES": round(sum(len(r["got_tables"]) for r in rows) / n, 2),
        "METRIC_COLUMN_COVERAGE": round(100.0 * sum(1 for r in rows if r["metric_cols_ok"]) / n, 2),
        "DIMENSION_COLUMN_COVERAGE": round(100.0 * sum(1 for r in rows if r["dim_cols_ok"]) / n, 2),
        "FILTER_COLUMN_COVERAGE": round(100.0 * sum(1 for r in rows if r["filter_cols_ok"]) / n, 2),
        "TIME_SOURCE_COVERAGE": round(100.0 * sum(1 for r in rows if r["time_source_ok"]) / n, 2),
        "cases_with_bridges": sum(1 for r in rows if r["bridge_tables"]),
        "failure_shape": dict(Counter(
            (("missing", r["missing"]) if r["missing"] else ("extra", r["extra"]))[0]
            for r in rows if not r["exact"]
        )),
    }
    return {"metrics": agg, "cases": rows}


def main() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out = run_schema_benchmark()
    with open(RESULTS_FILE, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
    m = out["metrics"]
    print("Schema retrieval correctness (golden table sets)")
    print("=" * 60)
    for k, v in m.items():
        print(f"{k:28s} {v}")
    print(f"\nresults: {RESULTS_FILE}")
    ne = [r["id"] for r in out["cases"] if not r["exact"]]
    if ne:
        print(f"non-exact cases ({len(ne)}): {ne}")


if __name__ == "__main__":
    main()