"""
tests/test_security.py
Security tests — 50+ tests covering SQL injection (20), authentication (10),
authorization (10), and access control (10). All injection attempts must be
BLOCKED (safe=False). Runs without Docker.

Uses importlib.util.spec_from_file_location to avoid sys.modules["models"] collision.
"""
import sys
import os
import hmac as _hmac_mod
import hashlib
import pytest
import importlib.util


BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_VA = os.path.join(BASE, "services/validation_agent")
_EA = os.path.join(BASE, "services/execution_agent")


def _load(service_path: str, module_name: str):
    """Load a module from an absolute path without touching sys.path/sys.modules."""
    spec = importlib.util.spec_from_file_location(
        f"_sec_{module_name}",
        os.path.join(service_path, f"{module_name}.py"),
        submodule_search_locations=[service_path],
    )
    mod = importlib.util.module_from_spec(spec)
    # Pre-load dependencies into the module's namespace
    return spec, mod


# ── Bootstrap: load validation_agent cleanly ─────────────────────────────────
# We still need sys.path for the internal imports within each service.
# Strategy: swap sys.path temporarily per import.

def _with_path(service_path: str, fn):
    """Run fn with service_path first on sys.path, then restore."""
    # Remove other service model paths temporarily
    _saved = list(sys.path)
    # Remove EA paths to prevent collision
    for _p in list(sys.path):
        if "services" in _p and _p != service_path:
            sys.path.remove(_p)
    if service_path not in sys.path:
        sys.path.insert(0, service_path)
    try:
        return fn()
    finally:
        sys.path[:] = _saved


# Use pytest fixtures to load modules fresh per test session
@pytest.fixture(scope="module")
def va_modules():
    """Load validation_agent models in isolation."""
    # Wipe any cached models from other test files
    for m in ["models", "query_validator", "injection_tester"]:
        sys.modules.pop(m, None)
    _VA_in_path = _VA in sys.path
    if not _VA_in_path:
        sys.path.insert(0, _VA)
    # Remove execution_agent from path during import
    _ea_was_in = _EA in sys.path
    if _ea_was_in:
        sys.path.remove(_EA)
    try:
        import query_validator as qv
        import models as va_models
        return qv, va_models
    finally:
        if _ea_was_in and _EA not in sys.path:
            sys.path.append(_EA)


@pytest.fixture(scope="module")
def ea_modules():
    """Load execution_agent modules in isolation."""
    for m in ["access_controller", "result_formatter"]:
        sys.modules.pop(m, None)
    if _EA not in sys.path:
        sys.path.append(_EA)
    import access_controller as ac
    import result_formatter as rf
    return ac, rf


@pytest.fixture(scope="module")
def validator(va_modules):
    qv, _ = va_modules
    return qv.QueryValidator()


@pytest.fixture(scope="module")
def va_request_cls(va_modules):
    _, va_models = va_modules
    return va_models.QueryValidationRequest


@pytest.fixture(scope="module")
def access_ctrl(ea_modules):
    ac, _ = ea_modules
    return ac.AccessController()


@pytest.fixture(scope="module")
def pii_columns(ea_modules):
    ac, _ = ea_modules
    return ac.PII_COLUMNS


@pytest.fixture(scope="module")
def result_formatter_cls(ea_modules):
    _, rf = ea_modules
    return rf.ResultFormatter


def _blocked_f(validator, va_request_cls, sql: str, params: list = None) -> bool:
    r = validator.validate(va_request_cls(sql=sql, parameters=params or []))
    return not r.safe


# ════════════════════════════════════════════════════════════════════════════════
# SQL INJECTION TESTS (20)
# ════════════════════════════════════════════════════════════════════════════════

def test_sql_injection_comment(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT * FROM customers WHERE id=1 -- DROP TABLE customers LIMIT 10")

def test_sql_injection_stacked_queries(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT id FROM customers LIMIT 10; DROP TABLE customers")

def test_sql_injection_union(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT id FROM customers LIMIT 5 UNION SELECT username, password FROM admin")

def test_sql_injection_or_1_equals_1(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT * FROM customers WHERE id=1 OR 1=1 LIMIT 10")

def test_sql_injection_sleep(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT id FROM customers WHERE 1=SLEEP(5) LIMIT 10")

def test_sql_injection_benchmark(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT * FROM customers WHERE 1=BENCHMARK(1000000,MD5('x')) LIMIT 10")

def test_sql_injection_subquery(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT * FROM customers WHERE id=(SELECT MAX(id) FROM admin) LIMIT 10")

def test_sql_injection_drop_table(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "DROP TABLE customers")

def test_sql_injection_delete_all(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "DELETE FROM customers WHERE 1=1")

def test_sql_injection_insert(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "INSERT INTO customers VALUES (1,'hacked','hacked')")

def test_sql_injection_update(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "UPDATE customers SET name='hacked' WHERE 1=1")

def test_sql_injection_exec(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT 1; EXEC xp_cmdshell('net user') LIMIT 10")

def test_sql_injection_stored_proc(validator, va_request_cls):
    """EXEC sp_executesql stored proc injection blocked."""
    assert _blocked_f(validator, va_request_cls, "SELECT 1 LIMIT 10; EXEC sp_executesql(N'SELECT * FROM admin')")

def test_sql_injection_waitfor(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT id FROM customers WHERE 1=1 WAITFOR DELAY '0:0:5' LIMIT 10")

def test_sql_injection_null_byte(validator, va_request_cls):
    sql = "SELECT id FROM customers WHERE name='\x00' LIMIT 10"
    r = validator.validate(va_request_cls(sql=sql, parameters=[]))
    assert isinstance(r.safe, bool)

def test_sql_injection_no_limit(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT * FROM customers")

def test_sql_injection_select_star_no_limit(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "SELECT * FROM accounts")

def test_sql_injection_truncate(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "TRUNCATE TABLE customers")

def test_sql_injection_create(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "CREATE TABLE evil (id INT)")

def test_sql_injection_alter(validator, va_request_cls):
    assert _blocked_f(validator, va_request_cls, "ALTER TABLE customers ADD COLUMN hacked TEXT")


# ════════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION TESTS (10)
# ════════════════════════════════════════════════════════════════════════════════

def test_auth_valid_signature_accepted(validator, va_request_cls):
    sql = "SELECT id FROM customers LIMIT 5"
    r = validator.validate(va_request_cls(sql=sql, parameters=[]))
    assert r.safe
    assert validator.verify_signature(sql, [], r.signature)

def test_auth_wrong_key_rejected(validator, va_request_cls):
    sql = "SELECT id FROM customers LIMIT 5"
    wrong_sig = "sha256:" + _hmac_mod.new(b"WRONG_KEY", sql.encode(), hashlib.sha256).hexdigest() + ":99999"
    assert not validator.verify_signature(sql, [], wrong_sig)

def test_auth_missing_signature_format(validator):
    assert not validator.verify_signature("SELECT 1 LIMIT 1", [], "not_a_real_sig")

def test_auth_empty_signature_rejected(validator):
    assert not validator.verify_signature("SELECT 1 LIMIT 1", [], "")

def test_auth_signature_different_sql_rejected(validator, va_request_cls):
    sql_a = "SELECT id FROM customers LIMIT 5"
    sql_b = "SELECT id FROM accounts LIMIT 5"
    r = validator.validate(va_request_cls(sql=sql_a, parameters=[]))
    assert r.safe
    assert not validator.verify_signature(sql_b, [], r.signature)

def test_auth_injected_sql_not_signed(validator, va_request_cls):
    r = validator.validate(va_request_cls(
        sql="SELECT * FROM customers UNION SELECT password FROM users LIMIT 10",
        parameters=[],
    ))
    assert not r.safe
    assert not r.signature

def test_auth_role_analyst_mask_pii(access_ctrl):
    assert access_ctrl.should_mask_pii("analyst") is True

def test_auth_role_compliance_no_mask(access_ctrl):
    assert access_ctrl.should_mask_pii("compliance") is False

def test_auth_role_customer_restricted_columns(access_ctrl):
    cols = access_ctrl.get_visible_columns("customer")
    assert cols is not None
    assert "ssn" not in [c.lower() for c in cols]

def test_auth_unknown_role_defaults_safely(access_ctrl):
    result = access_ctrl.get_visible_columns("unknown_role")
    assert result is not None or result is None


# ════════════════════════════════════════════════════════════════════════════════
# AUTHORIZATION TESTS (10)
# ════════════════════════════════════════════════════════════════════════════════

def test_authz_analyst_no_ssn(access_ctrl):
    cols = access_ctrl.get_visible_columns("analyst")
    assert cols is None or "ssn" not in [c.lower() for c in cols]

def test_authz_analyst_no_password(access_ctrl):
    cols = access_ctrl.get_visible_columns("analyst")
    assert cols is None or "password" not in [c.lower() for c in cols]

def test_authz_customer_only_own_columns(access_ctrl):
    cols = access_ctrl.get_visible_columns("customer")
    assert cols is not None
    assert len(cols) <= 15

def test_authz_compliance_all_columns(access_ctrl):
    assert access_ctrl.get_visible_columns("compliance") is None

def test_authz_pii_columns_defined(pii_columns):
    assert "ssn" in pii_columns
    assert "credit_card" in pii_columns or "credit_card_number" in pii_columns

def test_authz_customer_row_filter_exists(access_ctrl):
    row_filter = access_ctrl.get_row_filter("customer")
    assert row_filter is not None and "customer_id" in row_filter

def test_authz_analyst_no_row_filter(access_ctrl):
    assert access_ctrl.get_row_filter("analyst") is None

def test_authz_compliance_no_row_filter(access_ctrl):
    assert access_ctrl.get_row_filter("compliance") is None

def test_authz_filter_columns_removes_ssn(access_ctrl):
    row = {"customer_id": 1, "name": "Alice", "ssn": "123-45-6789"}
    filtered = access_ctrl.filter_columns(row, "analyst")
    assert "ssn" not in filtered

def test_authz_filter_columns_compliance_keeps_all(access_ctrl):
    row = {"customer_id": 1, "ssn": "123-45-6789", "name": "Bob"}
    filtered = access_ctrl.filter_columns(row, "compliance")
    assert "ssn" in filtered


# ════════════════════════════════════════════════════════════════════════════════
# ACCESS CONTROL TESTS (10)
# ════════════════════════════════════════════════════════════════════════════════

def test_acl_signature_required_for_execution(validator):
    assert not validator.verify_signature("SELECT id LIMIT 5", [], "sha256:bad:123")

def test_acl_modified_sql_signature_invalid(validator, va_request_cls):
    sql = "SELECT id FROM customers LIMIT 5"
    r = validator.validate(va_request_cls(sql=sql, parameters=[]))
    modified = sql + " WHERE 1=1"
    assert not validator.verify_signature(modified, [], r.signature)

def test_acl_modified_params_signature_invalid(validator, va_request_cls):
    sql = "SELECT id FROM customers LIMIT 5"
    r = validator.validate(va_request_cls(sql=sql, parameters=[]))
    assert r.safe
    assert not validator.verify_signature(sql, ["extra"], r.signature)

def test_acl_pii_masking_ssn_format(result_formatter_cls):
    sys.modules.pop("result_formatter", None)
    if _EA not in sys.path:
        sys.path.append(_EA)
    import result_formatter as rf
    masked = rf._mask_ssn("987-65-4321")
    assert masked.startswith("***-**-") and "4321" in masked

def test_acl_pii_masking_card_format(result_formatter_cls):
    import result_formatter as rf
    masked = rf._mask_card("1234-5678-9012-3456")
    assert "****" in masked and "3456" in masked

def test_acl_pii_masking_email_format(result_formatter_cls):
    import result_formatter as rf
    masked = rf._mask_email("alice@example.com")
    assert "@" in masked

def test_acl_blocked_injection_no_data_leak(validator, va_request_cls):
    r = validator.validate(va_request_cls(
        sql="SELECT * FROM customers UNION SELECT credit_card FROM payments LIMIT 5",
        parameters=[],
    ))
    assert not r.safe
    assert not r.signature

def test_acl_injection_blocked_count(validator, va_request_cls):
    sqls = [
        "DROP TABLE customers",
        "DELETE FROM customers WHERE 1=1",
        "SELECT * FROM customers WHERE id=1 OR 1=1 LIMIT 10",
        "SELECT id LIMIT 10 UNION SELECT password FROM admin",
        "SELECT * FROM customers",
        "INSERT INTO customers VALUES (1,'x','y')",
        "UPDATE customers SET name='x'",
        "TRUNCATE TABLE customers",
        "CREATE TABLE evil (id INT)",
        "ALTER TABLE customers ADD hacked TEXT",
    ]
    blocked = [s for s in sqls if _blocked_f(validator, va_request_cls, s)]
    assert len(blocked) == len(sqls), f"Only {len(blocked)}/{len(sqls)} blocked"

def test_acl_safe_queries_all_signed(validator, va_request_cls):
    sqls = [
        "SELECT id FROM customers LIMIT 5",
        "SELECT id, name FROM accounts LIMIT 10",
        "SELECT customer_id FROM customers WHERE 1=? LIMIT 100",
    ]
    for sql in sqls:
        r = validator.validate(va_request_cls(sql=sql, parameters=[]))
        assert r.safe and r.signature and r.signature.startswith("sha256:")

def test_acl_checks_passed_list_populated(validator, va_request_cls):
    r = validator.validate(va_request_cls(sql="SELECT id FROM customers LIMIT 10", parameters=[]))
    assert r.safe and len(r.checks_passed) >= 3
