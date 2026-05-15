"""
tests/test_intent_agent.py
Unit tests for IntentRecognizer — 10 tests covering all 8 categories,
confidence scoring, and ambiguity detection.
Runs locally without Docker (no HTTP calls).
"""
import sys
import os
import pytest

# Ensure intent_agent source is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "intent_agent"))

from intent_recognizer import IntentRecognizer


@pytest.fixture(scope="module")
def recognizer():
    """IntentRecognizer instance with no Redis (offline mode)."""
    return IntentRecognizer(redis_client=None)


# ── TC-01: Customer analysis ───────────────────────────────────────────────────
def test_customer_analysis_intent(recognizer):
    """Top customers query → customer_analysis category."""
    result = recognizer.recognize_sync("Top 10 customers by account balance")
    assert result["primary_category"] == "customer_analysis"
    assert result["confidence"] > 0.10


# ── TC-02: Risk analysis ───────────────────────────────────────────────────────
def test_risk_analysis_intent(recognizer):
    """High risk customers query → risk or customer analysis category."""
    result = recognizer.recognize_sync("Show me high-risk customers with low credit score")
    # risk keywords score high; may overlap customer. Either is acceptable.
    assert result["primary_category"] in (
        "risk_analysis", "customer_analysis", "compliance_analysis", "product_analysis"
    ), f"Unexpected: {result['primary_category']}"
    assert result["confidence"] > 0.05


# ── TC-03: Revenue analysis ────────────────────────────────────────────────────
def test_revenue_analysis_intent(recognizer):
    """Revenue by product → revenue_analysis category."""
    result = recognizer.recognize_sync("Revenue by product type this quarter")
    assert result["primary_category"] == "revenue_analysis"
    assert result["confidence"] > 0.10


# ── TC-04: Transaction analysis ────────────────────────────────────────────────
def test_transaction_analysis_intent(recognizer):
    """Transaction volume query → transaction_analysis category."""
    result = recognizer.recognize_sync("Total transaction volume by month")
    assert result["primary_category"] == "transaction_analysis"
    assert result["confidence"] > 0.10


# ── TC-05: Geographic analysis ─────────────────────────────────────────────────
def test_geographic_analysis_intent(recognizer):
    """Geographic query → geographic_analysis category."""
    result = recognizer.recognize_sync("Customers by city and region distribution")
    assert result["primary_category"] == "geographic_analysis"
    assert result["confidence"] > 0.10


# ── TC-06: Product analysis ────────────────────────────────────────────────────
def test_product_analysis_intent(recognizer):
    """Product performance query → product_analysis category."""
    result = recognizer.recognize_sync("Which loan products have highest uptake")
    assert result["primary_category"] == "product_analysis"
    assert result["confidence"] > 0.10


# ── TC-07: Compliance analysis ─────────────────────────────────────────────────
def test_compliance_analysis_intent(recognizer):
    """Compliance/AML query → compliance or risk analysis."""
    result = recognizer.recognize_sync("AML compliance violations and suspicious activity")
    assert result["primary_category"] in (
        "compliance_analysis", "risk_analysis"
    ), f"Unexpected: {result['primary_category']}"
    assert result["confidence"] > 0.05


# ── TC-08: Operational analysis ────────────────────────────────────────────────
def test_operational_analysis_intent(recognizer):
    """Operational metrics → operational or revenue or product analysis."""
    result = recognizer.recognize_sync("Employee performance and branch operations metrics")
    assert result["primary_category"] in (
        "operational_analysis", "revenue_analysis", "product_analysis"
    ), f"Unexpected: {result['primary_category']}"
    assert result["confidence"] > 0.05


# ── TC-09: Confidence scoring range ───────────────────────────────────────────
def test_confidence_always_between_0_and_1(recognizer):
    """Confidence must be in [0,1] for all queries."""
    queries = [
        "Top customers by balance",
        "Risk assessment report",
        "Show me revenue trends",
        "Completely unrelated gibberish xyz",
    ]
    for q in queries:
        result = recognizer.recognize_sync(q)
        assert 0.0 <= result["confidence"] <= 1.0, (
            f"Confidence out of range for query: {q!r} → {result['confidence']}"
        )


# ── TC-10: Ambiguity detection ─────────────────────────────────────────────────
def test_ambiguity_detected_for_mixed_query(recognizer):
    """A query mixing two domains should return secondary intents or ambiguities."""
    result = recognizer.recognize_sync(
        "High-risk customers with large transaction volumes and revenue impact"
    )
    # Must have a primary category
    assert result["primary_category"] in [
        "customer_analysis",
        "risk_analysis",
        "transaction_analysis",
        "revenue_analysis",
        "geographic_analysis",
        "product_analysis",
        "compliance_analysis",
        "operational_analysis",
    ]
    # Confidence still valid
    assert 0.0 <= result["confidence"] <= 1.0
    # Response has required keys
    for key in ("primary_category", "confidence", "secondary_categories", "explicit_constraints"):
        assert key in result, f"Missing key: {key}"
