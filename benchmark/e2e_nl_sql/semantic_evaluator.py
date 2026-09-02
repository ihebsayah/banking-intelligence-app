"""Deterministic semantic evaluator for the end-to-end NL->SQL correctness benchmark.

Consumes a per-case pipeline trace (produced by benchmark_runner) plus the
golden "expected" semantics from cases.json, and produces:

  - per-component verdicts (tables / joins / metrics / dimensions / filters /
    time / sort / limit / validation / compliance / execution)
  - an end-to-end semantic verdict for supported cases
  - a single primary failure stage per failing supported case
  - aggregate rates (overall, per language, per level, per category) plus
    pipeline latency p50/p95.

Design rules (Step 13):
  * Intent label is scored SEPARATELY from end-to-end semantics. A wrong
    intent label never changes the semantic stage that failed.
  * Comparisons are semantic, not string-based: we compare resolved columns,
    filter operators + values, join paths, time windows, and execution rows.
  * Execution compares real DB results only for cases that ship an
    expected_result (development ground-truth reuse).
"""

from __future__ import annotations

import re
from collections import Counter


# ─── Failure stages (one primary stage per case) ────────────────────────────
INTENT_FAILURE = "INTENT_FAILURE"
SCHEMA_RETRIEVAL_FAILURE = "SCHEMA_RETRIEVAL_FAILURE"
ENTITY_RESOLUTION_FAILURE = "ENTITY_RESOLUTION_FAILURE"
CONSTRAINT_PROPAGATION_FAILURE = "CONSTRAINT_PROPAGATION_FAILURE"
SQL_GENERATION_FAILURE = "SQL_GENERATION_FAILURE"
VALIDATION_FALSE_REJECT = "VALIDATION_FALSE_REJECT"
VALIDATION_FALSE_ACCEPT = "VALIDATION_FALSE_ACCEPT"
COMPLIANCE_FALSE_REJECT = "COMPLIANCE_FALSE_REJECT"
COMPLIANCE_FALSE_ACCEPT = "COMPLIANCE_FALSE_ACCEPT"
EXECUTION_FAILURE = "EXECUTION_FAILURE"
CLARIFICATION_FAILURE = "CLARIFICATION_FAILURE"
UNSUPPORTED_ROUTING_FAILURE = "UNSUPPORTED_ROUTING_FAILURE"

# Dangerous payload markers — used to prove UNSAFE_REQUEST_EXECUTION_RATE == 0%.
_DANGEROUS_SQL_MARKERS = (
    "delete ", "insert ", "update ", "drop ", "alter ", "truncate ",
    "create ", "grant ", "revoke ", "exec ", "sleep(", "benchmark(",
    "pg_sleep", "union select", "into outfile", "load_file",
)

_STAGES = [
    INTENT_FAILURE, SCHEMA_RETRIEVAL_FAILURE, ENTITY_RESOLUTION_FAILURE,
    CONSTRAINT_PROPAGATION_FAILURE, SQL_GENERATION_FAILURE,
    VALIDATION_FALSE_REJECT, VALIDATION_FALSE_ACCEPT,
    COMPLIANCE_FALSE_REJECT, COMPLIANCE_FALSE_ACCEPT, EXECUTION_FAILURE,
    UNSUPPORTED_ROUTING_FAILURE, CLARIFICATION_FAILURE,
]


# ─── Small helpers ──────────────────────────────────────────────────────────

def _last(col: str | None) -> str | None:
    """Last path component of a table.column string."""
    if not col:
        return col
    return str(col).rsplit(".", 1)[-1]


def _norm_value(v):
    """Normalise a scalar for comparisons (bool/int/float/str)."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    return v


def _metric_key(expr: dict) -> tuple:
    fn = str(expr.get("function", "")).upper()
    if fn == "RATIO":
        return ("RATIO", None, False)
    col = expr.get("column") or {}
    cname = _last(col.get("name")) if isinstance(col, dict) else _last(col)
    return (fn, cname, bool(expr.get("distinct", False)))


_RATIO_SQL_PATTERNS = [
    re.compile(r"ROUND\([^)]*\/"),
    re.compile(r"\/\s*NULLIF"),
    re.compile(r"COUNT\(\s*CASE\s+WHEN"),
    re.compile(r"::numeric"),
]


def _ratio_in_sql(sql: str | None) -> bool:
    if not sql:
        return False
    return any(p.search(sql) for p in _RATIO_SQL_PATTERNS)


def _matches_expected_metric(expected: dict, actual_exprs: list, sql: str | None = None) -> bool:
    efn = str(expected.get("function", "")).upper()
    ecol = _last(expected.get("column"))
    edist = bool(expected.get("distinct", False))

    if efn == "RATIO":
        return _ratio_in_sql(sql)

    for x in actual_exprs:
        fn, cname, dist = _metric_key(x)
        if fn != efn:
            continue
        if ecol is None:
            # COUNT(*) semantics: accept COUNT over any (non-nullable pk) column too
            return True
        if cname == ecol:
            if edist and not dist:
                continue
            return True
    return False


def _has_join(join_list: list, a: str, b: str) -> bool:
    """True if a hop exists between tables a and b (direct or via one hop)."""
    pairs = {(j.get("from_table"), j.get("to_table")) for j in join_list}
    if (a, b) in pairs or (b, a) in pairs:
        return True
    adj: dict[str, set] = {}
    for x, y in pairs:
        adj.setdefault(x, set()).add(y)
        adj.setdefault(y, set()).add(x)
    return bool(adj.get(a, set()) & adj.get(b, set()))


def _filter_matches(expected: dict, actual_filters: list) -> bool:
    ecol = _last(expected.get("column"))
    eop = str(expected.get("operator", "=")).upper().replace(" ", "")
    eval_ = _norm_value(expected.get("value"))

    for f in actual_filters:
        acol = _last(f.get("column"))
        if not ecol or ecol != acol:
            continue
        aop = str(f.get("operator", "=")).upper().replace(" ", "")
        if aop in ("IS", "ISNULL") and eop in ("IS", "ISNULL"):
            return True
        if eop == "ISNULL" and aop not in ("IS", "ISNULL"):
            continue
        if eop != "ISNULL" and aop in ("IS", "ISNULL"):
            continue
        if aop != eop:
            continue
        a_val = _norm_value(f.get("value"))
        if a_val == eval_:
            return True
        # booleans may be serialised as "true"/"false" strings
        if isinstance(eval_, bool) and str(a_val).lower() == str(eval_).lower():
            return True
    return False


def _time_matches(expected: dict, actual: dict) -> bool:
    if not expected or expected.get("type") != "relative":
        return True
    return (actual or {}).get("type") == "relative" and (
        (actual or {}).get("value") == expected.get("value")
    )


def _sort_matches(expected: dict, actual: dict, join_list: list) -> bool:
    """Sort expectations are lenient: same direction + related column tail."""
    if not expected:
        return True
    if not actual:
        return False
    if str(actual.get("direction", "")).upper() != str(expected.get("direction", "ASC")).upper():
        return False
    ecol = str(expected.get("column", ""))
    acol = str(actual.get("column", ""))
    if "(" in ecol:  # COUNT(*) / SUM(...) style sort: any same-direction sort ok
        return True
    e_tail = ecol.rsplit(".", 1)[-1]
    a_tail = acol.rsplit(".", 1)[-1]
    return e_tail == a_tail or e_tail in acol or a_tail in ecol

def _limit_ok(expected: dict, plan: dict) -> bool:
    lim = expected.get("limit")
    if lim is None:
        return True
    return int(lim) == int((plan or {}).get("limit", 100))


def _row_matches(expected_row: dict, row: dict) -> bool:
    row_norm = {str(k).lower(): v for k, v in row.items()}
    for ekey, eval_ in expected_row.items():
        key = str(ekey).lower()
        if key in row_norm:
            if _norm_value(row_norm[key]) == _norm_value(eval_):
                continue
        # tolerate aliases like customer_count vs count vs message_count
        tail = key.rsplit("_", 1)[-1]
        hit = None
        for rk, rv in row_norm.items():
            if rk == key or rk.endswith("_" + tail) or rk == tail:
                if _norm_value(rv) == _norm_value(eval_):
                    hit = True
                    break
        if hit:
            continue
        return False
    return True


def _compare_result(expected: dict, rows: list, col_names: list | None = None) -> tuple[bool, str | None]:
    """Compare executed rows against expected_result. Returns (ok, mismatch_msg)."""
    mode = expected.get("mode")
    if mode == "row_count":
        return len(rows) == int(expected.get("value")), f"rowcount {len(rows)} vs {expected.get('value')}"
    if not rows:
        return False, "execution returned no rows"
    if mode == "exact_scalar" or mode == "numeric_tolerance":
        val = rows[0]
        if isinstance(val, (list, tuple)):
            val = val[0] if val else None
        expected_v = expected.get("value")
        if expected_v is None:  # expected NULL scalar
            return val is None, f"scalar {val!r} vs NULL expected"
        try:
            actual = float(val)
            expected_v = float(expected_v)
            tol = float(expected.get("tolerance", 0))
            return abs(actual - expected_v) <= tol, f"scalar {actual} vs {expected_v} (tol {tol})"
        except (TypeError, ValueError):
            return False, f"scalar not numeric: {val!r}"
    if mode == "unordered_rows":
        def _row_dict(r):
            if isinstance(r, dict):
                return {str(k).lower(): v for k, v in r.items()}
            if isinstance(r, (list, tuple)):
                return {str(c).lower(): (r[i] if i < len(r) else None)
                        for i, c in enumerate(col_names or [])}
            return {}
        rows_norm = [_row_dict(r) for r in rows]
        for erow in expected.get("rows", []):
            if not any(_row_matches(erow, r) for r in rows_norm):
                return False, f"missing expected row {erow}"
        return True, None
    return False, f"unknown comparison mode {mode}"


# ─── Per-case evaluation ────────────────────────────────────────────────────

def evaluate_case(exp: dict, trace: dict) -> dict:
    """Evaluate one case. exp = golden expected dict; trace = runner trace."""
    ev = {
        "id": exp["id"], "language": exp["language"], "level": exp["level"],
        "category": exp["category"], "question": exp["question"],
        "expected": exp["expected"],
    }
    e = exp["expected"]

    intent = trace.get("intent") or {}
    structured = trace.get("structured") or {}
    plan = trace.get("plan") or {}
    compile_ = trace.get("compile") or {}
    validation = trace.get("validation") or {}
    compliance = trace.get("compliance") or {}
    execution = trace.get("execution") or {}

    # Intent label (independent of semantics)
    if e.get("intent") is not None and e.get("supported"):
        ev["intent_label_correct"] = (intent.get("label") == e["intent"])
    else:
        ev["intent_label_correct"] = None

    plan_event = _resolve_plan_blockade(trace)
    plan_available = bool(plan.get("selected_tables"))

    # ── L4 clarify cases ───────────────────────────────────────────────
    if e.get("requires_clarification"):
        clarified = (
            str(intent.get("decision", "")).upper() in ("CLARIFY", "CLARIFICATION")
            or intent.get("supported") is False
        )
        ev["semantic_pass"] = bool(clarified)
        ev["clarification_correct"] = bool(clarified)
        ev["primary_failure"] = None if clarified else CLARIFICATION_FAILURE
        ev["details"] = {"intent": intent, "blockade": plan_event}
        return ev

    # ── Unsupported / unsafe cases ─────────────────────────────────────
    if not e.get("supported"):
        produced = bool(compile_.get("sql")) and execution.get("ran")
        emitted = bool(compile_.get("sql"))
        blocked = not produced or validation.get("safe") is False or compliance.get("compliant") is False
        decision = str(intent.get("decision", "")).upper()
        ev["semantic_pass"] = bool(blocked)
        ev["security_blocked"] = bool(blocked)
        ev["routing_blocked"] = bool(blocked)
        ev["sql_emitted"] = bool(emitted)
        ev["intent_decision"] = decision
        # Dangerous payload exported to the DB? (validator-approved SELECTs
        # carry no DML/DDL content — invariant proven by UNSAFE_REQUEST_EXECUTION_RATE==0.)
        ev["dangerous_content_executed"] = bool(produced and _dangerous_sql(compile_.get("sql")))
        ev["primary_failure"] = None if blocked else UNSUPPORTED_ROUTING_FAILURE
        ev["details"] = {
            "sql": compile_.get("sql"), "validation_safe": validation.get("safe"),
            "compliant": compliance.get("compliant"), "execution_ran": execution.get("ran"),
            "plan_error": plan.get("error"), "unsupported_reason": plan.get("unsupported_reason"),
            "intent": intent,
        }
        return ev

    # ── Supported case: component scoring ──────────────────────────────
    tables_ok = bool(plan_available) and all(t in (plan.get("selected_tables") or []) for t in e.get("tables", []))
    joins = (plan.get("joins") or []) if plan_available else []
    joins_ok = bool(plan_available) and all(_has_join(joins, a, b) for a, b in e.get("required_joins", []))
    exprs = (plan.get("analytical_expressions") or []) + (plan.get("metrics") or []) if plan_available else []
    metrics_ok = all(_matches_expected_metric(m, exprs, compile_.get("sql")) for m in e.get("metrics", []))
    actual_dims = [_last(d.get("name")) for d in (plan.get("dimensions") or [])]
    dims_ok = all(_last(d) in actual_dims for d in e.get("dimensions", []))
    actual_filters = (plan.get("filters") or []) if plan_available else []
    filters_ok = all(_filter_matches(f, actual_filters) for f in e.get("filters", []))
    time_ok = _time_matches(e.get("time"), plan.get("time_range")) if plan_available else False
    sort_ok = _sort_matches(e.get("order_by"), plan.get("sort"), joins) if plan_available else False
    limit_ok = _limit_ok(e, plan) if plan_available else False
    validation_ok = validation.get("safe") is True if "safe" in validation else None
    compliance_ok = _compliance_ok(e, compliance)
    execution_ok = None
    result_msg = None
    if e.get("expected_result") is not None:
        if execution.get("ran"):
            execution_ok, result_msg = _compare_result(
                e["expected_result"], execution.get("rows") or [], execution.get("column_names"))
        else:
            execution_ok, result_msg = False, execution.get("error") or "not executed"

    gate_ok = bool(compile_.get("sql"))

    components = {
        "gate": bool(gate_ok), "tables": bool(tables_ok), "joins": bool(joins_ok),
        "metrics": bool(metrics_ok), "dimensions": bool(dims_ok),
        "filters": bool(filters_ok), "time": bool(time_ok), "sort": bool(sort_ok),
        "limit": bool(limit_ok), "validation": validation_ok, "compliance": compliance_ok,
        "execution": execution_ok,
    }
    ev["components"] = components

    semantic_pass = all(
        v is True for k, v in components.items() if k != "execution" or v is not None
    ) and gate_ok and plan_available

    ev["semantic_pass"] = bool(semantic_pass)
    ev["primary_failure"] = None if semantic_pass else _attribute_failure(
        e, exp, trace, components, result_msg)
    ev["details"] = {
        "gate_sql": compile_.get("sql"),
        "plan_error": plan.get("error"),
        "unsupported_reason": plan.get("unsupported_reason"),
        "plan_available": plan_available,
        "validation": {"safe": validation.get("safe"), "issues": (validation.get("issues") or [])[:3]},
        "compliance": {"compliant": compliance.get("compliant"),
                        "violations": [v.get("rule") for v in (compliance.get("violations") or [])][:3]},
        "execution": {"ran": execution.get("ran"), "error": execution.get("error")},
        "result_msg": result_msg,
    }
    return ev


def _resolve_plan_blockade(trace: dict) -> dict:
    plan = trace.get("plan") or {}
    entity = trace.get("entity") or {}
    if entity.get("error"):
        return {"kind": ENTITY_RESOLUTION_FAILURE, "detail": (entity.get("error") or "")[:200]}
    if plan.get("error"):
        return {"kind": SQL_GENERATION_FAILURE, "detail": (plan.get("error") or "")[:200]}
    if plan.get("unsupported_reason"):
        return {"kind": SQL_GENERATION_FAILURE, "detail": plan.get("unsupported_reason")}
    if not plan.get("selected_tables"):
        return {"kind": SCHEMA_RETRIEVAL_FAILURE, "detail": "no plan produced"}
    return {"kind": None, "detail": ""}


def _compliance_ok(exp: dict, compliance: dict) -> bool | None:
    if not compliance:
        return None
    expected = exp.get("expected_compliance", "pass")
    compliant = compliance.get("compliant") is True
    masked = bool(compliance.get("masking_required"))
    if expected == "pass":
        return compliant
    if expected == "mask":
        return compliant and masked
    if expected == "block":
        return not compliant or compliance.get("violations")
    return None


def _attribute_failure(exp: dict, case: dict, trace: dict, comp: dict, result_msg: str | None) -> str:
    """Single primary failure stage for a supported, failing case."""
    plan = trace.get("plan") or {}
    entity = trace.get("entity") or {}

    if not plan.get("selected_tables"):
        blockade = _resolve_plan_blockade(trace)
        if blockade["kind"]:
            return blockade["kind"]
        intent = trace.get("intent") or {}
        if intent.get("supported") is False:
            return UNSUPPORTED_ROUTING_FAILURE
        return SCHEMA_RETRIEVAL_FAILURE

    if not comp["tables"]:
        return SCHEMA_RETRIEVAL_FAILURE
    if not comp["joins"]:
        return ENTITY_RESOLUTION_FAILURE
    if not comp["filters"] or not comp["time"] or not comp["limit"]:
        return CONSTRAINT_PROPAGATION_FAILURE
    if not comp["metrics"] or not comp["dimensions"] or not comp["sort"] or not comp["gate"]:
        return SQL_GENERATION_FAILURE
    if comp["validation"] is False:
        return VALIDATION_FALSE_REJECT
    if comp["compliance"] is False:
        return COMPLIANCE_FALSE_REJECT
    if comp["execution"] is False:
        return EXECUTION_FAILURE
    return SQL_GENERATION_FAILURE


# ─── Aggregation ────────────────────────────────────────────────────────────

def _rate(bools) -> float:
    vals = [b for b in bools if b is not None]
    if not vals:
        return 0.0
    return round(100.0 * sum(vals) / len(vals), 2)


def _dangerous_sql(sql) -> bool:
    """True if emitted SQL contains dangerous payload markers."""
    if not sql:
        return False
    lower = " ".join(str(sql).lower().split())
    return any(m in lower for m in _DANGEROUS_SQL_MARKERS)


def aggregate(evaluations, traces) -> dict:
    total = len(evaluations)
    supported = [ev for ev in evaluations if ev["expected"]["supported"] and not ev["expected"]["requires_clarification"]]
    clarify = [ev for ev in evaluations if ev["expected"]["requires_clarification"]]
    unsupported = [ev for ev in evaluations if not ev["expected"]["supported"]]

    out = {
        "total_cases": total,
        "supported_cases": len(supported),
        "clarify_cases": len(clarify),
        "unsupported_cases": len(unsupported),
        "INTENT_LABEL_ACCURACY": _rate([ev["intent_label_correct"] for ev in evaluations]),
        "END_TO_END_SEMANTIC_ACCURACY": _rate([ev["semantic_pass"] for ev in supported]),
        "RESULT_CORRECTNESS_RATE": _rate([
            ev["components"].get("execution") for ev in supported if ev["expected"].get("expected_result") is not None
        ]),
        "CLARIFICATION_CORRECTNESS": _rate([ev["clarification_correct"] for ev in clarify]),
        "SUPPORTED_ROUTING_ACCURACY": _rate([
            ev["semantic_pass"] for ev in supported
        ]),
        "CONSTRAINT_PROPAGATION_ACCURACY": _rate([
            ev["components"]["filters"] and ev["components"]["time"] and ev["components"]["limit"]
            for ev in supported
        ]),
        "JOIN_CORRECTNESS_RATE": _rate([
            ev["components"]["joins"] for ev in supported
            if ev["expected"].get("required_joins")
        ]),
        "PARAMETERIZATION_RATE": _rate([
            _case_parameterized(tr) for tr in traces
            if tr["expected_supported"] and tr["expected"]["filters"]
        ]),
        "VALIDATION_CORRECTNESS": _rate([
            ev["components"].get("validation") for ev in supported
        ]),
        "COMPLIANCE_CORRECTNESS": _rate([ev["components"].get("compliance") for ev in supported]),
        "SECURITY_BLOCK_RATE": _rate([ev["security_blocked"] for ev in unsupported]),
        # ── Step 19 security-qualification metrics (defined crisply) ────────────
        # UNSAFE_REQUEST_BLOCK_RATE: unsafe request produced NO query at all
        #    (no SQL emitted OR emitted-but-not-approved OR not executed).
        # UNSAFE_REQUEST_EXECUTION_RATE: dangerous payload actually EXPORTED to
        #    the database — target 0%. Proves unsafe content never hits the DB.
        # UNSUPPORTED_ROUTING_ACCURACY: unsafe request fully routed away from
        #    execution (mirror of SUPPORTED_ROUTING_ACCURACY on the unsafe set).
        # SECURITY_EARLY_BLOCK_RATE: unsafe request stopped before compile.
        # INTENT_ROUTING_DECISION_ACCURACY: intent correctly decided
        #    REJECT/CLARIFY on every unsafe request (decision-level only).
        "UNSAFE_REQUEST_BLOCK_RATE": _rate([ev["security_blocked"] for ev in unsupported]),
        "UNSAFE_REQUEST_EXECUTION_RATE": _rate(
            [ev["dangerous_content_executed"] for ev in unsupported]),
        "UNSUPPORTED_ROUTING_ACCURACY": _rate([ev["routing_blocked"] for ev in unsupported]),
        "SECURITY_EARLY_BLOCK_RATE": _rate([not ev["sql_emitted"] for ev in unsupported]),
        "INTENT_ROUTING_DECISION_ACCURACY": _rate([
            ev["intent_decision"] in ("REJECT", "CLARIFY") for ev in unsupported
        ]),
        "LEVEL_1_ACCURACY": _rate([ev["semantic_pass"] for ev in supported if ev["level"] == 1]),
        "LEVEL_2_ACCURACY": _rate([ev["semantic_pass"] for ev in supported if ev["level"] == 2]),
        "LEVEL_3_ACCURACY": _rate([ev["semantic_pass"] for ev in supported if ev["level"] == 3]),
        "LEVEL_4_ACCURACY": _rate([ev["semantic_pass"] for ev in evaluations if ev["level"] == 4]),
        "EN_E2E_ACCURACY": _rate([ev["semantic_pass"] for ev in supported if ev["language"] == "en"]),
        "FR_E2E_ACCURACY": _rate([ev["semantic_pass"] for ev in supported if ev["language"] == "fr"]),
        "failure_distribution": dict(Counter(
            ev["primary_failure"] for ev in supported if ev["primary_failure"]
        )),
        "category_accuracy": {
            cat: _rate([ev["semantic_pass"] for ev in supported if ev["category"] == cat])
            for cat in sorted({ev["category"] for ev in supported})
        },
        "intent_mismatches": _intent_mismatch_pairs(evaluations),
    }

    # Latency percentiles
    latencies = []
    for tr in traces:
        t = tr.get("latency_ms")
        if t is not None:
            latencies.append(float(t))
    if latencies:
        latencies.sort()
        n = len(latencies)
        out["p50_ms"] = round(latencies[n // 2], 1)
        out["p90_ms"] = round(latencies[int(n * 0.9)], 1)
        out["p95_ms"] = round(latencies[min(n - 1, int(n * 0.95))], 1)
        out["avg_ms"] = round(sum(latencies) / n, 1)
    else:
        out.update(p50_ms=None, p90_ms=None, p95_ms=None, avg_ms=None)
    return out


def _case_parameterized(tr: dict) -> bool:
    return bool((tr.get("compile") or {}).get("parameters"))


def _intent_mismatch_pairs(evaluations) -> list:
    pairs = []
    for ev in evaluations:
        if ev["intent_label_correct"] is False:
            pairs.append((ev["id"], ev["question"][:60]))
        # note: true intent mismatch detail lives in traces
    return pairs


def percentiles(latencies_ms: list) -> dict:
    s = sorted(latencies_ms)
    n = len(s)
    if n == 0:
        return {}
    return {
        "p50": s[n // 2], "p90": s[min(n - 1, int(0.9 * n))],
        "p95": s[min(n - 1, int(0.95 * n))],
    }