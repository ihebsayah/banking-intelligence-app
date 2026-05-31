import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Remove any previously added service dirs to avoid models.py collision
for _p in list(sys.path):
    if 'services' in _p and 'insights_agent' not in _p:
        sys.path.remove(_p)

INSIGHTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "services", "insights_agent"
)
if INSIGHTS_DIR not in sys.path:
    sys.path.insert(0, INSIGHTS_DIR)

from statistical_analyzer import StatisticalAnalyzer
from models import InsightsRequest, InsightsResponse, StatisticalAnalysis


# ─────────────────────────────────────────────────────────────────────────────
# StatisticalAnalyzer
# ─────────────────────────────────────────────────────────────────────────────

class TestStatisticalAnalyzer:

    def setup_method(self):
        self.analyzer = StatisticalAnalyzer()

    def test_empty_results_returns_empty_analysis(self):
        result = self.analyzer.analyze([])
        assert isinstance(result, StatisticalAnalysis)
        assert result.total_sum is None

    def test_detects_numeric_columns(self):
        rows = [{"name": "Alice", "balance": 100.0, "kyc": True}]
        cols = self.analyzer._detect_numeric_columns(rows)
        assert "balance" in cols
        assert "name" not in cols
        assert "kyc" not in cols   # bool excluded

    def test_basic_statistics_accuracy(self):
        rows = [
            {"balance": 100.0},
            {"balance": 200.0},
            {"balance": 300.0},
            {"balance": 400.0},
            {"balance": 500.0},
        ]
        stats = self.analyzer.analyze(rows, ["balance"])
        assert stats.total_sum == pytest.approx(1500.0)
        assert stats.average == pytest.approx(300.0)
        assert stats.median == pytest.approx(300.0)
        assert stats.min_value == pytest.approx(100.0)
        assert stats.max_value == pytest.approx(500.0)

    def test_percentiles_present(self):
        rows = [{"balance": float(i * 10)} for i in range(1, 21)]
        stats = self.analyzer.analyze(rows, ["balance"])
        assert "p25" in stats.percentiles
        assert "p75" in stats.percentiles
        assert "p99" in stats.percentiles

    def test_outlier_detection(self):
        # 1 outlier far from the mean
        rows = [{"balance": 100.0}] * 9 + [{"balance": 10000.0}]
        stats = self.analyzer.analyze(rows, ["balance"])
        assert len(stats.outliers) >= 1

    def test_no_outliers_uniform_data(self):
        rows = [{"balance": 500.0} for _ in range(10)]
        stats = self.analyzer.analyze(rows, ["balance"])
        assert stats.std_dev == pytest.approx(0.0)
        assert len(stats.outliers) == 0

    def test_auto_detect_multiple_numeric_cols(self):
        rows = [{"balance": 100.0, "amount": 50.0, "name": "X"}]
        cols = self.analyzer._detect_numeric_columns(rows)
        assert "balance" in cols
        assert "amount" in cols


# ─────────────────────────────────────────────────────────────────────────────
# InsightsGenerator (mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestInsightsGenerator:
    """Integration-lite tests with DB and Mistral mocked out."""

    @pytest.fixture
    def mock_config(self):
        cfg = MagicMock()
        cfg.DATABASE_URL = "postgresql://fake/fake"
        cfg.MISTRAL_API_URL = "http://localhost:11434"
        cfg.MISTRAL_MODEL = "mistral"
        return cfg

    @pytest.fixture
    def sample_results(self):
        return [
            {"customer_id": f"C{i:03d}", "name": f"Customer {i}", "balance": float(i * 50000)}
            for i in range(1, 11)
        ]

    @pytest.mark.asyncio
    async def test_generate_returns_success(self, mock_config, sample_results):
        from insights_generator import InsightsGenerator
        from models import ContextData

        gen = InsightsGenerator(mock_config)

        # Mock context gatherer
        gen.context_gatherer.initialize = AsyncMock()
        gen.context_gatherer.gather_context = AsyncMock(return_value=ContextData(
            system_totals={"total_deposits": 10_000_000, "total_customers": 500},
            regional_breakdown={"NY": 50, "CA": 30},
            segment_breakdown={"premium": 100, "standard": 200},
        ))

        # Mock Mistral
        gen.mistral.generate_summary = MagicMock(
            return_value="The top 10 customers hold 27.5% of total deposits, led by premium segment."
        )
        gen.mistral.generate_recommendations = MagicMock(return_value=[
            "1. Offer exclusive products to top-balance customers.",
            "2. Improve KYC for high-risk segment.",
            "3. Expand premium services in NY.",
        ])

        req = InsightsRequest(
            query_intent="customer_analysis",
            query_text="Top 10 customers by balance",
            results=sample_results,
            metadata={"tables": ["customers", "accounts"], "rows_returned": 10},
        )
        resp = await gen.generate(req)

        assert resp.status == "success"
        assert len(resp.recommendations) == 3
        assert resp.key_metrics["total_count"] == 10
        assert resp.confidence > 0

    @pytest.mark.asyncio
    async def test_generate_handles_empty_results(self, mock_config):
        from insights_generator import InsightsGenerator
        from models import ContextData

        gen = InsightsGenerator(mock_config)
        gen.context_gatherer.gather_context = AsyncMock(return_value=ContextData())
        gen.mistral.generate_summary = MagicMock(return_value="No data returned.")
        gen.mistral.generate_recommendations = MagicMock(return_value=[])

        req = InsightsRequest(
            query_intent="customer_analysis",
            query_text="Top 10 customers by balance",
            results=[],
            metadata={},
        )
        resp = await gen.generate(req)
        assert resp.status == "success"
        assert resp.key_metrics["total_count"] == 0

    @pytest.mark.asyncio
    async def test_generate_error_returns_error_status(self, mock_config):
        from insights_generator import InsightsGenerator

        gen = InsightsGenerator(mock_config)
        gen.context_gatherer.gather_context = AsyncMock(side_effect=RuntimeError("DB down"))
        gen.mistral.generate_summary = MagicMock(return_value="")
        gen.mistral.generate_recommendations = MagicMock(return_value=[])

        req = InsightsRequest(
            query_intent="risk_analysis",
            query_text="High risk customers",
            results=[{"balance": 1000}],
            metadata={},
        )
        resp = await gen.generate(req)
        assert resp.status == "error"
        assert resp.confidence == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class TestInsightsModels:

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
