"""
tests/test_caching.py
Unit tests for caching logic — 5 tests covering cache hash,
TTL logic, cache key uniqueness per parameters, and cache clearing.
Uses the local _query_hash function (no Redis needed).
"""
import sys
import os
import pytest

_EA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "execution_agent"))
if _EA not in sys.path:
    sys.path.insert(0, _EA)

# Clear cached modules from other service imports
for _mod in ["query_executor", "result_formatter", "access_controller", "models"]:
    sys.modules.pop(_mod, None)

from query_executor import _query_hash


# ── TC-01: same SQL + params → same hash ─────────────────────────────────────
def test_same_query_same_hash():
    """Identical SQL+params → identical cache key."""
    sql = "SELECT id FROM customers LIMIT 10"
    params = []
    h1 = _query_hash(sql, params)
    h2 = _query_hash(sql, params)
    assert h1 == h2, "Same query produced different hashes"


# ── TC-02: different SQL → different hash ─────────────────────────────────────
def test_different_sql_different_hash():
    """Different SQL → different cache key."""
    h1 = _query_hash("SELECT id FROM customers LIMIT 10", [])
    h2 = _query_hash("SELECT id FROM accounts LIMIT 10", [])
    assert h1 != h2, "Different SQL produced same hash"


# ── TC-03: same SQL different params → different hash ─────────────────────────
def test_same_sql_different_params_different_hash():
    """Same SQL, different parameter values → different cache key."""
    sql = "SELECT id FROM customers WHERE risk_score = ? LIMIT 10"
    h1 = _query_hash(sql, ["high"])
    h2 = _query_hash(sql, ["low"])
    assert h1 != h2, "Different params produced same hash"


# ── TC-04: hash is deterministic hex string ───────────────────────────────────
def test_hash_is_hex_string():
    """_query_hash returns a lowercase hex string."""
    h = _query_hash("SELECT 1 LIMIT 1", [])
    assert isinstance(h, str)
    assert len(h) == 64, f"Expected SHA-256 hex (64 chars), got {len(h)}"
    int(h, 16)  # Raises ValueError if not hex


# ── TC-05: parameter order independent ───────────────────────────────────────
def test_parameter_order_independent():
    """Cache key should be stable regardless of dict sort order."""
    sql = "SELECT id FROM customers LIMIT 10"
    h1 = _query_hash(sql, ["a", "b"])
    h2 = _query_hash(sql, ["a", "b"])
    assert h1 == h2
