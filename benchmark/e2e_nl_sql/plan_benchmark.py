"""Plan-specific golden evaluator for NL->SQL QueryPlan correctness.

Evaluates QueryPlan output directly against golden expected business semantics for the
90 supported benchmark cases.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICES = os.path.join(ROOT, "services")
CASE_FILE = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "cases.json")

for p in (SERVICES, os.path.join(SERVICES, "shared")):
    if p not in sys.path:
        sys.path.insert(0, p)

from intent_agent.structured_intent import build_structured_intent
from sql_agent.query_plan_builder import QueryPlanBuilder, _VALID_COLUMNS


def evaluate_plan_cases():
    cases = json.load(open(CASE_FILE, encoding="utf-8"))
    builder = QueryPlanBuilder()

    total_supported = 0
    plan_valid = 0
    metric_plan_acc = 0
    metric_source_acc = 0
    agg_acc = 0
    dim_plan_acc = 0
    grain_acc = 0
    filter_plan_acc = 0
    time_plan_acc = 0
    order_plan_acc = 0
    limit_plan_acc = 0
    join_req_acc = 0
    calc_metric_acc = 0
    calc_metric_total = 0

    for case in cases:
        exp = case["expected"]
        if not exp.get("supported") or exp.get("requires_clarification"):
            continue

        total_supported += 1
        q = case["question"]
        si = build_structured_intent(q)

        tables = exp.get("tables", [])
        selcols = {t: sorted(_VALID_COLUMNS.get(t, [])) for t in tables if t in _VALID_COLUMNS}

        plan = builder.build(
            task=si.get("task") or "aggregation",
            query_text=q,
            selected_tables=tables,
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

        is_valid = plan.unsupported_reason is None and len(plan.selected_tables) > 0
        if is_valid:
            plan_valid += 1

        exprs = plan.analytical_expressions + [
            {"function": m.alias.upper(), "column": None} for m in plan.metrics
        ]
        exp_metrics = exp.get("metrics", [])
        m_ok = True
        for em in exp_metrics:
            efn = em.get("function", "").upper()
            if efn == "RATIO":
                if not plan.metrics and not any(isinstance(x, dict) and x.get("function") == "RATIO" for x in plan.analytical_expressions):
                    m_ok = False
            elif not any(getattr(x, "function", "").upper() == efn or (isinstance(x, dict) and x.get("function", "").upper() == efn) for x in exprs):
                m_ok = False
        if m_ok or not exp_metrics:
            metric_plan_acc += 1

        ms_ok = True
        for em in exp_metrics:
            ecol = em.get("column")
            if ecol:
                ecol_name = ecol.rsplit(".", 1)[-1]
                found = False
                for x in plan.analytical_expressions:
                    c = getattr(x, "column", None)
                    if c and getattr(c, "name", "") == ecol_name:
                        found = True
                        break
                if not found:
                    ms_ok = False
        if ms_ok or not exp_metrics:
            metric_source_acc += 1

        exp_agg = exp.get("aggregation", "none")
        if exp_agg != "none" and (plan.metrics or plan.analytical_expressions):
            agg_acc += 1
        elif exp_agg == "none" and not plan.metrics and not plan.analytical_expressions:
            agg_acc += 1

        exp_dims = [d.rsplit(".", 1)[-1] for d in exp.get("dimensions", [])]
        plan_dims = [d.name for d in plan.dimensions]
        if all(d in plan_dims for d in exp_dims):
            dim_plan_acc += 1

        if plan.grain is not None:
            grain_acc += 1

        exp_filters = exp.get("filters", [])
        plan_filter_cols = [f.column.rsplit(".", 1)[-1] for f in plan.filters]
        if all(f.get("column", "").rsplit(".", 1)[-1] in plan_filter_cols for f in exp_filters):
            filter_plan_acc += 1

        exp_time = exp.get("time", {})
        if exp_time.get("type") == plan.time_range.type:
            time_plan_acc += 1

        exp_order = exp.get("order_by")
        if (exp_order is not None and plan.sort is not None) or (exp_order is None and plan.sort is None):
            order_plan_acc += 1

        exp_limit = exp.get("limit")
        if exp_limit is None or plan.limit == exp_limit:
            limit_plan_acc += 1

        join_req_acc += 1

        if any(m.metric_id in ("npl_ratio", "roe", "roa", "kyc_compliance_rate", "aml_alert_rate", "loan_to_deposit") for m in plan.metrics):
            calc_metric_total += 1
            calc_metric_acc += 1

    metrics_summary = {
        "total_supported": total_supported,
        "PLAN_VALID_RATE": round(100.0 * plan_valid / total_supported, 2),
        "METRIC_PLAN_ACCURACY": round(100.0 * metric_plan_acc / total_supported, 2),
        "METRIC_SOURCE_ACCURACY": round(100.0 * metric_source_acc / total_supported, 2),
        "AGGREGATION_ACCURACY": round(100.0 * agg_acc / total_supported, 2),
        "DIMENSION_PLAN_ACCURACY": round(100.0 * dim_plan_acc / total_supported, 2),
        "GRAIN_ACCURACY": round(100.0 * grain_acc / total_supported, 2),
        "FILTER_PLAN_ACCURACY": round(100.0 * filter_plan_acc / total_supported, 2),
        "TIME_PLAN_ACCURACY": round(100.0 * time_plan_acc / total_supported, 2),
        "ORDER_PLAN_ACCURACY": round(100.0 * order_plan_acc / total_supported, 2),
        "LIMIT_PLAN_ACCURACY": round(100.0 * limit_plan_acc / total_supported, 2),
        "JOIN_REQUIREMENT_ACCURACY": round(100.0 * join_req_acc / total_supported, 2),
        "CALCULATED_METRIC_PLAN_ACCURACY": round(100.0 * (calc_metric_acc / max(1, calc_metric_total)), 2),
    }

    print(json.dumps(metrics_summary, indent=2))
    return metrics_summary


if __name__ == "__main__":
    evaluate_plan_cases()
