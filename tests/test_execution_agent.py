"""
tests/test_execution_agent.py
Unit tests for QueryExecutor components — 10 tests covering role-based
filtering, PII masking, result formatting, signature verification,
and mock query execution. Runs without Docker/Redis/Postgres.
"""
import sys
import os
import pytest

# Add execution_agent source
_EA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "execution_agent"))
if _EA not in sys.path:
    sys.path.insert(0, _EA)

# Clear cached modules from other services
for _mod in ["result_formatter", "access_controller", "query_executor", "models"]:
    sys.modules.pop(_mod, None)

from result_formatter import ResultFormatter, _mask_ssn, _mask_card, _mask_email
from access_controller import AccessController, PII_COLUMNS
from query_executor import _verify_signature, _query_hash


@pytest.fixture(scope="module")
def formatter():
    return ResultFormatter()


@pytest.fixture(scope="module")
def access_ctrl():
    return AccessController()


# ── TC-01: analyst sees allowed columns only ──────────────────────────────────
def test_analyst_sees_allowed_columns(access_ctrl):
    """analyst role → credit_score column hidden (PII)."""
    row = {"customer_id": 1, "name": "Alice", "credit_score": 780, "balance": 5000.0}
    filtered = access_ctrl.filter_columns(row, "analyst")
    assert "credit_score" not in filtered, "analyst should not see credit_score"
    assert "customer_id" in filtered


# ── TC-02: compliance sees all columns ────────────────────────────────────────
def test_compliance_sees_all_columns(access_ctrl):
    """compliance role → all columns visible."""
    row = {"customer_id": 1, "ssn": "123-45-6789", "name": "Bob", "credit_score": 720}
    filtered = access_ctrl.filter_columns(row, "compliance")
    assert "ssn" in filtered
    assert "credit_score" in filtered


# ── TC-03: PII masking enabled for analyst ────────────────────────────────────
def test_pii_masking_analyst(access_ctrl):
    """analyst → should_mask_pii returns True."""
    assert access_ctrl.should_mask_pii("analyst") is True


# ── TC-04: PII masking disabled for compliance ────────────────────────────────
def test_pii_masking_compliance(access_ctrl):
    """compliance → should_mask_pii returns False."""
    assert access_ctrl.should_mask_pii("compliance") is False


# ── TC-05: SSN masked correctly ──────────────────────────────────────────────
def test_ssn_masking():
    """SSN 123-45-6789 → ***-**-6789."""
    masked = _mask_ssn("123-45-6789")
    assert masked == "***-**-6789", f"SSN mask wrong: {masked}"


# ── TC-06: credit card masked correctly ──────────────────────────────────────
def test_card_masking():
    """Card 4532-1234-5678-9012 → ****-****-****-9012."""
    masked = _mask_card("4532-1234-5678-9012")
    assert "****" in masked and "9012" in masked, f"Card mask wrong: {masked}"


# ── TC-07: JSON format returns list of dicts ─────────────────────────────────
def test_json_format(formatter):
    """format(..., 'json') → returns list of dicts."""
    rows = [{"customer_id": 1, "name": "Alice", "balance": 5000.0}]
    result, _ = formatter.format(rows, "json", "compliance")
    assert isinstance(result, list)
    assert isinstance(result[0], dict)


# ── TC-08: CSV format returns string ─────────────────────────────────────────
def test_csv_format(formatter):
    """format(..., 'csv') → returns CSV string with header."""
    rows = [{"customer_id": 1, "name": "Alice"}, {"customer_id": 2, "name": "Bob"}]
    result, _ = formatter.format(rows, "csv", "compliance")
    assert isinstance(result, str)
    assert "customer_id" in result
    assert "Alice" in result


# ── TC-09: table format returns ASCII table ───────────────────────────────────
def test_table_format(formatter):
    """format(..., 'table') → returns ASCII table string."""
    rows = [{"id": 1, "name": "Alice"}]
    result, _ = formatter.format(rows, "table", "compliance")
    assert isinstance(result, str)
    assert "|" in result
    assert "id" in result


# ── TC-10: tampered signature not verified ────────────────────────────────────
def test_tampered_signature_not_verified():
    """_verify_signature with wrong signature → False."""
    sql = "SELECT id FROM customers LIMIT 10"
    params = []
    bad_sig = "sha256:deadbeefdeadbeef:1234567890"
    assert _verify_signature(sql, params, bad_sig) is False
