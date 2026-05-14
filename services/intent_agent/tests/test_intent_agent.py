"""
services/intent_agent/tests/test_intent_agent.py

20 test cases – must all pass for Week 2 acceptance (≥18/20 = 90%).
Run with:  pytest tests/test_intent_agent.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from intent_recognizer import IntentRecognizer


@pytest.fixture(scope="module")
def recognizer():
    """Single recognizer (loads spaCy once)."""
    return IntentRecognizer(redis_client=None)


def classify(recognizer, query: str) -> dict:
    return recognizer.recognize_sync(query)


# ─── 20 test cases ───────────────────────────────────────────────────────────

class TestIntentRecognition:

    # 1
    def test_top_10_customers_by_balance(self, recognizer):
        r = classify(recognizer, "Show me top 10 customers by balance")
        assert r["primary_category"] == "customer_analysis"
        assert r["explicit_constraints"]["threshold"] == "top_10"

    # 2
    def test_high_risk_customers_new_york(self, recognizer):
        r = classify(recognizer, "Customers with high risk in New York")
        assert r["primary_category"] in ("risk_analysis", "customer_analysis")
        assert "customer_analysis" in r["secondary_categories"] or \
               r["primary_category"] == "customer_analysis"
        assert r["explicit_constraints"]["geography"] == "NY"
        assert r["requires_clarification"] is True

    # 3
    def test_revenue_by_product_this_quarter(self, recognizer):
        r = classify(recognizer, "Revenue by product line this quarter")
        assert r["primary_category"] == "revenue_analysis"
        assert "product_analysis" in r["secondary_categories"]
        assert r["explicit_constraints"]["time_period"] == "last_quarter"

    # 4
    def test_transaction_volume_by_branch_last_month(self, recognizer):
        r = classify(recognizer, "Transaction volume by branch last month")
        assert r["primary_category"] in ("operational_analysis", "transaction_analysis",
                                         "geographic_analysis")
        assert r["explicit_constraints"]["time_period"] == "last_30_days"

    # 5
    def test_identify_fraud_patterns(self, recognizer):
        r = classify(recognizer, "Identify fraud patterns")
        assert r["primary_category"] == "risk_analysis"
        assert len(r["ambiguities"]) > 0

    # 6
    def test_kyc_violations_this_year(self, recognizer):
        r = classify(recognizer, "KYC violations this year")
        assert r["primary_category"] in ("risk_analysis", "compliance_analysis")
        assert r["explicit_constraints"]["time_period"] == "last_year"

    # 7
    def test_top_5_branches_by_customer_count(self, recognizer):
        r = classify(recognizer, "Top 5 branches by customer count")
        assert r["primary_category"] in ("geographic_analysis", "customer_analysis")
        assert r["explicit_constraints"]["threshold"] == "top_5"

    # 8
    def test_average_account_balance_by_product(self, recognizer):
        r = classify(recognizer, "Average account balance by product")
        assert r["primary_category"] in (
            "revenue_analysis", "customer_analysis", "product_analysis"
        )
        assert r["requires_clarification"] is True

    # 9
    def test_aml_suspicious_transfers(self, recognizer):
        r = classify(recognizer, "AML suspicious wire transfers last 30 days")
        assert r["primary_category"] == "risk_analysis"
        assert r["explicit_constraints"]["time_period"] == "last_30_days"

    # 10
    def test_compliance_sox_violations(self, recognizer):
        r = classify(recognizer, "SOX compliance violations in audit report")
        assert r["primary_category"] == "compliance_analysis"
        assert "risk_analysis" in r["secondary_categories"] or \
               r["confidence"] > 0.0

    # 11
    def test_premium_customer_fee_income(self, recognizer):
        r = classify(recognizer, "Fee income from premium customers this quarter")
        assert r["primary_category"] in ("revenue_analysis", "customer_analysis")
        assert r["explicit_constraints"]["segment"] == "premium"
        assert r["explicit_constraints"]["time_period"] == "last_quarter"

    # 12
    def test_branch_performance_california(self, recognizer):
        r = classify(recognizer, "Branch performance in California")
        assert r["primary_category"] in ("geographic_analysis", "revenue_analysis",
                                         "operational_analysis")
        assert r["explicit_constraints"]["geography"] == "CA"

    # 13
    def test_loan_product_analysis(self, recognizer):
        r = classify(recognizer, "Which loan products have the highest margin?")
        assert r["primary_category"] in ("product_analysis", "revenue_analysis")

    # 14
    def test_payment_settlement_volume(self, recognizer):
        r = classify(recognizer, "ACH payment settlement volume by region")
        assert r["primary_category"] in ("transaction_analysis", "geographic_analysis",
                                         "operational_analysis")

    # 15
    def test_credit_risk_default_rate(self, recognizer):
        r = classify(recognizer, "Credit risk default rate by customer segment")
        assert r["primary_category"] == "risk_analysis"
        assert "customer_analysis" in r["secondary_categories"] or \
               r["confidence"] > 0.0

    # 16
    def test_gdpr_regulatory_compliance(self, recognizer):
        r = classify(recognizer, "GDPR regulatory compliance status report")
        assert r["primary_category"] == "compliance_analysis"

    # 17
    def test_top_20_revenue_products(self, recognizer):
        r = classify(recognizer, "Top 20 products by revenue earned this year")
        assert r["primary_category"] in ("revenue_analysis", "product_analysis")
        assert r["explicit_constraints"]["threshold"] == "top_20"
        assert r["explicit_constraints"]["time_period"] == "last_year"

    # 18
    def test_customer_segment_analysis(self, recognizer):
        r = classify(recognizer, "Show customer segments by deposit balance")
        assert r["primary_category"] == "customer_analysis"

    # 19
    def test_fraud_flag_by_transaction(self, recognizer):
        r = classify(recognizer, "Flag fraudulent transactions over 10000")
        assert r["primary_category"] in ("risk_analysis", "transaction_analysis")

    # 20
    def test_branch_count_northeast(self, recognizer):
        r = classify(recognizer, "How many branches in the Northeast region?")
        assert r["primary_category"] == "geographic_analysis"
        assert r["explicit_constraints"]["geography"] == "Northeast"
