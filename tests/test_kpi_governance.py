"""
tests/test_kpi_governance.py

Tests for the KPI Governance endpoints and service layer.

Run:
    pytest tests/test_kpi_governance.py -v
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'api_gateway'))


# ─── KPIService unit tests ─────────────────────────────────────────────────────

class TestKPIServiceComputeKPI:
    """Tests for KPIService.compute_kpi()"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.fetch_one = AsyncMock()
        db.fetch_all = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_compute_active_kpi_returns_value(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_one.side_effect = [
            # kpi_definitions row
            {
                'kpi_id': 'total_deposits', 'name': 'Total Deposits', 'category': 'liquidity',
                'description': 'Sum of balances', 'metric_type': 'currency',
                'formula': 'SUM(accounts.balance)', 'status': 'active', 'unavailable_reason': None,
                'owner_id': None
            },
            # computed value
            {'value': 1_500_000.0},
        ]
        mock_db.fetch_all.return_value = []
        result = await KPIService.compute_kpi(mock_db, 'total_deposits')
        assert result['kpi_id'] == 'total_deposits'
        assert result['status'] == 'active'
        assert result['value'] == 1_500_000.0

    @pytest.mark.asyncio
    async def test_compute_unavailable_kpi_returns_none_value(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_one.return_value = {
            'kpi_id': 'npl_ratio', 'name': 'NPL Ratio', 'category': 'credit_quality',
            'description': None, 'metric_type': 'percentage',
            'formula': None, 'status': 'unavailable',
            'unavailable_reason': 'No loan delinquency data available',
            'owner_id': None
        }
        mock_db.fetch_all.return_value = []
        result = await KPIService.compute_kpi(mock_db, 'npl_ratio')
        assert result['status'] == 'unavailable'
        assert result['value'] is None
        assert 'unavailable_reason' in result

    @pytest.mark.asyncio
    async def test_compute_unknown_kpi_raises_value_error(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_one.return_value = None
        with pytest.raises(ValueError, match='not found'):
            await KPIService.compute_kpi(mock_db, 'nonexistent_kpi')

    @pytest.mark.asyncio
    async def test_get_all_kpis_returns_list(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_all.return_value = [
            {
                'kpi_id': 'total_deposits', 'name': 'Total Deposits', 'category': 'liquidity',
                'description': None, 'metric_type': 'currency', 'formula': 'SUM(accounts.balance)',
                'status': 'active', 'unavailable_reason': None, 'owner_id': None
            },
            {
                'kpi_id': 'npl_ratio', 'name': 'NPL Ratio', 'category': 'credit_quality',
                'description': None, 'metric_type': 'percentage', 'formula': None,
                'status': 'unavailable', 'unavailable_reason': 'No data', 'owner_id': None
            }
        ]
        mock_db.fetch_one.return_value = {'value': 1_200_000.0}
        results = await KPIService.get_all_kpis(mock_db)
        assert isinstance(results, list)
        kpi_ids = [r['kpi_id'] for r in results]
        assert 'total_deposits' in kpi_ids
        assert 'npl_ratio' in kpi_ids


# ─── Threshold evaluation tests ───────────────────────────────────────────────

class TestThresholdEvaluation:
    """Tests for KPIService.evaluate_threshold()"""

    def test_healthy_evaluation(self):
        from kpi_service import KPIService
        threshold = {
            'healthy_min': 10.0, 'healthy_max': 20.0,
            'warning_min': 5.0, 'warning_max': 25.0,
            'critical_min': None, 'critical_max': 30.0,
        }
        result = KPIService.evaluate_threshold(15.0, threshold)
        assert result == 'healthy'

    def test_warning_evaluation_low(self):
        from kpi_service import KPIService
        threshold = {
            'healthy_min': 10.0, 'healthy_max': 20.0,
            'warning_min': 5.0, 'warning_max': 25.0,
            'critical_min': None, 'critical_max': 30.0,
        }
        result = KPIService.evaluate_threshold(7.0, threshold)
        assert result == 'warning'

    def test_critical_evaluation_exceeded(self):
        from kpi_service import KPIService
        threshold = {
            'healthy_min': 10.0, 'healthy_max': 20.0,
            'warning_min': 5.0, 'warning_max': 25.0,
            'critical_min': None, 'critical_max': 30.0,
        }
        result = KPIService.evaluate_threshold(35.0, threshold)
        assert result == 'critical'

    def test_none_threshold_returns_unknown(self):
        from kpi_service import KPIService
        result = KPIService.evaluate_threshold(None, None)
        assert result == 'unknown'

    def test_none_value_returns_unknown(self):
        from kpi_service import KPIService
        threshold = {'healthy_min': 10.0, 'healthy_max': 20.0, 'warning_min': 5.0,
                     'warning_max': 25.0, 'critical_min': None, 'critical_max': 30.0}
        result = KPIService.evaluate_threshold(None, threshold)
        assert result == 'unknown'


# ─── Trend query tests ─────────────────────────────────────────────────────────

class TestKPITrends:
    """Tests for KPIService.get_kpi_trends()"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.fetch_all = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_trends_returns_list(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_all.return_value = [
            {'month': '2024-01', 'value': 1_000_000.0},
            {'month': '2024-02', 'value': 1_100_000.0},
        ]
        result = await KPIService.get_kpi_trends(mock_db, 'total_deposits', 3)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_trends_fallback_on_error(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_all.side_effect = Exception('DB error')
        result = await KPIService.get_kpi_trends(mock_db, 'bad_id', 12)
        assert result == []


# ─── Explanation tests ────────────────────────────────────────────────────────

class TestKPIExplanation:
    """Tests for KPIService.get_kpi_explanation()"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.fetch_one = AsyncMock()
        db.fetch_all = AsyncMock(return_value=[])
        return db

    @pytest.mark.asyncio
    async def test_explanation_structure(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_one.side_effect = [
            {
                'kpi_id': 'total_deposits', 'name': 'Total Deposits', 'category': 'liquidity',
                'description': 'Sum of all account balances.', 'metric_type': 'currency',
                'formula': 'SUM(accounts.balance)', 'status': 'active', 'unavailable_reason': None,
                'owner_id': None
            },
            {'value': 1_500_000.0},
        ]
        result = await KPIService.get_kpi_explanation(mock_db, 'total_deposits')
        assert 'kpi_id' in result
        assert 'explanation' in result
        assert isinstance(result['explanation'], str)
        assert len(result['explanation']) > 10

    @pytest.mark.asyncio
    async def test_explanation_unavailable_kpi(self, mock_db):
        from kpi_service import KPIService
        mock_db.fetch_one.return_value = {
            'kpi_id': 'npl_ratio', 'name': 'NPL Ratio', 'category': 'credit_quality',
            'description': None, 'metric_type': 'percentage', 'formula': None,
            'status': 'unavailable', 'unavailable_reason': 'No delinquency data', 'owner_id': None
        }
        mock_db.fetch_all.return_value = []
        result = await KPIService.get_kpi_explanation(mock_db, 'npl_ratio')
        assert result['kpi_id'] == 'npl_ratio'
        assert 'explanation' in result


# ─── Catalog enrichment tests ─────────────────────────────────────────────────

class TestCatalogIntegrity:
    """Tests that catalog contains required governance fields."""

    REQUIRED_FIELDS = ['kpi_id', 'name', 'category', 'metric_type', 'status']

    def test_catalog_entry_has_required_fields(self):
        entry = {
            'kpi_id': 'net_interest_margin', 'name': 'Net Interest Margin',
            'category': 'profitability', 'metric_type': 'percentage', 'status': 'active',
            'formula': '(Interest Income - Interest Expense) / Average Earning Assets',
            'owner_name': 'CFO Office', 'owner_email': 'cfo@bank.com',
        }
        for f in self.REQUIRED_FIELDS:
            assert f in entry, f"Missing required field: {f}"

    def test_unavailable_entry_has_reason(self):
        entry = {
            'kpi_id': 'npl_ratio', 'name': 'NPL Ratio', 'category': 'credit_quality',
            'metric_type': 'percentage', 'status': 'unavailable',
            'unavailable_reason': 'No loan delinquency data in schema',
        }
        assert entry['status'] == 'unavailable'
        assert 'unavailable_reason' in entry
        assert entry['unavailable_reason']
