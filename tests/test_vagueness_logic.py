"""
tests/test_vagueness_logic.py
Unit tests for the vagueness logic in IntentRecognizer.

Verifies that vague phrases (e.g. "need info", "informations sur") do NOT
trigger requires_clarification when the structured intent has enough
analytical substance (domain + task + entity/metric/filter).
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "intent_agent"))

from intent_recognizer import IntentRecognizer


def _recognize(query: str) -> dict:
    return IntentRecognizer(semantic_layer_enabled=True).recognize_sync(query)


# ── Should CONTINUE (structured intent has substance) ─────────────────────────

class TestVaguePhraseWithStructure:
    """Queries with vague phrasing but sufficient analytical structure."""

    def test_info_about_customers_with_kyc_filter(self):
        r = _recognize("I need info about customers with inactive KYC status.")
        assert r["requires_clarification"] is False

    def test_info_about_accounts_with_time_range(self):
        r = _recognize("Give me information about accounts opened last month.")
        assert r["requires_clarification"] is False

    def test_report_with_ranking_and_metric(self):
        r = _recognize("Show me the report of the top five branches by deposit volume.")
        assert r["requires_clarification"] is False

    def test_info_about_customers_with_overdue_loans(self):
        r = _recognize("I need info about customers with overdue loans.")
        assert r["requires_clarification"] is False

    def test_french_informations_with_date(self):
        r = _recognize("Informations sur les comptes clôturés en 2025.")
        assert r["requires_clarification"] is False

    def test_which_ten_customers_most_transactions(self):
        r = _recognize("Which ten customers have the most transactions?")
        assert r["requires_clarification"] is False


# ── Should REQUIRE clarification (truly vague, no structure) ──────────────────

class TestTrulyVague:
    """Queries that are genuinely vague with no analytical substance."""

    def test_need_info_about_customers(self):
        r = _recognize("I need info about customers.")
        assert r["requires_clarification"] is True

    def test_tell_me_about_accounts(self):
        r = _recognize("Tell me about accounts.")
        assert r["requires_clarification"] is True

    def test_show_me_the_report(self):
        r = _recognize("Show me the report.")
        assert r["requires_clarification"] is True

    def test_give_me_some_figures(self):
        r = _recognize("Give me some figures.")
        assert r["requires_clarification"] is True

    def test_french_besoin_informations_comptes(self):
        r = _recognize("J'ai besoin d'informations sur les comptes.")
        assert r["requires_clarification"] is True
