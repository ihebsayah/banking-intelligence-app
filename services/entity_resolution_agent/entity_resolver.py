"""
services/entity_resolution_agent/entity_resolver.py
Core resolution logic — finds primary key + builds join paths.

Phase 6B: When SEMANTIC_LAYER_ENABLED=True, normalizes entity synonyms via
business_glossary and discovers join paths via BFS over join_registry.
Falls back to hardcoded SEMANTIC_JOIN_MAP when flag is off or DB unavailable.
"""
import logging
import os
from collections import deque
from typing import List, Dict, Optional, Tuple

from models import EntityResolutionRequest, EntityResolutionResponse, JoinPath
from semantic_id_mapper import (
    get_primary_key,
    get_primary_table,
    get_tables_containing_key,
    find_join_key,
)

logger = logging.getLogger(__name__)

SEMANTIC_LAYER_ENABLED = os.getenv("SEMANTIC_LAYER_ENABLED", "false").lower() == "true"


# ──────────────────────────────────────────────────────────────────────────────
# In-memory caches (populated once at startup when semantic layer is active)
# ──────────────────────────────────────────────────────────────────────────────
_glossary_cache: Dict[str, str] = {}     # synonym_term → canonical_term
_join_graph: Dict[str, List[dict]] = {}  # table → [{to_table, join_key, condition, join_type}]
_cache_ready: bool = False

# Sensitive log and compliance tables that are excluded from auto-reversal
SENSITIVE_LOG_TABLES = {
    "audit_log", "user_activity_log", "compliance_events", "compliance_rules",
    "compliance_violations", "compliance_cases", "compliance_reviews", "regulatory_reports"
}


def initialize_entity_cache(db_conn) -> None:
    """
    Load business_glossary synonyms + join_registry graph into memory.
    Called once at startup when SEMANTIC_LAYER_ENABLED is True.
    Must be idempotent — safe to call multiple times.
    Cache ready=True ONLY if both glossary and join graph are non-empty.
    """
    global _glossary_cache, _join_graph, _cache_ready
    if _cache_ready:
        return
    try:
        with db_conn.cursor() as cur:
            # --- business_glossary: build synonym → canonical map ---
            # ponytail: no is_active column in schema — load all rows
            cur.execute(
                "SELECT term, synonyms FROM business_glossary"
            )
            glossary: Dict[str, str] = {}
            for row in cur.fetchall():
                canonical = row[0].lower()
                synonyms = row[1] or []
                glossary[canonical] = canonical          # canonical resolves to itself
                for syn in synonyms:
                    glossary[syn.lower()] = canonical
            _glossary_cache = glossary

            # --- join_registry: build adjacency graph ---
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

                # Check confidence threshold
                if conf_idx != -1 and row[conf_idx] is not None:
                    if float(row[conf_idx]) < 0.8:
                        continue

                jtype = row[jtype_idx] if jtype_idx != -1 else "LEFT JOIN"
                if not jtype:
                    jtype = "LEFT JOIN"

                cond = f"{from_t}.{key} = {to_t}.{target_col}"

                is_bidirectional = True
                if bidir_idx != -1 and row[bidir_idx] is not None:
                    is_bidirectional = bool(row[bidir_idx])

                # Apply sensitive tables policy
                if from_t in SENSITIVE_LOG_TABLES or to_t in SENSITIVE_LOG_TABLES:
                    is_bidirectional = False

                graph.setdefault(from_t, []).append(
                    {"to_table": to_t, "join_key": key, "condition": cond, "join_type": jtype}
                )
                if is_bidirectional:
                    # Construct reverse condition
                    rev_cond = f"{to_t}.{target_col} = {from_t}.{key}"
                    graph.setdefault(to_t, []).append(
                        {"to_table": from_t, "join_key": target_col, "condition": rev_cond, "join_type": jtype}
                    )
            _join_graph = graph

        # Cache ready ONLY if minimum metadata present — prevents silent empty-cache mode
        if not _glossary_cache:
            logger.warning(
                "[EntityResolver] business_glossary is empty — semantic cache NOT ready; falling back to legacy"
            )
            _cache_ready = False
            return
        if not _join_graph:
            logger.warning(
                "[EntityResolver] join_registry has no entries — semantic cache NOT ready; falling back to legacy"
            )
            _cache_ready = False
            return

        _cache_ready = True
        logger.info(
            "[EntityResolver] Semantic cache ready: %d glossary terms, %d join graph nodes",
            len(_glossary_cache), len(_join_graph)
        )
    except Exception as exc:
        logger.warning("[EntityResolver] Semantic cache init failed — using hardcoded fallback: %s", exc)
        _cache_ready = False


def _normalize_entity(entity: str) -> str:
    """Resolve a user entity term to its canonical form via glossary."""
    lower = entity.lower()
    return _glossary_cache.get(lower, lower)


def _bfs_join_path(start: str, end: str) -> Optional[List[dict]]:
    """
    BFS over _join_graph to find shortest safe join path from start to end.
    Returns ordered list of join steps, or None if no path found.
    """
    if start == end:
        return []
    visited = {start}
    # queue: (current_node, path_so_far)
    queue: deque = deque([(start, [])])
    while queue:
        node, path = queue.popleft()
        # Limit BFS search depth: MAX_JOIN_PATH_DEPTH = 3.
        # len(path) is the number of edges. If it's already 3 edges, do not expand.
        if len(path) >= 3:
            continue
        for edge in _join_graph.get(node, []):
            nxt = edge["to_table"]
            if nxt in visited:
                continue
            new_path = path + [edge]
            if nxt == end:
                return new_path
            visited.add(nxt)
            queue.append((nxt, new_path))
    return None


class EntityResolver:
    """
    Resolves entity relationships and builds semantic join structures.

    When SEMANTIC_LAYER_ENABLED=True:
      - Normalizes entity names via business_glossary cache
      - Discovers join paths via BFS over join_registry graph
      - Returns structured error (no joins invented) if no safe path exists

    When SEMANTIC_LAYER_ENABLED=False (default):
      - Falls through to hardcoded SEMANTIC_JOIN_MAP logic (unchanged)
    """

    def resolve(self, request: EntityResolutionRequest) -> EntityResolutionResponse:
        entity_raw = request.primary_entity.lower()
        tables = [t.lower() for t in request.tables]

        # ── Semantic layer path ──────────────────────────────────────────────
        if SEMANTIC_LAYER_ENABLED and _cache_ready:
            return self._resolve_semantic(entity_raw, tables)

        # ── Legacy hardcoded path (unchanged behavior) ───────────────────────
        return self._resolve_legacy(entity_raw, tables)

    # ─────────────────────────────────────────────────────────────────────────
    # Semantic resolution (Phase 6B)
    # ─────────────────────────────────────────────────────────────────────────
    def _resolve_semantic(self, entity_raw: str, tables: List[str]) -> EntityResolutionResponse:
        entity = _normalize_entity(entity_raw)
        primary_key = get_primary_key(entity)
        primary_table = get_primary_table(entity)
        tables_with_key = get_tables_containing_key(primary_key, tables)
        join_targets = [t for t in tables if t != primary_table]

        join_paths: List[JoinPath] = []
        warnings: List[str] = []

        for target in join_targets:
            path = _bfs_join_path(primary_table, target)
            if path is None:
                warnings.append(
                    f"No safe join path in join_registry from '{primary_table}' to '{target}' — skipped"
                )
                logger.warning(
                    "[EntityResolver] No safe join path: %s → %s",
                    primary_table, target
                )
                continue
            for step in path:
                join_paths.append(JoinPath(
                    from_table=step.get("from_table", primary_table),
                    to_table=step["to_table"],
                    join_key=step["join_key"],
                    join_type=step.get("join_type", "INNER JOIN"),
                    condition=step["condition"],
                ))

        if warnings:
            notes = (
                f"Semantic resolution from '{primary_table}'. Warnings: " + "; ".join(warnings)
            )
        else:
            notes = (
                f"Semantic resolution: {len(join_paths)} join(s) from '{primary_table}'."
                if join_paths else f"Single table '{primary_table}' — no joins needed."
            )

        logger.info(
            "[EntityResolver][semantic] entity=%s pk=%s joins=%d warnings=%d",
            entity, primary_key, len(join_paths), len(warnings)
        )

        return EntityResolutionResponse(
            primary_entity=entity,
            primary_key=primary_key,
            primary_table=primary_table,
            tables_containing_entity=tables_with_key,
            join_structure=join_paths,
            resolution_confidence=1.0 if not warnings else 0.8,
            notes=notes,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Legacy hardcoded resolution (original behavior, preserved exactly)
    # ─────────────────────────────────────────────────────────────────────────
    def _resolve_legacy(self, entity: str, tables: List[str]) -> EntityResolutionResponse:
        primary_key = get_primary_key(entity)
        primary_table = get_primary_table(entity)
        tables_with_key = get_tables_containing_key(primary_key, tables)
        join_targets = [t for t in tables if t != primary_table]

        if primary_table not in tables:
            logger.warning(
                "primary_table '%s' not in requested tables %s — proceeding anyway",
                primary_table, tables
            )

        if "products" in join_targets and "accounts" not in join_targets and primary_table != "accounts":
            join_targets.append("accounts")

        join_paths: List[JoinPath] = []
        for target in join_targets:
            if target == "products":
                join_paths.append(JoinPath(
                    from_table="accounts",
                    to_table="products",
                    join_key="account_type",
                    join_type="LEFT JOIN",
                    condition="accounts.account_type = products.category",
                ))
                continue
            join_key = find_join_key(primary_table, target) or primary_key
            condition = f"{primary_table}.{join_key} = {target}.{join_key}"
            join_paths.append(JoinPath(
                from_table=primary_table,
                to_table=target,
                join_key=join_key,
                join_type="LEFT JOIN",
                condition=condition,
            ))

        notes = (
            f"Single table '{primary_table}' — no joins needed."
            if not join_paths
            else f"Resolved {len(join_paths)} join(s) from '{primary_table}'."
        )

        logger.info(
            "Entity resolution: entity=%s pk=%s joins=%d",
            entity, primary_key, len(join_paths)
        )

        return EntityResolutionResponse(
            primary_entity=entity,
            primary_key=primary_key,
            primary_table=primary_table,
            tables_containing_entity=tables_with_key,
            join_structure=join_paths,
            resolution_confidence=1.0,
            notes=notes,
        )
