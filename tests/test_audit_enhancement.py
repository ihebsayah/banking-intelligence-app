"""
tests/test_audit_enhancement.py
Unit tests for Phase 2 Audit Enhancement Service (Week 4-6).
DB pools are fully mocked.
"""
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

# Remove any previously added service dirs to avoid models.py collision
for _p in list(sys.path):
    if 'services' in _p and 'audit_enhancement' not in _p:
        sys.path.remove(_p)

AUDIT_ENH_DIR = os.path.join(
    os.path.dirname(__file__), "..", "services", "audit_enhancement"
)
if AUDIT_ENH_DIR not in sys.path:
    sys.path.insert(0, AUDIT_ENH_DIR)

from data_lineage_tracker import DataLineageTracker
from models import LineageResponse, ReportResponse


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    cfg = MagicMock()
    cfg.DATABASE_URL = "postgresql://fake/fake"
    cfg.AUDIT_DATABASE_URL = "postgresql://fake/fake_audit"
    return cfg


@pytest.fixture
def tracker(mock_config):
    t = DataLineageTracker(mock_config)
    # Provide a mock pool
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_conn),
        __aexit__=AsyncMock(return_value=False),
    ))
    mock_conn.execute = AsyncMock()
    t.pool = mock_pool
    t._mock_conn = mock_conn
    return t


# ─────────────────────────────────────────────────────────────────────────────
# DataLineageTracker
# ─────────────────────────────────────────────────────────────────────────────

class TestDataLineageTracker:

    @pytest.mark.asyncio
    async def test_track_returns_logged_true(self, tracker):
        result = await tracker.track(
            query_id="QRY001",
            user_id="U001",
            source_tables=["customers", "accounts"],
            accessed_columns=["customer_id", "balance"],
        )
        assert isinstance(result, LineageResponse)
        assert result.logged is True

    @pytest.mark.asyncio
    async def test_track_correct_record_count(self, tracker):
        result = await tracker.track(
            query_id="QRY002",
            user_id="U001",
            source_tables=["customers", "accounts"],
            accessed_columns=["customer_id", "balance", "segment"],
        )
        # 2 tables × 3 columns = 6 records
        assert result.records == 6

    @pytest.mark.asyncio
    async def test_track_single_table_single_col(self, tracker):
        result = await tracker.track(
            query_id="QRY003",
            user_id="U002",
            source_tables=["transactions"],
            accessed_columns=["amount"],
        )
        assert result.records == 1

    @pytest.mark.asyncio
    async def test_track_no_pool_returns_error(self, mock_config):
        t = DataLineageTracker(mock_config)
        t.pool = None
        result = await t.track("Q", "U", ["customers"], ["id"])
        assert result.logged is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_track_db_failure_returns_error(self, mock_config):
        t = DataLineageTracker(mock_config)
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=False),
        ))
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))
        t.pool = mock_pool
        result = await t.track("Q", "U", ["customers"], ["id"])
        assert result.logged is False


# ─────────────────────────────────────────────────────────────────────────────
# ComplianceReporter
# ─────────────────────────────────────────────────────────────────────────────

class TestComplianceReporter:

    @pytest.fixture
    def reporter(self, mock_config):
        from compliance_reporter import ComplianceReporter
        r = ComplianceReporter(mock_config)

        # Mock main_pool
        main_pool = MagicMock()
        main_pool.fetch = AsyncMock(return_value=[])
        main_pool.execute = AsyncMock()
        r.main_pool = main_pool

        # Mock audit_pool
        audit_pool = MagicMock()
        audit_pool.fetch = AsyncMock(return_value=[])
        r.audit_pool = audit_pool

        return r

    @pytest.mark.asyncio
    async def test_gdpr_report_returns_response(self, reporter):
        result = await reporter.generate_gdpr_report("U001", days=30)
        assert isinstance(result, ReportResponse)
        assert result.report_type == "GDPR_Right_to_Access"
        assert result.regulation == "GDPR"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_gdpr_report_period_in_response(self, reporter):
        result = await reporter.generate_gdpr_report("U001", days=90)
        assert "90" in result.period

    @pytest.mark.asyncio
    async def test_gdpr_report_stored(self, reporter):
        result = await reporter.generate_gdpr_report("U001", days=30)
        assert result.stored is True
        reporter.main_pool.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sox_report_returns_response(self, reporter):
        result = await reporter.generate_sox_report(days=90)
        assert isinstance(result, ReportResponse)
        assert result.report_type == "SOX_Access_Log"
        assert result.regulation == "SOX"

    @pytest.mark.asyncio
    async def test_sox_report_stored(self, reporter):
        result = await reporter.generate_sox_report(days=30)
        assert result.stored is True

    @pytest.mark.asyncio
    async def test_gdpr_report_handles_db_failure(self, reporter):
        reporter.main_pool.fetch = AsyncMock(side_effect=Exception("DB down"))
        result = await reporter.generate_gdpr_report("U001", days=30)
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_sox_report_handles_audit_db_failure(self, reporter):
        reporter.audit_pool.fetch = AsyncMock(side_effect=Exception("Audit DB down"))
        result = await reporter.generate_sox_report(days=30)
        # Should still succeed with empty data
        assert result.report_type == "SOX_Access_Log"


# ─────────────────────────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditEnhancementModels:

    def test_lineage_response_defaults(self):
        r = LineageResponse(logged=True)
        assert r.records == 0
        assert r.error is None

    def test_report_response_defaults(self):
        r = ReportResponse(
            report_type="GDPR_Right_to_Access",
            regulation="GDPR",
            generated_at="2026-05-19T12:00:00",
            period="Last 90 days",
        )
        assert r.data == {}
        assert r.stored is False
        assert r.error is None
