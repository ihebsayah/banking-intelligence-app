"""
benchmark/e2e_nl_sql/drift_audit.py
Step 19 — Execution-fixture drift audit.

For every EXECUTION_FAILURE case in a results file, re-run the exact compiled
SQL exactly the way benchmark_runner._execution does and classify the mismatch:

  - SQL_ERROR          : execution genuinely errors (compiler/compile defect)
  - FIXTURE_DRIFT      : query runs; value / row-count differs from golden
  - RECONCILED         : query runs and now matches golden

Embedding the audit in a script (not a shell heredoc) avoids `$1` expansion
corruption and gives a repeatable, reviewable artifact.

Usage:
    testenv/bin/python3 benchmark/e2e_nl_sql/drift_audit.py \
        --result benchmark/e2e_nl_sql/results/E2E_POST_VALIDATION_FIX_V2.json \
        --out  benchmark/e2e_nl_sql/results/execution_drift_audit.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "benchmark", "e2e_nl_sql"))
sys.path.insert(0, os.path.join(ROOT, "services"))

import benchmark_runner as BR  # noqa: E402
from semantic_evaluator import _compare_result, _norm_value  # noqa: E402

PG_TEST_DSN = os.environ.get(
    "PG_TEST_DSN",
    "postgresql://banking_user:securepass123@localhost:5432/banking_dev",
)


def _classify(ev: dict, tr: dict) -> dict:
    c = tr.get("compile") or {}
    sql, param_dicts = c.get("sql"), c.get("parameters") or []
    params = [type("P", (), {"value": p["value"]})() for p in param_dicts]
    res = BR._execution(sql, params) if sql else {"ran": False, "error": "no SQL"}

    exp = (ev.get("expected") or {}).get("expected_result") or {}
    cls, detail = None, None
    if not res.get("ran"):
        cls, detail = "SQL_ERROR", res.get("error") or "execution failed"
    elif not exp or "mode" not in exp:
        # no golden expectation to compare — execution ran, nothing to reconcile
        cls, detail = "RECONCILED", "no expected_result (semantic-only case)"
    else:
        ok, msg = _compare_result(exp, res.get("rows") or [], res.get("column_names"))
        cls = "RECONCILED" if ok else "FIXTURE_DRIFT"
        detail = msg or "matches"

    return {
        "id": ev["id"], "classification": cls, "detail": detail,
        "sql_error": cls == "SQL_ERROR",
        "fixture_drift": cls == "FIXTURE_DRIFT",
        "reconciled": cls == "RECONCILED",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True, help="results JSON (with evaluations)")
    ap.add_argument("--out", required=True, help="output audit JSON path")
    args = ap.parse_args()

    data = json.load(open(args.result, encoding="utf-8"))
    traces_path = os.path.splitext(args.result)[0] + "_traces.jsonl"
    traces = {}
    if os.path.exists(traces_path):
        for line in open(traces_path, encoding="utf-8"):
            tr = json.loads(line)
            traces[tr["id"]] = tr

    failing = [ev for ev in data["evaluations"]
               if ev.get("primary_failure") == "EXECUTION_FAILURE"]
    rows = []
    for ev in failing:
        tr = traces.get(ev["id"]) or {}
        row = _classify(ev, tr)
        row["question"] = ev.get("question")
        rows.append(row)

    counts = {"SQL_ERROR": 0, "FIXTURE_DRIFT": 0, "RECONCILED": 0}
    for r in rows:
        counts[r["classification"]] += 1

    out = {
        "generated_at": BR.time.strftime("%Y-%m-%dT%H:%M:%S"),
        "dsn": PG_TEST_DSN,
        "FROM": args.result,
        "execution_failure_count": len(rows),
        "classification_counts": counts,
        "compiler_defects": counts["SQL_ERROR"],
        "fixture_drift_cases": counts["FIXTURE_DRIFT"],
        "reconciled_cases": counts["RECONCILED"],
        "cases": rows,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    print(json.dumps(counts, indent=2))
    for r in rows:
        print(f'{r["id"]:7s} {r["classification"]:14s} {r["detail"][:95]}')


if __name__ == "__main__":
    main()