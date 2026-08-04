"""
services/schema_agent/schema_matcher.py

Pattern-based and semantic-layer-based domain/table/join mappings.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Any
import sys
import os

_schema_agent_dir = os.path.dirname(os.path.abspath(__file__))
if _schema_agent_dir not in sys.path:
    sys.path.insert(0, _schema_agent_dir)

import models as _svc_models  # noqa: E402 — always schema_agent/models.py

JoinPath = _svc_models.JoinPath
SchemaSelectionResponse = _svc_models.SchemaSelectionResponse

logger = logging.getLogger(__name__)

# ── Fallback Intent → Domains ─────────────────────────────────────────────────

INTENT_TO_DOMAINS: Dict[str, List[str]] = {
    "customer_analysis":    ["customer_analysis", "account_analysis", "customer"],
    "risk_analysis":        ["risk_analysis", "customer_analysis", "risk", "loan"],
    "revenue_analysis":     ["revenue_analysis", "account_analysis", "finance"],
    "operational_analysis": ["operational_analysis", "transaction_analysis", "payment"],
    "geographic_analysis":  ["geographic_analysis", "branch_analysis", "organization"],
    "product_analysis":     ["product_analysis", "revenue_analysis", "product"],
    "compliance_analysis":  ["compliance_analysis", "risk_analysis", "compliance", "kyc"],
    "transaction_analysis": ["transaction_analysis", "account_analysis", "payment"],
    "loan_analysis":        ["loan", "risk"],
    "kyc_analysis":         ["kyc", "compliance"],
    "aml_analysis":         ["compliance", "risk"],
    "profitability_analysis": ["finance"],
    "liquidity_analysis":   ["liquidity", "finance"]
}

# ── Fallback Domains → Tables ──────────────────────────────────────────────────

DOMAIN_TO_TABLES: Dict[str, List[str]] = {
    "customer_analysis":    ["customers"],
    "account_analysis":     ["accounts"],
    "risk_analysis":        ["risk_flags"],
    "revenue_analysis":     ["customers", "accounts", "transactions", "branches"],
    "operational_analysis": ["transactions"],
    "geographic_analysis":  ["branches"],
    "product_analysis":     ["products"],
    "compliance_analysis":  ["risk_flags", "kyc_cases", "compliance_violations"],
    "transaction_analysis": ["transactions"],
    "branch_analysis":      ["branches"],
}

# ── Fallback Entity → primary key ──────────────────────────────────────────────

PRIMARY_ENTITY_KEYS: Dict[str, str] = {
    "customer":    "customer_id",
    "account":     "account_id",
    "transaction": "transaction_id",
    "branch":      "branch_id",
    "product":     "product_id",
    "region":      "region_id",
}

# ── Fallback Table → filtering columns ─────────────────────────────────────────

TABLE_FILTER_COLUMNS: Dict[str, List[str]] = {
    "customers":            ["segment", "kyc_verified", "risk_score", "name", "email", "phone"],
    "accounts":             ["account_type", "status", "balance", "currency"],
    "transactions":         ["transaction_type", "status", "amount", "transaction_date"],
    "risk_flags":           ["flag_type", "severity", "resolved"],
    "products":             ["name", "category"],
    "branches":             ["state", "city", "name"],
}

# ── Fallback join graph (source → list of join specs) ────────────────────────

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

    def __init__(self, db=None, semantic_layer_enabled=False):
        self._db = db
        self._semantic_layer_enabled = semantic_layer_enabled
        self._table_metadata_cache: Dict[str, Dict[str, Any]] = {}
        self._column_metadata_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._join_registry_cache: List[Dict[str, Any]] = []
        self._is_initialized = False
        
        # Phase 6C Progressive Schema Selection
        import sys as _sys, os as _os
        _dir = _os.path.dirname(_os.path.abspath(__file__))
        if _dir not in _sys.path:
            _sys.path.insert(0, _dir)
        from progressive_schema import ProgressiveSchemaRetrieval
        self.progressive_retriever = ProgressiveSchemaRetrieval(self)

    def progressive_map(self,
                         query: str,
                         domain: str,
                         task: str,
                         metrics: List[str],
                         dimensions: List[str],
                         filters_structured: List[Dict],
                         limit_requested: Optional[int],
                         intent: Optional["StructuredIntent"] = None,
                         requested_fields: Optional[List[str]] = None,
                         max_candidate_tables: int = 20,
                         max_selected_tables: int = 6,
                         max_total_tables: int = 10) -> SchemaSelectionResponse:
        """Execute progressive schema retrieval and minimal tables/columns selection."""
        # Backward compatibility: extract intent fields if intent not provided
        if intent is None:
            from intent_agent.structured_intent import build_structured_intent
            intent_dict = build_structured_intent(query=query)
            # Use dict as a duck-typed intent object
            intent = type('StructuredIntent', (), intent_dict)()
        
        return self.progressive_retriever.retrieve(
            query=query,
            domain=domain,
            task=task,
            metrics=metrics,
            dimensions=dimensions,
            filters_structured=filters_structured,
            limit_requested=limit_requested,
            requested_fields=requested_fields or [],
            max_candidate_tables=max_candidate_tables,
            max_selected_tables=max_selected_tables,
            max_total_tables=max_total_tables,
            intent=intent
        )


    async def initialize_db_cache(self) -> None:
        """Fetch all semantic metadata from database and cache in memory."""
        if not self._semantic_layer_enabled or not self._db:
            return
        try:
            tbl_rows = await self._db.fetch_all("SELECT * FROM table_metadata")
            self._table_metadata_cache = {r["table_name"].lower(): dict(r) for r in tbl_rows}

            col_rows = await self._db.fetch_all("SELECT * FROM column_metadata")
            self._column_metadata_cache = {
                (r["table_name"].lower(), r["column_name"].lower()): dict(r)
                for r in col_rows
            }

            join_rows = await self._db.fetch_all("SELECT * FROM join_registry")
            self._join_registry_cache = [dict(r) for r in join_rows]

            self._is_initialized = True
            logger.info(
                "SchemaMatcher cache initialized: %d tables, %d columns, %d joins",
                len(self._table_metadata_cache), len(self._column_metadata_cache), len(self._join_registry_cache)
            )
        except Exception as exc:
            logger.warning("Failed to populate SchemaMatcher DB cache: %s. Falling back to static mappings.", exc)

    def match_domains(self, intent_categories: List[str]) -> List[str]:
        """Map a list of intent categories to relevant database domains."""
        domains: set = set()
        for cat in intent_categories:
            domains.update(INTENT_TO_DOMAINS.get(cat, []))
        return sorted(domains)

    def get_tables(self, domains: List[str]) -> List[str]:
        """Return sorted, deduplicated table list for the given domains."""
        if self._semantic_layer_enabled and self._is_initialized:
            # Domain-based table selection
            matched = []
            for t_name, meta in self._table_metadata_cache.items():
                t_dom = meta.get("domain") or ""
                # Also support substring matching for domains
                if t_dom in domains or any(d in t_dom or t_dom in d for d in domains):
                    matched.append(t_name)
            if matched:
                return sorted(list(set(matched)))

        # Fallback
        tables: set = set()
        for domain in domains:
            tables.update(DOMAIN_TO_TABLES.get(domain, []))
        return sorted(tables)

    def get_table_enrichment(self, tables: List[str], intent_categories: List[str]) -> Tuple[Dict[str, str], Dict[str, float]]:
        """Compute table explanations and confidence scores based on semantic ranking."""
        explanations = {}
        confidence_scores = {}
        for t in tables:
            if self._semantic_layer_enabled and self._is_initialized and t in self._table_metadata_cache:
                meta = self._table_metadata_cache[t]
                desc = meta.get("business_description") or "Database table"
                explanations[t] = f"{desc} (Domain: {meta.get('domain')})"
                
                # Confidence score based on intent match
                score = 0.85
                t_dom = meta.get("domain") or ""
                for intent in intent_categories:
                    if t_dom in intent or intent in t_dom:
                        score = 1.0
                confidence_scores[t] = score
            else:
                explanations[t] = f"Fallback table mapping for {t}"
                confidence_scores[t] = 0.75
        return explanations, confidence_scores

    def get_key_columns(
        self,
        tables: List[str],
        primary_entity: Optional[str] = None,
    ) -> Dict:
        """Determine filtering columns and joining key for the given tables."""
        filtering: set = set()
        
        if self._semantic_layer_enabled and self._is_initialized:
            for (t_name, col_name), meta in self._column_metadata_cache.items():
                if t_name in tables:
                    filtering.add(col_name)
        else:
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
        """Build join paths from primary_table to all other tables."""
        if self._semantic_layer_enabled and self._is_initialized:
            join_paths = []
            for target in tables:
                if target == primary_table:
                    continue
                path = self._bfs_join_path(primary_table, target)
                if path:
                    join_paths.extend(path)
            return join_paths

        # Fallback
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

        _add(primary_table)
        for table in list(table_set - {primary_table}):
            _add(table)
        return paths

    # Sensitive log and compliance tables that are excluded from auto-reversal
    SENSITIVE_LOG_TABLES = {
        "audit_log", "user_activity_log", "compliance_events", "compliance_rules",
        "compliance_violations", "compliance_cases", "compliance_reviews", "regulatory_reports"
    }

    def _bfs_join_path(self, from_table: str, to_table: str) -> List[JoinPath]:
        """BFS graph traversal to discover the shortest join path using join_registry."""
        queue = [[from_table]]
        visited = {from_table}

        while queue:
            path = queue.pop(0)
            curr = path[-1]
            if curr == to_table:
                join_paths = []
                for i in range(len(path) - 1):
                    s = path[i]
                    t = path[i+1]
                    edge = self._find_edge(s, t)
                    if edge:
                        join_paths.append(JoinPath(
                            from_table=edge["source_table"],
                            to_table=edge["target_table"],
                            join_key=edge["source_column"],
                            join_type=edge.get("join_type", "LEFT JOIN")
                        ))
                return join_paths

            # Limit depth of search: MAX_JOIN_PATH_DEPTH = 3.
            # Number of joins (edges) is len(path) - 1. If it's already 3 joins, do not expand.
            if len(path) >= 4:
                continue

            # Neighbors
            for edge in self._join_registry_cache:
                src = edge["source_table"].lower()
                tgt = edge["target_table"].lower()
                
                # Check for bidirectional permission
                is_bidirectional = edge.get("is_bidirectional", True)
                if is_bidirectional is not False: # True or None or other truthy
                    if src in self.SENSITIVE_LOG_TABLES or tgt in self.SENSITIVE_LOG_TABLES:
                        is_bidirectional = False

                if src == curr and tgt not in visited:
                    visited.add(tgt)
                    queue.append(path + [tgt])
                elif tgt == curr and is_bidirectional and src not in visited:
                    visited.add(src)
                    queue.append(path + [src])
        return []

    def _find_edge(self, s: str, t: str) -> Optional[Dict[str, Any]]:
        for edge in self._join_registry_cache:
            src = edge["source_table"].lower()
            tgt = edge["target_table"].lower()
            
            is_bidirectional = edge.get("is_bidirectional", True)
            if is_bidirectional is not False:
                if src in self.SENSITIVE_LOG_TABLES or tgt in self.SENSITIVE_LOG_TABLES:
                    is_bidirectional = False
                    
            if src == s and tgt == t:
                return edge
            if src == t and tgt == s and is_bidirectional:
                return edge
        return None
