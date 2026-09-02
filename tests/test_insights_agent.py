import sys
import os
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock

for _p in list(sys.path):
    if 'services' in _p and 'insights_agent' not in _p:
        sys.path.remove(_p)

INSIGHTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "services", "insights_agent"
)
if INSIGHTS_DIR not in sys.path:
    sys.path.insert(0, INSIGHTS_DIR)

from statistical_analyzer import StatisticalAnalyzer
from models import (
    InsightsRequest,
    InsightsResponse,
    AnalyticalFactPackage,
    DatasetProfile,
    DescriptiveStats,
    CategoricalDistribution,
    AnomalyFact,
    CorrelationFact,
    TemporalComparison,
    RecommendationCandidate,
    EvidenceQuality,
    Provenance,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_config():
    cfg = MagicMock()
    cfg.DATABASE_URL = "postgresql://fake/fake"
    cfg.MISTRAL_API_URL = "http://localhost:11434"
    cfg.MISTRAL_MODEL = "mistral"
    cfg.ENABLE_LLM_INSIGHTS = False
    return cfg


# ─────────────────────────────────────────────────────────────────────────────
# 1. Column Classification
# ─────────────────────────────────────────────────────────────────────────────

class TestColumnClassification:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_empty_results(self):
        profile = self.analyzer.classify_columns([])
        assert profile.row_count == 0
        assert profile.numeric_columns == []
        assert profile.categorical_columns == []

    def test_numeric_detection(self):
        rows = [{"balance": 100.0, "name": "Alice", "active": True}]
        profile = self.analyzer.classify_columns(rows)
        assert "balance" in profile.numeric_columns
        assert "name" in profile.categorical_columns
        assert "active" in profile.identifier_columns or "active" in profile.categorical_columns

    def test_temporal_detection(self):
        rows = [
            {"date": "2024-01-15", "amount": 100.0},
            {"date": "2024-02-20", "amount": 200.0},
            {"date": "2024-03-10", "amount": 300.0},
        ]
        profile = self.analyzer.classify_columns(rows)
        assert "date" in profile.temporal_columns
        assert "amount" in profile.numeric_columns

    def test_identifier_detection(self):
        rows = [
            {"id": "CUST_001", "balance": 100.0},
            {"id": "CUST_002", "balance": 200.0},
            {"id": "CUST_003", "balance": 300.0},
        ]
        profile = self.analyzer.classify_columns(rows)
        assert "id" in profile.identifier_columns
        assert "balance" in profile.numeric_columns

    def test_null_counts(self):
        rows = [
            {"a": 1, "b": None},
            {"a": None, "b": 2},
        ]
        profile = self.analyzer.classify_columns(rows)
        assert profile.null_counts["a"] == 1
        assert profile.null_counts["b"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. Descriptive Statistics
# ─────────────────────────────────────────────────────────────────────────────

class TestDescriptiveStats:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_basic_accuracy(self):
        rows = [{"balance": float(i * 100)} for i in range(1, 6)]
        stats = self.analyzer.compute_descriptive_stats(rows, ["balance"])
        assert len(stats) == 1
        s = stats[0]
        assert s.column == "balance"
        assert s.count == 5
        assert s.sum == pytest.approx(1500.0)
        assert s.mean == pytest.approx(300.0)
        assert s.median == pytest.approx(300.0)
        assert s.min == pytest.approx(100.0)
        assert s.max == pytest.approx(500.0)
        assert s.std_dev > 0

    def test_provenance_set(self):
        rows = [{"balance": float(i)} for i in range(1, 4)]
        stats = self.analyzer.compute_descriptive_stats(rows, ["balance"])
        assert stats[0].provenance.source == "deterministic_calculation"
        assert stats[0].provenance.method == "numpy_descriptive_statistics"

    def test_null_count(self):
        rows = [{"balance": 100.0}, {"balance": None}, {"balance": 300.0}]
        stats = self.analyzer.compute_descriptive_stats(rows, ["balance"])
        assert stats[0].null_count == 1

    def test_single_row_yields_lookup_stat(self):
        # a lone value is a valid direct-lookup stat (std guards at n>=2)
        rows = [{"balance": 27450.0}]
        stats = self.analyzer.compute_descriptive_stats(rows, ["balance"])
        assert len(stats) == 1
        assert stats[0].sum == pytest.approx(27450.0)
        assert stats[0].std_dev == 0.0

    def test_percentiles(self):
        rows = [{"x": float(i)} for i in range(1, 21)]
        stats = self.analyzer.compute_descriptive_stats(rows, ["x"])
        s = stats[0]
        assert s.p25 is not None
        assert s.p75 is not None
        assert s.p90 is not None
        assert s.p99 is not None
        assert s.p25 < s.p75 < s.p90


# ─────────────────────────────────────────────────────────────────────────────
# 3. Categorical Distributions
# ─────────────────────────────────────────────────────────────────────────────

class TestCategoricalDistributions:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_dominant_value(self):
        rows = [
            {"region": "Tunis"}, {"region": "Tunis"},
            {"region": "Sfax"}, {"region": "Sfax"},
            {"region": "Tunis"},
        ]
        dists = self.analyzer.compute_categorical_distributions(rows, ["region"])
        assert len(dists) == 1
        d = dists[0]
        assert d.column == "region"
        assert d.unique_count == 2
        assert d.dominant_value == "Tunis"
        assert d.dominant_share == pytest.approx(0.6, abs=0.01)
        assert d.value_counts["Tunis"] == 3
        assert d.value_counts["Sfax"] == 2

    def test_provenance(self):
        rows = [{"type": "A"}, {"type": "B"}]
        dists = self.analyzer.compute_categorical_distributions(rows, ["type"])
        assert dists[0].provenance.source == "execution_result"
        assert dists[0].provenance.method == "count_distinct"


# ─────────────────────────────────────────────────────────────────────────────
# 4. Anomaly Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestAnomalyDetection:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_extreme_anomaly_detected(self):
        rows = [{"balance": float(i)} for i in range(1, 21)] + [{"balance": 9999.0}]
        anomalies = self.analyzer.detect_anomalies(rows, ["balance"])
        assert len(anomalies) >= 1
        assert anomalies[0].column == "balance"
        assert anomalies[0].deviation > 2.0

    def test_no_anomalies_uniform(self):
        rows = [{"balance": 500.0} for _ in range(10)]
        anomalies = self.analyzer.detect_anomalies(rows, ["balance"])
        assert anomalies == []

    def test_provenance(self):
        rows = [{"balance": 100.0}] * 9 + [{"balance": 10000.0}]
        anomalies = self.analyzer.detect_anomalies(rows, ["balance"])
        assert anomalies[0].provenance.method == "z_score_anomaly_detection"


# ─────────────────────────────────────────────────────────────────────────────
# 5. Correlations
# ─────────────────────────────────────────────────────────────────────────────

class TestCorrelations:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_strong_positive_correlation(self):
        rows = [{"a": float(i), "b": float(i * 2)} for i in range(1, 20)]
        corrs = self.analyzer.compute_correlations(rows, ["a", "b"])
        assert len(corrs) == 1
        assert corrs[0].coefficient == pytest.approx(1.0, abs=0.01)
        assert corrs[0].sample_size == 19
        assert corrs[0].provenance.method == "pearson_correlation"

    def test_no_correlation_with_single_column(self):
        rows = [{"a": float(i)} for i in range(1, 10)]
        corrs = self.analyzer.compute_correlations(rows, ["a"])
        assert corrs == []

    def test_zero_variance_skipped(self):
        rows = [{"a": 5.0, "b": float(i)} for i in range(1, 10)]
        corrs = self.analyzer.compute_correlations(rows, ["a", "b"])
        assert corrs == []


# ─────────────────────────────────────────────────────────────────────────────
# 6. Temporal Comparisons
# ─────────────────────────────────────────────────────────────────────────────

class TestTemporalComparisons:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_period_over_period_change(self):
        rows = [
            {"date": "2024-01-01", "amount": 100.0},
            {"date": "2024-01-02", "amount": 120.0},
            {"date": "2024-01-03", "amount": 140.0},
            {"date": "2024-01-04", "amount": 160.0},
        ]
        comps = self.analyzer.compute_temporal_comparisons(rows, ["date"], ["amount"])
        assert len(comps) == 1
        tc = comps[0]
        assert tc.column == "amount"
        assert tc.percentage_change is not None
        assert tc.percentage_change > 0
        assert tc.provenance.method == "period_over_period_grouped"

    def test_unsorted_timestamps(self):
        rows = [
            {"date": "2024-03-10", "amount": 160.0},
            {"date": "2024-01-01", "amount": 100.0},
            {"date": "2024-01-15", "amount": 120.0},
            {"date": "2024-03-20", "amount": 180.0},
        ]
        comps = self.analyzer.compute_temporal_comparisons(rows, ["date"], ["amount"])
        # daily bucket; only latest complete day vs preceding day still meaningful
        assert len(comps) == 1
        assert comps[0].percentage_change is not None

    def test_only_one_period_unavailable(self):
        # All rows within a single day -> no previous period to compare
        rows = [
            {"date": "2024-01-01", "amount": 100.0},
            {"date": "2024-01-01", "amount": 110.0},
            {"date": "2024-01-01", "amount": 120.0},
        ]
        comps = self.analyzer.compute_temporal_comparisons(rows, ["date"], ["amount"])
        assert comps == []

    def test_invalid_dates_skipped(self):
        rows = [
            {"date": "not-a-date", "amount": 100.0},
            {"date": "2024-01-02", "amount": 120.0},
            {"date": "2024-01-03", "amount": 140.0},
            {"date": "2024-01-04", "amount": 160.0},
        ]
        comps = self.analyzer.compute_temporal_comparisons(rows, ["date"], ["amount"])
        # invalid date filtered out; 3 valid dates, latest day vs preceding day
        assert len(comps) == 1

    def test_monthly_granularity_detected(self):
        rows = [
            {"date": "2024-01-10", "amount": 100.0},
            {"date": "2024-01-20", "amount": 110.0},
            {"date": "2024-02-05", "amount": 130.0},
            {"date": "2024-02-15", "amount": 140.0},
        ]
        comps = self.analyzer.compute_temporal_comparisons(rows, ["date"], ["amount"])
        assert len(comps) == 1
        assert comps[0].latest_period == "2024-02"
        assert comps[0].earliest_period == "2024-01"

    def test_no_temporal_columns(self):
        rows = [{"amount": float(i)} for i in range(1, 10)]
        comps = self.analyzer.compute_temporal_comparisons(rows, [], ["amount"])
        assert comps == []


# ─────────────────────────────────────────────────────────────────────────────
# 7. Fact Package Builder (Integration)
# ─────────────────────────────────────────────────────────────────────────────

class TestFactPackageBuilder:

    @pytest.mark.asyncio
    async def test_full_pipeline(self):
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())

        req = InsightsRequest(
            query_intent="customer_analysis",
            query_text="Top 10 customers by balance",
            results=[
                {"customer_id": f"C{i:03d}", "name": f"Customer {i}",
                 "balance": float(i * 50000), "region": "Tunis" if i % 2 == 0 else "Sfax"}
                for i in range(1, 11)
            ],
            metadata={"tables": ["customers", "accounts"], "rows_returned": 10},
        )
        gen.context_gatherer.gather_context = AsyncMock(return_value=MagicMock(
            system_totals={"rows_returned": 10}
        ))
        gen.mistral.interpret = MagicMock(side_effect=AssertionError("LLM must not run"))

        resp = await gen.generate(req)

        assert resp.status == "success"
        assert resp.confidence > 0  # evidence quality, not hardcoded 0.85
        assert resp.key_metrics["total_count"] == 10
        assert "primary_column" in resp.key_metrics
        # RANKING without explicit explanation -> deterministic (no LLM call)
        gen.mistral.interpret.assert_not_called()
        assert resp.summary != ""

    @pytest.mark.asyncio
    async def test_empty_results_returns_no_data(self):
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())

        req = InsightsRequest(
            query_intent="customer_analysis",
            query_text="Empty query",
            results=[],
            metadata={},
        )
        resp = await gen.generate(req)
        assert resp.status == "no_data"
        assert resp.confidence == 0.0
        assert resp.recommendations == []


# ─────────────────────────────────────────────────────────────────────────────
# 8. Recommendation Candidates
# ─────────────────────────────────────────────────────────────────────────────

class TestRecommendationCandidates:

    def test_anomaly_recommendation(self):
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())
        profile = DatasetProfile(
            row_count=10, columns=["balance"],
            numeric_columns=["balance"],
        )
        anomalies = [AnomalyFact(
            column="balance", observed_value=10000.0,
            mean=100.0, std_dev=10.0, deviation=990.0,
            severity="extreme",
            provenance=Provenance(source="deterministic_calculation", column="balance", method="z_score"),
        )]
        recs = gen._generate_recommendation_candidates(profile, [], anomalies, [], [])
        assert len(recs) >= 1
        assert recs[0].rule == "anomaly_concentration"
        assert "extreme" in recs[0].message.lower() or "anomal" in recs[0].message.lower()

    def test_no_generic_recommendations(self):
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())
        profile = DatasetProfile(row_count=10, columns=["x"], numeric_columns=["x"])
        recs = gen._generate_recommendation_candidates(profile, [], [], [], [])
        # No evidence → no recommendations
        assert recs == []


# ─────────────────────────────────────────────────────────────────────────────
# 9. Evidence Quality Score
# ─────────────────────────────────────────────────────────────────────────────

class TestEvidenceQuality:

    def test_high_quality(self):
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())
        profile = DatasetProfile(
            row_count=100, columns=["a", "b", "c"],
            numeric_columns=["a", "b"],
            categorical_columns=["c"],
            null_counts={"a": 0, "b": 0, "c": 0},
        )
        eq = gen._compute_evidence_quality(profile, [{"a": 1, "b": 2, "c": "X"}] * 100)
        assert eq.score >= 0.6
        assert eq.row_count_adequate is True
        assert eq.has_numeric_data is True
        assert eq.completeness_ratio == pytest.approx(1.0)

    def test_low_quality_small_dataset(self):
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())
        profile = DatasetProfile(
            row_count=2, columns=["x"], categorical_columns=["x"],
            null_counts={"x": 1},
        )
        eq = gen._compute_evidence_quality(profile, [{"x": "a"}])
        assert eq.row_count_adequate is False
        assert eq.score < 0.8

    def test_quality_does_not_reward_patterns(self):
        """Quality score measures data quality, not pattern presence."""
        from insights_generator import InsightsGenerator
        gen = InsightsGenerator(_make_config())
        profile = DatasetProfile(
            row_count=100, columns=["a", "b"],
            numeric_columns=["a", "b"], null_counts={"a": 0, "b": 0},
        )
        # The evidence-quality model exposes NO pattern-count fields
        eq = gen._compute_evidence_quality(profile, [{"a": 1.0, "b": 2.0}] * 100)
        assert not hasattr(eq, "anomaly_count")
        assert not hasattr(eq, "correlation_pairs_computed")
        assert not hasattr(eq, "has_temporal_comparison")


# ─────────────────────────────────────────────────────────────────────────────
# 10. Model Backward Compatibility
# ─────────────────────────────────────────────────────────────────────────────

class TestModelBackwardCompatibility:

    def test_insights_request_defaults(self):
        req = InsightsRequest(
            query_intent="revenue_analysis",
            query_text="Total revenue by product",
            results=[],
        )
        assert req.metadata == {}

    def test_insights_response_defaults(self):
        resp = InsightsResponse(status="success", summary="All good")
        assert resp.trends == []
        assert resp.recommendations == []
        assert resp.anomalies == []
        assert resp.confidence == 0.0

    def test_analytical_fact_package_fields(self):
        pkg = AnalyticalFactPackage(
            query_intent="test",
            dataset_profile=DatasetProfile(row_count=5),
        )
        assert pkg.query_intent == "test"
        assert pkg.dataset_profile.row_count == 5
        assert pkg.descriptive_stats == []
        assert pkg.anomalies == []
        assert pkg.correlations == []
        assert pkg.evidence_quality.score == 0.0

    def test_provenance_model(self):
        p = Provenance(source="deterministic_calculation", column="balance", method="numpy")
        assert p.source == "deterministic_calculation"
        assert p.column == "balance"

    def test_recommendation_candidate_model(self):
        rc = RecommendationCandidate(
            rule="test_rule",
            message="Test message",
            severity="warning",
        )
        assert rc.rule == "test_rule"
        assert rc.severity == "warning"
        assert rc.evidence_column is None
