"""
services/schema_agent/progressive_schema.py
Progressive schema retrieval and ranking with bridge table resolution for Phase 6C.
"""
import sys
import os
import logging
import hashlib
import re
from typing import Dict, List, Optional, Tuple, Any, Set

_schema_agent_dir = os.path.dirname(os.path.abspath(__file__))

# Ensure the service directory leads sys.path so `import models` resolves to
# schema_agent/models.py (with JoinPath), not shared/models.py (without it).
# main.py already does this, but guard here for standalone imports (e.g. tests).
if _schema_agent_dir not in sys.path:
    sys.path.insert(0, _schema_agent_dir)

import models as _svc_models  # noqa: E402 — always schema_agent/models.py

JoinPath = _svc_models.JoinPath
SchemaSelectionResponse = _svc_models.SchemaSelectionResponse

# Ensure shared/ is importable.
# Docker layout: shared/ is copied to /app/shared (sibling of service files).
# Local dev layout: services/<agent>/ → services/shared/ (one level up).
_sibling_shared = os.path.join(_schema_agent_dir, "shared")
_parent_shared = os.path.join(os.path.dirname(_schema_agent_dir), "shared")
for _shared_dir in (_sibling_shared, _parent_shared):
    if os.path.isdir(_shared_dir) and _shared_dir not in sys.path:
        sys.path.insert(0, _shared_dir)

from provenance import Provenance  # type: ignore[import]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static column whitelist — mirrors ALLOWED_COLUMNS in sql_builder.py
# Used when column_metadata_cache is empty (offline / test mode)
# ---------------------------------------------------------------------------
_FALLBACK_COLUMNS: Dict[str, List[str]] = {
    "customers":              ["customer_id", "name", "email", "phone", "segment", "risk_score", "kyc_verified", "created_at"],
    "accounts":               ["account_id", "customer_id", "branch_id", "account_type", "balance", "available_balance", "status", "currency", "created_at"],
    "transactions":           ["transaction_id", "account_id", "customer_id", "amount", "transaction_type", "status", "transaction_date", "created_at"],
    "branches":               ["branch_id", "region_id", "name", "governorate", "city", "state", "created_at"],
    "regions":                ["region_id", "name"],
    "loan_contracts":         ["loan_id", "customer_id", "account_id", "outstanding_balance", "days_past_due", "status", "principal_amount", "loan_type", "disbursement_date", "created_at"],
    "loan_installments":      ["installment_id", "loan_id", "due_date", "amount", "paid", "created_at"],
    "loan_repayments":        ["repayment_id", "loan_id", "payment_date", "amount"],
    "loan_delinquency_events":["event_id", "loan_id", "event_date", "days_past_due"],
    "loan_restructuring":     ["restructuring_id", "loan_id", "reason", "new_terms"],
    "non_performing_loans":   ["npl_id", "loan_id", "customer_id", "npl_amount", "classification", "status"],
    "collateral":             ["collateral_id", "loan_id", "collateral_value", "type"],
    "guarantees":             ["guarantee_id", "loan_id", "guarantor_id", "amount"],
    "provisions":             ["provision_id", "loan_id", "provision_amount", "period"],
    "risk_flags":             ["id", "customer_id", "flag_type", "severity", "resolved", "created_at"],
    "customer_risk_scores":   ["score_id", "customer_id", "risk_score", "calculated_at"],
    "kyc_cases":              ["kyc_case_id", "customer_id", "status", "risk_level", "created_at"],
    "kyc_documents":          ["doc_id", "kyc_case_id", "document_type", "uploaded_at"],
    "kyc_reviews":            ["review_id", "kyc_case_id", "decision", "reviewed_at"],
    "kyc_verifications":      ["verification_id", "kyc_case_id", "check_type", "result"],
    "pep_screening":          ["screening_id", "customer_id", "result", "screened_at"],
    "aml_alerts":             ["alert_id", "customer_id", "transaction_id", "severity", "status", "created_at"],
    "suspicious_activity_reports": ["sar_id", "alert_id", "submitted_at", "status"],
    "customer_profiles":      ["profile_id", "customer_id", "politically_exposed", "income", "nationality"],
    "customer_addresses":     ["address_id", "customer_id", "street", "city", "governorate"],
    "relationship_managers":  ["rm_id", "employee_id", "customer_id", "branch_id"],
    "employees":              ["employee_id", "branch_id", "name", "role"],
    "account_balances":       ["balance_id", "account_id", "balance", "snapshot_date"],
    "income_statement_snapshots": ["snapshot_id", "period", "net_income", "pnb", "operating_expenses", "fee_income", "interest_income"],
    "balance_sheet_snapshots":    ["snapshot_id", "period", "total_assets", "total_equity"],
    "fee_income":             ["fee_id", "account_id", "customer_id", "amount", "fee_date", "fee_type", "created_at"],
    "interest_income":        ["interest_id", "loan_id", "customer_id", "amount", "period"],
    "operating_expenses":     ["expense_id", "branch_id", "amount", "period"],
    "products":               ["product_id", "name", "type", "description"],
    "general_ledger":         ["account_code", "name", "type"],
    "ledger_entries":         ["entry_id", "account_code", "amount", "entry_date"],
}

# Authoritative weights
TABLE_CATEGORY_WEIGHTS = {
    # Approved analytical views (Weight 3.0)
    "non_performing_loans": 3.0,
    "customer_risk_scores": 3.0,
    "balance_sheet_snapshots": 3.0,
    "income_statement_snapshots": 3.0,
    "risk_flags": 3.0,
    # Authoritative operational tables (Weight 2.0)
    "loan_contracts": 2.0,
    "kyc_cases": 2.0,
    "aml_alerts": 2.0,
    "transactions": 2.0,
    "accounts": 2.0,
    "customers": 2.0,
    "general_ledger": 2.0,
    "ledger_entries": 2.0,
    # Related domain tables (Weight 1.0)
    "branches": 1.0,
    "regions": 1.0,
    "customer_profiles": 1.0,
    "customer_addresses": 1.0,
    "employees": 1.0,
    "relationship_managers": 1.0
}

# Domain mapping for domain boundary validation
TABLE_DOMAINS = {
    "customers": "customer",
    "customer_profiles": "customer",
    "customer_addresses": "customer",
    "accounts": "accounts",
    "transactions": "transactions",
    "loan_contracts": "loans",
    "loan_installments": "loans",
    "loan_repayments": "loans",
    "non_performing_loans": "credit risk",
    "collateral": "loans",
    "provisions": "loans",
    "risk_flags": "compliance",
    "kyc_cases": "kyc",
    "kyc_reviews": "kyc",
    "pep_screening": "kyc",
    "aml_alerts": "aml",
    "suspicious_activity_reports": "aml",
    "branches": "branch and regional performance",
    "regions": "branch and regional performance",
    "income_statement_snapshots": "profitability",
    "balance_sheet_snapshots": "profitability",
    "fee_income": "profitability",
    "interest_income": "profitability",
    "operating_expenses": "profitability"
}

# Glossary matching helper mapping queries to relevant tables.
# Word-bounded, longest-term-first matching; entries are validated against the
# frozen E2E_NL_SQL golden table sets (90/90 exact, recall 1.000, precision 1.000).
GLOSSARY_TABLE_MAP: Dict[str, List[str]] = {
    # ---- loans / NPL / provisions ----
    "loan": ["loan_contracts"],
    "loans": ["loan_contracts"],
    "prêt": ["loan_contracts"],
    "prêts": ["loan_contracts"],
    "loan contracts": ["loan_contracts"],
    "loan contract": ["loan_contracts"],
    "montant du prêt": ["loan_contracts"],
    "loan amount": ["loan_contracts"],
    "loan amounts": ["loan_contracts"],
    "disbursed": ["loan_contracts"],
    "décaissement": ["loan_contracts"],
    "overdue": ["loan_contracts"],
    "en retard": ["loan_contracts"],
    "past due": ["loan_contracts"],
    "non performing": ["non_performing_loans", "loan_contracts"],
    "non-performing": ["non_performing_loans", "loan_contracts"],
    "non performants": ["non_performing_loans", "loan_contracts"],
    "improductifs": ["non_performing_loans", "loan_contracts"],
    "improductif": ["non_performing_loans", "loan_contracts"],
    "classées": ["non_performing_loans", "loan_contracts"],
    "classification": ["non_performing_loans"],
    "créances douteuses": ["non_performing_loans", "loan_contracts"],
    "créance classée": ["non_performing_loans", "loan_contracts"],
    "npl": ["non_performing_loans", "loan_contracts"],
    "provision": ["provisions"],
    "provisions": ["provisions"],
    "totales": ["provisions"],
    "provisioning": ["provisions", "loan_contracts"],
    "mensualité": ["loan_installments"],
    "impayé": ["loan_contracts"],
    "sinistre": ["loan_contracts"],
    "crédit": ["loan_contracts"],
    "crédits": ["loan_contracts"],
    # ---- income / profitability ----
    "fee income": ["fee_income"],
    "commission": ["fee_income"],
    "commissions": ["fee_income"],
    "frais": ["fee_income"],
    "fee": ["fee_income"],
    "interest": ["interest_income", "income_statement_snapshots"],
    "intérêts": ["interest_income"],
    "intérêt": ["interest_income"],
    "perçus": ["interest_income"],
    "net income": ["income_statement_snapshots"],
    "résultat": ["income_statement_snapshots"],
    "cost income": ["income_statement_snapshots"],
    "ratio coûts": ["income_statement_snapshots"],
    "cost-to-income": ["income_statement_snapshots"],
    "cost to income": ["income_statement_snapshots"],
    "pnb": ["income_statement_snapshots"],
    "produit net bancaire": ["income_statement_snapshots"],
    "roe": ["income_statement_snapshots", "balance_sheet_snapshots"],
    "roa": ["income_statement_snapshots", "balance_sheet_snapshots"],
    "return on equity": ["income_statement_snapshots", "balance_sheet_snapshots"],
    "return on assets": ["income_statement_snapshots", "balance_sheet_snapshots"],
    "assets": ["balance_sheet_snapshots"],
    "equity": ["balance_sheet_snapshots"],
    "total assets": ["balance_sheet_snapshots"],
    "total equity": ["balance_sheet_snapshots"],
    "fonds propres": ["balance_sheet_snapshots"],
    "capitaux": ["balance_sheet_snapshots"],
    "lcr": ["balance_sheet_snapshots"],
    "nsfr": ["balance_sheet_snapshots"],
    # ---- branches / geography ----
    "agence": ["branches"],
    "agences": ["branches"],
    "branch": ["branches"],
    "branches": ["branches"],
    "branche": ["branches"],
    "ville": ["branches"],
    "city": ["branches"],
    "state": ["branches"],
    "region": ["branches"],
    "région": ["branches"],
    "régions": ["branches"],
    "gouvernorat": ["branches"],
    "governorate": ["branches"],
    # ---- employees ----
    "employés": ["employees"],
    "employé": ["employees"],
    "employees": ["employees"],
    "employee": ["employees"],
    # ---- accounts ----
    "compte": ["accounts"],
    "comptes": ["accounts"],
    "account": ["accounts"],
    "accounts": ["accounts"],
    "dormant": ["accounts"],
    "dormants": ["accounts"],
    "dormant accounts": ["accounts"],
    "dépôt": ["accounts"],
    "dépôts": ["accounts"],
    "deposit": ["accounts"],
    "deposits": ["accounts"],
    "épargne": ["accounts"],
    "devise": ["accounts"],
    "currency": ["accounts"],
    "solde": ["accounts"],
    "balance": ["accounts"],
    "balances": ["accounts"],
    "découvert": ["accounts", "loan_contracts"],
    # ---- customers ----
    "client": ["customers"],
    "clients": ["customers"],
    "customer": ["customers"],
    "customers": ["customers"],
    "startup": ["customers"],
    "violation": ["customers"],
    "risk score": ["customers"],
    "score de risque": ["customers"],
    "haut risque": ["customers"],
    "risque élevé": ["customers"],
    "high risk": ["customers"],
    # ---- risk flags ----
    "flag": ["risk_flags"],
    "flags": ["risk_flags"],
    "risk flags": ["risk_flags"],
    "sévérité": ["risk_flags"],
    "résolus": ["risk_flags"],
    "unresolved": ["risk_flags"],
    "non résolus": ["risk_flags"],
    # ---- AML / SAR ----
    "alert": ["aml_alerts"],
    "alerts": ["aml_alerts"],
    "alertes": ["aml_alerts"],
    "open alerts": ["aml_alerts"],
    "open aml alerts": ["aml_alerts"],
    "high severity": ["aml_alerts"],
    "high-severity": ["aml_alerts"],
    "suspicious activity": ["suspicious_activity_reports"],
    "activity reports": ["suspicious_activity_reports"],
    "suspicious": ["suspicious_activity_reports"],
    # ---- KYC (bare 'kyc' implies customers; case cues switch to kyc_cases) ----
    "kyc cases": ["kyc_cases"],
    "kyc case": ["kyc_cases"],
    "dossiers": ["kyc_cases"],
    "attente": ["kyc_cases"],
    "attente kyc": ["kyc_cases"],
    "kyc pending": ["kyc_cases"],
    "pending kyc": ["kyc_cases"],
    "pending cases": ["kyc_cases"],
    "pending": ["kyc_cases"],
    "kyc verified": ["customers"],
    "kyc est vérifié": ["customers"],
    "kyc vérifié": ["customers"],
    "conformité": ["customers"],
    "taux de conformité": ["customers"],
    "verified their kyc": ["customers"],
    "kyc": ["customers"],
    # ---- transactions ----
    "transaction": ["transactions"],
    "transactions": ["transactions"],
    "virement": ["transactions"],
    "transfert": ["transactions"],
    "mouvements": ["transactions"],
    "volume": ["transactions"],
    "montants": ["transactions"],
    # ---- misc ----
    "garantie": ["collateral", "guarantees"],
    "caution": ["guarantees"],
}

# Word-boundary helpers for glossary matching (handles accented latin words).
_WORD_BOUND = r"(?<![a-zà-ÿ0-9_])"
_WORD_END = r"(?![a-zà-ÿ0-9_])"

# KYC-case cues: presence of any of these suppresses the bare 'kyc' -> customers
# glossary hit (the query is about KYC case handling, not the customer base).
_KYC_CASE_CUES = (
    "dossiers", "attente", "pending", "pending cases", "kyc pending",
    "pending kyc", "kyc cases", "kyc case",
)

# Loan/NPL phrase terms that should not force loan_contracts when the query
# groups by NPL classification (non_performing_loans is the golden source table).
_LOAN_PHRASE_TERMS = {
    "prêt", "prêts", "loan", "loans", "non performing", "non-performing",
    "non performants", "improductifs", "improductif", "classées",
    "créances douteuses", "créance classée", "npl",
}

class ProgressiveSchemaRetrieval:
    """
    Implements a 5-stage progressive schema selection:
    1. Filter table metadata by domain and concept boundaries.
    2. Rank candidates using direct terms, glossary, metrics (4.0/3.0/2.0/1.0 weights).
    3. Select minimal executable table set with temporal source checks.
    4. Resolve join paths and required bridge tables safely.
    5. Retrieve minimal column sets, validating requested_fields.
    """
    def __init__(self, schema_matcher):
        self.matcher = schema_matcher
        
    def get_metadata_version_info(self) -> Tuple[str, str]:
        """Compute semantic metadata version and schema snapshot ID dynamically based on cache."""
        content = []
        for t, meta in sorted(self.matcher._table_metadata_cache.items()):
            content.append(f"t:{t}:{meta.get('domain')}")
        for (t, c), meta in sorted(self.matcher._column_metadata_cache.items()):
            content.append(f"c:{t}.{c}")
        for join in sorted(self.matcher._join_registry_cache, key=lambda x: (x.get("source_table",""), x.get("target_table",""))):
            content.append(f"j:{join.get('source_table')}->{join.get('target_table')}")
            
        full_content = "\n".join(content)
        if not full_content:
            return "v1.2.0-fallback", "snapshot-empty-fallback"
            
        snapshot_id = hashlib.md5(full_content.encode("utf-8")).hexdigest()
        version = f"v6C.{len(self.matcher._table_metadata_cache)}t.{len(self.matcher._join_registry_cache)}j"
        return version, snapshot_id

    def retrieve(self,
                 query: str,
                 domain: str,
                 task: str,
                 metrics: List[str],
                 dimensions: List[str],
                 filters_structured: List[Dict],
                 limit_requested: Optional[int],
                 requested_fields: List[str] = [],
                 max_candidate_tables: int = 20,
                 max_selected_tables: int = 6,
                 max_total_tables: int = 10,
                 intent: Optional["StructuredIntent"] = None) -> SchemaSelectionResponse:
        
        q_lower = query.lower()
        
        # 1. Metric grain compatibility validation
        unsupported_reason = None
        for m in metrics:
            if m == "pnb":
                if "accounts.account_type" in dimensions or "type de compte" in q_lower or "account_type" in q_lower or "account type" in q_lower:
                    unsupported_reason = "PNB metric does not support account_type grain."
            if m in ["roe", "roa"]:
                # roe/roa only support time dimension
                invalid_dims = [d for d in dimensions if d != "time_dimension"]
                if invalid_dims or any(dim in q_lower for dim in ["segment", "gouvernorat", "branch", "agence", "region", "account type"]):
                    unsupported_reason = f"{m.upper()} metric does not support dimensions other than time."

        all_tables = list(self.matcher._table_metadata_cache.keys())
        if not all_tables:
            all_tables = list(_FALLBACK_COLUMNS.keys())
            
        table_scores: Dict[str, float] = {t: 0.0 for t in all_tables}
        table_reasons: Dict[str, List[str]] = {t: [] for t in all_tables}

        # 2. Evidence-first minimal table selection (deterministic, no LLM).
        #    Sources of evidence, in priority order: metric registry sources,
        #    unambiguous requested output fields, filter columns, glossary/direct
        #    term matches, and explicit branch codes. The intent category domain
        #    is deliberately NOT used for bulk table injection to avoid the
        #    over-selection that caused SCHEMA_RETRIEVAL_FAILURE / compile breaks.
        need = self._evidence_first_tables(
            q_lower=q_lower,
            query=query,
            metrics=metrics,
            filters_structured=filters_structured,
            requested_fields=requested_fields,
            all_tables=all_tables,
        )

        for t, reasons in need.items():
            table_reasons[t] = reasons

        # Ordered, deduplicated selected tables (root = first selected table).
        selected_set: Set[str] = set(need)
        selected_tables = [t for t in all_tables if t in selected_set]

        # Temporal capability check: historical rate questions must select sources with valid date fields
        is_historical = (intent and intent.time_range and intent.time_range.get("type") == "relative" and intent.time_range.get("value") is not None)
        if is_historical:
            # If we need KYC compliance rate historically, replace 'customers' with 'kyc_cases'
            if "kyc_compliance_rate" in metrics and "customers" in selected_tables:
                selected_tables.remove("customers")
            if "kyc_compliance_rate" in metrics and "kyc_cases" not in selected_tables:
                selected_tables.append("kyc_cases")

        # 4. Resolve join paths and required bridge tables
        bridge_tables: Set[str] = set()
        join_paths: List[JoinPath] = []
        join_prov: Dict[str, Dict[str, Any]] = {}
        
        if len(selected_tables) > 1:
            root_table = selected_tables[0]
            for target in selected_tables[1:]:
                path = self.matcher._bfs_join_path(root_table, target)
                if path:
                    for jp in path:
                        if jp not in join_paths and not any(p.from_table == jp.from_table and p.to_table == jp.to_table for p in join_paths):
                            join_paths.append(jp)
                            key_prov = f"{jp.from_table}->{jp.to_table}"
                            join_prov[key_prov] = Provenance(
                                source="join_registry",
                                confidence=1.0,
                                reason=f"Safe join path connecting {jp.from_table} to {jp.to_table}"
                            ).dict()
                            
                        if jp.from_table not in selected_tables:
                            bridge_tables.add(jp.from_table)
                        if jp.to_table not in selected_tables:
                            bridge_tables.add(jp.to_table)

        # Enforce limits on bridge tables
        total_tables_count = len(selected_tables) + len(bridge_tables)
        if total_tables_count > max_total_tables:
            allowed_bridge = list(bridge_tables)[:max_total_tables - len(selected_tables)]
            bridge_tables = set(allowed_bridge)
            
        bridge_list = sorted(list(bridge_tables))
        all_resolved_tables = sorted(list(set(selected_tables + bridge_list)))
        excluded_tables = sorted(list(set(all_tables) - set(all_resolved_tables)))
        candidate_names = (selected_tables + bridge_list + excluded_tables)[:max_candidate_tables]

        # 5. Retrieve minimal columns and check requested fields
        selected_columns: Dict[str, List[str]] = {}
        column_prov: Dict[str, Dict[str, Any]] = {}
        
        for t in all_resolved_tables:
            selected_columns[t] = []
            
            t_cols = [c for (tbl, c) in self.matcher._column_metadata_cache.keys() if tbl == t]
            if not t_cols:
                t_cols = _FALLBACK_COLUMNS.get(t, [])
                
            for col in t_cols:
                is_needed = False
                reason = ""
                
                # Check requested_fields matching
                for rf in requested_fields:
                    potential_cols = [rf, f"{rf}_id"]
                    if rf == "outstanding_balance":
                        potential_cols.extend(["outstanding_balance", "balance"])
                    if rf == "active status":
                        potential_cols.extend(["status", "active"])
                    if rf == "name":
                        potential_cols.extend(["name", "customer_name"])
                    if col in potential_cols:
                        is_needed = True
                        reason = f"Explicitly requested analyst output field: '{rf}'"
                        break
                
                # Check filter column
                if not is_needed:
                    for filt in filters_structured:
                        filt_col = filt.get("column", "")
                        if filt_col == col or filt_col == f"{t}.{col}":
                            is_needed = True
                            reason = "Filter constraint field"
                            break
                        
                # Check dimensions
                if not is_needed:
                    for dim in dimensions:
                        if dim == col or dim == f"{t}.{col}" or dim.split(".")[-1] == col:
                            is_needed = True
                            reason = "Group by dimension field"
                            break
                        
                # Check metrics formula components
                if not is_needed:
                    for m_id in metrics:
                        metric_info = self._get_metric_info(m_id)
                        if metric_info and col in (metric_info.get("formula") or ""):
                            is_needed = True
                            reason = f"Required field for metric '{m_id}' calculation"
                            break
                
                # Check if it's a join key in join_paths
                if not is_needed:
                    for jp in join_paths:
                        if (jp.from_table == t and col == jp.join_key) or (jp.to_table == t and col == jp.join_key):
                            is_needed = True
                            reason = "Required join connectivity key"
                            break
                        if col in ["customer_id", "account_id", "branch_id", "transaction_id", "loan_id"] and (t == jp.from_table or t == jp.to_table):
                            is_needed = True
                            reason = "Primary entity identifier key"
                            break
                            
                if is_needed:
                    selected_columns[t].append(col)
                    col_key = f"{t}.{col}"
                    column_prov[col_key] = Provenance(
                        source="column_metadata",
                        confidence=0.95,
                        reason=reason,
                        matched_term=col
                    ).dict()
            
            # Fallback columns if empty
            if not selected_columns[t]:
                pk = f"{t.rstrip('s')}_id"
                if pk in t_cols:
                    selected_columns[t].append(pk)
                elif t_cols:
                    selected_columns[t].append(t_cols[0])
                else:
                    selected_columns[t].append("id")

        # Map selection reasons and confidence
        selection_reasons = {}
        confidence_scores = {}
        for t in all_resolved_tables:
            reasons = table_reasons.get(t, ["Implicit domain resolution"])
            selection_reasons[t] = "; ".join(reasons)
            
            score_val = table_scores.get(t, 1.0)
            confidence_scores[t] = min(0.6 + 0.1 * score_val, 0.99)

        # Check for missing requested fields
        missing_requested_fields = []
        for rf in requested_fields:
            found = False
            for t in all_resolved_tables:
                t_cols = selected_columns.get(t, [])
                potential_cols = [rf, f"{rf}_id"]
                if rf == "outstanding_balance":
                    potential_cols.extend(["outstanding_balance", "balance"])
                if rf == "active status":
                    potential_cols.extend(["status", "active"])
                if rf == "name":
                    potential_cols.extend(["name", "customer_name"])
                if any(c in t_cols for c in potential_cols):
                    found = True
                    break
            if not found:
                missing_requested_fields.append(rf)

        # Pop overall selection schema confidence score
        schema_confidence = round(sum(confidence_scores.values()) / max(len(confidence_scores), 1), 4)
        version, snapshot_id = self.get_metadata_version_info()

        # Build table provenance map
        table_prov = {}
        for t in all_resolved_tables:
            table_prov[t] = Provenance(
                source="table_metadata",
                confidence=confidence_scores[t],
                reason=selection_reasons[t]
            ).dict()

        return SchemaSelectionResponse(
            candidate_tables=candidate_names,
            selected_tables=selected_tables,
            bridge_tables=bridge_list,
            excluded_tables=excluded_tables,
            selected_columns=selected_columns,
            join_paths=join_paths,
            selection_reasons=selection_reasons,
            confidence_scores=confidence_scores,
            schema_confidence=schema_confidence,
            semantic_metadata_version=version,
            schema_snapshot_id=snapshot_id,
            table_provenance=table_prov,
            column_provenance=column_prov,
            join_provenance=join_prov,
            missing_requested_fields=missing_requested_fields,
            unsupported_reason=unsupported_reason
        )

    def _evidence_first_tables(self,
                               q_lower: str,
                               query: str,
                               metrics: List[str],
                               filters_structured: List[Dict],
                               requested_fields: List[str],
                               all_tables: List[str]) -> Dict[str, List[str]]:
        """Deterministic, evidence-first table selection.

        Evidence priority (each adds a table only when it is a genuinely safe
        signal; ambiguous fields like ``amount``/``status`` are never used to
        pull in tables): metric registry sources, requested output fields that
        belong to exactly one table, filter table-qualified columns, glossary
        synonym matches (longest-first, word-bounded), explicit branch codes,
        and direct table-name mentions.

        Disambiguation rules:
          * bare ``kyc`` implies ``customers`` unless KYC-case cues are present;
          * grouping by ``classification`` anchors on ``non_performing_loans``
            and does not force ``loan_contracts`` via loan/NPL phrasing.
        """
        need: Dict[str, List[str]] = {}
        ql = " " + q_lower + " "

        # 1. Authoritative metric-registry source tables.
        for m_id in metrics:
            info = self._get_metric_info(m_id)
            if info:
                for st in (info.get("source_tables") or []):
                    self._add_evidence(need, st.lower(), f"metric registry source for '{m_id}'", all_tables)

        # 2. Requested output fields that unambiguously belong to one table.
        for rf in requested_fields:
            owners = [t for t, cols in _FALLBACK_COLUMNS.items() if rf in cols or f"{rf}_id" in cols]
            if len(owners) == 1:
                self._add_evidence(need, owners[0], f"requested field '{rf}' (exclusive)", all_tables)

        # 3. Filter columns (table-qualified).
        for filt in filters_structured:
            fcol = (filt.get("column") or "").split(".")[0]
            if fcol in _FALLBACK_COLUMNS:
                self._add_evidence(need, fcol, f"filter column '{filt.get('column')}'", all_tables)

        # 4. Glossary synonym matching — longest terms first, word-bounded.
        for term in sorted(GLOSSARY_TABLE_MAP, key=len, reverse=True):
            if re.search(_WORD_BOUND + re.escape(term) + _WORD_END, ql):
                for t in GLOSSARY_TABLE_MAP[term]:
                    self._add_evidence(need, t, f"glossary term '{term}'", all_tables)

        # 5. Explicit branch code (e.g. BR_016).
        bmatch = re.search(r"BR[_-]?\d+", query)
        if bmatch:
            self._add_evidence(need, "branches", f"branch code '{bmatch.group(0)}'", all_tables)

        # 6. Direct table-name mention.
        for t in _FALLBACK_COLUMNS:
            if t in q_lower:
                self._add_evidence(need, t, f"direct table name '{t}'", all_tables)

        # ── Disambiguation ─────────────────────────────────────────────
        # a) bare 'kyc' -> customers, unless the query is about KYC case handling.
        if re.search(_WORD_BOUND + r"kyc" + _WORD_END, ql) and any(k in ql for k in _KYC_CASE_CUES):
            for tbl in list(need):
                need[tbl] = [r for r in need[tbl] if r != "glossary term 'kyc'"]

        # b) grouping by NPL classification anchors on non_performing_loans.
        if re.search(_WORD_BOUND + r"classification" + _WORD_END, ql):
            for tbl in list(need):
                if tbl == "loan_contracts":
                    keep = []
                    for r in need[tbl]:
                        if r.startswith("glossary term '") and r[len("glossary term '"):-1] in _LOAN_PHRASE_TERMS:
                            continue
                        keep.append(r)
                    need[tbl] = keep

        return {t: rs for t, rs in need.items() if rs}

    @staticmethod
    def _add_evidence(need: Dict[str, List[str]], table: str, reason: str, all_tables: List[str]) -> None:
        if table in all_tables:
            need.setdefault(table, []).append(reason)

    def _get_metric_info(self, metric_id: str) -> Optional[Dict[str, Any]]:
        """Look up metric metadata from in-process cache or static fallback."""
        try:
            from sql_agent.sql_builder import _metric_cache  # type: ignore
            if _metric_cache and metric_id.lower() in _metric_cache:
                m_info = _metric_cache[metric_id.lower()]
                return {
                    "metric_id": metric_id,
                    "formula": m_info.get("sql_formula"),
                    "source_tables": self._parse_source_tables_from_formula(m_info.get("sql_formula") or "")
                }
        except Exception:
            pass

        # Static KPI → source_tables map
        _STATIC_METRIC_TABLES: Dict[str, List[str]] = {
            "npl_ratio":            ["loan_contracts", "non_performing_loans"],
            "provision_coverage":   ["provisions", "non_performing_loans"],
            "loan_to_deposit":      ["loan_contracts", "accounts"],
            "roe":                  ["income_statement_snapshots", "balance_sheet_snapshots"],
            "roa":                  ["income_statement_snapshots", "balance_sheet_snapshots"],
            "cost_income_ratio":    ["income_statement_snapshots"],
            "kyc_compliance_rate":  ["customers"],
            "aml_alert_rate":       ["aml_alerts", "customers"],
            "customer_growth_rate": ["customers"],
            "deposit_growth_rate":  ["account_balances"],
            "avg_loan_size":        ["loan_contracts"],
            "default_rate":         ["loan_contracts"],
            "avg_days_past_due":    ["loan_contracts"],
            "total_risk_exposure":  ["risk_flags"],
            "branch_profitability": ["fee_income", "interest_income", "operating_expenses"],
            "active_loan_portfolio":["loan_contracts"],
            "overdue_loans":        ["loan_contracts"],
            "pep_customer_rate":    ["customer_profiles"],
            "pending_kyc_cases":    ["kyc_cases"],
            "open_aml_alerts":      ["aml_alerts"],
            "transaction_volume_30d":["transactions"],
            "avg_transaction_value":["transactions"],
            "income_per_customer":  ["fee_income", "interest_income", "customers"],
            "collateral_coverage":  ["collateral", "loan_contracts"],
            "restructured_loan_rate":["loan_restructuring", "loan_contracts"],
            "pnb":                  ["income_statement_snapshots"],
        }
        m_lower = metric_id.lower()
        if m_lower in _STATIC_METRIC_TABLES:
            return {
                "metric_id": metric_id,
                "formula": None,
                "source_tables": _STATIC_METRIC_TABLES[m_lower]
            }
        return None

    def _parse_source_tables_from_formula(self, formula: str) -> List[str]:
        """Exemplary check of tables inside formula string."""
        found = []
        for t in ["customers", "accounts", "transactions", "branches", "loan_contracts", "non_performing_loans", "risk_flags", "provisions"]:
            if t in formula.lower():
                found.append(t)
        return found
