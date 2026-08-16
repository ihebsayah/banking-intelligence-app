"""Tests for the submitted investigation review queue (Phase 3A.9B).

Verifies authorization (Compliance allowed, Analyst without investigation:review denied, Admin prohibited),
server-side status/scope filtering, and non-interference with Analyst list_assigned.
"""
import pytest
from unittest.mock import AsyncMock, patch

from shared.authorise import (
    ApplicationUser, PermissionDeniedError, ProhibitedComboError,
)
from workbench.services.investigation_service import InvestigationService
from workbench.models import Investigation

COMPLIANCE = ApplicationUser(
    user_id="comp1",
    role="compliance",
    permissions=["investigation:read", "investigation:review"],
    scopes=["hq_main"],
)

ANALYST = ApplicationUser(
    user_id="analyst1",
    role="analyst",
    permissions=["investigation:read_own", "investigation:transition"],
    scopes=["hq_main"],
)

ADMIN = ApplicationUser(
    user_id="admin1",
    role="admin",
    permissions=["investigation:read", "investigation:review"],
    scopes=["hq_main"],
)

MOCK_SUBMITTED_ROW = {
    "investigation_id": "inv_sub_1",
    "title": "Submitted AML Case",
    "description": "Findings ready for compliance review",
    "alert_id": "alt_1",
    "scope_id": "hq_main",
    "status": "submitted",
    "priority": "high",
    "assigned_to": "analyst1",
    "created_by": "analyst1",
    "findings_text": "Evidence of structuring",
    "findings_refs": [],
    "conclusion": "Escalating",
    "started_at": "2026-08-16T00:00:00Z",
    "submitted_at": "2026-08-16T02:00:00Z",
    "completed_at": None,
    "return_reason": None,
    "version": 2,
    "created_at": "2026-08-16T00:00:00Z",
    "updated_at": "2026-08-16T02:00:00Z",
}


@pytest.fixture
def mock_db_fetch():
    return {
        "_fetch_all": AsyncMock(return_value=[MOCK_SUBMITTED_ROW]),
        "_fetch_one": AsyncMock(return_value=None),
    }


class TestSubmittedQueueAuthorization:
    @pytest.mark.asyncio
    async def test_compliance_can_access_submitted_queue(self, mock_db, mock_db_fetch):
        with patch("workbench.repos._fetch_all", mock_db_fetch["_fetch_all"]):
            items, total = await InvestigationService(mock_db).list_submitted(COMPLIANCE, "hq_main")
        assert len(items) == 1
        assert items[0].investigation_id == "inv_sub_1"
        assert items[0].status == "submitted"
        assert total == 1

        # Verify SQL query sent status="submitted"
        call_args = mock_db_fetch["_fetch_all"].call_args
        sql = call_args[0][1]
        params = call_args[0][2]
        assert "status = $" in sql
        assert "submitted" in params

    @pytest.mark.asyncio
    async def test_analyst_without_review_perm_denied(self, mock_db):
        with pytest.raises(PermissionDeniedError):
            await InvestigationService(mock_db).list_submitted(ANALYST, "hq_main")

    @pytest.mark.asyncio
    async def test_admin_is_prohibited_from_review_queue(self, mock_db):
        with pytest.raises(ProhibitedComboError):
            await InvestigationService(mock_db).list_submitted(ADMIN, "hq_main")

    @pytest.mark.asyncio
    async def test_analyst_assigned_queue_remains_intact(self, mock_db, mock_db_fetch):
        with patch("workbench.repos._fetch_all", mock_db_fetch["_fetch_all"]):
            items, total = await InvestigationService(mock_db).list_assigned(ANALYST, "hq_main")
        assert len(items) == 1
        # Verify call used user_id
        call_args = mock_db_fetch["_fetch_all"].call_args
        params = call_args[0][2]
        assert "analyst1" in params
