"""
services/schema_agent/schema_matcher.py

Hardcoded domain/table/join mappings for MVP.
No ML; pure lookup tables (fast, predictable, auditable).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from models import JoinPath

# ── Intent → Domains ─────────────────────────────────────────────────────────

INTENT_TO_DOMAINS: Dict[str, List[str]] = {
    "customer_analysis":    ["customer_analysis", "account_analysis"],
    "risk_analysis":        ["risk_analysis", "customer_analysis"],
    "revenue_analysis":     ["revenue_analysis", "account_analysis"],
    "operational_analysis": ["operational_analysis", "transaction_analysis"],
    "geographic_analysis":  ["geographic_analysis", "branch_analysis"],
    "product_analysis":     ["product_analysis", "revenue_analysis"],
    "compliance_analysis":  ["compliance_analysis", "risk_analysis"],
    "transaction_analysis": ["transaction_analysis", "account_analysis"],
}

# ── Domains → Tables ──────────────────────────────────────────────────────────

DOMAIN_TO_TABLES: Dict[str, List[str]] = {
    "customer_analysis":    ["customers", "customer_segments"],
    "account_analysis":     ["accounts", "account_types"],
    "risk_analysis":        ["risk_flags", "aml_flags", "fraud_detection", "credit_risk_scores"],
    "revenue_analysis":     ["fees", "commissions", "interest_income", "products"],
    "operational_analysis": ["transactions", "transaction_details"],
    "geographic_analysis":  ["regions", "branches", "branch_locations"],
    "product_analysis":     ["products"],
    "compliance_analysis":  ["kyc_status", "audit_logs", "regulatory_reports"],
    "transaction_analysis": ["transactions", "transaction_details"],
    "branch_analysis":      ["branches", "branch_locations", "branch_performance"],
}

# ── Entity → primary key ──────────────────────────────────────────────────────

PRIMARY_ENTITY_KEYS: Dict[str, str] = {
    "customer":    "customer_id",
    "account":     "account_id",
    "transaction": "transaction_id",
    "branch":      "branch_id",
    "product":     "product_id",
    "region":      "region_id",
}

# ── Table → filtering columns ─────────────────────────────────────────────────

TABLE_FILTER_COLUMNS: Dict[str, List[str]] = {
    "customers":            ["customer_segment", "kyc_verified", "risk_score", "country"],
    "customer_segments":    ["segment_name", "tier"],
    "accounts":             ["account_type", "status", "balance", "currency"],
    "account_types":        ["type_name", "product_category"],
    "transactions":         ["transaction_type", "status", "amount", "channel", "transaction_date"],
    "transaction_details":  ["detail_type", "value"],
    "risk_flags":           ["flag_type", "severity", "status", "created_at"],
    "aml_flags":            ["flag_category", "resolution_status"],
    "fraud_detection":      ["fraud_score", "case_status"],
    "credit_risk_scores":   ["pd_score", "lgd", "ead", "rating"],
    "fees":                 ["fee_type", "amount", "fee_date"],
    "commissions":          ["commission_type", "amount"],
    "interest_income":      ["product_type", "amount", "period"],
    "products":             ["product_name", "product_category", "status"],
    "branches":             ["state", "city", "region_id", "status"],
    "branch_locations":     ["address", "latitude", "longitude"],
    "branch_performance":   ["revenue", "customer_count", "headcount", "period"],
    "kyc_status":           ["verification_status", "last_verified_at"],
    "audit_logs":           ["action_type", "severity", "actor_id", "created_at"],
    "regulatory_reports":   ["report_type", "submission_status", "regulator"],
    "regions":              ["region_name", "country"],
}

# ── Hardcoded join graph (source → list of join specs) ────────────────────────

JoinSpec = Dict  # {"to": str, "key": str, "type": str}

JOIN_GRAPH: Dict[str, List[JoinSpec]] = {
    "customers": [
        {"to": "accounts",          "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "risk_flags",        "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "aml_flags",         "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "kyc_status",        "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "customer_segments", "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "credit_risk_scores","key": "customer_id",    "type": "LEFT JOIN"},
    ],
    "accounts": [
        {"to": "transactions",      "key": "account_id",     "type": "LEFT JOIN"},
        {"to": "account_types",     "key": "account_type_id","type": "INNER JOIN"},
        {"to": "fees",              "key": "account_id",     "type": "LEFT JOIN"},
        {"to": "interest_income",   "key": "account_id",     "type": "LEFT JOIN"},
    ],
    "transactions": [
        {"to": "accounts",          "key": "account_id",     "type": "INNER JOIN"},
        {"to": "transaction_details","key": "transaction_id","type": "LEFT JOIN"},
        {"to": "fraud_detection",   "key": "transaction_id", "type": "LEFT JOIN"},
    ],
    "branches": [
        {"to": "branch_locations",  "key": "branch_id",      "type": "LEFT JOIN"},
        {"to": "branch_performance","key": "branch_id",      "type": "LEFT JOIN"},
        {"to": "regions",           "key": "region_id",      "type": "INNER JOIN"},
    ],
    "products": [
        {"to": "accounts",          "key": "product_id",     "type": "LEFT JOIN"},
        {"to": "commissions",       "key": "product_id",     "type": "LEFT JOIN"},
    ],
}


class SchemaMatcher:
    """Maps intent categories → database domains → tables → join paths."""

    # ── Public API ────────────────────────────────────────────────────────────

    def match_domains(self, intent_categories: List[str]) -> List[str]:
        """Map a list of intent categories to relevant database domains."""
        domains: set = set()
        for cat in intent_categories:
            domains.update(INTENT_TO_DOMAINS.get(cat, []))
        return sorted(domains)

    def get_tables(self, domains: List[str]) -> List[str]:
        """Return sorted, deduplicated table list for the given domains."""
        tables: set = set()
        for domain in domains:
            tables.update(DOMAIN_TO_TABLES.get(domain, []))
        return sorted(tables)

    def get_key_columns(
        self,
        tables: List[str],
        primary_entity: Optional[str] = None,
    ) -> Dict:
        """Determine filtering columns and joining key for the given tables."""
        filtering: set = set()
        for table in tables:
            filtering.update(TABLE_FILTER_COLUMNS.get(table, []))

        entity = (primary_entity or "customer").lower()
        join_key = PRIMARY_ENTITY_KEYS.get(entity, "id")

        return {
            "filtering": sorted(filtering),
            "joining": [join_key],
        }

    def get_join_paths(
        self,
        tables: List[str],
        primary_table: str,
    ) -> List[JoinPath]:
        """
        Build join paths from primary_table to all other tables,
        traversing the static join graph (one-hop only for MVP).
        """
        table_set = set(tables)
        paths: List[JoinPath] = []
        visited: set = set()

        def _add(from_t: str) -> None:
            for spec in JOIN_GRAPH.get(from_t, []):
                to_t = spec["to"]
                edge  = (from_t, to_t)
                if to_t in table_set and edge not in visited:
                    visited.add(edge)
                    paths.append(JoinPath(
                        from_table=from_t,
                        to_table=to_t,
                        join_key=spec["key"],
                        join_type=spec["type"],
                    ))

        # Start from primary table
        _add(primary_table)

        # Then crawl one level deeper for reachable tables
        for table in list(table_set - {primary_table}):
            _add(table)

        return paths
