"""
tests/test_validation_agent.py
Unit tests for QueryValidator — 10 tests covering good queries, bad queries,
signature generation, verification, and all 5 safety checks.
Runs locally without Docker.
"""
import sys
import os
import importlib
import pytest

# Prepend validation_agent so its models.py takes priority
_VA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "validation_agent"))
if _VA not in sys.path:
    sys.path.insert(0, _VA)

# Force re-import in correct order
import importlib
for _mod in ["models", "query_validator"]:
    sys.modules.pop(_mod, None)

from query_validator import QueryValidator
from models import QueryValidationRequest


@pytest.fixture(scope="module")
def validator():
    """QueryValidator instance."""
    return QueryValidator()


def _validate(validator, sql: str, params: list = None) -> object:
    """Helper: build request and validate."""
    return validator.validate(QueryValidationRequest(
        sql=sql,
        parameters=params or [],
    ))


# ── TC-01: safe query passes all checks ───────────────────────────────────────
def test_safe_query_passes(validator):
    """Clean SELECT with LIMIT → is_safe=True."""
    r = _validate(validator, "SELECT customer_id, name FROM customers LIMIT 10")
    assert r.safe, f"Safe query failed: {r.issues}"
    assert r.signature is not None and r.signature != ""


# ── TC-02: DROP TABLE blocked ─────────────────────────────────────────────────
def test_drop_table_blocked(validator):
    """DROP TABLE → is_safe=False, select_only check fails."""
    r = _validate(validator, "DROP TABLE customers")
    assert not r.safe
    assert len(r.issues) > 0


# ── TC-03: DELETE blocked ─────────────────────────────────────────────────────
def test_delete_blocked(validator):
    """DELETE statement → is_safe=False."""
    r = _validate(validator, "DELETE FROM customers WHERE 1=1")
    assert not r.safe


# ── TC-04: UNION injection blocked ────────────────────────────────────────────
def test_union_injection_blocked(validator):
    """UNION SELECT injection → is_safe=False."""
    r = _validate(validator, "SELECT id FROM customers LIMIT 10 UNION SELECT username, password FROM admin")
    assert not r.safe


# ── TC-05: OR 1=1 injection blocked ───────────────────────────────────────────
def test_or_1_equals_1_blocked(validator):
    """OR 1=1 pattern → is_safe=False."""
    r = _validate(validator, "SELECT * FROM customers WHERE id=1 OR 1=1 LIMIT 10")
    assert not r.safe


# ── TC-06: no LIMIT → blocked ─────────────────────────────────────────────────
def test_missing_limit_blocked(validator):
    """SELECT without LIMIT → is_safe=False (limit_check fails)."""
    r = _validate(validator, "SELECT customer_id FROM customers")
    assert not r.safe
    assert any("LIMIT" in issue.upper() or "limit" in issue.lower() for issue in r.issues)


# ── TC-07: signature generated for safe query ─────────────────────────────────
def test_signature_generated_for_safe_query(validator):
    """Safe query → signature starts with 'sha256:'."""
    r = _validate(validator, "SELECT id, name FROM customers LIMIT 5")
    assert r.safe
    assert r.signature.startswith("sha256:"), f"Bad signature format: {r.signature}"


# ── TC-08: signature verification works ──────────────────────────────────────
def test_signature_verification(validator):
    """Generated signature → verify_signature returns True."""
    sql = "SELECT id FROM customers LIMIT 5"
    params = []
    r = _validate(validator, sql, params)
    assert r.safe
    verified = validator.verify_signature(sql, params, r.signature)
    assert verified, "Signature verification failed for legitimate query"


# ── TC-09: tampered signature rejected ───────────────────────────────────────
def test_tampered_signature_rejected(validator):
    """Tampered signature → verify_signature returns False."""
    sql = "SELECT id FROM customers LIMIT 5"
    r = _validate(validator, sql, [])
    assert r.safe
    # Corrupt the HMAC hex part (index 1 of sha256:HEX:TIMESTAMP)
    parts = r.signature.split(":")
    parts[1] = "0" * len(parts[1])  # zero out the hex digest
    bad_sig = ":".join(parts)
    assert not validator.verify_signature(sql, [], bad_sig)


# ── TC-10: EXEC/DECLARE blocked ──────────────────────────────────────────────
def test_exec_declare_blocked(validator):
    """EXEC or DECLARE keywords → is_safe=False."""
    r = _validate(validator, "SELECT 1; EXEC xp_cmdshell('dir') LIMIT 10")
    assert not r.safe
