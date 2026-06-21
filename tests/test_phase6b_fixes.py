"""
tests/test_phase6b_fixes.py
Unit tests verifying Phase 6B critical production fixes:
1. BFS Depth limiting (max depth = 3 joins).
2. Metric formula sanitization whitelists and blocklists.
3. Directional join audits (sensitive logs/compliance tables are non-bidirectional).
"""
import sys
import os
import pytest
from unittest.mock import MagicMock

# Function to clean and set sys.path for a specific agent
def setup_agent_imports(agent_dir_name):
    agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", agent_dir_name))
    
    # Remove other agent paths from sys.path
    for d in ["sql_agent", "schema_agent", "entity_resolution_agent"]:
        other_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", d))
        if other_path in sys.path:
            sys.path.remove(other_path)
            
    # Add target path
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
        
    # Clear cached modules to force reload from the new path
    for m in ["models", "sql_builder", "schema_matcher", "entity_resolver"]:
        sys.modules.pop(m, None)


# ==========================================
# 1. SQL Agent: Formula Sanitization Tests
# ==========================================

@pytest.mark.parametrize("formula, expected_safe", [
    ("SUM(accounts.balance)", True),
    ("COUNT(CASE WHEN status = 'active' THEN 1 END)", True),
    ("AVG(risk_score) * 100", True),
    ("COALESCE(amount, 0.0) + 10", True),
    ("100.0 - (violations * 10.0)", True),
    # Dangerous commands
    ("SUM(balance); DROP TABLE users", False),
    ("SUM(balance) -- comment", False),
    ("AVG(risk_score) /* block comment */", False),
    ("AVG(risk_score) UNION SELECT * FROM users", False),
    ("DELETE FROM accounts", False),
    ("INSERT INTO logs VALUES(1)", False),
    # Disallowed functions
    ("UPPER(name)", False),
    ("SUBSTR(name, 1, 3)", False),
])
def test_formula_sanitization(formula, expected_safe):
    setup_agent_imports("sql_agent")
    from sql_builder import _sanitize_metric_formula
    is_safe, reason = _sanitize_metric_formula(formula)
    assert is_safe == expected_safe, f"Formula '{formula}' failed validation. Safe={is_safe}, Reason: {reason}"


# ==========================================
# 2. Schema Agent: Depth Limit & Directional Joins
# ==========================================

def test_schema_agent_bfs_depth_limit():
    setup_agent_imports("schema_agent")
    from schema_matcher import SchemaMatcher
    
    matcher = SchemaMatcher(semantic_layer_enabled=True)
    # Mock join registry with a chain of 4 hops: A -> B -> C -> D -> E
    matcher._join_registry_cache = [
        {"source_table": "table_a", "target_table": "table_b", "source_column": "id", "is_bidirectional": True},
        {"source_table": "table_b", "target_table": "table_c", "source_column": "id", "is_bidirectional": True},
        {"source_table": "table_c", "target_table": "table_d", "source_column": "id", "is_bidirectional": True},
        {"source_table": "table_d", "target_table": "table_e", "source_column": "id", "is_bidirectional": True},
    ]

    # BFS path A -> D (3 hops/joins) should succeed
    path_3 = matcher._bfs_join_path("table_a", "table_d")
    assert len(path_3) == 3

    # BFS path A -> E (4 hops/joins) should be empty due to MAX_JOIN_PATH_DEPTH = 3 limit
    path_4 = matcher._bfs_join_path("table_a", "table_e")
    assert len(path_4) == 0


def test_schema_agent_sensitive_directional_join():
    setup_agent_imports("schema_agent")
    from schema_matcher import SchemaMatcher
    
    matcher = SchemaMatcher(semantic_layer_enabled=True)
    # Jointure between customer and audit_log (sensitive)
    matcher._join_registry_cache = [
        {"source_table": "customers", "target_table": "audit_log", "source_column": "customer_id", "is_bidirectional": True}
    ]

    # Forward direction (customers -> audit_log) should work
    forward = matcher._bfs_join_path("customers", "audit_log")
    assert len(forward) == 1

    # Reverse direction (audit_log -> customers) should be blocked because audit_log is in SENSITIVE_LOG_TABLES
    reverse = matcher._bfs_join_path("audit_log", "customers")
    assert len(reverse) == 0


# ==========================================
# 3. Entity Resolution: Depth Limit & Directional Joins
# ==========================================

def test_entity_resolver_bfs_depth_limit():
    setup_agent_imports("entity_resolution_agent")
    import entity_resolver
    
    # Setup mock _join_graph with A -> B -> C -> D -> E
    entity_resolver._join_graph = {
        "table_a": [{"to_table": "table_b", "join_key": "id", "condition": "a=b", "join_type": "INNER JOIN"}],
        "table_b": [{"to_table": "table_c", "join_key": "id", "condition": "b=c", "join_type": "INNER JOIN"}],
        "table_c": [{"to_table": "table_d", "join_key": "id", "condition": "c=d", "join_type": "INNER JOIN"}],
        "table_d": [{"to_table": "table_e", "join_key": "id", "condition": "d=e", "join_type": "INNER JOIN"}],
    }

    # 3 hops (A -> D) should work
    path_3 = entity_resolver._bfs_join_path("table_a", "table_d")
    assert path_3 is not None
    assert len(path_3) == 3

    # 4 hops (A -> E) should fail due to cap of 3
    path_4 = entity_resolver._bfs_join_path("table_a", "table_e")
    assert path_4 is None


def test_entity_resolver_directional_join_loading():
    setup_agent_imports("entity_resolution_agent")
    import entity_resolver
    
    # Mock db cursor to return a sensitive audit_log join record with is_bidirectional=True
    # and verify that initialize_entity_cache correctly forces is_bidirectional=False
    mock_cur = MagicMock()
    mock_cur.description = [
        ("source_table",), ("source_column",), ("target_table",), ("target_column",),
        ("join_type",), ("confidence",), ("is_bidirectional",)
    ]
    mock_cur.fetchall.return_value = [
        # (source, col, target, col, type, conf, is_bidir)
        ("customers", "customer_id", "audit_log", "customer_id", "LEFT JOIN", 1.0, True)
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    # Clear cache and run initialization
    entity_resolver._cache_ready = False
    entity_resolver.initialize_entity_cache(mock_conn)

    # customers -> audit_log should be added
    assert "customers" in entity_resolver._join_graph
    assert any(x["to_table"] == "audit_log" for x in entity_resolver._join_graph["customers"])

    # audit_log -> customers should NOT be added (sensitive table)
    if "audit_log" in entity_resolver._join_graph:
        assert not any(x["to_table"] == "customers" for x in entity_resolver._join_graph["audit_log"])
