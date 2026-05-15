"""
tests/test_entity_resolution_agent.py
Unit tests for EntityResolver — 10 tests covering semantic ID mapping,
join path construction, primary key resolution, and multi-table scenarios.
Runs locally without Docker.
"""
import sys
import os
import pytest

_ERA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "entity_resolution_agent"))
if _ERA not in sys.path:
    sys.path.insert(0, _ERA)

# Clear cached wrong models
for _mod in ["models", "entity_resolver", "semantic_id_mapper"]:
    sys.modules.pop(_mod, None)

from entity_resolver import EntityResolver
from models import EntityResolutionRequest


@pytest.fixture(scope="module")
def resolver():
    """EntityResolver instance."""
    return EntityResolver()


def _req(entity: str, tables: list) -> EntityResolutionRequest:
    """Helper: build EntityResolutionRequest."""
    return EntityResolutionRequest(primary_entity=entity, tables=tables)


# ── TC-01: customer primary key ───────────────────────────────────────────────
def test_customer_primary_key(resolver):
    """customer entity → primary_key is customer_id."""
    result = resolver.resolve(_req("customer", ["customers"]))
    assert result.primary_key == "customer_id"


# ── TC-02: account primary key ────────────────────────────────────────────────
def test_account_primary_key(resolver):
    """account entity → primary_key is account_id."""
    result = resolver.resolve(_req("account", ["accounts"]))
    assert result.primary_key == "account_id"


# ── TC-03: transaction primary key ────────────────────────────────────────────
def test_transaction_primary_key(resolver):
    """transaction entity → primary_key is transaction_id."""
    result = resolver.resolve(_req("transaction", ["transactions"]))
    assert result.primary_key == "transaction_id"


# ── TC-04: branch primary key ─────────────────────────────────────────────────
def test_branch_primary_key(resolver):
    """branch entity → primary_key is branch_id."""
    result = resolver.resolve(_req("branch", ["branches"]))
    assert result.primary_key == "branch_id"


# ── TC-05: customer + accounts join path ──────────────────────────────────────
def test_customer_accounts_join_path(resolver):
    """customer + accounts tables → join path produced."""
    result = resolver.resolve(_req("customer", ["customers", "accounts"]))
    assert len(result.join_structure) >= 1
    assert any(jp.to_table == "accounts" for jp in result.join_structure)


# ── TC-06: join condition has correct format ───────────────────────────────────
def test_join_condition_format(resolver):
    """join condition should be table1.key = table2.key format."""
    result = resolver.resolve(_req("customer", ["customers", "risk_flags"]))
    for jp in result.join_structure:
        assert "=" in jp.condition, f"Join condition malformed: {jp.condition}"
        assert "." in jp.condition, f"Join condition missing table prefix: {jp.condition}"


# ── TC-07: single table → no joins needed ─────────────────────────────────────
def test_single_table_no_joins(resolver):
    """Single table query → zero join paths."""
    result = resolver.resolve(_req("customer", ["customers"]))
    assert len(result.join_structure) == 0


# ── TC-08: multi-table resolution ────────────────────────────────────────────
def test_multi_table_resolution(resolver):
    """3 tables → resolver returns multiple join paths."""
    result = resolver.resolve(_req("customer", ["customers", "accounts", "risk_flags"]))
    assert len(result.join_structure) >= 2


# ── TC-09: resolution confidence ─────────────────────────────────────────────
def test_resolution_confidence(resolver):
    """resolution_confidence should be between 0 and 1."""
    result = resolver.resolve(_req("customer", ["customers", "accounts"]))
    assert 0.0 <= result.resolution_confidence <= 1.0


# ── TC-10: primary table correctly set ───────────────────────────────────────
def test_primary_table_set(resolver):
    """primary_table should be the plural of primary_entity."""
    result = resolver.resolve(_req("customer", ["customers", "accounts"]))
    assert result.primary_table == "customers"
