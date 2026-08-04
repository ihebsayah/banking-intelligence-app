"""
tests/test_branch_resolver.py
Unit tests for BranchResolver resolution policy (exact -> unique partial -> fail closed).
"""
import sys
import os

_SA = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "sql_agent"))
if _SA not in sys.path:
    sys.path.insert(0, _SA)

from branch_resolver import BranchResolver

BRANCHES = [
    ("BR_TN_001", "Tunis Main Branch"),
    ("BR_TN_002", "Sfax Hub Branch"),
    ("BR_016", "Agence Lac 2 16"),
    ("BR_002", "Agence Ariana Centre 2"),
    ("BR_027", "Agence Ariana Centre 27"),
]


class FakeCursor:
    def __init__(self, sql, param):
        self.sql = sql
        self.param = param

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        name = (params[0] or "").lower()
        if "=" in sql.upper():
            rows = [r for r in BRANCHES if r[1].lower() == name]
        else:
            rows = [r for r in BRANCHES if name in r[1].lower()]
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return FakeCursor("", None)


def make_resolver():
    return BranchResolver(get_conn=lambda: FakeConn())


def test_exact_match_case_insensitive():
    r = make_resolver().resolve("tunis main branch")
    assert r["resolved"] is True
    assert r["branch_id"] == "BR_TN_001"
    assert r["match_type"] == "exact"


def test_unique_partial_match():
    r = make_resolver().resolve("Lac 2 16")
    assert r["resolved"] is True
    assert r["branch_id"] == "BR_016"
    assert r["name"] == "Agence Lac 2 16"
    assert r["match_type"] == "partial"


def test_no_match_fails_closed():
    r = make_resolver().resolve("Sfax Main Branch")
    assert r["resolved"] is False
    assert r["reason"] == "not_found"
    assert r["matches"] == []


def test_ambiguous_returns_candidates():
    r = make_resolver().resolve("Ariana Centre")
    assert r["resolved"] is False
    assert r["reason"] == "ambiguous"
    assert len(r["matches"]) == 2


def test_empty_name_fails_closed():
    r = make_resolver().resolve("   ")
    assert r["resolved"] is False
    assert r["reason"] == "empty_name"
