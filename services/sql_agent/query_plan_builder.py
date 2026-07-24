"""
services/sql_agent/query_plan_builder.py
Deterministic QueryPlan construction from structured intent + schema selection.

Increment 2.6: Entity-aware counting (COUNT DISTINCT on identity columns when
joins present), conditional aggregation (CaseExpression for boolean columns),
fan-out detection, grain tracking, RatioExpression aggregation strategy,
expanded ExpectedAnswer types.

No LLM calls. Purely rule-based validation and plan assembly.
Fails safely on: unresolved fields, unsupported grain, missing capability,
no join path, version mismatch, unknown metrics, fan-out risk.
"""
import logging
import os
import re
from collections import deque
from typing import Dict, List, Optional, Set, Tuple, Any

from sql_agent.plan_models import (
    QueryPlan, ColumnRef, JoinSpec, JoinCardinality, MetricReference,
    FilterSpec, TimeRangeSpec, SortSpec, ExpectedAnswer, GrainSpec,
    AggregateExpression, RatioExpression, CaseExpression, AnalyticalExpression,
    MetricExecutionStrategy,
)

logger = logging.getLogger(__name__)


# ─── Join graph cache (loaded once from join_registry) ────────────────────────
# ponytail: mirrors entity_resolver pattern — load once, BFS many times
_join_graph: Dict[str, List[dict]] = {}
_join_graph_ready: bool = False

SENSITIVE_LOG_TABLES = {
    "audit_log", "user_activity_log", "compliance_events", "compliance_rules",
    "compliance_violations", "compliance_cases", "compliance_reviews", "regulatory_reports",
}


def initialize_join_registry(db_conn) -> None:
    """Load join_registry into memory for BFS join resolution. Idempotent."""
    global _join_graph, _join_graph_ready
    if _join_graph_ready:
        return
    try:
        with db_conn.cursor() as cur:
            cur.execute("SELECT * FROM join_registry")
            colnames = [desc[0].lower() for desc in cur.description]
            src_idx = colnames.index("source_table")
            src_col_idx = colnames.index("source_column")
            tgt_idx = colnames.index("target_table")
            tgt_col_idx = colnames.index("target_column")
            jtype_idx = colnames.index("join_type") if "join_type" in colnames else -1
            conf_idx = colnames.index("confidence") if "confidence" in colnames else -1
            bidir_idx = colnames.index("is_bidirectional") if "is_bidirectional" in colnames else -1

            graph: Dict[str, List[dict]] = {}
            for row in cur.fetchall():
                from_t = row[src_idx].lower()
                key = row[src_col_idx]
                to_t = row[tgt_idx].lower()
                target_col = row[tgt_col_idx]
                if conf_idx != -1 and row[conf_idx] is not None and float(row[conf_idx]) < 0.8:
                    continue
                jtype = row[jtype_idx] if jtype_idx != -1 and row[jtype_idx] else "LEFT JOIN"
                cond = f"{from_t}.{key} = {to_t}.{target_col}"
                is_bidirectional = True
                if bidir_idx != -1 and row[bidir_idx] is not None:
                    is_bidirectional = bool(row[bidir_idx])
                if from_t in SENSITIVE_LOG_TABLES or to_t in SENSITIVE_LOG_TABLES:
                    is_bidirectional = False
                graph.setdefault(from_t, []).append(
                    {"to_table": to_t, "join_key": key, "condition": cond, "join_type": jtype}
                )
                if is_bidirectional:
                    rev_cond = f"{to_t}.{target_col} = {from_t}.{key}"
                    graph.setdefault(to_t, []).append(
                        {"to_table": from_t, "join_key": target_col, "condition": rev_cond, "join_type": jtype}
                    )
            _join_graph = graph
        _join_graph_ready = bool(_join_graph)
        if _join_graph_ready:
            logger.info("[QueryPlanBuilder] Join registry loaded: %d graph nodes", len(_join_graph))
    except Exception as exc:
        logger.warning("[QueryPlanBuilder] Join registry init failed: %s", exc)
        _join_graph_ready = False


def _bfs_join_path(start: str, end: str) -> Optional[List[dict]]:
    """BFS over _join_graph to find shortest join path. Returns list of edge dicts or None."""
    if start == end:
        return []
    visited = {start}
    queue: deque = deque([(start, [])])
    while queue:
        node, path = queue.popleft()
        if len(path) >= 3:
            continue
        for edge in _join_graph.get(node, []):
            nxt = edge["to_table"]
            if nxt in visited:
                continue
            step = {**edge, "from_table": node}
            new_path = path + [step]
            if nxt == end:
                return new_path
            visited.add(nxt)
            queue.append((nxt, new_path))
    return None


def _auto_resolve_joins(tables: List[str]) -> List[dict]:
    """Resolve join paths between multiple tables via BFS over join_registry.
    Sorts tables so BFS primary matches compiler's FROM primary."""
    if len(tables) < 2 or not _join_graph_ready:
        return []
    sorted_tables = sorted(tables)
    primary = sorted_tables[0]
    join_paths: List[dict] = []
    joined = {primary}
    for target in sorted_tables[1:]:
        if target in joined:
            continue
        path = _bfs_join_path_excluding(primary, target, joined)
        if path is None:
            logger.warning("[QueryPlanBuilder] No join path: %s → %s", primary, target)
            continue
        for step in path:
            join_paths.append(step)
            joined.add(step["to_table"])
    return join_paths


def _bfs_join_path_excluding(start: str, end: str, exclude: Set[str]) -> Optional[List[dict]]:
    """BFS that avoids already-joined tables as intermediate hops."""
    if start == end:
        return []
    visited = {start} | exclude
    queue: deque = deque([(start, [])])
    while queue:
        node, path = queue.popleft()
        if len(path) >= 3:
            continue
        for edge in _join_graph.get(node, []):
            nxt = edge["to_table"]
            if nxt in visited and nxt != end:
                continue
            step = {**edge, "from_table": node}
            new_path = path + [step]
            if nxt == end:
                return new_path
            visited.add(nxt)
            queue.append((nxt, new_path))
    return None


# ─── Approved metric formulas (static registry) ──────────────────────────────

APPROVED_METRICS: Dict[str, Dict[str, Any]] = {
    "npl_ratio": {
        "formula": "ROUND(100.0 * COUNT(CASE WHEN lp.status = 'non_performing' THEN 1 END) / NULLIF(COUNT(*), 0), 2)",
        "alias": "npl_ratio",
        "source_tables": ["loan_contracts", "non_performing_loans"],
        "grains": {"scalar"},
        "execution_strategy": {
            "execution_strategy": "independent_subqueries",
            "fan_out_safe": True,
            "preaggregation_required": True,
            "allowed_join_patterns": ["many_to_one"],
        },
        "population": {
            "numerator": "COUNT(DISTINCT n.loan_id) from non_performing_loans WHERE created_at <= reporting_date",
            "denominator": "COUNT(DISTINCT lc.loan_id) from loan_contracts WHERE created_at <= reporting_date",
            "governed_loan_identity": "loan_id (non_performing_loans.loan_id → loan_contracts.loan_id)",
            "numerator_uniqueness": "DISTINCT — one NPL row per loan_id even with historical classification changes",
            "denominator_inclusion": "All governed loan_contracts as of reporting date (active, rembourse, contentieux)",
            "current_state_vs_historical": "Numerator: distinct loans classified NPL as of reporting date. "
                                           "Denominator: distinct loans in governed population as of same reporting date. "
                                           "Both use the same as-of cutoff; not a period flow metric.",
            "reporting_date_alignment": "Both numerator and denominator use created_at as the synthetic benchmark "
                                        "reporting timestamp (live schema has no classification_date/effective_date)",
            "definition": "count-based as-of (COUNT DISTINCT NPL loan_id as-of date / COUNT DISTINCT governed loan_id as-of date)",
            "currency_invariant": True,
            "schema_column_mapping": "created_at → synthetic classification/effective reporting timestamp "
                                     "(live schema: non_performing_loans.created_at, loan_contracts.created_at)",
        },
        "temporal_policy": {
            "allowed_time_ranges": ["last_30_days", "last_90_days", "last_quarter", "last_year", "ytd"],
            "default_time_range": "last_quarter",
            "numerator_business_date": "non_performing_loans.created_at",
            "denominator_business_date": "loan_contracts.created_at",
            "as_of_semantics": "Both numerator and denominator use created_at as the synthetic benchmark "
                               "reporting timestamp; live schema has no dedicated classification_date or "
                               "effective_date columns — not a period-flow metric, measures stock",
            "timezone": "UTC (all timestamps stored as UTC in PostgreSQL)",
        },
    },
    "roe": {
        "formula": "ROUND(100.0 * ins.net_income / NULLIF(bss.total_equity, 0), 2)",
        "alias": "roe",
        "source_tables": ["income_statement_snapshots", "balance_sheet_snapshots"],
        "grains": {"scalar"},
        "execution_strategy": {
            "execution_strategy": "independent_subqueries",
            "fan_out_safe": True,
            "preaggregation_required": True,
            "allowed_join_patterns": ["many_to_one"],
        },
        "population": {
            "numerator": "net_income from income_statement_snapshots",
            "denominator": "total_equity from balance_sheet_snapshots",
            "description": "Return on equity: net income divided by shareholders equity",
            "temporal_source": "income_statement_snapshots.period, balance_sheet_snapshots.period",
        },
        "temporal_policy": {
            "allowed_time_ranges": ["last_quarter", "last_year", "ytd"],
            "default_time_range": "last_year",
            "note": "Requires matching reporting periods across numerator and denominator.",
        },
    },
    "roa": {
        "formula": "ROUND(100.0 * ins.net_income / NULLIF(bss.total_assets, 0), 2)",
        "alias": "roa",
        "source_tables": ["income_statement_snapshots", "balance_sheet_snapshots"],
        "grains": {"scalar"},
        "execution_strategy": {
            "execution_strategy": "independent_subqueries",
            "fan_out_safe": True,
            "preaggregation_required": True,
            "allowed_join_patterns": ["many_to_one"],
        },
        "population": {
            "numerator": "net_income from income_statement_snapshots",
            "denominator": "total_assets from balance_sheet_snapshots",
            "description": "Return on assets: net income divided by total assets",
            "temporal_source": "income_statement_snapshots.period, balance_sheet_snapshots.period",
        },
        "temporal_policy": {
            "allowed_time_ranges": ["last_quarter", "last_year", "ytd"],
            "default_time_range": "last_year",
            "note": "Requires matching reporting periods across numerator and denominator.",
        },
    },
    "kyc_compliance_rate": {
        "formula": "ROUND(100.0 * COUNT(CASE WHEN c.kyc_verified = true THEN 1 END) / NULLIF(COUNT(*), 0), 2)",
        "alias": "kyc_compliance_rate",
        "source_tables": ["customers"],
        "grains": {"branch", "governorate", "region", "segment", "time"},
        "execution_strategy": {
            "execution_strategy": "single_query",
            "fan_out_safe": True,
            "preaggregation_required": False,
            "allowed_join_patterns": ["many_to_one"],
        },
    },
    "aml_alert_rate": {
        "formula": "ROUND(100.0 * COUNT(aa.alert_id) / NULLIF(COUNT(DISTINCT c.customer_id), 0), 2)",
        "alias": "aml_alert_rate",
        "source_tables": ["aml_alerts", "customers"],
        "grains": {"branch", "governorate", "region", "time"},
        "execution_strategy": {
            "execution_strategy": "single_query",
            "fan_out_safe": True,
            "preaggregation_required": False,
            "allowed_join_patterns": ["many_to_one"],
        },
    },
    "loan_to_deposit": {
        "formula": "ROUND(SUM(CASE WHEN lc.loan_id IS NOT NULL THEN lc.principal_amount ELSE 0 END) / NULLIF(SUM(a.balance), 0), 4)",
        "alias": "loan_to_deposit",
        "source_tables": ["loan_contracts", "accounts"],
        "grains": {"scalar"},
        "execution_strategy": {
            "execution_strategy": "independent_subqueries",
            "fan_out_safe": True,
            "preaggregation_required": True,
            "allowed_join_patterns": [],
        },
        "population": {
            "numerator": "SUM(lc.principal_amount) from loan_contracts WHERE currency = 'TND'",
            "denominator": "SUM(a.balance) from accounts WHERE currency = 'TND'",
            "reporting_currency": "TND",
            "currency_enforcement": "Hardcoded WHERE currency = 'TND' in both subqueries; "
                                    "requests with mixed or non-TND currencies are rejected at SQL level",
            "temporal_source_numerator": "loan_contracts.created_at",
            "temporal_source_denominator": "accounts.created_at",
        },
        "temporal_policy": {
            "allowed_time_ranges": ["last_30_days", "last_90_days", "last_quarter", "last_year", "ytd"],
            "default_time_range": "last_quarter",
            "numerator_business_date": "loan_contracts.created_at",
            "denominator_business_date": "accounts.created_at",
            "as_of_semantics": "Both numerator and denominator use independent temporal windows; "
                               "mismatched windows produce meaningless ratios",
            "timezone": "UTC (all timestamps stored as UTC in PostgreSQL)",
        },
    },
    "pnb": {
        "formula": "COALESCE(ins.fee_income, 0) + COALESCE(ins.interest_income, 0) - COALESCE(ins.operating_expenses, 0)",
        "alias": "pnb",
        "source_tables": ["income_statement_snapshots", "fee_income", "interest_income"],
        "grains": {"time"},
    },
    "provision_coverage": {
        "formula": "ROUND(100.0 * SUM(p.provision_amount) / NULLIF(SUM(npl.npl_amount), 0), 2)",
        "alias": "provision_coverage",
        "source_tables": ["provisions", "non_performing_loans"],
        "grains": {"branch", "time"},
    },
    "cost_income_ratio": {
        "formula": "ROUND(100.0 * ins.operating_expenses / NULLIF(ins.fee_income + ins.interest_income, 0), 2)",
        "alias": "cost_income_ratio",
        "source_tables": ["income_statement_snapshots"],
        "grains": {"time"},
    },
    "avg_loan_size": {
        "formula": "ROUND(AVG(lc.principal_amount), 2)",
        "alias": "avg_loan_size",
        "source_tables": ["loan_contracts"],
        "grains": {"branch", "governorate", "time"},
    },
    "default_rate": {
        "formula": "ROUND(100.0 * COUNT(CASE WHEN lc.status = 'default' THEN 1 END) / NULLIF(COUNT(*), 0), 2)",
        "alias": "default_rate",
        "source_tables": ["loan_contracts"],
        "grains": {"branch", "governorate", "time"},
    },
    "total_risk_exposure": {
        "formula": "COUNT(rf.flag_id)",
        "alias": "total_risk_exposure",
        "source_tables": ["risk_flags"],
        "grains": {"branch", "governorate", "time"},
    },
    "customer_growth_rate": {
        "formula": "ROUND(100.0 * (COUNT(CASE WHEN c.onboarding_date >= (CURRENT_DATE - INTERVAL '1 year') THEN 1 END)) / NULLIF(COUNT(*), 0), 2)",
        "alias": "customer_growth_rate",
        "source_tables": ["customers"],
        "grains": {"branch", "governorate", "time"},
    },
    "pending_kyc_cases": {
        "formula": "COUNT(CASE WHEN kc.status = 'pending' THEN 1 END)",
        "alias": "pending_kyc_cases",
        "source_tables": ["kyc_cases"],
        "grains": {"branch", "time"},
    },
    "open_aml_alerts": {
        "formula": "COUNT(CASE WHEN aa.status = 'open' THEN 1 END)",
        "alias": "open_aml_alerts",
        "source_tables": ["aml_alerts"],
        "grains": {"branch", "governorate", "time"},
    },
}


# ─── Grain name mapping ──────────────────────────────────────────────────────

_DIMENSION_TO_GRAIN: Dict[str, str] = {
    "customers.segment": "segment",
    "branches.region_id": "region",
    "branches.region": "region",
    "branches.name": "branch",
    "branches.state": "branch",
    "branches.city": "branch",
    "accounts.account_type": "account_type",
    "loan_contracts.loan_type": "loan_type",
    "loan_contracts.status": "loan_status",
    "fee_income.fee_type": "fee_type",
    "time": "time",
}

# ─── Entity identity registry ────────────────────────────────────────────────

ENTITY_IDENTITIES: Dict[str, Dict[str, Any]] = {
    "customers": {"identity": "customer_id", "source_table": "customers"},
    "accounts": {"identity": "account_id", "source_table": "accounts"},
    "loan_contracts": {"identity": "loan_id", "source_table": "loan_contracts"},
    "transactions": {"identity": "transaction_id", "source_table": "transactions"},
    "branches": {"identity": "branch_id", "source_table": "branches"},
    "employees": {"identity": "employee_id", "source_table": "employees"},
    "cards": {"identity": "card_id", "source_table": "cards"},
    "products": {"identity": "product_id", "source_table": "products"},
    "risk_flags": {"identity": "id", "source_table": "risk_flags"},
    "kyc_cases": {"identity": "kyc_case_id", "source_table": "kyc_cases"},
    "aml_alerts": {"identity": "alert_id", "source_table": "aml_alerts"},
    "non_performing_loans": {"identity": "npl_id", "source_table": "non_performing_loans"},
    "provisions": {"identity": "provision_id", "source_table": "provisions"},
    "fee_income": {"identity": "fee_income_id", "source_table": "fee_income"},
    "compliance_violations": {"identity": "id", "source_table": "compliance_violations"},
    "suspicious_activity_reports": {"identity": "sar_id", "source_table": "suspicious_activity_reports"},
}

# ─── Boolean columns for conditional aggregation ─────────────────────────────

_BOOLEAN_COLUMNS: Dict[str, Set[str]] = {
    "customers": {"kyc_verified"},
    "branches": {"is_active"},
    "employees": {"is_active"},
    "products": {"is_active"},
    "kyc_cases": set(),
}

# ─── Entity keyword → table mapping (for "count customers" detection) ────────

_ENTITY_KEYWORDS: Dict[str, str] = {
    "customer": "customers", "client": "customers",
    "account": "accounts", "compte": "accounts",
    "loan": "loan_contracts", "pret": "loan_contracts", "prêt": "loan_contracts",
    "prêts": "loan_contracts", "credits": "loan_contracts",
    "provision": "provisions", "provisions": "provisions",
    "transaction": "transactions", "virement": "transactions",
    "branch": "branches", "agence": "branches", "succursale": "branches",
    "employee": "employees", "employé": "employees",
    "card": "cards", "carte": "cards",
    "fee": "fee_income", "commission": "fee_income", "frais": "fee_income",
    "kyc": "kyc_cases",
    "aml": "aml_alerts", "suspicious": "suspicious_activity_reports",
    "compliance": "compliance_violations", "violation": "compliance_violations",
    "product": "products", "produit": "products",
}

# ─── Valid column whitelist ──────────────────────────────────────────────────

_VALID_COLUMNS: Dict[str, Set[str]] = {
    "customers": {
        "customer_id", "name", "email", "phone", "kyc_verified", "risk_score",
        "segment", "created_at", "updated_at",
    },
    "accounts": {
        "account_id", "customer_id", "account_type", "balance",
        "available_balance", "currency", "status", "branch_id", "created_at",
    },
    "transactions": {
        "transaction_id", "account_id", "customer_id", "amount",
        "transaction_type", "status", "description", "transaction_date",
        "created_at",
    },
    "branches": {
        "branch_id", "name", "state", "city", "manager_id", "created_at",
        "region_id",
    },
    "loan_contracts": {
        "loan_id", "customer_id", "account_id", "branch_id", "loan_product_id",
        "loan_type", "principal_amount", "currency", "interest_rate",
        "term_months", "installment_amount", "disbursement_date",
        "maturity_date", "status", "outstanding_balance", "days_past_due",
        "created_at", "updated_at",
    },
    "non_performing_loans": {
        "npl_id", "loan_id", "npl_amount", "npl_date",
        "classification", "recovery_status", "created_at",
    },
    "provisions": {
        "provision_id", "loan_id", "provision_date", "provision_amount",
        "calculation_model", "created_at",
    },
    "risk_flags": {
        "id", "customer_id", "flag_type", "severity", "created_at",
        "account_id", "transaction_id", "resolved_at", "resolved_by",
        "risk_category", "source",
    },
    "kyc_cases": {
        "kyc_case_id", "customer_id", "case_type", "status",
        "risk_level", "assigned_to", "opened_at", "closed_at",
        "due_date", "notes", "created_at",
    },
    "aml_alerts": {
        "alert_id", "customer_id", "transaction_id", "severity", "status",
        "created_at",
    },
    "income_statement_snapshots": {
        "snapshot_id", "period", "net_income", "pnb",
        "operating_expenses", "fee_income", "interest_income",
    },
    "balance_sheet_snapshots": {
        "snapshot_id", "period", "total_assets", "total_equity",
    },
    "fee_income": {
        "fee_income_id", "customer_id", "account_id", "fee_type",
        "amount", "value_date", "created_at",
    },
    "interest_income": {
        "interest_id", "loan_id", "customer_id", "amount", "period",
    },
    "employees": {
        "employee_id", "branch_id", "department_id", "first_name", "last_name",
        "title", "role", "hire_date", "is_active", "email",
        "supervisor_id", "created_at",
    },
    "cards": {
        "card_id", "account_id", "customer_id", "card_type",
        "card_number_masked", "expiry_date", "status",
        "daily_limit", "monthly_limit", "issued_date",
    },
    "products": {
        "product_id", "name", "category", "description",
    },
    "compliance_violations": {
        "id", "query_id", "user_id", "violation_type", "severity",
        "description", "regulation", "detected_at", "status",
        "resolution_notes",
    },
    "suspicious_activity_reports": {
        "sar_id", "alert_id", "customer_id", "report_date", "status",
        "ctaf_reference", "description", "created_at",
    },
}


class QueryPlanBuilder:
    """
    Constructs a validated QueryPlan from structured intent + schema selection.

    All analytical decisions are made here:
    - Implicit aggregation resolution from natural language
    - Entity-aware counting (COUNT DISTINCT on identity when joins present)
    - Conditional aggregation (CaseExpression for boolean columns)
    - Fan-out detection (reject/flag when joins duplicate fact rows)
    - Unknown metric detection (invalidates plan)
    - GROUP BY / ordering / ExpectedAnswer generation
    - Grain tracking (source → aggregate input → output)

    The compiler is a pure SQL renderer.
    """

    def build(
        self,
        *,
        task: str,
        query_text: str,
        selected_tables: List[str],
        bridge_tables: List[str],
        selected_columns: Dict[str, List[str]],
        join_paths: List[Dict[str, Any]],
        metrics: List[str],
        dimensions: List[str],
        filters_structured: List[Dict[str, Any]],
        time_range: Dict[str, Any],
        sort_structured: Optional[List[Dict[str, Any]]] = None,
        limit_requested: Optional[int],
        requested_fields: List[str],
        missing_requested_fields: Optional[List[str]] = None,
        unsupported_reason: Optional[str] = None,
        semantic_metadata_version: str = "",
        schema_snapshot_id: str = "",
        requested_currency: Optional[str] = None,
    ) -> QueryPlan:
        # ── Fast-fail on known-bad states ─────────────────────────────────
        if unsupported_reason:
            return self._fail_plan(
                unsupported_reason, semantic_metadata_version, schema_snapshot_id,
                task, query_text, selected_tables, selected_columns,
                missing_requested_fields or [],
            )

        if missing_requested_fields:
            return self._fail_plan(
                f"Requested fields not found in schema: {', '.join(missing_requested_fields)}",
                semantic_metadata_version, schema_snapshot_id,
                task, query_text, selected_tables, selected_columns,
                missing_requested_fields,
            )

        # ── Validate metrics (FAIL on unknown) ────────────────────────────
        validated_metrics, metric_fail = self._validate_metrics(
            metrics, dimensions, selected_tables, selected_columns,
        )
        if metric_fail:
            return self._fail_plan(
                metric_fail, semantic_metadata_version, schema_snapshot_id,
                task, query_text, selected_tables, selected_columns,
                missing_requested_fields or [],
            )

        # ── Validate requested_currency for governed metrics ──────────────
        currency_err = self._validate_metric_currency(
            validated_metrics, requested_currency,
        )
        if currency_err:
            return self._fail_plan(
                currency_err, semantic_metadata_version, schema_snapshot_id,
                task, query_text, selected_tables, selected_columns,
                missing_requested_fields or [],
            )

        # ── Build joins (before fan-out detection) ────────────────────────
        # ponytail: auto-resolve when caller passes empty joins for multi-table
        resolved_paths = join_paths
        if not resolved_paths and len(selected_tables) > 1:
            resolved_paths = _auto_resolve_joins(selected_tables)
        join_specs = self._build_joins(resolved_paths)

        # ── Detect fan-out risk ───────────────────────────────────────────
        fan_out = self._detect_fan_out(join_specs, selected_tables)

        # ── Resolve implicit analytical expressions ───────────────────────
        implicit_exprs = self._resolve_implicit_aggregation(
            task, query_text, requested_fields, selected_tables,
            selected_columns, dimensions, join_specs,
        )

        # ── Build dimensions ──────────────────────────────────────────────
        dim_refs = self._build_dimensions(dimensions, selected_tables)

        # ── Build grain ───────────────────────────────────────────────────
        grain = self._build_grain(selected_tables, dim_refs, time_range)

        # ── Build filters ─────────────────────────────────────────────────
        filter_specs = self._build_filters(filters_structured, selected_tables)

        # ── Build time range ──────────────────────────────────────────────
        time_spec = self._build_time_range(time_range)

        # ── Build sort ────────────────────────────────────────────────────
        sort_spec = self._build_sort(sort_structured, task)

        # ── Build requested columns ───────────────────────────────────────
        col_refs = self._build_requested_columns(
            requested_fields, selected_columns, selected_tables,
        )

        # ── Determine limit ───────────────────────────────────────────────
        limit = limit_requested if limit_requested and limit_requested > 0 else 100
        limit = min(limit, 10_000)

        # ── ExpectedAnswer ────────────────────────────────────────────────
        expected = self._build_expected_answer(
            task, validated_metrics, implicit_exprs, dim_refs, sort_spec,
            col_refs, requested_fields,
        )

        plan = QueryPlan(
            schema_snapshot_id=schema_snapshot_id,
            semantic_metadata_version=semantic_metadata_version,
            task=task,
            query_text=query_text,
            selected_tables=sorted(selected_tables),
            bridge_tables=sorted(bridge_tables),
            selected_columns=selected_columns,
            joins=join_specs,
            requested_columns=col_refs,
            metrics=validated_metrics,
            analytical_expressions=implicit_exprs,
            grain=grain,
            dimensions=dim_refs,
            filters=filter_specs,
            time_range=time_spec,
            sort=sort_spec,
            limit=limit,
            expected_answer=expected,
            fan_out_risk=fan_out,
            missing_requested_fields=missing_requested_fields or [],
            unsupported_reason=unsupported_reason,
        )

        logger.info(
            "[QueryPlanBuilder] Plan built: tables=%d metrics=%d exprs=%d dims=%d filters=%d fan_out=%s",
            len(plan.selected_tables), len(plan.metrics),
            len(plan.analytical_expressions), len(plan.dimensions),
            len(plan.filters), fan_out,
        )
        return plan

    # ── Fail ──────────────────────────────────────────────────────────────

    def _fail_plan(
        self, reason: str, version: str, snapshot: str,
        task: str, query_text: str, tables: List[str],
        columns: dict, missing: List[str],
    ) -> QueryPlan:
        return QueryPlan(
            schema_snapshot_id=snapshot,
            semantic_metadata_version=version,
            task=task,
            query_text=query_text,
            selected_tables=sorted(tables),
            selected_columns=columns,
            unsupported_reason=reason,
            missing_requested_fields=missing,
        )

    # ── Validate named metrics (FAIL on unknown) ──────────────────────────

    def _validate_metrics(
        self, metric_ids: List[str], dimensions: List[str],
        tables: List[str], selected_columns: Dict[str, List[str]],
    ) -> Tuple[List[MetricReference], Optional[str]]:
        validated = []
        for mid in metric_ids:
            info = APPROVED_METRICS.get(mid.lower())
            if not info:
                return [], f"Unknown metric '{mid}' — not in approved registry"

            dim_grains = {_DIMENSION_TO_GRAIN.get(d, d) for d in dimensions}
            allowed_grains = info.get("grains", set())
            if dim_grains and not dim_grains.issubset(allowed_grains):
                disallowed = dim_grains - allowed_grains
                return [], (
                    f"Metric '{mid}' does not support grain(s) {disallowed}. "
                    f"Allowed grains: {allowed_grains}. "
                    f"Grouped independent subqueries are not implemented."
                )

            strategy = None
            strategy_raw = info.get("execution_strategy")
            if strategy_raw:
                strategy = MetricExecutionStrategy(**strategy_raw)

            validated.append(MetricReference(
                metric_id=mid.lower(),
                alias=info["alias"],
                formula=info["formula"],
                source_tables=info["source_tables"],
                grain_supported=True,
                execution_strategy=strategy,
            ))
        return validated, None

    # ── Currency validation ────────────────────────────────────────────────

    # ponytail: per-metric currency table. Add entries as new currency-bound metrics appear.
    _METRIC_GOVERNED_CURRENCY: Dict[str, str] = {
        "loan_to_deposit": "TND",
    }

    def _validate_metric_currency(
        self, metrics: List[MetricReference], requested_currency: Optional[str],
    ) -> Optional[str]:
        """Validate requested_currency against governed currency for ratio metrics.

        Rules for loan_to_deposit (and any metric in _METRIC_GOVERNED_CURRENCY):
        - No requested_currency: use governed default (TND) silently
        - Explicit TND: accepted
        - Explicit non-TND: rejected at planning (not silently answered with TND SQL)
        - Mixed currencies: rejected at planning
        """
        if not requested_currency:
            return None
        for m in metrics:
            governed = self._METRIC_GOVERNED_CURRENCY.get(m.metric_id)
            if governed and requested_currency.upper() != governed.upper():
                return (
                    f"Metric '{m.metric_id}' is governed by reporting currency "
                    f"'{governed}'. Requested currency '{requested_currency}' is not "
                    f"supported. Either omit requested_currency (defaults to {governed}) "
                    f"or request '{governed}' explicitly."
                )
        return None

    # ── Fan-out detection ─────────────────────────────────────────────────

    def _detect_fan_out(
        self, joins: List[JoinSpec], tables: List[str],
    ) -> bool:
        """Return True when a join can duplicate fact rows."""
        for j in joins:
            if j.cardinality in ("one_to_many", "many_to_many"):
                return True
        return False

    # ── Implicit analytical expression resolution ─────────────────────────

    def _resolve_implicit_aggregation(
        self,
        task: str,
        query_text: str,
        requested_fields: List[str],
        tables: List[str],
        selected_columns: Dict[str, List[str]],
        dimensions: List[str],
        joins: Optional[List[JoinSpec]] = None,
    ) -> List[AnalyticalExpression]:
        if task == "detail_listing":
            return []

        q = query_text.lower()
        exprs: List[AnalyticalExpression] = []
        joins = joins or []

        if task in ("aggregation", "ranking"):
            # Detect ratio/percentage first (higher priority)
            ratio_expr = self._detect_ratio(q, tables, selected_columns)
            if ratio_expr:
                exprs.append(ratio_expr)
                return exprs

            # Detect percentage as conditional ratio
            pct_expr = self._detect_percentage(q, tables, selected_columns)
            if pct_expr:
                exprs.append(pct_expr)
                return exprs

            # Detect plain aggregation
            agg_expr = self._detect_plain_aggregation(
                q, requested_fields, tables, selected_columns, dimensions, joins,
            )
            if agg_expr:
                exprs.append(agg_expr)

        return exprs

    def _detect_plain_aggregation(
        self, q: str, requested_fields: List[str],
        tables: List[str], selected_columns: Dict[str, List[str]],
        dimensions: List[str],
        joins: Optional[List[JoinSpec]] = None,
    ) -> Optional[AggregateExpression]:
        """Detect COUNT/SUM/AVG/MIN/MAX from query text."""
        dim_set = {d.split(".")[-1] if "." in d else d for d in dimensions}
        joins = joins or []

        func = self._detect_aggregate_function(q, None)

        if func in ("COUNT", "DISTINCT_COUNT"):
            # Entity-aware: detect entity keyword in query → COUNT(DISTINCT pk)
            entity_col = self._find_entity_count(
                q, tables, selected_columns, dim_set, joins,
            )
            if entity_col:
                return AggregateExpression(
                    function="COUNT", column=entity_col, distinct=True,
                    alias=f"count_{entity_col.name}",
                )
            target_col = self._find_count_target(requested_fields, tables, selected_columns, dim_set)
            if func == "DISTINCT_COUNT" and target_col:
                return AggregateExpression(
                    function="COUNT", column=target_col, distinct=True,
                    alias=f"distinct_count_{target_col.name}",
                )
            if func == "COUNT" and target_col:
                return AggregateExpression(
                    function="COUNT", column=target_col,
                    alias=f"count_{target_col.name}",
                )
            return AggregateExpression(
                function="COUNT", column=None, alias="count_all",
            )

        if func and func not in ("COUNT", "DISTINCT_COUNT"):
            target_col = self._find_target_column(
                requested_fields, tables, selected_columns, dim_set,
            )
            if target_col:
                alias = f"{func.lower()}_{target_col.name}"
                return AggregateExpression(
                    function=func, column=target_col, alias=alias,
                )

        if not func and dimensions:
            return AggregateExpression(
                function="COUNT", column=None, alias="count_all",
            )

        return None

    def _find_entity_count(
        self, q: str, tables: List[str],
        selected_columns: Dict[str, List[str]],
        dim_set: set, joins: List[JoinSpec],
    ) -> Optional[ColumnRef]:
        """Detect entity keyword in query → COUNT(DISTINCT entity_pk).
        Only returns DISTINCT when a one_to_many or many_to_many join exists."""
        has_fan_out = any(j.cardinality in ("one_to_many", "many_to_many") for j in joins)
        for keyword, table in _ENTITY_KEYWORDS.items():
            if re.search(r'\b' + re.escape(keyword) + r's?\b', q):
                if table in tables:
                    info = ENTITY_IDENTITIES.get(table)
                    if info:
                        pk = info["identity"]
                        col = ColumnRef(table=table, name=pk)
                        if has_fan_out:
                            return col
        return None

    def _find_count_target(
        self, requested_fields: List[str],
        tables: List[str], selected_columns: Dict[str, List[str]],
        dim_set: set,
    ) -> Optional[ColumnRef]:
        """Find column for COUNT(col). Only from explicit requested_fields,
        excluding dimension columns. Returns None for COUNT(*)."""
        skip = {
            "total", "sum", "amount", "montant", "somme", "balance", "solde",
            "average", "avg", "moyenne", "minimum", "min", "maximum", "max",
            "count", "number", "combien", "nombre", "client", "customer",
            "account", "compte", "branch", "agence",
        }
        for rf in requested_fields:
            if rf.lower() in skip or rf in dim_set:
                continue
            for t in tables:
                cols = selected_columns.get(t, [])
                if rf in cols:
                    return ColumnRef(table=t, name=rf)
        return None

    def _detect_aggregate_function(
        self, q: str, target_col: Optional[ColumnRef],
    ) -> Optional[str]:
        """Detect aggregate function from query keywords using word boundaries."""
        _wb = lambda w: re.search(r'\b' + re.escape(w) + r'\b', q)
        _wb_any = lambda words: any(_wb(w) for w in words)

        has_avg = _wb_any(["average", "avg", "moyenne"])
        has_min = _wb_any(["minimum", "min", "lowest", "plus bas", "moins"])
        has_max = _wb_any(["maximum", "max", "highest", "plus grand", "meilleur"])
        has_sum = _wb_any(["total", "sum", "amount", "montant", "somme", "totaliser"])
        has_count = _wb_any([
            "count", "number", "how many", "combien", "nombre",
            "nombre de", "quantité",
        ])
        has_distinct = _wb_any(["unique", "distinct", "distincts", "différents"])

        if has_avg:
            return "AVG"
        if has_min:
            return "MIN"
        if has_max:
            return "MAX"
        if has_distinct and has_count:
            return "DISTINCT_COUNT"
        if has_count:
            return "COUNT"
        if has_sum:
            return "SUM"
        return None

    def _detect_ratio(
        self, q: str, tables: List[str],
        selected_columns: Dict[str, List[str]],
    ) -> Optional[RatioExpression]:
        """Detect ratio expressions. LDR requires the named metric
        (independent subqueries) — fail here to avoid fan-out."""
        if "loan to deposit" in q or "ldr" in q:
            # Fan-out: joining loan_contracts + accounts duplicates rows.
            # Must use the named metric 'loan_to_deposit' (independent subqueries).
            return None
        return None

    def _detect_percentage(
        self, q: str, tables: List[str],
        selected_columns: Dict[str, List[str]],
    ) -> Optional[RatioExpression]:
        """Detect percentage with conditional numerator (CaseExpression)."""
        if "percentage" not in q and "pourcentage" not in q:
            return None

        # Find boolean column → COUNT(CASE WHEN col = true THEN 1 END)
        for t in tables:
            bool_cols = _BOOLEAN_COLUMNS.get(t, set())
            selected = set(selected_columns.get(t, []))
            for c in bool_cols & selected:
                return RatioExpression(
                    numerator=CaseExpression(
                        column=ColumnRef(table=t, name=c),
                        condition_column=c,
                        condition_value=True,
                        function="COUNT",
                        alias="numerator_count",
                    ),
                    denominator=AggregateExpression(
                        function="COUNT", column=None,
                        alias="denominator_count",
                    ),
                    multiply_100=True,
                    alias="percentage",
                    aggregation_strategy="same_relation",
                )
        return None

    def _find_target_column(
        self, requested_fields: List[str],
        tables: List[str], selected_columns: Dict[str, List[str]],
        dim_set: Optional[set] = None,
    ) -> Optional[ColumnRef]:
        """Find the column to aggregate based on requested fields."""
        dim_set = dim_set or set()
        agg_keywords = {
            "total", "sum", "amount", "montant", "somme", "balance", "solde",
            "average", "avg", "moyenne", "minimum", "min", "maximum", "max",
            "count", "number", "combien", "nombre",
        }

        for rf in requested_fields:
            if rf.lower() in agg_keywords or rf in dim_set:
                continue
            for t in tables:
                cols = selected_columns.get(t, [])
                if rf in cols:
                    return ColumnRef(table=t, name=rf)
                if f"{t}.{rf}" in [f"{t}.{c}" for c in cols]:
                    return ColumnRef(table=t, name=rf)

        # Fallback: use the first numeric-looking column from the primary table
        _NUMERIC_HINTS = {
            "balance", "amount", "principal_amount", "outstanding_balance",
            "risk_score", "fee_amount", "npl_amount", "provision_amount",
        }
        for t in sorted(tables):
            for c in selected_columns.get(t, []):
                if c in _NUMERIC_HINTS:
                    return ColumnRef(table=t, name=c)

        return None

    # ── Grain tracking ────────────────────────────────────────────────────

    def _build_grain(
        self, tables: List[str], dims: List[ColumnRef],
        time_range: Dict[str, Any],
    ) -> GrainSpec:
        source_table = tables[0] if tables else ""
        identity = ENTITY_IDENTITIES.get(source_table, {}).get("identity", "")
        source_grain = identity or "row"

        output_parts = [d.name for d in dims]
        output_grain = ", ".join(output_parts) if output_parts else "scalar"

        temporal = ""
        if time_range.get("type") == "relative":
            temporal = time_range.get("value", "")

        return GrainSpec(
            source_table=source_table,
            source_grain=source_grain,
            aggregate_input_grain=source_grain,
            output_grain=output_grain,
            temporal_grain=temporal,
            identity_columns=[identity] if identity else [],
        )

    # ── ExpectedAnswer generation ─────────────────────────────────────────

    def _build_expected_answer(
        self,
        task: str,
        metrics: List[MetricReference],
        implicit_exprs: List[AnalyticalExpression],
        dims: List[ColumnRef],
        sort: Optional[SortSpec],
        cols: List[ColumnRef],
        requested_fields: List[str],
    ) -> ExpectedAnswer:
        has_agg = bool(metrics) or bool(implicit_exprs)

        # Answer type
        if task == "ranking":
            answer_type = "ranked_list"
        elif has_agg and not dims:
            answer_type = "scalar"
        elif has_agg and dims:
            answer_type = "grouped_rows"
        elif not has_agg and not dims:
            answer_type = "detail_rows"
        else:
            answer_type = "detail_rows"

        # Check for time-series signal
        if dims and any(
            d.name in ("period", "created_at", "transaction_date", "snapshot_id")
            for d in dims
        ):
            if has_agg:
                answer_type = "time_series"

        grain = [d.name for d in dims]

        exp_metrics = [m.alias for m in metrics]
        for expr in implicit_exprs:
            if hasattr(expr, "alias"):
                exp_metrics.append(expr.alias)

        exp_dims = [f"{d.table}.{d.name}" for d in dims]

        ordering = None
        if sort:
            ordering = f"{sort.column} {sort.direction}"
        elif task == "ranking" and exp_metrics:
            ordering = f"{exp_metrics[0]} DESC"

        agg_required = has_agg or bool(dims)

        exp_cols = [f"{c.table}.{c.name}" for c in cols]
        exp_cols.extend(exp_metrics)

        return ExpectedAnswer(
            answer_type=answer_type,
            expected_grain=grain,
            expected_metrics=exp_metrics,
            expected_dimensions=exp_dims,
            ordering=ordering,
            aggregation_required=agg_required,
            expected_columns=exp_cols,
        )

    # ── Dimension / filter / time / sort builders ─────────────────────────

    def _build_dimensions(
        self, dimensions: List[str], tables: List[str],
    ) -> List[ColumnRef]:
        refs = []
        for dim in dimensions:
            parts = dim.split(".")
            if len(parts) == 2:
                t, c = parts
                if t in tables:
                    refs.append(ColumnRef(table=t, name=c))
            else:
                for t in tables:
                    if dim in _VALID_COLUMNS.get(t, set()):
                        refs.append(ColumnRef(table=t, name=dim))
                        break
        return refs

    def _build_filters(
        self, filters: List[Dict[str, Any]], tables: List[str],
    ) -> List[FilterSpec]:
        specs = []
        dropped = []
        for f in filters:
            col = f.get("column", "")
            op = f.get("operator", "=")
            val = f.get("value")

            parts = col.split(".")
            if len(parts) == 2:
                t, c = parts
                if t not in tables:
                    dropped.append(col)
                    continue
                if c not in _VALID_COLUMNS.get(t, set()):
                    dropped.append(col)
                    continue
            else:
                found = False
                for t in tables:
                    if col in _VALID_COLUMNS.get(t, set()):
                        col = f"{t}.{col}"
                        found = True
                        break
                if not found:
                    dropped.append(col)
                    continue

            param_name = col.replace(".", "_")
            specs.append(FilterSpec(
                column=col, operator=op, value=val, param_name=param_name,
            ))
        if dropped:
            raise ValueError(
                f"Unsupported filter column(s): {', '.join(dropped)}. "
                f"Filters must reference columns from the selected tables: {tables}"
            )
        return specs

    def _build_time_range(self, time_range: Dict[str, Any]) -> TimeRangeSpec:
        if not time_range:
            return TimeRangeSpec()
        t = time_range.get("type", "none")
        v = time_range.get("value")
        if t == "relative" and v:
            return TimeRangeSpec(type="relative", value=v)
        return TimeRangeSpec()

    def _build_sort(
        self, sort_structured: Optional[List[Dict[str, Any]]], task: str,
    ) -> Optional[SortSpec]:
        if sort_structured:
            s = sort_structured[0]
            col = s.get("column", "")
            direction = s.get("direction", "ASC").upper()
            if direction not in ("ASC", "DESC"):
                direction = "ASC"
            return SortSpec(column=col, direction=direction)
        return None

    def _build_joins(self, join_paths: List[Dict[str, Any]]) -> List[JoinSpec]:
        specs = []
        for jp in join_paths:
            join_type = jp.get("join_type", "INNER JOIN")
            if join_type not in ("INNER JOIN", "LEFT JOIN", "RIGHT JOIN"):
                join_type = "INNER JOIN"
            cardinality = jp.get("cardinality", "many_to_one")
            if cardinality not in ("one_to_one", "many_to_one", "one_to_many", "many_to_many"):
                cardinality = "many_to_one"
            specs.append(JoinSpec(
                from_table=jp["from_table"],
                to_table=jp["to_table"],
                join_type=join_type,
                join_key=jp.get("join_key", ""),
                condition=jp.get("condition", ""),
                cardinality=cardinality,
            ))
        return specs

    def _build_requested_columns(
        self,
        requested_fields: List[str],
        selected_columns: Dict[str, List[str]],
        tables: List[str],
    ) -> List[ColumnRef]:
        if not requested_fields:
            refs = []
            for t in sorted(selected_columns.keys()):
                for c in selected_columns[t]:
                    refs.append(ColumnRef(table=t, name=c))
            return refs

        refs = []
        seen = set()

        for rf in requested_fields:
            for t in tables:
                cols = selected_columns.get(t, [])
                candidates = [rf, f"{rf}_id"]
                if rf == "outstanding_balance":
                    candidates.extend(["outstanding_balance", "balance"])
                if rf == "active status":
                    candidates.extend(["status"])
                for c in candidates:
                    if c in cols and c not in seen:
                        refs.append(ColumnRef(table=t, name=c))
                        seen.add(c)
                        break

        return refs
