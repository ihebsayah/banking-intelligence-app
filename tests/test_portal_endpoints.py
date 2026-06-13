"""
tests/test_portal_endpoints.py
Unit tests for all new Banking Intelligence portal API endpoints.

Runs WITHOUT Docker — uses FastAPI TestClient with mocked DatabaseConnector
and asyncpg stubs installed by conftest.py.

Coverage:
  - Auth & RBAC (role enforcement on all endpoint groups)
  - Dashboard endpoints (overview, kpis, recent-activity, charts)
  - KPI endpoints (catalog, values, metrics, trends)
  - Risk endpoints (overview, flags, segments, summary)
  - Compliance endpoints (overview, report, rules, violations)
  - Audit logs endpoint (paginated)
  - Reports endpoints (list, generate)
  - Profile endpoints (users/me, auth/me)
  - Admin endpoints (users, roles, permissions)
"""
import sys
import os
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# ─── path setup ───────────────────────────────────────────────────────────────
BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GATEWAY = os.path.join(BASE, "services/api_gateway")
SHARED = os.path.join(BASE, "services/shared")

for p in [GATEWAY, SHARED, "/app/shared", "/app"]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ─── FastAPI TestClient ────────────────────────────────────────────────────────
from fastapi.testclient import TestClient
from shared.models import User, UserRole


# ─── Helpers to build mock DB ─────────────────────────────────────────────────

def make_db(fetch_one_return=None, fetch_all_return=None, execute_return="OK"):
    """Return a mock DatabaseConnector with configurable return values."""
    db = MagicMock()
    
    async def mock_fetch_one(query, *args):
        if "SELECT status, role, permissions FROM users" in query:
            uid = args[0] if args else "admin_001"
            role = "admin"
            if "analyst" in uid:
                role = "analyst"
            elif "compliance" in uid:
                role = "compliance"
            elif "manager" in uid:
                role = "manager"
            return {
                "user_id": uid,
                "role": role,
                "password_hash": "$2b$12$kc0bFMxOvWwy6Y6vd23VOeoWHSgBh3MPKUqlBiD2wmEG.nbuChW4y",
                "permissions": [],
                "status": "active",
                "must_change_password": False
            }
        if isinstance(fetch_one_return, list):
            return fetch_one_return.pop(0) if fetch_one_return else None
        return fetch_one_return

    db.fetch_one = AsyncMock(side_effect=mock_fetch_one)
    db.fetch_all = AsyncMock(return_value=fetch_all_return or [])
    db.execute = AsyncMock(return_value=execute_return)
    db._pool = MagicMock()
    return db


# ─── Shared fixture: test app + tokens ───────────────────────────────────────

@pytest.fixture(scope="module")
def app_and_tokens():
    """
    Boots the FastAPI app and returns (client, tokens_dict).
    Tokens are generated via create_access_token for each role.
    """
    import main as gw
    from auth import create_access_token, verify_token
    from routes import get_current_user, security
    from fastapi import Depends, HTTPException
    
    client = TestClient(gw.app, raise_server_exceptions=False)
    
    tokens = {
        role: f"Bearer {create_access_token(f'{role}_001', role)[0]}"
        for role in ("analyst", "manager", "compliance", "admin")
    }
    
    async def override_get_current_user(credentials = Depends(security)):
        # Mirror production: no credentials → 401, invalid token → 401
        if not credentials:
            raise HTTPException(status_code=401, detail="Not authenticated")
        try:
            user_id, user_role = verify_token(credentials.credentials)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        ROLE_PERMISSIONS = {
            "analyst":    ["read:customers", "read:accounts", "read:transactions", "read:risk_flags"],
            "manager":    ["read:customers", "read:accounts", "read:transactions", "read:branch_data", "read:risk_summary"],
            "compliance": ["read:customers", "read:accounts", "read:transactions", "read:risk_flags", "read:audit_logs", "read:pii"],
            "admin":      ["read:customers", "read:accounts", "read:transactions", "read:risk_flags", "read:audit_logs", "read:pii", "admin:users", "admin:roles", "write:reports"],
        }
        return User(
            user_id=user_id,
            user_role=user_role,
            permissions=ROLE_PERMISSIONS.get(user_role, [])
        )
        
    gw.app.dependency_overrides[get_current_user] = override_get_current_user
    
    yield client, tokens
    
    gw.app.dependency_overrides.pop(get_current_user, None)


# ─── Auth header shortcuts ────────────────────────────────────────────────────

def _h(token: str) -> dict:
    return {"Authorization": token}


# ─── DB injection via app.state ───────────────────────────────────────────────

@pytest.fixture(autouse=True)
def inject_db(app_and_tokens):
    """Before each test inject a fresh mock DB into app.state."""
    client, _ = app_and_tokens
    app = client.app
    app.state.db = make_db()
    app.state.audit_db = make_db()
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# ─── AUTH & HEALTH ────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthAndAuth:
    def test_health_returns_200(self, app_and_tokens):
        client, _ = app_and_tokens
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_login_missing_creds_returns_422(self, app_and_tokens):
        client, _ = app_and_tokens
        r = client.post("/auth/login")
        assert r.status_code == 422

    def test_protected_route_without_token_returns_401(self, app_and_tokens):
        client, _ = app_and_tokens
        r = client.get("/dashboard/overview")
        assert r.status_code == 401

    def test_invalid_token_returns_401(self, app_and_tokens):
        client, _ = app_and_tokens
        r = client.get("/dashboard/overview", headers={"Authorization": "Bearer INVALID"})
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# ─── RBAC ENFORCEMENT ─────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestRBAC:
    """Verify that role-restricted routes return 403 for wrong roles."""

    def test_compliance_endpoint_blocked_for_analyst(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_one_return={
            "total": 12, "enabled_count": 12,
            "total_violations": 0, "aml_count": 0,
            "kyc_incomplete": 0
        })
        r = client.get("/compliance/overview", headers=_h(tokens["analyst"]))
        assert r.status_code == 403

    def test_audit_logs_blocked_for_manager(self, app_and_tokens):
        client, tokens = app_and_tokens
        r = client.get("/audit/logs", headers=_h(tokens["manager"]))
        assert r.status_code == 403

    def test_admin_users_blocked_for_compliance(self, app_and_tokens):
        client, tokens = app_and_tokens
        r = client.get("/admin/users", headers=_h(tokens["compliance"]))
        assert r.status_code == 403

    def test_admin_endpoint_accessible_by_admin(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[])
        r = client.get("/admin/users", headers=_h(tokens["admin"]))
        assert r.status_code == 200

    def test_compliance_endpoint_accessible_by_compliance(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_one_return={
            "total": 12, "enabled_count": 12,
            "total_violations": 0, "aml_count": 0,
            "kyc_incomplete": 0
        })
        r = client.get("/compliance/overview", headers=_h(tokens["compliance"]))
        assert r.status_code == 200

    def test_compliance_endpoint_accessible_by_admin(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_one_return={
            "total": 12, "enabled_count": 12,
            "total_violations": 0, "aml_count": 0,
            "kyc_incomplete": 0
        })
        r = client.get("/compliance/overview", headers=_h(tokens["admin"]))
        assert r.status_code == 200

    def test_risk_summary_accessible_by_analyst(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(
            fetch_all_return=[{"severity": "high", "n": 5}],
            fetch_one_return={"high_risk_customers": 3, "critical_customers": 1, "avg_risk_score": 0.45}
        )
        r = client.get("/risk/summary", headers=_h(tokens["analyst"]))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# ─── DASHBOARD ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def _setup_overview_db(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_one_return={
            "total_customers": 210, "total_accounts": 415,
            "active_accounts": 385, "total_deposits": 12_345_678.50,
            "monthly_transactions": 1234, "high_risk_customers": 18,
        })
        return client, tokens

    def test_dashboard_overview_200(self, app_and_tokens):
        client, tokens = self._setup_overview_db(app_and_tokens)
        r = client.get("/dashboard/overview", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total_customers"] == 210
        assert body["total_deposits"] == 12_345_678.50

    def test_dashboard_overview_has_last_updated(self, app_and_tokens):
        client, tokens = self._setup_overview_db(app_and_tokens)
        r = client.get("/dashboard/overview", headers=_h(tokens["analyst"]))
        assert "last_updated" in r.json()

    def test_dashboard_kpis_returns_list(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(
            fetch_one_return={"total_deposits": 9_000_000, "monthly_revenue": 18_000,
                              "active_customers": 190, "avg_risk_score": 0.35},
        )
        r = client.get("/dashboard/kpis", headers=_h(tokens["manager"]))
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        assert len(body) == 4
        ids = [k["kpi_id"] for k in body]
        assert "total_deposits" in ids
        assert "avg_risk_score" in ids

    def test_dashboard_kpis_values_are_numeric(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(
            fetch_one_return={"total_deposits": 1_000_000, "monthly_revenue": 2_000,
                              "active_customers": 50, "avg_risk_score": 0.25},
        )
        r = client.get("/dashboard/kpis", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        for kpi in r.json():
            assert isinstance(kpi["value"], (int, float))

    def test_dashboard_recent_activity_returns_list(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[{
            "transaction_id": "TXN001", "customer_id": "CUST001", "account_id": "ACC001",
            "amount": 1500.0, "transaction_type": "credit", "status": "completed",
            "description": "Salary", "transaction_date": datetime.utcnow(),
        }])
        r = client.get("/dashboard/recent-activity", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert r.json()[0]["transaction_id"] == "TXN001"

    def test_dashboard_recent_activity_limit_param(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[])
        r = client.get("/dashboard/recent-activity?limit=5", headers=_h(tokens["analyst"]))
        assert r.status_code == 200

    def test_dashboard_chart_revenue_trend(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"label": "Jan", "value": 10_000}, {"label": "Feb", "value": 11_000}
        ])
        r = client.get("/dashboard/charts/revenue_trend", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert body["chart_id"] == "revenue_trend"
        assert body["chart_type"] == "line"
        assert len(body["data"]) == 2

    def test_dashboard_chart_risk_levels(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"label": "low", "value": 60}, {"label": "high", "value": 15}
        ])
        r = client.get("/dashboard/charts/risk_levels", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert r.json()["chart_type"] == "pie"

    def test_dashboard_chart_concentration(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"label": "premium", "value": 5_000_000}
        ])
        r = client.get("/dashboard/charts/concentration", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert r.json()["chart_type"] == "bar"

    def test_dashboard_chart_growth_rate(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"label": "Jan", "value": 12}
        ])
        r = client.get("/dashboard/charts/growth_rate", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert r.json()["chart_type"] == "area"

    def test_dashboard_chart_unknown_returns_404(self, app_and_tokens):
        client, tokens = app_and_tokens
        r = client.get("/dashboard/charts/unknown_chart", headers=_h(tokens["analyst"]))
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# ─── KPI ──────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestKPI:
    def test_kpi_catalog_returns_list(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"kpi_id": "total_deposits", "name": "Total Deposits",
             "metric_type": "currency", "category": "profitability",
             "description": "Desc", "data_freshness": "real-time", "created_at": datetime.utcnow()}
        ])
        r = client.get("/kpi/catalog", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_kpi_values_has_six_kpis(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(
            fetch_one_return={"total_deposits": 1_000_000, "monthly_revenue": 2_000,
                              "active_customers": 50, "avg_risk_score": 0.25, "kyc_compliance_rate": 90.0},
        )
        client.app.state.db.fetch_all = AsyncMock(return_value=[])
        r = client.get("/kpi/values", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert len(r.json()) == 6

    def test_kpi_metrics_alias_matches_values(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(
            fetch_one_return={"total_deposits": 1_000_000, "monthly_revenue": 2_000,
                              "active_customers": 50, "avg_risk_score": 0.25, "kyc_compliance_rate": 90.0},
        )
        client.app.state.db.fetch_all = AsyncMock(return_value=[])
        r = client.get("/kpi/metrics", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert len(r.json()) == 6

    def test_kpi_trends_returns_trend_data(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"month": "2026-01", "fee_revenue": 5000.0,
             "transaction_count": 100, "avg_transaction_size": 500.0}
        ])
        r = client.get("/kpi/trends?months=6", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert "trends" in body
        assert body["months"] == 6


# ═══════════════════════════════════════════════════════════════════════════════
# ─── RISK ─────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestRisk:
    def test_risk_overview_returns_correct_fields(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_one_return={
            "total_flags": 50, "critical_flags": 2, "high_flags": 10,
            "medium_flags": 20, "low_flags": 18,
            "avg_risk": 0.42, "high_risk_count": 15, "kyc_incomplete": 5
        })
        r = client.get("/risk/overview", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total_flags"] == 50
        assert body["critical_flags"] == 2
        assert body["average_risk_score"] == pytest.approx(0.42, abs=0.001)

    def test_risk_flags_pagination(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_one = AsyncMock(return_value={"n": 100})
        db.fetch_all = AsyncMock(return_value=[{
            "flag_id": "f1", "customer_id": "CUST001", "flag_type": "aml_suspicious",
            "severity": "high", "description": "Test flag", "resolved": False,
            "created_at": datetime.utcnow(),
        }])
        client.app.state.db = db
        r = client.get("/risk/flags?page=1&page_size=10", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 100
        assert body["page"] == 1
        assert body["page_size"] == 10
        assert len(body["items"]) == 1

    def test_risk_flags_severity_filter_accepted(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_one = AsyncMock(return_value={"n": 0})
        db.fetch_all = AsyncMock(return_value=[])
        client.app.state.db = db
        r = client.get("/risk/flags?severity=critical", headers=_h(tokens["analyst"]))
        assert r.status_code == 200

    def test_risk_segments_returns_list(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[
            {"segment": "premium", "customer_count": 70, "avg_risk_score": 0.15, "total_balance": 8_000_000},
            {"segment": "standard", "customer_count": 120, "avg_risk_score": 0.40, "total_balance": 3_000_000},
        ])
        r = client.get("/risk/segments", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert len(r.json()) == 2

    def test_risk_summary_structure(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_all = AsyncMock(return_value=[{"severity": "high", "n": 10}])
        db.fetch_one = AsyncMock(return_value={
            "high_risk_customers": 15, "critical_customers": 2, "avg_risk_score": 0.38
        })
        client.app.state.db = db
        r = client.get("/risk/summary", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert "risk_level_distribution" in body
        assert body["risk_level_distribution"]["high"] == 10
        assert body["average_risk_score"] == pytest.approx(0.38, abs=0.001)


# ═══════════════════════════════════════════════════════════════════════════════
# ─── COMPLIANCE ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompliance:
    def _compliance_db(self, app_and_tokens, violations=0, kyc_incomplete=0):
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_one = AsyncMock(side_effect=[
            {"total": 12, "enabled_count": 12},        # rules query
            {"total_violations": violations, "aml_count": 0},  # violations query
            {"kyc_incomplete": kyc_incomplete},         # kyc query
        ])
        client.app.state.db = db
        return client, tokens

    def test_compliance_overview_compliant(self, app_and_tokens):
        client, tokens = self._compliance_db(app_and_tokens)
        r = client.get("/compliance/overview", headers=_h(tokens["compliance"]))
        assert r.status_code == 200
        body = r.json()
        assert body["gdpr_status"] == "compliant"
        assert body["total_rules"] == 12

    def test_compliance_overview_warning_when_violations(self, app_and_tokens):
        client, tokens = self._compliance_db(app_and_tokens, violations=3)
        r = client.get("/compliance/overview", headers=_h(tokens["compliance"]))
        body = r.json()
        assert body["gdpr_status"] == "warning"
        assert body["active_violations_count"] == 3

    def test_compliance_report_alias(self, app_and_tokens):
        client, tokens = self._compliance_db(app_and_tokens)
        r = client.get("/compliance/report", headers=_h(tokens["compliance"]))
        assert r.status_code == 200
        assert "gdpr_status" in r.json()

    def test_compliance_rules_returns_list(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_all_return=[{
            "rule_id": "some-uuid", "rule_name": "Mask PII - GDPR",
            "regulation": "GDPR", "rule_type": "data_masking",
            "condition": "column IN (email)", "action": "MASK_VALUE",
            "enabled": True, "created_at": datetime.utcnow(),
        }])
        r = client.get("/compliance/rules", headers=_h(tokens["compliance"]))
        assert r.status_code == 200
        rules = r.json()
        assert len(rules) == 1
        assert rules[0]["regulation"] == "GDPR"

    def test_compliance_violations_paginated(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_one = AsyncMock(return_value={"n": 5})
        db.fetch_all = AsyncMock(return_value=[{
            "violation_id": "v1", "query_id": None, "user_id": "analyst_001",
            "violation_type": "data_access", "severity": "medium", "description": "Desc",
            "regulation": "GDPR", "detected_at": datetime.utcnow(), "status": "open",
            "resolution_notes": None,
        }])
        client.app.state.db = db
        r = client.get("/compliance/violations", headers=_h(tokens["compliance"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 5
        assert len(body["items"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ─── AUDIT LOGS ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditLogs:
    def test_audit_logs_paginated(self, app_and_tokens):
        client, tokens = app_and_tokens
        audit_db = make_db()
        audit_db.fetch_one = AsyncMock(return_value={"n": 42})
        audit_db.fetch_all = AsyncMock(return_value=[{
            "id": "some-id", "audit_id": "audit-1",
            "timestamp": datetime.utcnow(), "user_id": "analyst_001",
            "user_role": "analyst", "action": "api_call", "status": "success",
            "ip_address": "127.0.0.1", "endpoint": "/dashboard/kpis",
            "http_method": "GET", "execution_time_ms": 45, "error_message": None,
        }])
        client.app.state.audit_db = audit_db
        r = client.get("/audit/logs?page=1&page_size=10", headers=_h(tokens["compliance"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 42
        assert body["page"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["user_id"] == "analyst_001"

    def test_audit_logs_user_filter(self, app_and_tokens):
        client, tokens = app_and_tokens
        audit_db = make_db()
        audit_db.fetch_one = AsyncMock(return_value={"n": 5})
        audit_db.fetch_all = AsyncMock(return_value=[])
        client.app.state.audit_db = audit_db
        r = client.get("/audit/logs?user_id=analyst_001", headers=_h(tokens["compliance"]))
        assert r.status_code == 200

    def test_audit_logs_blocked_for_analyst(self, app_and_tokens):
        client, tokens = app_and_tokens
        r = client.get("/audit/logs", headers=_h(tokens["analyst"]))
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# ─── REPORTS ──────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestReports:
    def test_list_reports_paginated(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_one = AsyncMock(return_value={"n": 3})
        db.fetch_all = AsyncMock(return_value=[{
            "report_id": "r1", "report_type": "aml_summary", "regulation": "AML",
            "report_period_start": None, "report_period_end": None,
            "generated_at": datetime.utcnow(), "status": "draft",
            "submitted_to": None, "submitted_at": None,
        }])
        client.app.state.db = db
        r = client.get("/reports", headers=_h(tokens["manager"]))
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        assert body["items"][0]["report_type"] == "aml_summary"

    def test_generate_aml_report(self, app_and_tokens):
        # write:reports is an admin-only permission
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_all = AsyncMock(return_value=[
            {"transaction_type": "credit", "status": "completed", "tx_count": 100, "total_amount": 500_000}
        ])
        db.fetch_one = AsyncMock(return_value={
            "report_id": "new-report-id", "generated_at": datetime.utcnow()
        })
        client.app.state.db = db
        r = client.post("/reports/generate", headers=_h(tokens["admin"]),
            json={"report_type": "aml_summary", "regulation": "AML"})
        assert r.status_code == 201
        body = r.json()
        assert body["report_type"] == "aml_summary"
        assert body["status"] == "draft"
        assert "report_id" in body

    def test_generate_kyc_report(self, app_and_tokens):
        # write:reports is an admin-only permission
        client, tokens = app_and_tokens
        db = make_db()
        db.fetch_all = AsyncMock(return_value=[
            {"kyc_verified": True, "segment": "premium", "customer_count": 50, "avg_risk": 0.12}
        ])
        db.fetch_one = AsyncMock(return_value={
            "report_id": "kyc-report-id", "generated_at": datetime.utcnow()
        })
        client.app.state.db = db
        r = client.post("/reports/generate", headers=_h(tokens["admin"]),
            json={"report_type": "kyc_status", "regulation": "KYC"})
        assert r.status_code == 201

    def test_generate_report_missing_fields_422(self, app_and_tokens):
        # admin has write:reports; validation (422) fires before permission check
        client, tokens = app_and_tokens
        r = client.post("/reports/generate", headers=_h(tokens["admin"]), json={})
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# ─── PROFILE ──────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestProfile:
    def _profile_db(self, app_and_tokens, user_row=None):
        client, tokens = app_and_tokens
        client.app.state.db = make_db(fetch_one_return=user_row or {
            "user_id": "analyst_001", "email": "analyst_001@bankintel.hq",
            "name": "Analyst One", "role": "analyst", "bank_id": "hq_main",
            "created_at": datetime.utcnow(), "last_login": datetime.utcnow(), "status": "active"
        })
        return client, tokens

    def test_users_me_returns_profile(self, app_and_tokens):
        client, tokens = self._profile_db(app_and_tokens)
        r = client.get("/users/me", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == "analyst_001"
        assert body["role"] == "analyst"

    def test_auth_me_alias_returns_profile(self, app_and_tokens):
        client, tokens = self._profile_db(app_and_tokens)
        r = client.get("/auth/me", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        assert "user_id" in r.json()

    def test_users_me_fallback_when_db_none(self, app_and_tokens):
        client, tokens = app_and_tokens
        client.app.state.db = None
        r = client.get("/users/me", headers=_h(tokens["analyst"]))
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == "analyst_001"

    def test_users_me_no_token_401(self, app_and_tokens):
        client, _ = app_and_tokens
        r = client.get("/users/me")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# ─── ADMIN ────────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdmin:
    def _admin_db(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db(fetch_all_return=[{
            "user_id": "analyst_001", "email": "analyst_001@bankintel.hq",
            "name": "Analyst One", "role": "analyst", "bank_id": "hq_main",
            "created_at": datetime.utcnow(), "last_login": datetime.utcnow(), "status": "active"
        }])
        db.fetch_one = AsyncMock(return_value={"count": 1})
        client.app.state.db = db
        return client, tokens

    def test_admin_users_returns_list(self, app_and_tokens):
        client, tokens = self._admin_db(app_and_tokens)
        r = client.get("/admin/users", headers=_h(tokens["admin"]))
        assert r.status_code == 200
        body = r.json()
        assert "items" in body
        assert isinstance(body["items"], list)
        assert body["items"][0]["user_id"] == "analyst_001"

    def test_admin_users_role_filter(self, app_and_tokens):
        client, tokens = app_and_tokens
        db = make_db(fetch_all_return=[])
        db.fetch_one = AsyncMock(return_value={"count": 0})
        client.app.state.db = db
        r = client.get("/admin/users?role=analyst", headers=_h(tokens["admin"]))
        assert r.status_code == 200

    def test_admin_roles_returns_roles(self, app_and_tokens):
        client, tokens = app_and_tokens
        
        def mock_fetch_all(query, *args):
            if "role_permissions" in query:
                return [
                    {"role_id": "analyst", "permission_key": "read:customers"},
                    {"role_id": "compliance", "permission_key": "read:audit_logs"},
                    {"role_id": "admin", "permission_key": "admin:users"},
                ]
            elif "users" in query:
                return [
                    {"role": "analyst", "user_count": 2},
                    {"role": "compliance", "user_count": 1},
                    {"role": "admin", "user_count": 1},
                ]
            return [
                {"role_id": "analyst", "label": "Analyst", "description": "Analyst role"},
                {"role_id": "compliance", "label": "Compliance", "description": "Compliance role"},
                {"role_id": "admin", "label": "Admin", "description": "Admin role"},
            ]
            
        db = make_db()
        db.fetch_all = AsyncMock(side_effect=mock_fetch_all)
        client.app.state.db = db
        
        r = client.get("/admin/roles", headers=_h(tokens["admin"]))
        assert r.status_code == 200
        roles = r.json()
        assert len(roles) == 3
        roles_map = {ro["role_id"]: ro for ro in roles}
        assert "analyst" in roles_map
        assert len(roles_map["compliance"]["permissions"]) > 0

    def test_admin_permissions_returns_permission_list(self, app_and_tokens):
        client, tokens = app_and_tokens
        
        def mock_fetch_all(query, *args):
            if "role_permissions" in query:
                return [
                    {"role_id": "admin", "permission_key": "admin:users"},
                    {"role_id": "admin", "permission_key": "read:customers"},
                ]
            return [
                {"permission_key": "read:customers", "label": "Read Customers", "description": "Read customers description", "category": "read"},
                {"permission_key": "admin:users", "label": "Admin Users", "description": "Admin users description", "category": "admin"},
            ]
            
        db = make_db()
        db.fetch_all = AsyncMock(side_effect=mock_fetch_all)
        client.app.state.db = db
        
        r = client.get("/admin/permissions", headers=_h(tokens["admin"]))
        assert r.status_code == 200
        perms = r.json()
        assert len(perms) >= 2
        perm_names = [p["permission_key"] for p in perms]
        assert "read:customers" in perm_names
        assert "admin:users" in perm_names

    def test_admin_permissions_only_admin_has_admin_role(self, app_and_tokens):
        client, tokens = app_and_tokens
        
        def mock_fetch_all(query, *args):
            if "role_permissions" in query:
                return [
                    {"role_id": "admin", "permission_key": "admin:users"},
                ]
            return [
                {"permission_key": "admin:users", "label": "Admin Users", "description": "Admin users description", "category": "admin"},
            ]
            
        db = make_db()
        db.fetch_all = AsyncMock(side_effect=mock_fetch_all)
        client.app.state.db = db
        
        r = client.get("/admin/permissions", headers=_h(tokens["admin"]))
        perms = r.json()
        admin_perm = next(p for p in perms if p["permission_key"] == "admin:users")
        assert admin_perm["roles"] == ["admin"]
