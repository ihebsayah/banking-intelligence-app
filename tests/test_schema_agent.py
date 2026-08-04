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
    """revenue_analysis intent → transaction-based revenue tables."""
    domains = matcher.match_domains(["revenue_analysis"])
    tables = matcher.get_tables(domains)
    revenue_tables = {"customers", "accounts", "transactions", "branches"}
    assert revenue_tables & set(tables), f"No revenue tables in {tables}"


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


# ── Phase 6C Increment 1: Progressive Schema Selection tests ───────────────────
def test_progressive_schema_selection(matcher):
    """Test progressive schema selection and column pruning."""
    res = matcher.progressive_map(
        query="Show risk flags for customer",
        domain="customer",
        task="detail_listing",
        metrics=[],
        dimensions=[],
        filters_structured=[],
        limit_requested=None
    )
    assert "customers" in res.selected_tables
    assert res.schema_confidence > 0.0
    assert len(res.selected_columns) > 0
    assert "customers" in res.selected_columns

def test_bridge_table_preservation(matcher):
    """Test that bridge tables are resolved and preserved to connect joins."""
    # Ensure join registry mock or actual is loaded
    matcher._join_registry_cache = [
        {"source_table": "customers", "source_column": "customer_id", "target_table": "accounts", "target_column": "customer_id", "is_bidirectional": True},
        {"source_table": "accounts", "source_column": "branch_id", "target_table": "branches", "target_column": "branch_id", "is_bidirectional": True}
    ]
    matcher._table_metadata_cache = {
        "customers": {"domain": "customer"},
        "accounts": {"domain": "accounts"},
        "branches": {"domain": "branch and regional performance"}
    }
    
    res = matcher.progressive_map(
        query="Branches showing customer details",
        domain="customer",
        task="detail_listing",
        metrics=[],
        dimensions=["branches.name"],
        filters_structured=[],
        limit_requested=None
    )
    # Connecting customers to branches requires accounts as a bridge table!
    assert "customers" in res.selected_tables
    assert "branches" in res.selected_tables
    assert "accounts" in res.bridge_tables or "accounts" in res.selected_tables
    assert len(res.join_paths) >= 2

def test_provenance_and_versioning(matcher):
    """Test provenance tracking and snapshot versioning."""
    res = matcher.progressive_map(
        query="Show customer risk score",
        domain="customer",
        task="detail_listing",
        metrics=[],
        dimensions=[],
        filters_structured=[],
        limit_requested=None
    )
    assert res.semantic_metadata_version.startswith("v6C.")
    assert len(res.schema_snapshot_id) == 32 # MD5 hash length
    assert "customers" in res.table_provenance
    assert res.table_provenance["customers"]["source"] == "table_metadata"

def test_max_total_tables_constraint(matcher):
    """Test that total tables are bounded by SEMANTIC_MAX_TOTAL_TABLES."""
    # Populate large set of dummy joins
    matcher._join_registry_cache = [
        {"source_table": f"t{i}", "source_column": "id", "target_table": f"t{i+1}", "target_column": "id", "is_bidirectional": True}
        for i in range(1, 15)
    ]
    matcher._table_metadata_cache = {
        f"t{i}": {"domain": "customer"} for i in range(1, 16)
    }
    
    # Run progressive map with SEMANTIC_MAX_TOTAL_TABLES = 5
    res = matcher.progressive_map(
        query="t1 to t15",
        domain="customer",
        task="detail_listing",
        metrics=[],
        dimensions=[],
        filters_structured=[],
        limit_requested=None,
        max_selected_tables=2,
        max_total_tables=5
    )
    total_resolved = len(res.selected_tables) + len(res.bridge_tables)
    assert total_resolved <= 5


# ── Phase 6C Schema Selection Semantic Corrections Regression Tests ───────────
def test_requested_fields_reporting(matcher):
    """Test that missing requested output fields are reported."""
    # Populate mock cache with customers table and name column
    matcher._table_metadata_cache = {
        "customers": {"domain": "customer"}
    }
    matcher._column_metadata_cache = {
        ("customers", "name"): {"column_name": "name", "table_name": "customers"},
        ("customers", "customer_id"): {"column_name": "customer_id", "table_name": "customers"}
    }
    
    res = matcher.progressive_map(
        query="Show customer nonexistent_field and name",
        domain="customer",
        task="detail_listing",
        metrics=[],
        dimensions=[],
        filters_structured=[],
        limit_requested=None,
        requested_fields=["nonexistent_field", "name"]
    )
    assert "nonexistent_field" in res.missing_requested_fields
    assert "name" not in res.missing_requested_fields

def test_metric_grain_compatibility(matcher):
    """Test grain incompatibility detection for PNB and ROE."""
    # PNB with account type is unsupported
    res_pnb = matcher.progressive_map(
        query="PNB by account type",
        domain="profitability",
        task="aggregation",
        metrics=["pnb"],
        dimensions=["accounts.account_type"],
        filters_structured=[],
        limit_requested=None
    )
    assert res_pnb.unsupported_reason is not None
    assert "account_type" in res_pnb.unsupported_reason

    # ROE with branch is unsupported
    res_roe = matcher.progressive_map(
        query="ROE by agence",
        domain="profitability",
        task="aggregation",
        metrics=["roe"],
        dimensions=["branches.name"],
        filters_structured=[],
        limit_requested=None
    )
    assert res_roe.unsupported_reason is not None
    assert "dimensions other than time" in res_roe.unsupported_reason

def test_temporal_source_capability(matcher):
    """Test temporal source validation swaps customers -> kyc_cases for historical queries."""
    res = matcher.progressive_map(
        query="KYC compliance rate last year",
        domain="kyc",
        task="aggregation",
        metrics=["kyc_compliance_rate"],
        dimensions=[],
        filters_structured=[],
        limit_requested=None
    )
    # Since it is a historical query (last year), we cannot use the current-state 'customers' table.
    # It must select the historical log table 'kyc_cases'.
    assert "kyc_cases" in res.selected_tables
    assert "customers" not in res.selected_tables

def test_authoritative_source_priority(matcher):
    """Test priority weighting: metric registry source table (4.0) > analytical view (3.0) > operational (2.0)."""
    # Force mock metadata
    matcher._table_metadata_cache = {
        "loan_contracts": {"domain": "loans"},           # Operational (2.0)
        "non_performing_loans": {"domain": "loans"},     # Analytical view (3.0)
        "branches": {"domain": "branch performance"}     # Related (1.0)
    }
    
    # In 'npl_ratio' query, non_performing_loans is analytical view (3.0) + metric source (+4.0) -> total 7.0
    # loan_contracts is operational (2.0) + metric source (+4.0) -> total 6.0
    res = matcher.progressive_map(
        query="NPL ratio",
        domain="credit risk",
        task="aggregation",
        metrics=["npl_ratio"],
        dimensions=[],
        filters_structured=[],
        limit_requested=None
    )
    assert res.selected_tables[0] == "non_performing_loans"


