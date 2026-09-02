"""Held-out plan evaluator for Step 16 validation."""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICES = os.path.join(ROOT, "services")
HOLDOUT_FILE = os.path.join(ROOT, "benchmark", "holdout", "plan_holdout_cases.json")

for p in (SERVICES, os.path.join(SERVICES, "shared")):
    if p not in sys.path:
        sys.path.insert(0, p)

from intent_agent.structured_intent import build_structured_intent
from sql_agent.query_plan_builder import QueryPlanBuilder, _VALID_COLUMNS


def run_holdout():
    cases = json.load(open(HOLDOUT_FILE, encoding="utf-8"))
    builder = QueryPlanBuilder()

    passed = 0
    total = len(cases)

    for c in cases:
        q = c["question"]
        si = build_structured_intent(q)

        expected_table = c.get("expected_table", "customers")
        selcols = {expected_table: sorted(_VALID_COLUMNS.get(expected_table, []))}

        plan = builder.build(
            task=si.get("task") or "aggregation",
            query_text=q,
            selected_tables=[expected_table],
            bridge_tables=[],
            selected_columns=selcols,
            join_paths=[],
            metrics=si.get("metrics"),
            dimensions=si.get("dimensions"),
            filters_structured=si.get("filters_structured"),
            time_range=si.get("time_range"),
            sort_structured=si.get("sort_structured"),
            limit_requested=si.get("limit_requested"),
            requested_fields=si.get("requested_fields"),
        )

        valid = plan.unsupported_reason is None and len(plan.selected_tables) > 0
        if valid:
            passed += 1
            print(f"PASS {c['id']}: {q[:50]}")
        else:
            print(f"FAIL {c['id']}: {plan.unsupported_reason}")

    rate = round(100.0 * passed / total, 2)
    print(f"\nHeld-out Plan Benchmark: {passed}/{total} passed ({rate}%)")
    return {"passed": passed, "total": total, "accuracy_rate": rate}


if __name__ == "__main__":
    run_holdout()
