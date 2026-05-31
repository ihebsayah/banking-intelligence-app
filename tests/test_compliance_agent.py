"""
tests/test_compliance_agent.py
Unit tests for Phase 2 Compliance Agent (Week 4-6).
No database required — pool is mocked.
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock

# Remove any previously added service dirs to avoid models.py collision
for _p in list(sys.path):
    if 'services' in _p and 'compliance_agent' not in _p:
        sys.path.remove(_p)

COMPLIANCE_DIR = os.path.join(
    os.path.dirname(__file__), "..", "services", "compliance_agent"
)
if COMPLIANCE_DIR not in sys.path:
    sys.path.insert(0, COMPLIANCE_DIR)

from compliance_checker import ComplianceChecker
from models import ComplianceResponse


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.DATABASE_URL = "postgresql://fake/fake"
    return cfg


@pytest.fixture
def checker(mock_config):
    c = ComplianceChecker(mock_config)
    c.pool = None   # skip DB; _check_db_rules returns empty lists
    return c


# ─────────────────────────────────────────────────────────────────────────────
# GDPR Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestGDPRCompliance:

    @pytest.mark.asyncio
    async def test_pii_columns_trigger_masking(self, checker):
        resp = await checker.check_compliance(
            user_id="U001", user_role="analyst",
            query_intent="customer_analysis",
            tables=["customers"],
            columns=["name", "email", "phone"],
        )
        assert isinstance(resp, ComplianceResponse)
        masked_cols = {m.column for m in resp.masking_required}
        assert "email" in masked_cols
        assert "phone" in masked_cols

    @pytest.mark.asyncio
    async def test_non_pii_columns_no_masking(self, checker):
        resp = await checker.check_compliance(
            user_id="U001", user_role="analyst",
            query_intent="customer_analysis",
            tables=["customers"],
            columns=["customer_id", "segment", "risk_score"],
        )
        gdpr_masks = [m for m in resp.masking_required if m.regulation == "GDPR"]
        assert len(gdpr_masks) == 0


# ─────────────────────────────────────────────────────────────────────────────
# PCI-DSS Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPCIDSSCompliance:

    @pytest.mark.asyncio
    async def test_card_data_blocked_for_analyst(self, checker):
        resp = await checker.check_compliance(
            user_id="U002", user_role="analyst",
            query_intent="payment_analysis",
            tables=["payments"],
            columns=["credit_card", "amount"],
        )
        critical = [v for v in resp.violations if v.severity == "critical"]
        assert len(critical) >= 1
        assert resp.compliant is False

    @pytest.mark.asyncio
    async def test_card_data_allowed_for_compliance(self, checker):
        resp = await checker.check_compliance(
            user_id="U003", user_role="compliance",
            query_intent="payment_analysis",
            tables=["payments"],
            columns=["credit_card", "amount"],
        )
        # Compliance role allowed, but masking still applied
        critical = [v for v in resp.violations if v.severity == "critical"]
        assert len(critical) == 0
        masked = [m for m in resp.masking_required if m.column == "credit_card"]
        assert len(masked) >= 1

    @pytest.mark.asyncio
    async def test_card_data_allowed_for_admin(self, checker):
        resp = await checker.check_compliance(
            user_id="U004", user_role="admin",
            query_intent="payment_analysis",
            tables=["payments"],
            columns=["card_number"],
        )
        critical = [v for v in resp.violations if v.severity == "critical"]
        assert len(critical) == 0


# ─────────────────────────────────────────────────────────────────────────────
# SOX Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSOXCompliance:

    @pytest.mark.asyncio
    async def test_maker_checker_role_blocked(self, checker):
        resp = await checker.check_compliance(
            user_id="U005", user_role="maker_checker",
            query_intent="operational_analysis",
            tables=["accounts", "transactions"],
            columns=["balance"],
        )
        sox_violations = [v for v in resp.violations if v.regulation == "SOX"]
        assert len(sox_violations) >= 1

    @pytest.mark.asyncio
    async def test_analyst_sox_sensitive_tables_allowed(self, checker):
        resp = await checker.check_compliance(
            user_id="U006", user_role="analyst",
            query_intent="operational_analysis",
            tables=["accounts"],
            columns=["balance", "account_type"],
        )
        sox_violations = [v for v in resp.violations if v.regulation == "SOX"]
        assert len(sox_violations) == 0


# ─────────────────────────────────────────────────────────────────────────────
# AML Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAMLCompliance:

    @pytest.mark.asyncio
    async def test_transaction_intent_without_clearance_flagged(self, checker):
        resp = await checker.check_compliance(
            user_id="U007", user_role="teller",
            query_intent="transaction_analysis",
            tables=["transactions"],
            columns=["amount", "transaction_type"],
        )
        aml_violations = [v for v in resp.violations if v.regulation == "AML"]
        assert len(aml_violations) >= 1

    @pytest.mark.asyncio
    async def test_analyst_transaction_allowed(self, checker):
        resp = await checker.check_compliance(
            user_id="U008", user_role="analyst",
            query_intent="transaction_analysis",
            tables=["transactions"],
            columns=["amount"],
        )
        aml_critical = [
            v for v in resp.violations
            if v.regulation == "AML" and v.severity == "critical"
        ]
        assert len(aml_critical) == 0


# ─────────────────────────────────────────────────────────────────────────────
# KYC Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestKYCCompliance:

    @pytest.mark.asyncio
    async def test_kyc_intent_blocked_for_teller(self, checker):
        resp = await checker.check_compliance(
            user_id="U009", user_role="teller",
            query_intent="kyc_verification",
            tables=["customers"],
            columns=["kyc_verified"],
        )
        kyc_violations = [v for v in resp.violations if v.regulation == "KYC"]
        assert len(kyc_violations) >= 1

    @pytest.mark.asyncio
    async def test_kyc_intent_allowed_for_kyc_officer(self, checker):
        resp = await checker.check_compliance(
            user_id="U010", user_role="kyc_officer",
            query_intent="kyc_verification",
            tables=["customers"],
            columns=["kyc_verified"],
        )
        kyc_violations = [v for v in resp.violations if v.regulation == "KYC"]
        assert len(kyc_violations) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Compliant query
# ─────────────────────────────────────────────────────────────────────────────

class TestCompliantQuery:

    @pytest.mark.asyncio
    async def test_clean_query_is_compliant(self, checker):
        resp = await checker.check_compliance(
            user_id="U011", user_role="analyst",
            query_intent="customer_analysis",
            tables=["customers"],
            columns=["customer_id", "segment", "balance"],
        )
        # 'balance' is not a PCI/GDPR field; analyst is AML-cleared
        critical_violations = [
            v for v in resp.violations if v.severity in ("critical", "high")
        ]
        assert len(critical_violations) == 0
        assert resp.compliant is True

    @pytest.mark.asyncio
    async def test_regulations_always_checked(self, checker):
        resp = await checker.check_compliance(
            user_id="U012", user_role="admin",
            query_intent="revenue_analysis",
            tables=["accounts"],
            columns=["balance"],
        )
        assert "GDPR" in resp.regulations_checked
        assert "PCI-DSS" in resp.regulations_checked
        assert "SOX" in resp.regulations_checked


# ─────────────────────────────────────────────────────────────────────────────
# Helper method unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestHelpers:

    def test_col_matches_in_clause(self):
        assert ComplianceChecker._col_matches("email", "column IN (ssn, email, phone)") is True
        assert ComplianceChecker._col_matches("balance", "column IN (ssn, email, phone)") is False

    def test_col_matches_eq_clause(self):
        assert ComplianceChecker._col_matches("credit_card", "column = credit_card") is True
        assert ComplianceChecker._col_matches("balance", "column = credit_card") is False

    def test_role_allowed_not_in(self):
        assert ComplianceChecker._role_allowed("compliance", "user_role NOT IN (compliance, admin)") is True
        assert ComplianceChecker._role_allowed("teller", "user_role NOT IN (compliance, admin)") is False
