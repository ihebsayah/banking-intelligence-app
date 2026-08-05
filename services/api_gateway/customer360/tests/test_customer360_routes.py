"""Route-level guard tests for Customer 360 (Phase 3A.2a).

Verify the permission gate (require_any_permission_audited) independently of
any org scope, plus the 200/403/404 behaviour of the overview and transactions
endpoints. The Customer 360 service is faked so only routing/auth is tested.
"""
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.models import User

import routes as routes_mod
from customer360.models import (
    Customer360Overview,
    CustomerIdentity,
    DataQuality,
    TransactionRow,
    TransactionSummary,
)


def _user(role="analyst", permissions=None, user_id="u_1"):
    return User(user_id=user_id, user_role=role, permissions=permissions or [])


class _FakeService:
    """Raises if called — lets tests prove the guard blocks before the service."""

    def __init__(self, overview=None, tx_result=None):
        self.overview = overview
        self.tx_result = tx_result
        self.calls = []

    async def get_overview(self, user, customer_id, request_id=""):
        self.calls.append(("overview", user.user_id, customer_id))
        return self.overview

    async def get_transactions(self, user, customer_id, request_id="", limit=20, offset=0):
        self.calls.append(("transactions", user.user_id, customer_id))
        return self.tx_result


def _min_overview():
    return (
        Customer360Overview(
            customer=CustomerIdentity(customer_id="CUST_00001", name="Fouad Ben Salah"),
            generated_at="t",
        ),
        {"sections_granted": ["relationship"]},
    )


def _min_tx():
    return (
        TransactionSummary(d30_total_count=1),
        [TransactionRow(transaction_id="TX-1", amount="-100.00")],
        1,
        DataQuality(),
        {"sections_granted": ["transactions"]},
    )


def _make_client(monkeypatch, user, fake_service):
    app = FastAPI()
    app.include_router(routes_mod.router)

    async def override_user():
        return user

    app.dependency_overrides[routes_mod.get_current_user] = override_user
    monkeypatch.setattr(routes_mod, "_get_customer360_service", lambda request: fake_service)
    return TestClient(app)


def test_manager_denied_even_with_scope_assigned(monkeypatch):
    # Manager holds no customer:read_* permission. A scope in the fixture (the
    # fake service would resolve one and would be called) must NOT matter — the
    # guard denies before the service is ever reached.
    fake = _FakeService(overview=_min_overview(), tx_result=_min_tx())
    client = _make_client(
        monkeypatch,
        _user("manager", [], user_id="manager_001"),
        fake,
    )
    assert client.get("/api/v1/customers/CUST_00001/overview").status_code == 403
    assert client.get("/api/v1/customers/CUST_00001/transactions").status_code == 403
    assert fake.calls == []  # guard fired before the service


def test_admin_transactions_denied_403(monkeypatch):
    # Admin has metadata perms but no customer:read_transactions.
    fake = _FakeService(overview=_min_overview(), tx_result=_min_tx())
    client = _make_client(
        monkeypatch,
        _user(
            "admin",
            ["customer:read", "customer:read_basic", "customer:read_operational_metadata"],
            user_id="admin_001",
        ),
        fake,
    )
    assert client.get("/api/v1/customers/CUST_00001/transactions").status_code == 403
    # overview still allowed (metadata view)
    assert client.get("/api/v1/customers/CUST_00001/overview").status_code == 200
    assert ("overview", "admin_001", "CUST_00001") in fake.calls
    assert not any(c[0] == "transactions" for c in fake.calls)


def test_analyst_transactions_allowed_in_scope(monkeypatch):
    fake = _FakeService(tx_result=_min_tx())
    client = _make_client(
        monkeypatch,
        _user(
            "analyst",
            ["customer:read", "customer:read_transactions", "customer:read_basic"],
            user_id="analyst_001",
        ),
        fake,
    )
    resp = client.get("/api/v1/customers/CUST_00001/transactions")
    assert resp.status_code == 200
    assert resp.json()["recent_transactions"][0]["transaction_id"] == "TX-1"
    assert ("transactions", "analyst_001", "CUST_00001") in fake.calls


def test_out_of_scope_compliance_overview_404(monkeypatch):
    # Compliance holds perms but the service resolves no overlap -> 404.
    fake = _FakeService(overview=None)  # None == customer missing / out of scope
    client = _make_client(
        monkeypatch,
        _user(
            "compliance",
            ["customer:read", "customer:read_basic", "customer:read_pii"],
            user_id="compliance_001",
        ),
        fake,
    )
    resp = client.get("/api/v1/customers/CUST_00001/overview")
    assert resp.status_code == 404
    assert resp.json()["detail"]["error"] == "CUSTOMER_NOT_FOUND"
