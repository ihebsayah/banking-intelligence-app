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
    "customer_analysis":    ["customers"],
    "account_analysis":     ["accounts"],
    "risk_analysis":        ["risk_flags"],
    "revenue_analysis":     ["products"],
    "operational_analysis": ["transactions"],
    "geographic_analysis":  ["branches"],
    "product_analysis":     ["products"],
    "compliance_analysis":  ["risk_flags"],
    "transaction_analysis": ["transactions"],
    "branch_analysis":      ["branches"],
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
    "customers":            ["segment", "kyc_verified", "risk_score", "name", "email", "phone"],
    "accounts":             ["account_type", "status", "balance", "currency"],
    "transactions":         ["transaction_type", "status", "amount", "transaction_date"],
    "risk_flags":           ["flag_type", "severity", "resolved"],
    "products":             ["name", "category"],
    "branches":             ["state", "city", "name"],
}

# ── Hardcoded join graph (source → list of join specs) ────────────────────────

JoinSpec = Dict  # {"to": str, "key": str, "type": str}

JOIN_GRAPH: Dict[str, List[JoinSpec]] = {
    "customers": [
        {"to": "accounts",          "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "risk_flags",        "key": "customer_id",    "type": "LEFT JOIN"},
        {"to": "transactions",      "key": "customer_id",    "type": "LEFT JOIN"},
    ],
    "accounts": [
        {"to": "transactions",      "key": "account_id",     "type": "LEFT JOIN"},
        {"to": "customers",         "key": "customer_id",    "type": "INNER JOIN"},
        {"to": "branches",          "key": "branch_id",      "type": "LEFT JOIN"},
    ],
    "transactions": [
        {"to": "accounts",          "key": "account_id",     "type": "INNER JOIN"},
        {"to": "customers",         "key": "customer_id",    "type": "INNER JOIN"},
    ],
    "branches": [
        {"to": "accounts",          "key": "branch_id",      "type": "LEFT JOIN"},
    ],
    "products": [],
    "risk_flags": [
        {"to": "customers",         "key": "customer_id",    "type": "INNER JOIN"},
    ]
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
        joined_tables: set = {primary_table}

        def _add(from_t: str) -> None:
            for spec in JOIN_GRAPH.get(from_t, []):
                to_t = spec["to"]
                if to_t in table_set and to_t not in joined_tables:
                    joined_tables.add(to_t)
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
