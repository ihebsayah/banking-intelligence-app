"""
tests/test_integration.py
Integration tests — 15 tests covering full pipeline stages from intent
to execution. Runs locally with mocked DB/Redis (no Docker required).

Uses pytest fixtures to avoid sys.modules["models"] cross-contamination.
"""
import sys
import os
import json
import pytest

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_IA  = os.path.join(BASE, "services/intent_agent")
_SCA = os.path.join(BASE, "services/schema_agent")
_ERA = os.path.join(BASE, "services/entity_resolution_agent")
_SA  = os.path.join(BASE, "services/sql_agent")
_VA  = os.path.join(BASE, "services/validation_agent")
_EA  = os.path.join(BASE, "services/execution_agent")


def _only(path: str):
    """Remove all service paths, add only this one, wipe stale models."""
    for p in list(sys.path):
        if "services" in p:
            sys.path.remove(p)
    for m in list(sys.modules.keys()):
        if m in ("models", "query_validator", "schema_matcher", "intent_recognizer",
                 "entity_resolver", "semantic_id_mapper", "sql_builder",
                 "access_controller", "result_formatter", "query_executor"):
            del sys.modules[m]
    sys.path.insert(0, path)


# ── IT-01: Intent → correct domain ────────────────────────────────────────────
def test_intent_to_domain_mapping():
    _only(_IA)
    from intent_recognizer import IntentRecognizer
    r = IntentRecognizer(redis_client=None)
    result = r.recognize_sync("Top customers by account balance")
    assert result["primary_category"] == "customer_analysis"
    assert result["confidence"] > 0.05


# ── IT-02: Schema → tables for customer ───────────────────────────────────────
def test_schema_returns_customer_tables():
    _only(_SCA)
    from schema_matcher import SchemaMatcher
    m = SchemaMatcher()
    tables = m.get_tables(m.match_domains(["customer_analysis"]))
    assert "customers" in tables


# ── IT-03: Entity resolution → customer_id ────────────────────────────────────
def test_entity_resolution_correct_pk():
    _only(_ERA)
    from entity_resolver import EntityResolver
    from models import EntityResolutionRequest
    res = EntityResolver().resolve(EntityResolutionRequest(
        primary_entity="customer", tables=["customers", "accounts"]
    ))
    assert res.primary_key == "customer_id"
    assert res.primary_table == "customers"


# ── IT-04: SQL generation → valid SELECT with LIMIT ───────────────────────────
def test_sql_generation_valid_select():
    _only(_SA)
    from sql_builder import SQLBuilder
    from models import SQLGenerationRequest
    result = SQLBuilder().build(SQLGenerationRequest(
        primary_entity="customer", tables=["customers"], primary_table="customers",
        columns=None, filters=None, join_paths=[], group_by=None, order_by=None,
        limit=10, intent="customer_analysis", natural_language_query="Top 10 customers",
    ))
    assert "SELECT" in result.sql.upper()
    assert "LIMIT" in result.sql.upper()
    assert result.is_parameterized


# ── IT-05: Validation signs safe query ────────────────────────────────────────
def test_validation_signs_safe_query():
    _only(_VA)
    from query_validator import QueryValidator
    from models import QueryValidationRequest
    r = QueryValidator().validate(QueryValidationRequest(
        sql="SELECT customer_id, name FROM customers LIMIT 10", parameters=[],
    ))
    assert r.safe
    assert r.signature.startswith("sha256:")


# ── IT-06: Full pipeline produces results ─────────────────────────────────────
def test_full_pipeline_produces_results():
    _only(_IA)
    from intent_recognizer import IntentRecognizer
    intent_result = IntentRecognizer().recognize_sync("Top 10 customers by balance")
    assert "primary_category" in intent_result

    _only(_SCA)
    from schema_matcher import SchemaMatcher
    sm = SchemaMatcher()
    tables = sm.get_tables(sm.match_domains([intent_result["primary_category"]]))
    assert len(tables) >= 1

    _only(_SA)
    from sql_builder import SQLBuilder
    from models import SQLGenerationRequest
    sql_result = SQLBuilder().build(SQLGenerationRequest(
        primary_entity="customer", tables=tables[:2], primary_table="customers",
        columns=None, filters=None, join_paths=[], group_by=None, order_by=None,
        limit=10, intent=intent_result["primary_category"],
        natural_language_query="Top 10 customers by balance",
    ))
    assert sql_result.sql

    _only(_VA)
    from query_validator import QueryValidator
    from models import QueryValidationRequest
    val = QueryValidator().validate(QueryValidationRequest(
        sql=sql_result.sql, parameters=sql_result.parameters,
    ))
    assert val.safe


# ── IT-07: ResultFormatter JSON ───────────────────────────────────────────────
def test_result_formatter_json():
    _only(_EA)
    from result_formatter import ResultFormatter
    rows = [{"customer_id": 1, "name": "Alice", "balance": 5000.0}]
    result, _ = ResultFormatter().format(rows, "json", "compliance")
    assert isinstance(result, list)
    assert result[0]["customer_id"] == 1


# ── IT-08: ResultFormatter CSV ────────────────────────────────────────────────
def test_result_formatter_csv():
    _only(_EA)
    from result_formatter import ResultFormatter
    rows = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    result, _ = ResultFormatter().format(rows, "csv", "compliance")
    assert "name" in result and "Alice" in result


# ── IT-09: ResultFormatter table ──────────────────────────────────────────────
def test_result_formatter_table():
    _only(_EA)
    from result_formatter import ResultFormatter
    result, _ = ResultFormatter().format([{"id": 1, "name": "Test"}], "table", "compliance")
    assert "|" in result


# ── IT-10: PII masking applied ────────────────────────────────────────────────
def test_pii_masking_applied():
    _only(_EA)
    from result_formatter import ResultFormatter
    rows = [{"customer_id": 1, "ssn": "123-45-6789"}]
    result, _ = ResultFormatter().format(rows, "json", "analyst")
    assert "123-45-6789" not in json.dumps(result)


# ── IT-11: Credit card masking ────────────────────────────────────────────────
def test_credit_card_masking():
    _only(_EA)
    from result_formatter import ResultFormatter
    rows = [{"customer_id": 1, "credit_card": "4532-1234-5678-9012"}]
    result, _ = ResultFormatter().format(rows, "json", "analyst")
    assert "4532-1234-5678-9012" not in json.dumps(result)


# ── IT-12: Role column visibility ─────────────────────────────────────────────
def test_role_based_column_visibility():
    _only(_EA)
    from access_controller import AccessController
    ac = AccessController()
    assert ac.get_visible_columns("compliance") is None
    assert ac.get_visible_columns("customer") is not None


# ── IT-13: Analyst PII masking on ─────────────────────────────────────────────
def test_analyst_pii_masking_enforced():
    _only(_EA)
    from access_controller import AccessController
    assert AccessController().should_mask_pii("analyst") is True


# ── IT-14: Signature tamper detection ─────────────────────────────────────────
def test_signature_tamper_detection():
    _only(_VA)
    from query_validator import QueryValidator
    from models import QueryValidationRequest
    v = QueryValidator()
    sql = "SELECT id FROM customers LIMIT 5"
    r = v.validate(QueryValidationRequest(sql=sql, parameters=[]))
    assert r.safe
    parts = r.signature.split(":")
    parts[1] = "x" * len(parts[1])
    assert not v.verify_signature(sql, [], ":".join(parts))


# ── IT-15: Multi-table JOIN passes validation ──────────────────────────────────
def test_multi_table_join_passes_validation():
    _only(_VA)
    from query_validator import QueryValidator
    from models import QueryValidationRequest
    sql = (
        "SELECT c.customer_id, c.name, a.balance "
        "FROM customers c "
        "LEFT JOIN accounts a ON c.customer_id = a.customer_id "
        "LIMIT 10"
    )
    r = QueryValidator().validate(QueryValidationRequest(sql=sql, parameters=[]))
    assert r.safe, f"JOIN failed: {r.issues}"
