"""
tests/test_schema_agent.py
Unit tests for SchemaMatcher — 10 tests covering intent→domain mapping,
domain→table mapping, join paths, and edge cases.
Runs locally without Docker.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "schema_agent"))

from schema_matcher import SchemaMatcher, INTENT_TO_DOMAINS, DOMAIN_TO_TABLES


@pytest.fixture(scope="module")
def matcher():
    """SchemaMatcher instance."""
    return SchemaMatcher()


# ── TC-01: customer_analysis → customer domain ─────────────────────────────────
def test_customer_analysis_maps_to_customer_domain(matcher):
    """customer_analysis intent → customer_analysis domain."""
    domains = matcher.match_domains(["customer_analysis"])
    assert "customer_analysis" in domains


# ── TC-02: risk_analysis → risk tables ────────────────────────────────────────
def test_risk_analysis_returns_risk_tables(matcher):
    """risk_analysis intent → risk-related tables returned."""
    domains = matcher.match_domains(["risk_analysis"])
    tables = matcher.get_tables(domains)
    risk_tables = {"risk_flags", "aml_flags", "credit_risk_scores"}
    assert risk_tables & set(tables), f"No risk tables in {tables}"


# ── TC-03: revenue_analysis → revenue tables ───────────────────────────────────
def test_revenue_analysis_returns_revenue_tables(matcher):
    """revenue_analysis intent → revenue-related tables."""
    domains = matcher.match_domains(["revenue_analysis"])
    tables = matcher.get_tables(domains)
    assert any(t in tables for t in ["fees", "commissions", "interest_income", "products"])


# ── TC-04: transaction_analysis → transactions table ──────────────────────────
def test_transaction_analysis_returns_transactions(matcher):
    """transaction_analysis intent → transactions table."""
    domains = matcher.match_domains(["transaction_analysis"])
    tables = matcher.get_tables(domains)
    assert "transactions" in tables


# ── TC-05: geographic_analysis → branches/regions ─────────────────────────────
def test_geographic_analysis_returns_location_tables(matcher):
    """geographic_analysis intent → branches or regions table."""
    domains = matcher.match_domains(["geographic_analysis"])
    tables = matcher.get_tables(domains)
    assert any(t in tables for t in ["branches", "regions", "branch_locations"])


# ── TC-06: compliance_analysis → kyc/audit tables ─────────────────────────────
def test_compliance_analysis_returns_kyc_tables(matcher):
    """compliance_analysis → kyc_status or audit_logs."""
    domains = matcher.match_domains(["compliance_analysis"])
    tables = matcher.get_tables(domains)
    assert any(t in tables for t in ["kyc_status", "audit_logs"])


# ── TC-07: multi-intent → union of tables ─────────────────────────────────────
def test_multi_intent_unions_tables(matcher):
    """Multiple intents → union of their tables (no duplicates)."""
    domains = matcher.match_domains(["customer_analysis", "risk_analysis"])
    tables = matcher.get_tables(domains)
    # Both customers and risk tables should be present
    assert "customers" in tables or "customer_segments" in tables
    assert any(t in tables for t in ["risk_flags", "aml_flags"])
    # No duplicates
    assert len(tables) == len(set(tables))


# ── TC-08: join paths produced for customers primary table ─────────────────────
def test_join_paths_for_customers(matcher):
    """customers primary table → join paths to related tables."""
    domains = matcher.match_domains(["customer_analysis", "account_analysis"])
    tables = matcher.get_tables(domains)
    join_paths = matcher.get_join_paths(tables, "customers")
    # Should have at least one join path
    assert len(join_paths) >= 1
    for jp in join_paths:
        # JoinPath may be a dict or Pydantic model — handle both
        if isinstance(jp, dict):
            assert "from_table" in jp
            assert "to_table" in jp
            assert "condition" in jp
        else:
            assert hasattr(jp, "from_table")
            assert hasattr(jp, "to_table")
            assert hasattr(jp, "join_key")


# ── TC-09: unknown intent → empty domain list (no crash) ──────────────────────
def test_unknown_intent_returns_empty(matcher):
    """Unknown intent → no crash, returns empty or partial list."""
    domains = matcher.match_domains(["totally_unknown_intent"])
    # Should not crash, may return empty
    assert isinstance(domains, list)


# ── TC-10: key columns for customer entity ────────────────────────────────────
def test_key_columns_for_customer_entity(matcher):
    """customers entity → customer_id as key column."""
    domains = matcher.match_domains(["customer_analysis"])
    tables = matcher.get_tables(domains)
    key_cols = matcher.get_key_columns(tables, "customer")
    assert any("customer_id" in v for v in key_cols.values()), (
        f"customer_id not found in key columns: {key_cols}"
    )
