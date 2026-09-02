"""
tests/test_validator_matrix.py
Validator qualification matrix (Step 19): 28 cases TC-01..TC-28.

ACCEPT group (13): legitimate queries must PASS — including the compiler's
calculated-metric SQL (derived tables, scalar subqueries, EXISTS subqueries)
that the pre-Step-19 regex `nested_select` / `subselect_where` checks wrongly
rejected (E2E_021/061/062/086).

REJECT group (15): injection / DML / DDL / policy vectors must be BLOCKED.

Full security negative matrix lives in tests/test_security.py (50) +
services/validation_agent/injection_tester.py (22 live vectors).
"""
import sys
import os
import pytest

_VA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "validation_agent"))
if _VA not in sys.path:
    sys.path.insert(0, _VA)

for _mod in ["models", "query_validator"]:
    sys.modules.pop(_mod, None)

from query_validator import QueryValidator
from models import QueryValidationRequest


@pytest.fixture(scope="module")
def validator():
    return QueryValidator()


def _validate(validator, sql, params=None):
    return validator.validate(QueryValidationRequest(sql=sql, parameters=params or []))


# ─── ACCEPT GROUP (TC-01 .. TC-13) ─────────────────────────────────────────

def test_tc01_plain_select(validator):
    r = _validate(validator, "SELECT customer_id, name FROM customers ORDER BY name LIMIT 10")
    assert r.safe, r.issues
    assert r.signature
    assert len(r.checks_failed) == 0


def test_tc02_ratio_derived_table_npl(validator):
    sql = (
        "SELECT ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2) AS npl_ratio "
        "FROM (SELECT COUNT(DISTINCT n.loan_id) AS num FROM non_performing_loans n) AS _num, "
        "(SELECT COUNT(DISTINCT lc.loan_id) AS den FROM loan_contracts lc) AS _den LIMIT 100"
    )
    r = _validate(validator, sql)
    assert r.safe, f"derived-table ratio rejected: {r.issues}"


def test_tc03_ratio_roe(validator):
    sql = (
        "SELECT ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2) AS roe "
        "FROM (SELECT COALESCE(SUM(t.amount), 0) AS num FROM transactions t WHERE t.amount > 0) AS _num, "
        "(SELECT COALESCE(SUM(a.balance), 0) AS den FROM accounts a WHERE a.status = 'active') AS _den LIMIT 100"
    )
    r = _validate(validator, sql)
    assert r.safe, f"ROE derived tables rejected: {r.issues}"


def test_tc04_ratio_roa(validator):
    sql = (
        "SELECT ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2) AS roa "
        "FROM (SELECT COALESCE(SUM(n.provision_amount), 0) AS num FROM risk_flags n) AS _num, "
        "(SELECT COALESCE(SUM(c.asset_value), 0) AS den FROM customers c) AS _den LIMIT 100"
    )
    r = _validate(validator, sql)
    assert r.safe, f"ROA derived tables rejected: {r.issues}"


def test_tc05_ratio_loan_to_deposit(validator):
    sql = (
        "SELECT ROUND(100.0 * _num.num::numeric / NULLIF(_den.den::numeric, 0), 2) AS loan_to_deposit "
        "FROM (SELECT COALESCE(SUM(lc.principal_amount), 0) AS num FROM loan_contracts lc WHERE lc.currency = 'TND') AS _num, "
        "(SELECT COALESCE(SUM(a.balance), 0) AS den FROM accounts a WHERE a.currency = 'TND') AS _den LIMIT 100"
    )
    r = _validate(validator, sql)
    assert r.safe, f"loan-to-deposit rejected: {r.issues}"


def test_tc06_scalar_subquery_in_select(validator):
    sql = "SELECT (SELECT COUNT(*) FROM customers) AS total_customers LIMIT 1"
    r = _validate(validator, sql)
    assert r.safe, f"scalar subquery rejected: {r.issues}"


def test_tc07_exists_subquery(validator):
    sql = (
        "SELECT c.name FROM customers c "
        "WHERE EXISTS (SELECT 1 FROM accounts a WHERE a.customer_id = c.customer_id) LIMIT 10"
    )
    r = _validate(validator, sql)
    assert r.safe, f"EXISTS subquery rejected: {r.issues}"


def test_tc08_readonly_cte(validator):
    sql = "WITH recent AS (SELECT customer_id, name FROM customers WHERE kyc_verified = TRUE) SELECT * FROM recent LIMIT 5"
    r = _validate(validator, sql)
    assert r.safe, f"read-only CTE rejected: {r.issues}"


def test_tc09_parameterized_filter(validator):
    sql = "SELECT loan_id, principal_amount FROM loan_contracts WHERE status = $1 AND days_past_due > $2 LIMIT 100"
    r = _validate(validator, sql, params=["active", 30])
    assert r.safe, r.issues


def test_tc10_aggregation_group_by(validator):
    sql = "SELECT branch_id, COUNT(*) FROM accounts GROUP BY branch_id ORDER BY COUNT(*) DESC LIMIT 100"
    r = _validate(validator, sql)
    assert r.safe, r.issues


def test_tc11_join_where_limit(validator):
    sql = (
        "SELECT c.customer_id, c.name, a.balance FROM customers c "
        "INNER JOIN accounts a ON c.customer_id = a.customer_id "
        "WHERE a.balance > $1 AND a.currency = 'USD' LIMIT 100"
    )
    r = _validate(validator, sql, params=[0])
    assert r.safe, r.issues


def test_tc12_commentless_sanitization(validator):
    sql = "SELECT customer_id FROM customers WHERE segment = 'premium' LIMIT 50"
    r = _validate(validator, sql)
    assert r.safe
    assert "sanitized_sql" in r.model_dump() or r.sanitized_sql is not None


def test_tc13_signature_roundtrip(validator):
    sql = "SELECT customer_id FROM customers LIMIT 5"
    r = _validate(validator, sql)
    assert r.safe
    assert r.signature.startswith("sha256:")
    assert validator.verify_signature(sql, [], r.signature) is True


# ─── REJECT GROUP (TC-14 .. TC-28) ─────────────────────────────────────────

def test_tc14_drop_table(validator):
    r = _validate(validator, "DROP TABLE customers")
    assert not r.safe
    assert "keyword_check" in r.checks_failed or "select_only" in r.checks_failed


def test_tc15_stacked_delete(validator):
    r = _validate(validator, "SELECT * FROM customers; DELETE FROM customers WHERE 1=1")
    assert not r.safe


def test_tc16_union_select_exfil(validator):
    sql = "SELECT customer_id FROM customers LIMIT 10 UNION SELECT username, password FROM admin"
    r = _validate(validator, sql)
    assert not r.safe


def test_tc17_or_1_equals_1(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE customer_id = 1 OR 1=1 LIMIT 10")
    assert not r.safe


def test_tc18_and_true_boolean_blind(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE status = 'inactive' AND TRUE LIMIT 100")
    assert not r.safe


def test_tc19_sleep_time_based(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE customer_id = 1 AND SLEEP(5) LIMIT 100")
    assert not r.safe


def test_tc20_benchmark_time_based(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE 1=BENCHMARK(1000000,MD5('test')) LIMIT 100")
    assert not r.safe


def test_tc21_pg_sleep(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE customer_id = 1 AND (SELECT pg_sleep(5)) LIMIT 100")
    assert not r.safe


def test_tc22_subquery_exfil_in_where(validator):
    sql = "SELECT * FROM customers WHERE customer_id = (SELECT id FROM users WHERE email='x@y.z') LIMIT 100"
    r = _validate(validator, sql)
    assert not r.safe, "subquery exfil in WHERE must be blocked"


def test_tc23_block_comment_bypass(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE /*injected*/ 1=1 LIMIT 100")
    assert not r.safe


def test_tc24_inline_comment_bypass(validator):
    r = _validate(validator, "SELECT * FROM customers WHERE customer_id = 1 --' AND active=1 LIMIT 1")
    assert not r.safe


def test_tc25_insert(validator):
    r = _validate(validator, "INSERT INTO customers (email) VALUES ('attacker@evil.com')")
    assert not r.safe
    assert "keyword_check" in r.checks_failed or "select_only" in r.checks_failed


def test_tc26_update(validator):
    r = _validate(validator, "UPDATE customers SET credit_score = 999 WHERE 1=1")
    assert not r.safe


def test_tc27_exec_cmdshell(validator):
    r = _validate(validator, "EXEC xp_cmdshell('whoami')")
    assert not r.safe


def test_tc28_missing_limit(validator):
    r = _validate(validator, "SELECT customer_id FROM customers")
    assert not r.safe
    assert "limit_check" in r.checks_failed