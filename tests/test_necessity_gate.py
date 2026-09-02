import sys
import os
import pytest

for _p in list(sys.path):
    if 'services' in _p and 'insights_agent' not in _p:
        sys.path.remove(_p)

INSIGHTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "services", "insights_agent"
)
if INSIGHTS_DIR not in sys.path:
    sys.path.insert(0, INSIGHTS_DIR)

from necessity_gate import NecessityGate, DeterministicFormatter
from models import (
    AnalyticalFactPackage,
    DatasetProfile,
    AnomalyFact,
    CorrelationFact,
    TemporalComparison,
    Provenance,
    InsightsDecision,
)


def _profile(
    row_count=100,
    numeric=("balance",),
    categorical=("region",),
    nulls=None,
):
    cols = list(numeric) + list(categorical)
    return DatasetProfile(
        row_count=row_count,
        columns=cols,
        numeric_columns=list(numeric),
        categorical_columns=list(categorical),
        null_counts={c: 0 for c in cols} if nulls is None else nulls,
    )


def _pkg(profile=None, anomalies=(), correlations=(), temporal=(), recs=(), eq_score=0.9):
    profile = profile or _profile()
    pkg = AnalyticalFactPackage(
        query_intent="x", query_text="", dataset_profile=profile,
        anomalies=list(anomalies), correlations=list(correlations),
        temporal_comparisons=list(temporal),
        recommendation_candidates=list(recs),
    )
    pkg.evidence_quality.score = eq_score
    return pkg


def _anomaly(col="balance"):
    return AnomalyFact(
        column=col, observed_value=9999.0, mean=100.0, std_dev=10.0,
        deviation=900.0, severity="extreme",
        provenance=Provenance(source="deterministic_calculation", column=col, method="z"),
    )


def _corr(a="a", b="b", r=0.9):
    return CorrelationFact(column_a=a, column_b=b, coefficient=r, sample_size=100,
                           provenance=Provenance(source="deterministic_calculation", method="pearson"))


def _tc(col="balance", pct=30.0):
    return TemporalComparison(
        column=col, earliest_period="2024-01", latest_period="2024-02",
        previous_value=100.0, current_value=130.0,
        absolute_change=30.0, percentage_change=pct,
        provenance=Provenance(source="deterministic_calculation", method="period_over_period"),
    )


GATE = NecessityGate()
FMT = DeterministicFormatter()


# ── DIRECT / SIMPLE → deterministic ───────────────────────────────────────────

def _lookup_pkg():
    return _pkg(_profile(row_count=1, numeric=("balance",), categorical=()))


class TestDirectDeterministic:
    def test_balance_lookup_is_deterministic(self):
        d = GATE.evaluate("retrieve", "Balance of customer CUST_00141", _lookup_pkg())
        assert not d.use_llm
        assert d.formatter_mode == "deterministic"
        assert "DIRECT_LOOKUP" in d.reason_codes or "USER_REQUESTED_EXPLANATION" not in d.reason_codes

    def test_count_query_is_deterministic(self):
        d = GATE.evaluate("customer_analysis", "How many customers are in branch X?", _pkg(_profile(numeric=())))
        # count-style: no explicit analysis words, no numeric facts → deterministic
        assert not d.use_llm

    def test_average_loan_is_deterministic(self):
        d = GATE.evaluate("product_analysis", "Average loan amount", _pkg())
        assert not d.use_llm

    def test_top_n_without_explanation_is_deterministic(self):
        d = GATE.evaluate("customer_analysis", "Top 5 branches by deposits", _pkg())
        assert not d.use_llm


# ── ANALYTICAL → LLM useful ──────────────────────────────────────────────────

class TestAnalyticalLlmUseful:
    def test_concentration_analysis_multi_dim(self):
        d = GATE.evaluate(
            "geographic_analysis", "Analyze deposit concentration by region",
            _pkg(_profile(numeric=("balance",), categorical=("region",))),
        )
        # "analyze" is an explicit signal
        assert d.use_llm

    def test_trend_analysis_with_valid_temporal(self):
        d = GATE.evaluate("transaction_analysis", "Explain the trend in loan exposure",
                          _pkg(temporal=(_tc(),), anomalies=(), correlations=()))
        assert d.use_llm

    def test_anomaly_analysis_with_anomaly_facts(self):
        d = GATE.evaluate("risk_analysis", "Identify unusual transaction activity",
                          _pkg(anomalies=(_anomaly(),)))
        assert d.use_llm

    def test_compare_and_explain(self):
        d = GATE.evaluate("geographic_analysis", "Compare branches and explain what stands out",
                          _pkg())
        assert d.use_llm


# ── USER OVERRIDE ────────────────────────────────────────────────────────────

class TestUserOverride:
    def test_simple_metric_with_explain_is_llm(self):
        d = GATE.evaluate("retrieve", "Balance of CUST_00141 explain the reason",
                          _lookup_pkg())
        assert d.use_llm

    def test_simple_metric_without_explain_is_deterministic(self):
        d = GATE.evaluate("retrieve", "Balance of CUST_00141", _lookup_pkg())
        assert not d.use_llm


# ── FACT AVAILABILITY → no fabrication ───────────────────────────────────────

class TestFactAvailability:
    def test_trend_request_no_temporal_evidence(self):
        d = GATE.evaluate("transaction_analysis", "Explain the trend in loan exposure",
                          _pkg())  # no temporal
        assert not d.use_llm
        assert "TREND_UNAVAILABLE" in d.reason_codes

    def test_anomaly_request_none_detected(self):
        d = GATE.evaluate("risk_analysis", "Identify unusual transaction activity",
                          _pkg())  # no anomalies
        assert not d.use_llm
        assert "NO_ANOMALIES" in d.reason_codes


# ── EMPTY / POOR DATA ────────────────────────────────────────────────────────

class TestEmptyPoorData:
    def test_empty_results_deterministic(self):
        pkg = _pkg(_profile(row_count=0, numeric=(), categorical=()))
        pkg.evidence_quality.score = 0.0
        d = GATE.evaluate("customer_analysis", "Analyze concentration", pkg)
        assert not d.use_llm

    def test_low_evidence_quality_safe(self):
        pkg = _pkg(eq_score=0.2)
        d = GATE.evaluate("risk_analysis", "explain unusual activity", pkg)
        # low evidence quality suppresses LLM even with explicit signal
        assert not d.use_llm


# ── MULTILINGUAL ─────────────────────────────────────────────────────────────

class TestMultilingual:
    def test_french_analytical_classified(self):
        d = GATE.evaluate("geographic_analysis", "Analyser la concentration des dépôts par région",
                          _pkg())
        assert d.use_llm

    def test_french_direct_lookup(self):
        d = GATE.evaluate("retrieve", "Solde de CUST_00141", _lookup_pkg())
        assert not d.use_llm


# ── Deterministic Formatter ──────────────────────────────────────────────────

class TestDeterministicFormatter:
    def test_direct_lookup_format(self):
        from statistical_analyzer import StatisticalAnalyzer
        analyzer = StatisticalAnalyzer()
        pkg = _pkg(_profile(row_count=1, numeric=("balance",), categorical=()))
        rows = [{"balance": 27450.0}]
        stats = analyzer.compute_descriptive_stats(rows, ["balance"])
        pkg.dataset_profile = _profile(row_count=1, numeric=("balance",), categorical=())
        pkg.descriptive_stats = stats
        decision = GATE.evaluate("retrieve", "Balance of CUST_00141", pkg)
        out = FMT.format(pkg, decision, {})
        assert out.startswith("Balance")
        assert "27,450" in out

    def test_no_anomalies_message(self):
        # deterministic formatter must report no anomalies found, not fabricate
        assert "No results" in FMT.format(
            _pkg(_profile(row_count=0, numeric=(), categorical=())),
            InsightsDecision(provenance=Provenance(source="deterministic_calculation", method="t")),
            {},
        )
