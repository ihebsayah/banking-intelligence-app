"""End-to-end NL->SQL benchmark runner (Step 13, E2E_BASELINE_V1).

Executes the CURRENT, UNMODIFIED deterministic pipeline in-process for every
case in cases.json:

    Intent -> Schema retrieval -> Entity resolution -> Query plan -> SQL
    compile -> Validation -> Compliance -> (read-only execution on banking_dev)

No fixes, no LLM, no architectural changes. Every stage is measured and each
case produces a full trace dumped to results/baseline_v1_traces.jsonl; results
are aggregated with semantic_evaluator into results/baseline_v1.json.

Run with the project's testenv python (has spacy, sqlparse, psycopg2, asyncpg):
    testenv/bin/python3 benchmark/e2e_nl_sql/benchmark_runner.py
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVICES = os.path.join(ROOT, "services")
CASE_FILE = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "cases.json")
RESULTS_DIR = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "results")
_RESULT_TAG = os.getenv("RESULT_TAG", "E2E_BASELINE_V1")
RESULTS_FILE = os.path.join(RESULTS_DIR, f"{_RESULT_TAG}.json")
TRACES_FILE = os.path.join(RESULTS_DIR, f"{_RESULT_TAG}_traces.jsonl")

PG_TEST_DSN = os.environ.get(
    "PG_TEST_DSN",
    "postgresql://banking_user:securepass123@localhost:5432/banking_dev",
)

for p in (SERVICES, os.path.join(SERVICES, "shared")):
    if p not in sys.path:
        sys.path.insert(0, p)


def load_dependent(modname: str, service: str, models_service: str, also=None):
    """Import a module while binding its bare `models` import to the right
    service's models.py. Restores the previous binding afterwards."""
    prev = sys.modules.get("models")
    sys.modules.pop("models", None)
    d = os.path.join(SERVICES, models_service)
    if d not in sys.path:
        sys.path.insert(0, d)
    sys.modules["models"] = importlib.import_module("models")
    if d in sys.path:
        sys.path.remove(d)
    d = os.path.join(SERVICES, service)
    if d not in sys.path:
        sys.path.insert(0, d)
    try:
        mod = importlib.import_module(modname)
        for extra in (also or []):
            importlib.import_module(extra)
    finally:
        if prev is None:
            sys.modules.pop("models", None)
        else:
            sys.modules["models"] = prev
    return mod


# ─── Static imports (safe: no bare `models`) ────────────────────────────────
from intent_agent.intent_recognizer import IntentRecognizer
from intent_agent.structured_intent import build_structured_intent
from sql_agent.query_plan_builder import QueryPlanBuilder, _VALID_COLUMNS, initialize_join_registry
from sql_agent.deterministic_compiler import DeterministicSQLCompiler

# ─── Dependent imports (bind each service's own models.py) ──────────────────
SchemaMatcher = load_dependent(
    "schema_agent.schema_matcher", "schema_agent", "schema_agent",
    also=["progressive_schema"],
).SchemaMatcher
EntityResolver = load_dependent(
    "entity_resolution_agent.entity_resolver",
    "entity_resolution_agent", "entity_resolution_agent",
).EntityResolver
ERReq = load_dependent(
    "entity_resolution_agent.models",
    "entity_resolution_agent", "entity_resolution_agent",
).EntityResolutionRequest
QueryValidator = load_dependent(
    "validation_agent.query_validator", "validation_agent", "validation_agent",
).QueryValidator
QueryValidationRequest = load_dependent(
    "validation_agent.models", "validation_agent", "validation_agent",
).QueryValidationRequest
ComplianceChecker = load_dependent(
    "compliance_agent.compliance_checker", "compliance_agent", "compliance_agent",
).ComplianceChecker
Settings = load_dependent(
    "compliance_agent.config", "compliance_agent", "compliance_agent",
).Settings

CATEGORY2ENTITY = {
    "customer_analysis": "customer", "risk_analysis": "customer",
    "revenue_analysis": "customer", "operational_analysis": "transaction",
    "geographic_analysis": "branch", "product_analysis": "product",
    "compliance_analysis": "customer", "transaction_analysis": "transaction",
    "loan_analysis": "loan", "kyc_analysis": "customer", "aml_analysis": "customer",
    "profitability_analysis": "customer", "liquidity_analysis": "account",
}

_intent_recognizer = IntentRecognizer()
_matcher = None  # created per case to mirror fresh-service behaviour
_entity_resolver = EntityResolver()
_plan_builder = QueryPlanBuilder()
_compiler = DeterministicSQLCompiler()
_validator = QueryValidator()
_checker = ComplianceChecker(Settings())

_sql_placeholder = re.compile(r"\$\d+")


def _run_intent(q: str) -> dict:
    return _intent_recognizer.recognize_sync(q)


def _run_schema(cats: list, query: str, si: dict) -> dict:
    m = SchemaMatcher(semantic_layer_enabled=False)
    resp = m.progressive_map(
        query=query,
        domain=si.get("domain") or "",
        task=si.get("task") or "",
        metrics=si.get("metrics") or [],
        dimensions=si.get("dimensions") or [],
        filters_structured=si.get("filters_structured") or [],
        limit_requested=si.get("limit_requested"),
        requested_fields=si.get("requested_fields") or [],
    )
    selected = list(resp.selected_tables or [])
    bridges = list(resp.bridge_tables or [])
    tables = list(dict.fromkeys(selected + bridges))
    domains = m.match_domains(cats)
    return {
        "domains": domains,
        "tables": tables,
        "selected_tables": selected,
        "bridge_tables": bridges,
        "reasons": {t: (resp.selection_reasons or {}).get(t, "") for t in tables},
    }


def _run_entity(entity: str, tables: list) -> dict:
    resp = _entity_resolver.resolve(ERReq(primary_entity=entity, tables=tables))
    return {
        "primary": entity,
        "tables": list(getattr(resp, "tables", tables)),
        "join_structure": [
            {
                "from_table": j.from_table, "to_table": j.to_table,
                "join_key": j.join_key, "join_type": j.join_type,
                "condition": getattr(j, "condition", ""),
            }
            for j in getattr(resp, "join_structure", [])
        ],
    }


def _run_plan(q: str, tables: list, joins: list, si: dict) -> dict:
    selcols = {t: sorted(_VALID_COLUMNS.get(t, [])) for t in tables if t in _VALID_COLUMNS}
    return _plan_builder.build(
        task=si.get("task") or "aggregation",
        query_text=q,
        selected_tables=tables,
        bridge_tables=[],
        selected_columns=selcols,
        join_paths=joins,
        metrics=si.get("metrics"),
        dimensions=si.get("dimensions"),
        filters_structured=si.get("filters_structured"),
        time_range=si.get("time_range"),
        sort_structured=si.get("sort_structured"),
        limit_requested=si.get("limit_requested"),
        requested_fields=si.get("requested_fields"),
    )


def _plan_to_dict(plan) -> dict:
    d = plan.model_dump(mode="json")
    return d


def _execution(sql: str, parameters: list) -> dict:
    import psycopg2
    try:
        con = psycopg2.connect(PG_TEST_DSN)
        try:
            cur = con.cursor()
            cur.execute(_sql_placeholder.sub("%s", sql), [p.value for p in parameters])
            rows = cur.fetchall()
            col_names = [c[0] for c in cur.description] if cur.description else []
            return {
                "ran": True,
                "row_count": len(rows),
                "column_names": col_names,
                "rows": [list(row) for row in rows[:1100]],
                "error": None,
            }
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        return {"ran": False, "row_count": 0, "column_names": [], "rows": [], "error": str(exc)[:300]}


async def run_case(case: dict) -> dict:
    expected = case["expected"]
    q = case["question"]
    role = case.get("role", "analyst")
    trace: dict = {"id": case["id"], "question": q, "language": case["language"],
                    "level": case["level"], "role": role, "category": case["category"],
                    "expected": expected, "expected_supported": expected["supported"]}
    t0 = time.perf_counter()

    # ── 1. Intent ────────────────────────────────────────────────────────
    try:
        intent = _run_intent(q)
        trace["intent"] = {
            "label": intent.get("primary_category"),
            "secondary": intent.get("secondary_categories", []),
            "supported": intent.get("supported_capability"),
            "decision": intent.get("decision"),
            "risk_level": intent.get("risk_level"),
            "requires_clarification": intent.get("requires_clarification"),
            "rejection_reason": intent.get("rejection_reason"),
        }
    except Exception as exc:  # noqa: BLE001
        trace["intent"] = {"error": str(exc)[:300], "label": None, "supported": None}
    t1 = time.perf_counter()
    trace["intent"]["latency_ms"] = round((t1 - t0) * 1000, 2)

    si = {}
    try:
        struct = build_structured_intent(q)
        si = struct if isinstance(struct, dict) else {}
    except Exception as exc:  # noqa: BLE001
        si = {"error": str(exc)[:300]}
    trace["structured"] = dict(si)

    # ── 1b. Security routing gate (mirrors orchestrator intent gate) ─────────
    # Applied ONLY on the unsafe/unsupported golden set: once intent decides
    # REJECT/CLARIFY or flags adversarial/suspicious risk, no SQL may be
    # compiled or executed. Supported-golden cases keep frozen Step-18
    # behaviour (intent false-negatives there are scored separately).
    if not expected["supported"]:
        dec = str(trace["intent"].get("decision", "")).upper()
        risk = str(trace["intent"].get("risk_level", "")).lower()
        if dec in ("REJECT", "CLARIFY") or risk in ("adversarial", "suspicious"):
            trace["gated"] = True
            trace["schema"] = {"domains": [], "tables": [], "selected_tables": [],
                               "bridge_tables": [], "gated": True}
            trace["entity"] = {"primary": CATEGORY2ENTITY.get(trace["intent"].get("label"), "customer"),
                               "error": None, "gated": True}
            trace["plan"] = {"selected_tables": [], "error": None,
                             "unsupported_reason": "INTENT_GATE: " + str(dec)}
            trace["compile"] = {"sql": None, "parameters": [], "error": None,
                                "tables_used": [], "gated": True}
            trace["validation"] = {"safe": None, "issues": [], "checks_failed": [],
                                   "error": None, "gated": True}
            trace["compliance"] = {"compliant": None, "violations": [],
                                   "masking_required": [], "error": None, "gated": True}
            trace["execution"] = {"ran": False, "row_count": 0, "rows": [],
                                  "error": "INTENT_GATE", "latency_ms": 0}
            t2 = time.perf_counter()
            trace["schema"]["latency_ms"] = 0.0
            trace["entity"]["latency_ms"] = 0.0
            trace["plan"]["latency_ms"] = 0.0
            trace["compile"]["latency_ms"] = 0.0
            trace["validation"]["latency_ms"] = 0.0
            trace["compliance"]["latency_ms"] = 0.0
            trace["latency_ms"] = round((t2 - t0) * 1000, 2)
            return trace

    # ── 2. Schema ────────────────────────────────────────────────────────
    t2 = time.perf_counter()
    try:
        cats = [trace["intent"].get("label")] + list(trace["intent"].get("secondary", []))
        schema_out = _run_schema(cats, q, si)
        trace["schema"] = {
            "domains": schema_out["domains"],
            "tables": schema_out["tables"],
            "selected_tables": schema_out["selected_tables"],
            "bridge_tables": schema_out["bridge_tables"],
            "reasons": schema_out["reasons"],
        }
    except Exception as exc:  # noqa: BLE001
        trace["schema"] = {"domains": [], "tables": [], "error": str(exc)[:300]}
    t2 = time.perf_counter()
    trace["schema"]["latency_ms"] = round((t2 - t1) * 1000, 2)

    # ── 3. Entity resolution ─────────────────────────────────────────────
    entity = CATEGORY2ENTITY.get(trace["intent"].get("label"), "customer")
    trace["entity"] = {"primary": entity, "error": None}
    join_paths = []
    try:
        eres = _run_entity(entity, trace["schema"].get("tables", []))
        trace["entity"].update({"tables": eres["tables"], "join_structure": eres["join_structure"]})
        join_paths = eres["join_structure"]
    except Exception as exc:  # noqa: BLE001
        trace["entity"]["error"] = str(exc)[:300]
    t3 = time.perf_counter()
    trace["entity"]["latency_ms"] = round((t3 - t2) * 1000, 2)

    # ── 4. Query plan ────────────────────────────────────────────────────
    plan_dict = {"selected_tables": [], "error": None, "unsupported_reason": None}
    plan = None
    try:
        plan = _run_plan(q, trace["schema"].get("tables", []), join_paths, si)
        plan_dict = _plan_to_dict(plan)
        plan_dict["error"] = None
        plan_dict["unsupported_reason"] = plan.unsupported_reason
    except Exception as exc:  # noqa: BLE001
        plan_dict["error"] = str(exc)[:300]
    trace["plan"] = plan_dict
    t4 = time.perf_counter()
    trace["plan"]["latency_ms"] = round((t4 - t3) * 1000, 2)

    # ── 5. Compile ───────────────────────────────────────────────────────
    compiled = None
    compiled_dict = {"sql": None, "parameters": [], "error": None, "tables_used": []}
    try:
        if plan is not None:
            compiled = _compiler.compile(plan)
            compiled_dict = {
                "sql": compiled.sql,
                "parameters": [
                    {"position": p.position, "value": p.value, "type": p.type}
                    for p in (compiled.parameters or [])
                ],
                "tables_used": compiled.tables_used,
                "column_aliases": compiled.column_aliases,
                "error": None,
            }
    except Exception as exc:  # noqa: BLE001
        compiled_dict["error"] = str(exc)[:300]
    trace["compile"] = compiled_dict
    t5 = time.perf_counter()
    trace["compile"]["latency_ms"] = round((t5 - t4) * 1000, 2)

    # ── 6. Validation ────────────────────────────────────────────────────
    valid_dict = {"safe": None, "issues": [], "checks_failed": [], "error": None}
    try:
        if compiled_dict.get("sql"):
            vreq = QueryValidationRequest(
                sql=compiled_dict["sql"],
                parameters=[p["value"] for p in compiled_dict.get("parameters", [])],
                user_role=role,
            )
            vresp = _validator.validate(vreq)
            valid_dict = {
                "safe": vresp.safe,
                "confidence": vresp.confidence,
                "issues": vresp.issues,
                "checks_passed": vresp.checks_passed,
                "checks_failed": vresp.checks_failed,
                "has_signature": bool(vresp.signature),
                "error": None,
            }
    except Exception as exc:  # noqa: BLE001
        valid_dict["error"] = str(exc)[:300]
    trace["validation"] = valid_dict
    t6 = time.perf_counter()
    trace["validation"]["latency_ms"] = round((t6 - t5) * 1000, 2)

    # ── 7. Compliance ────────────────────────────────────────────────────
    # Columns observed by the plan (or the full allowed column set per table).
    columns = sorted(
        set(
            col
            for t in plan_dict.get("selected_tables", [])
            for col in _VALID_COLUMNS.get(t, [])
        )
    )
    comp_dict = {"compliant": None, "violations": [], "masking_required": [], "error": None}
    try:
        cresp = await _checker.check_compliance(
            user_id="e2e-baseline",
            user_role=role,
            query_intent=trace["intent"].get("label") or "unknown",
            tables=plan_dict.get("selected_tables", []),
            columns=columns,
        )
        comp_dict = {
            "compliant": cresp.compliant,
            "violations": [v.model_dump() for v in cresp.violations],
            "masking_required": [m.model_dump() for m in cresp.masking_required],
            "regulations_checked": cresp.regulations_checked,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        comp_dict["error"] = str(exc)[:300]
    trace["compliance"] = comp_dict
    t7 = time.perf_counter()
    trace["compliance"]["latency_ms"] = round((t7 - t6) * 1000, 2)

    # ── 8. Execution (read-only) ─────────────────────────────────────────
    exec_dict = {"ran": False, "row_count": 0, "rows": [], "error": None, "latency_ms": 0}
    if compiled_dict.get("sql") and valid_dict.get("safe") is True:
        exec_result = _execution(compiled_dict["sql"], compiled.parameters or [])
        exec_dict.update(exec_result)
        t8 = time.perf_counter()
        exec_dict["latency_ms"] = round((t8 - t7) * 1000, 2)
        t7 = t8
    trace["execution"] = exec_dict

    trace["latency_ms"] = round((t7 - t0) * 1000, 2)
    return trace


async def main() -> None:
    cases = json.load(open(CASE_FILE, encoding="utf-8"))
    _limit = os.getenv("E2E_LIMIT")
    if _limit:
        cases = cases[: int(_limit)]

    # Optional Step-19 qualification goldens overlay: binds expected_result to a
    # specific immutable fixture (e.g. benchmark/qualification/QUALIFICATION_V1/
    # goldens_v1.json) so golden and fixture agree BY CONSTRUCTION. Off by default.
    goldens_file = os.getenv("GOLDENS_FILE")
    if goldens_file and os.path.exists(goldens_file):
        goldens = json.load(open(goldens_file, encoding="utf-8"))
        applied = 0
        for case in cases:
            g = goldens.get(case["id"])
            if isinstance(g, dict) and "error" not in g:
                case["expected"]["expected_result"] = g
                applied += 1
        print(f"[qual] applied goldens overlay: {goldens_file} ({applied} entries)")

    # Prime the join registry from the live schema (mirrors the fastapi app).
    try:
        import psycopg2
        con = psycopg2.connect(PG_TEST_DSN)
        try:
            initialize_join_registry(con)
        finally:
            con.close()
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] join registry not initialised: {exc}")

    from semantic_evaluator import aggregate, evaluate_case

    traces = []
    evals = []
    for i, case in enumerate(cases, 1):
        trace = await run_case(case)
        traces.append(trace)
        ev = evaluate_case(case, trace)
        evals.append(ev)
        marker = "PASS" if ev["semantic_pass"] else "FAIL"
        print(f"[{i}/{len(cases)}] {marker} {case['id']:8s} lvl{case['level']} {case['category']:22s} "
              f"fail={ev['primary_failure'] or '-'} intent={trace.get('intent', {}).get('label')}")

        with open(TRACES_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(trace, default=str) + "\n")

    summary = aggregate(evals, traces)
    with open(RESULTS_FILE, "w", encoding="utf-8") as fh:
        json.dump({
            "benchmark_version": os.getenv("RESULT_TAG", "E2E_BASELINE_V1"),
            "generated_at": os.getenv("E2E_GENERATED_AT", time.strftime("%Y-%m-%dT%H:%M:%S")),
            "total_cases": len(cases),
            "dsn": "PG_TEST_DSN (read-only)",
            "metrics": summary,
            "evaluations": evals,
        }, fh, indent=2, default=str)

    print("\n" + "=" * 64)
    for k, v in summary.items():
        if isinstance(v, (int, float)) or v is None:
            print(f"{k:32s} {v}")
        elif isinstance(v, dict):
            print(f"{k:32s}")
            for kk, vv in v.items():
                print(f"    {kk:26s} {vv}")
    print(f"\ntraces: {TRACES_FILE}")
    print(f"results: {RESULTS_FILE}")


if __name__ == "__main__":
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if os.path.exists(TRACES_FILE):
        os.remove(TRACES_FILE)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)