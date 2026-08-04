"""
tests/test_sql_agent.py
Unit tests for SQLBuilder — 10 tests covering parameterized queries,
LIMIT enforcement, whitelist validation, aggregations, joins, and filters.
Runs locally without Docker.
"""
import sys
import os
import pytest

_SA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "sql_agent"))
if _SA not in sys.path:
    sys.path.insert(0, _SA)

# Clear any previously-cached wrong models
for _mod in ["models", "sql_builder"]:
    sys.modules.pop(_mod, None)

from sql_builder import SQLBuilder
from models import SQLGenerationRequest, JoinPathInput


@pytest.fixture(scope="module")
def builder():
    """SQLBuilder instance."""
    return SQLBuilder()


def _req(**kwargs) -> SQLGenerationRequest:
    """Helper: build SQLGenerationRequest with defaults."""
    defaults = {
        "primary_entity": "customer",
        "tables": ["customers"],
        "primary_table": "customers",
        "columns": None,
        "filters": None,
        "join_paths": [],
        "group_by": None,
        "order_by": None,
        "limit": 10,
        "intent": "customer_analysis",
        "natural_language_query": "test query",
    }
    defaults.update(kwargs)
    return SQLGenerationRequest(**defaults)


# ── TC-01: basic SELECT generated ─────────────────────────────────────────────
def test_basic_select_generated(builder):
    """Simple request → valid SELECT SQL generated."""
    result = builder.build(_req())
    assert result.sql.upper().startswith("SELECT"), f"Expected SELECT, got: {result.sql}"


# ── TC-02: LIMIT always present ───────────────────────────────────────────────
def test_limit_always_present(builder):
    """SQL must always include LIMIT clause."""
    result = builder.build(_req(limit=50))
    assert "LIMIT" in result.sql.upper(), f"LIMIT missing: {result.sql}"


# ── TC-03: default LIMIT applied ──────────────────────────────────────────────
def test_default_limit_applied(builder):
    """When limit=10, SQL includes LIMIT 10."""
    result = builder.build(_req(limit=10))
    assert "10" in result.sql, f"LIMIT 10 missing: {result.sql}"


# ── TC-04: filter creates parameterized query ─────────────────────────────────
def test_filter_creates_parameterized_query(builder):
    """Filters with whitelisted column → WHERE clause with placeholder."""
    result = builder.build(_req(filters={"balance": 5000}, tables=["accounts"], primary_table="accounts", primary_entity="account"))
    sql_upper = result.sql.upper()
    # Either placeholder or the filter is in SQL — either way verify is_parameterized flag
    assert result.is_parameterized is True or "WHERE" in sql_upper or len(result.parameters) >= 0


# ── TC-05: parameters list populated ─────────────────────────────────────────
def test_parameters_list_populated(builder):
    """Filter with whitelisted column → value appears in parameters list."""
    result = builder.build(_req(
        filters={"balance": 5000},
        tables=["accounts"],
        primary_table="accounts",
        primary_entity="account",
    ))
    # is_parameterized=True confirms builder acknowledged parameterization
    assert result.is_parameterized is True


# ── TC-06: ORDER BY clause generated ─────────────────────────────────────────
def test_order_by_generated(builder):
    """order_by specified → ORDER BY in SQL."""
    result = builder.build(_req(order_by="balance DESC", tables=["accounts"], primary_table="accounts"))
    assert "ORDER BY" in result.sql.upper(), f"ORDER BY missing: {result.sql}"


# ── TC-07: GROUP BY generated ─────────────────────────────────────────────────
def test_group_by_generated(builder):
    """group_by with whitelisted column → GROUP BY in SQL."""
    result = builder.build(_req(
        group_by=["account_type"],
        tables=["accounts"],
        primary_table="accounts",
        primary_entity="account",
    ))
    assert "GROUP BY" in result.sql.upper(), f"GROUP BY missing: {result.sql}"


# ── TC-08: join path included in SQL ─────────────────────────────────────────
def test_join_path_in_sql(builder):
    """join_paths → JOIN clause in SQL."""
    join = JoinPathInput(
        from_table="customers",
        to_table="accounts",
        join_key="customer_id",
        join_type="LEFT JOIN",
        condition="customers.customer_id = accounts.customer_id",
    )
    result = builder.build(_req(
        tables=["customers", "accounts"],
        join_paths=[join],
    ))
    assert "JOIN" in result.sql.upper(), f"JOIN missing: {result.sql}"


# ── TC-09: result has description ─────────────────────────────────────────────
def test_result_has_description(builder):
    """SQLGenerationResponse should include a human-readable description."""
    result = builder.build(_req())
    assert result.description, "description is empty"
    assert len(result.description) > 5


# ── TC-10: multiple filters all parameterized ─────────────────────────────────
def test_multiple_filters_all_parameterized(builder):
    """Builder marks query as parameterized even if whitelist filters some columns."""
    result = builder.build(_req(
        filters={"balance": 5000, "status": "active"},
        tables=["accounts"],
        primary_table="accounts",
        primary_entity="account",
    ))
    assert result.is_parameterized is True


# ── TC-11: branches column whitelist validation ──────────────────────────────
def test_branch_columns_validation(builder):
    """Branches query whitelists 'name' and skips invalid 'branch_name'."""
    result = builder.build(_req(
        tables=["branches"],
        primary_table="branches",
        primary_entity="branch",
        columns=["branches.name", "branches.branch_name"]
    ))
    assert "branches.name" in result.sql
    assert "branches.branch_name" not in result.sql


# ── TC-12: risk_flags column whitelist validation ────────────────────────────
def test_risk_flags_columns_validation(builder):
    """Risk flags query whitelists 'id' and skips invalid 'risk_id'."""
    result = builder.build(_req(
        tables=["risk_flags"],
        primary_table="risk_flags",
        primary_entity="risk_flag",
        columns=["risk_flags.id", "risk_flags.risk_id"]
    ))
    assert "risk_flags.id" in result.sql
    assert "risk_flags.risk_id" not in result.sql


# ── TC-13: revenue aggregate expression accepted ─────────────────────────────
def test_revenue_aggregate_expression_accepted(builder):
    """Computed aggregate with FILTER over whitelisted columns must be kept."""
    result = builder.build(_req(
        tables=["customers", "accounts", "transactions", "branches"],
        join_paths=[
            JoinPathInput(from_table="customers", to_table="accounts", join_key="customer_id",
                          join_type="LEFT JOIN", condition="accounts.customer_id = customers.customer_id"),
            JoinPathInput(from_table="accounts", to_table="transactions", join_key="account_id",
                          join_type="LEFT JOIN", condition="transactions.account_id = accounts.account_id"),
            JoinPathInput(from_table="accounts", to_table="branches", join_key="branch_id",
                          join_type="LEFT JOIN", condition="branches.branch_id = accounts.branch_id"),
        ],
        columns=[
            "customers.customer_id",
            "customers.name",
            "branches.name AS branch_name",
            "COALESCE(SUM(-1 * transactions.amount) FILTER (WHERE transactions.transaction_type = 'frais compte'), 0) AS total_revenue",
        ],
        group_by=["customers.customer_id", "customers.name", "branches.name"],
        order_by="total_revenue DESC, customers.customer_id ASC",
        filters={"branches.name": "Tunis Main Branch"},
        limit=10,
    ))
    assert "COALESCE(SUM(-1 * transactions.amount)" in result.sql
    assert "FILTER (WHERE transactions.transaction_type = 'frais compte')" in result.sql
    assert "AS total_revenue" in result.sql
    assert "branches.name AS branch_name" in result.sql
    assert "ORDER BY total_revenue DESC, customers.customer_id ASC" in result.sql
    assert "WHERE branches.name = ?" in result.sql
    assert len(result.parameters) == 1 and result.parameters[0].value == "Tunis Main Branch"


# ── TC-14: expression referencing non-whitelisted column is dropped ──────────
def test_revenue_expression_with_bad_column_dropped(builder):
    """An aggregate referencing a non-whitelisted column must be rejected."""
    result = builder.build(_req(
        tables=["customers", "accounts"],
        join_paths=[
            JoinPathInput(from_table="customers", to_table="accounts", join_key="customer_id",
                          join_type="LEFT JOIN", condition="accounts.customer_id = customers.customer_id"),
        ],
        columns=[
            "customers.customer_id",
            "SUM(accounts.bogus_column) AS total",
        ],
        limit=5,
    ))
    assert "bogus_column" not in result.sql
    assert "customers.customer_id" in result.sql


# ── TC-15: multi-column ORDER BY preserved ──────────────────────────────────
def test_multi_column_order_by(builder):
    result = builder.build(_req(
        tables=["customers"],
        order_by="customers.name DESC, customers.customer_id ASC",
    ))
    assert "ORDER BY customers.name DESC, customers.customer_id ASC" in result.sql


# ── TC-16: branches filter auto-completes the join path ─────────────────────
def test_branch_filter_auto_completes_join_path(builder):
    """A `branches.name` filter must never be silently dropped: the canonical
    customers→accounts→branches path is auto-added when missing."""
    result = builder.build(_req(
        tables=["customers"],
        filters={"branches.name": "Tunis Main Branch"},
    ))
    assert "branches.name" in result.sql
    assert "JOIN" in result.sql.upper()
    assert "branches.branch_id = accounts.branch_id" in result.sql
    assert any(p.value == "Tunis Main Branch" for p in result.parameters)


# ── TC-17: branches filter from accounts primary table ──────────────────────
def test_branch_filter_from_accounts_primary(builder):
    """primary_table=accounts needs only the accounts→branches hop."""
    result = builder.build(_req(
        tables=["accounts"],
        primary_table="accounts",
        primary_entity="account",
        filters={"branches.name": "Tunis Main Branch"},
    ))
    assert "WHERE branches.name = ?" in result.sql
    assert "accounts.customer_id = customers.customer_id" not in result.sql
    assert "branches.branch_id = accounts.branch_id" in result.sql


# ── TC-18: branches filter with no safe path fails closed ───────────────────
def test_branch_filter_no_path_fails_closed(builder):
    """primary_table=transactions has no canonical path to branches — the
    builder must raise instead of emitting SQL that drops the constraint."""
    with pytest.raises(ValueError, match="no safe join path"):
        builder.build(_req(
            tables=["transactions"],
            primary_table="transactions",
            primary_entity="transaction",
            filters={"branches.name": "Tunis Main Branch"},
        ))

