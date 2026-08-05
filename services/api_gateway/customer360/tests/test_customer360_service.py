"""Essential unit tests for the Customer 360 read bridge (Phase 3A.2).

Runs without a live database — the repository collaborators are faked. Scope
resolution, permission gating, PII masking, DTO serialisation, error mapping
and workbench-link construction are the behaviour under test.
"""
import pytest

from customer360 import service as service_mod
from customer360.models import Customer360Overview
from customer360.service import Customer360Service, Customer360SourceUnavailable
from shared.models import User

BASE_PERMISSIONS = [
    "customer:read_basic",
    "customer:read_financial",
    "customer:read_transactions",
    "customer:read_kyc",
    "customer:read_risk",
    "customer:read_compliance_history",
]

CORE = {
    "customer_id": "CUST_00001",
    "name": "Fouad Ben Salah",
    "email": "fouad@example.com",
    "phone": "+21650123456",
    "kyc_verified": True,
    "risk_score": "0.85",
    "segment": "PART_PREM",
    "created_at": "2024-01-15 09:30:00",
}

PROFILE = {
    "date_of_birth": "1985-04-12",
    "nationality": "TN",
    "national_id": "09643321",
    "passport_number": "P1234567",
    "employment_status": "employed",
    "employer_name": "Acme Tunisie",
    "annual_income": "250000.00",
    "income_currency": "TND",
    "net_worth_band": "500k_1m",
    "politically_exposed": False,
    "pep_details": None,
    "tax_id": "TAX778899",
}

BRANCHES = [
    {"branch_id": "BR_001", "branch_name": "Agence Menezel Temime 1",
     "region_id": "REG_TUNIS", "region_name_fr": "Tunis"},
]

RMS = [
    {"employee_id": "EMP_1", "first_name": "Sami", "last_name": "Hammami",
     "title": "Relation Manager", "portfolio_type": "premium"},
]

ACCOUNTS = [
    {"account_id": "ACC-00001", "account_type": "current", "status": "active",
     "balance": "1500.50", "available_balance": "1200.00", "currency": "TND",
     "branch_id": "BR_001", "branch_name": "Agence Menezel Temime 1",
     "created_at": "2024-02-01 00:00:00"},
]

LOANS = [
    {"loan_id": "LOAN-0001", "loan_type": "consumer", "product_name": "Auto",
     "principal_amount": "50000.00", "outstanding_balance": "20000.00",
     "currency": "TND", "interest_rate": "8.50",
     "maturity_date": "2028-01-15", "status": "active", "days_past_due": 0},
]

TX_SUMMARY = [
    {"currency": "TND", "d30_count": 12, "d30_amount": "5000.00",
     "d30_inbound_count": 7, "d30_inbound_amount": "3000.00",
     "d30_outbound_count": 5, "d30_outbound_amount": "2000.00",
     "d90_count": 30, "d90_amount": "12000.00"},
]

RECENT_TX = [
    {"transaction_id": "TX-00001", "account_id": "ACC-00001", "amount": "-250.00",
     "currency": "TND", "transaction_type": "retrait DAB", "status": "completed",
     "description": "Retrait DAB", "transaction_date": "2026-08-01 10:00:00"},
]

AML_COUNTS = [
    {"bucket": "status", "value": "ouvert", "cnt": 2},
    {"bucket": "severity", "value": "élevé", "cnt": 2},
]

ANALYTICS_ALERTS = [
    {"alert_id": "ALT-1", "alert_type": "aml", "alert_label_fr": "Transaction suspecte",
     "severity": "élevé", "status": "ouvert", "score": "0.9",
     "triggered_at": "2026-07-20 00:00:00"},
]

RISK_FLAGS = [
    {"id": "FLAG-1", "flag_type": "aml_suspicious", "severity": "high",
     "description": "Patterns inhabituels", "created_at": "2026-07-01 00:00:00"},
]


class FakeMainRepo:
    """Stands in for Customer360Repository (methods the service actually calls)."""

    def __init__(self):
        self.core = CORE
        self.profile = PROFILE
        self.branches = BRANCHES
        self.primary = BRANCHES[0]
        self.rms = RMS
        self.accounts = ACCOUNTS
        self.loans = LOANS
        self.tx_summary = TX_SUMMARY
        self.recent_tx = RECENT_TX
        self.latest_tx_date = {"latest": "2026-08-01 10:00:00"}
        self.top_types = [{"transaction_type": "retrait DAB", "cnt": 5}]
        self.latest_kyc = None
        self.latest_pep = None
        self.latest_sanctions = None
        self.aml_counts = AML_COUNTS
        self.sar = {"cnt": 1}
        self.risk_flags = RISK_FLAGS
        self.analytics = ANALYTICS_ALERTS
        self.tx_count = 42
        self.fail_core = False

    async def fetch_customer_core(self, customer_id):
        if self.fail_core:
            raise RuntimeError("main db down")
        return self.core

    async def fetch_profile(self, customer_id):
        return self.profile

    async def fetch_customer_branches(self, customer_id):
        return list(self.branches)

    async def fetch_primary_branch(self, customer_id):
        return self.primary

    async def fetch_relationship_managers(self, customer_id):
        return list(self.rms)

    async def fetch_accounts(self, customer_id, allowed_branches=None):
        return list(self.accounts)

    async def fetch_loans(self, customer_id, allowed_branches=None):
        return list(self.loans)

    async def fetch_transaction_summary(self, customer_id, allowed_accounts=None):
        return list(self.tx_summary)

    async def fetch_recent_transactions(self, customer_id, allowed_accounts=None,
                                        limit=20, offset=0):
        return list(self.recent_tx)

    async def fetch_transaction_count(self, customer_id, allowed_accounts=None):
        return self.tx_count

    async def fetch_latest_transaction_date(self, customer_id):
        return self.latest_tx_date

    async def fetch_top_transaction_types(self, customer_id):
        return list(self.top_types)

    async def fetch_latest_kyc_case(self, customer_id):
        return self.latest_kyc

    async def fetch_latest_pep(self, customer_id):
        return self.latest_pep

    async def fetch_latest_sanctions(self, customer_id):
        return self.latest_sanctions

    async def fetch_aml_alert_counts(self, customer_id):
        return list(self.aml_counts)

    async def fetch_sar_count(self, customer_id):
        return self.sar

    async def fetch_active_risk_flags(self, customer_id):
        return list(self.risk_flags)

    async def fetch_analytics_alerts(self, customer_id):
        return list(self.analytics)


class FakeWbRepo:
    """Stands in for WorkbenchLinkRepository.

    Defaults to the seeded reality: a normal business user holds the hq_main
    bank scope (unrestricted customer reads).
    """

    DEFAULT_SCOPES = [{"scope_id": "hq_main", "scope_type": "bank"}]

    def __init__(self, scopes=None):
        self.scopes = FakeWbRepo.DEFAULT_SCOPES if scopes is None else scopes

    async def fetch_user_scopes(self, user_id):
        return list(self.scopes or [])

    async def fetch_customer_linked_alerts(self, customer_id):
        return []

    async def fetch_investigations_for_alerts(self, alert_ids):
        return []

    async def fetch_cases_for_links(self, alert_ids, investigation_ids):
        return []

    async def fetch_irs_for_links(self, case_ids, investigation_ids):
        return []


def _user(role="analyst", permissions=None, user_id="u_1"):
    return User(user_id=user_id, user_role=role, permissions=permissions or [])


def _make_service(monkeypatch, main=None, wb=None):
    if main is None:
        main = FakeMainRepo()
    monkeypatch.setattr(service_mod, "Customer360Repository", lambda db: main)
    monkeypatch.setattr(service_mod, "WorkbenchLinkRepository", lambda db: wb)
    return Customer360Service(main_db=object(), wb_db=object() if wb is not None else None)


@pytest.mark.asyncio
async def test_overview_full_view_with_all_sections(monkeypatch):
    service = _make_service(monkeypatch, wb=FakeWbRepo())
    user = _user("analyst", BASE_PERMISSIONS)
    result = await service.get_overview(user, "CUST_00001")
    assert result is not None
    overview, audit = result
    assert isinstance(overview, Customer360Overview)
    assert overview.customer.customer_id == "CUST_00001"
    assert overview.relationship.primary_branch == "Agence Menezel Temime 1"
    assert overview.financial_summary.account_count == 1
    assert overview.financial_summary.total_balance_by_currency == {"TND": "1500.50"}
    assert overview.transaction_summary.d30_total_count == 12
    assert len(overview.recent_transactions) == 1
    assert overview.risk.risk_score == 0.85
    assert overview.risk.unresolved_flag_count == 1
    assert audit["action"] == "customer_360_access"
    assert set(audit["sections_granted"]) == set(service_mod.ALL_SECTIONS)


@pytest.mark.asyncio
async def test_overview_pii_masked_without_read_pii(monkeypatch):
    service = _make_service(monkeypatch, wb=FakeWbRepo())
    user = _user("analyst", BASE_PERMISSIONS)
    overview, _ = await service.get_overview(user, "CUST_00001")
    assert overview.customer.national_id == "****3321"
    assert overview.customer.email == "****.com"
    assert overview.customer.annual_income == "****0.00"


@pytest.mark.asyncio
async def test_overview_pii_unmasked_with_read_pii(monkeypatch):
    service = _make_service(monkeypatch, wb=FakeWbRepo())
    user = _user("compliance", BASE_PERMISSIONS + ["customer:read_pii"])
    overview, audit = await service.get_overview(user, "CUST_00001")
    assert overview.customer.national_id == "09643321"
    assert overview.customer.email == "fouad@example.com"
    assert "national_id" not in audit["fields_masked"]


@pytest.mark.asyncio
async def test_overview_missing_customer_returns_none(monkeypatch):
    main = FakeMainRepo()
    main.core = None
    service = _make_service(monkeypatch, main=main, wb=FakeWbRepo())
    assert await service.get_overview(_user("analyst", BASE_PERMISSIONS), "CUST_99999") is None


@pytest.mark.asyncio
async def test_overview_out_of_scope_returns_none(monkeypatch):
    main = FakeMainRepo()
    main.branches = BRANCHES  # customer only at BR_001
    wb = FakeWbRepo(scopes=[{"scope_id": "BR999", "scope_type": "branch"}])
    service = _make_service(monkeypatch, main=main, wb=wb)
    assert await service.get_overview(_user("analyst", BASE_PERMISSIONS), "CUST_00001") is None


@pytest.mark.asyncio
async def test_overview_source_unavailable_raises(monkeypatch):
    main = FakeMainRepo()
    main.fail_core = True
    service = _make_service(monkeypatch, main=main)
    with pytest.raises(Customer360SourceUnavailable):
        await service.get_overview(_user("analyst", BASE_PERMISSIONS), "CUST_00001")


@pytest.mark.asyncio
async def test_overview_section_gating_hides_ungranted_sections(monkeypatch):
    service = _make_service(monkeypatch, wb=FakeWbRepo())
    user = _user("analyst", ["customer:read_risk"])
    overview, audit = await service.get_overview(user, "CUST_00001")
    assert overview.risk is not None
    assert overview.financial_summary is None
    assert overview.transaction_summary is None
    assert overview.kyc_aml is None
    assert overview.workbench_links == []
    assert audit["sections_granted"] == ["relationship", "risk"]


@pytest.mark.asyncio
async def test_transactions_view(monkeypatch):
    service = _make_service(monkeypatch, wb=FakeWbRepo())
    user = _user("analyst", ["customer:read_transactions"])
    result = await service.get_transactions(user, "CUST_00001", limit=10, offset=0)
    assert result is not None
    summary, rows, total, dq, audit = result
    assert total == 42
    assert len(rows) == 1
    assert rows[0].amount == "-250.00"
    assert summary.latest_transaction_date == "2026-08-01 10:00:00"
    assert audit["action"] == "customer_360_access"


@pytest.mark.asyncio
async def test_transactions_out_of_scope_returns_none(monkeypatch):
    wb = FakeWbRepo(scopes=[{"scope_id": "BR999", "scope_type": "branch"}])
    service = _make_service(monkeypatch, wb=wb)
    assert await service.get_transactions(
        _user("analyst", ["customer:read_transactions"]), "CUST_00001"
    ) is None


@pytest.mark.asyncio
async def test_integration_db_outage_falls_back_to_role_scope(monkeypatch):
    service = _make_service(monkeypatch, wb=None)  # integration pool down
    user = _user("admin", BASE_PERMISSIONS)
    overview, audit = await service.get_overview(user, "CUST_00001")
    assert overview is not None
    assert audit["scope_used"] == ["global"]


@pytest.mark.asyncio
async def test_money_fields_are_exact_strings(monkeypatch):
    service = _make_service(monkeypatch, wb=FakeWbRepo())
    user = _user("analyst", BASE_PERMISSIONS)
    overview, _ = await service.get_overview(user, "CUST_00001")
    assert isinstance(overview.accounts[0].balance, str)
    assert overview.accounts[0].balance == "1500.50"
    assert overview.loans[0].principal == "50000.00"
