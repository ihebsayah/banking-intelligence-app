"""
services/intent_agent/tests/test_constraint_propagation.py

Step 17 regression matrix: every explicit user constraint must be captured
deterministically by build_structured_intent (filters / time / limit / sort).
Each assertion encodes the golden expectation from benchmark/e2e_nl_sql/cases.json.

Run with:  pytest tests/test_constraint_propagation.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from structured_intent import build_structured_intent


def filters_of(q):
    s = build_structured_intent(q)
    return {(f["column"], f["operator"], f["value"]) for f in s["filters_structured"]}


def any_filter(q):
    return list(build_structured_intent(q)["filters_structured"])


def assert_filter(q, column, operator, value, absent=None, extra_ok=True):
    got = any_filter(q)
    assert {"column": column, "operator": operator, "value": value} in got
    if absent is not None:
        found = [f for f in got if (f["column"], f["operator"], f["value"]) == absent]
        assert not found


def assert_no_filters(q):
    assert any_filter(q) == []


class TestStatusFilters:
    def test_active_accounts_fr(self):
        assert_filter("Combien de comptes sont actifs ?",
                      "accounts.status", "=", "active")

    def test_dormant_accounts_fr(self):
        assert_filter("Combien de comptes sont dormants ?",
                      "accounts.status", "=", "dormant")

    def test_active_accounts_en(self):
        assert_filter("How many accounts are active?",
                      "accounts.status", "=", "active")

    def test_closed_accounts_fr(self):
        assert_filter("Combien de comptes sont clos ?",
                      "accounts.status", "=", "closed")

    def test_active_loan_status(self):
        assert_filter("Quel est le montant total du capital des prêts actifs ?",
                      "loan_contracts.status", "=", "active")

    def test_status_requires_owning_noun(self):
        # 'active' with no account/loan noun must NOT invent a filter.
        assert_no_filters("Show me the active risk score")


class TestAccountTypeFilter:
    def test_savings_fr(self):
        assert_filter("Combien de comptes épargne existent ?",
                      "accounts.account_type", "=", "savings")


class TestSegmentFilter:
    def test_corp_large_fr(self):
        assert_filter("Combien de clients sont dans le segment CORP_LARGE ?",
                      "customers.segment", "=", "CORP_LARGE")

    def test_part_mass_en(self):
        assert_filter("How many customers are in the PART_MASS segment?",
                      "customers.segment", "=", "PART_MASS")


class TestRiskFilters:
    def test_risk_gt_0_7_fr_comma(self):
        assert_filter("Combien de clients ont un score de risque supérieur à 0,7 ?",
                      "customers.risk_score", ">", 0.7)

    def test_risk_above_0_5_en(self):
        assert_filter("How many customers have a risk score above 0.5?",
                      "customers.risk_score", ">", 0.5)

    def test_risk_high_band_is_strict_gt(self):
        assert_filter("Clients à haut risque par segment",
                      "customers.risk_score", ">", 0.7)

    def test_risk_elevated_band(self):
        assert_filter("Clients en attente KYC avec un risque élevé",
                      "customers.risk_score", ">", 0.5)

    def test_no_risk_filter_without_threshold(self):
        # Ranking by risk is not a filter.
        assert_no_filters("Top 5 des clients par score de risque")


class TestKycFilters:
    def test_kyc_verified_true(self):
        assert_filter("How many customers have verified their KYC?",
                      "customers.kyc_verified", "=", True)

    def test_kyc_verified_true_fr(self):
        assert_filter("Quel est le score de risque moyen des clients dont le KYC est vérifié ?",
                      "customers.kyc_verified", "=", True)

    def test_kyc_verified_false(self):
        assert_filter("Combien de clients ont un KYC non vérifié ?",
                      "customers.kyc_verified", "=", False)

    def test_pending_kyc_cases(self):
        assert_filter("How many KYC cases are pending?",
                      "kyc_cases.status", "=", "pending")


class TestAmlFilters:
    def test_high_severity_open_aml(self):
        assert_filter("How many high-severity open AML alerts exist?",
                      "aml_alerts.severity", "=", "high")
        assert_filter("How many high-severity open AML alerts exist?",
                      "aml_alerts.status", "=", "open")


class TestRiskFlagFilters:
    def test_unresolved_risk_flags(self):
        assert_filter("Combien de flags de risque sont non résolus ?",
                      "risk_flags.resolved_at", "IS NULL", None)


class TestLoanDelayFilters:
    def test_overdue_more_than_30_days(self):
        assert_filter("Combien de clients ont des prêts avec retard de plus de 30 jours ?",
                      "loan_contracts.days_past_due", ">", 30)

    def test_bare_overdue_is_zero(self):
        assert_filter("Nombre de prêts en retard dans la branche Tunis",
                      "loan_contracts.days_past_due", ">", 0)

    def test_auto_loan_type_fr(self):
        assert_filter("Combien de prêts auto actifs par agence ?",
                      "loan_contracts.loan_type", "=", "auto")


class TestTransactionFilters:
    def test_completed_status(self):
        assert_filter("How many completed transactions were there in the last 30 days?",
                      "transactions.status", "=", "complété")

    def test_transfer_type(self):
        assert_filter("Top 10 largest transfer transactions",
                      "transactions.transaction_type", "=", "transfer")


class TestBranchFilters:
    def test_branch_code(self):
        assert_filter("Comptes dormants à la BR_016",
                      "branches.name", "=", "BR_016")

    def test_branch_name_fr_singular(self):
        assert_filter("Nombre de prêts en retard dans la branche Tunis",
                      "branches.name", "=", "Tunis Branch")

    def test_branch_name_fr_plural(self):
        assert_filter("Clients avec prêts dans les branches de Tunis",
                      "branches.name", "=", "Tunis Branch")

    def test_no_branch_filter_for_state_dimension(self):
        assert_no_filters("Nombre de clients par branch état")


class TestTimeRange:
    def test_this_year_is_last_year(self):
        s = build_structured_intent("Top 5 branches by deposits this year")
        assert s["time_range"] == {"type": "relative", "value": "last_year"}

    def test_cette_annee(self):
        s = build_structured_intent("Combien de clients ajoutés cette année ?")
        assert s["time_range"] == {"type": "relative", "value": "last_year"}


class TestLimits:
    def test_le_plus_de_is_top5(self):
        assert build_structured_intent("Agences avec le plus de comptes dormants")["limit_requested"] == 5

    def test_latest_is_top1(self):
        assert build_structured_intent("What is the latest PNB (net banking income)?")["limit_requested"] == 1

    def test_last_period_is_top1(self):
        assert build_structured_intent("What was the net income in the last period?")["limit_requested"] == 1


class TestSort:
    def test_count_ranking_sort(self):
        s = build_structured_intent("What are the top 5 branches by number of accounts?")
        assert s["sort_structured"] == [{"column": "count_all", "direction": "DESC"}]

    def test_largest_transfer_sort(self):
        s = build_structured_intent("Top 10 largest transfer transactions")
        assert s["sort_structured"] == [{"column": "transactions.amount", "direction": "DESC"}]

    def test_latest_period_sort(self):
        s = build_structured_intent("What is the latest PNB (net banking income)?")
        assert s["sort_structured"] == [{"column": "income_statement_snapshots.period", "direction": "DESC"}]

    def test_risk_ranking_sort(self):
        s = build_structured_intent("Top 5 des clients par score de risque")
        assert s["sort_structured"] == [{"column": "customers.risk_score", "direction": "DESC"}]