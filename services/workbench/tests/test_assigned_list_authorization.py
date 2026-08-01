"""Real-authorise service tests for the four assigned-list endpoints (2B.14b).

Regression guards for the empty-status WorkflowStateError that the real
(unmocked) authorise() raised on every assigned-list service. Unlike the
mocked service tests, these call the real authorise() engine; only the repo
fetch layer is patched, so the exact Resource each service constructs is what
the policy engine sees.
"""
import pytest
from unittest.mock import AsyncMock, patch

from shared.authorise import (
    ApplicationUser, PermissionDeniedError, Resource, WorkflowStateError,
    authorise,
)

from workbench.services.alert_service import AlertService
from workbench.services.case_service import CaseService
from workbench.services.information_request_service import InformationRequestService
from workbench.services.investigation_service import InvestigationService

ANALYST = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "alert:read_assigned", "investigation:read_own",
])
COMPLIANCE = ApplicationUser(user_id="user1", role="compliance", permissions=[
    "case:read_assigned", "info_request:read_assigned",
])
NO_PERM = ApplicationUser(user_id="user2", role="analyst", permissions=[
    "workbench:access",
])


@pytest.fixture
def empty_fetch():
    return {
        "_fetch_all": AsyncMock(return_value=[]),
        "_fetch_one": AsyncMock(return_value={"count": 0}),
    }


class TestAlertListAssignedRealAuthorise:
    @pytest.mark.asyncio
    async def test_valid_user_passes(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            items, total = await AlertService(mock_db).list_assigned(ANALYST, "hq_main")
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_missing_permission_denied(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            with pytest.raises(PermissionDeniedError):
                await AlertService(mock_db).list_assigned(NO_PERM, "hq_main")


class TestInvestigationListAssignedRealAuthorise:
    @pytest.mark.asyncio
    async def test_valid_user_passes(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            items, total = await InvestigationService(mock_db).list_assigned(
                ANALYST, "hq_main")
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_missing_permission_denied(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            with pytest.raises(PermissionDeniedError):
                await InvestigationService(mock_db).list_assigned(NO_PERM, "hq_main")


class TestCaseListAssignedRealAuthorise:
    @pytest.mark.asyncio
    async def test_valid_user_passes(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            items, total = await CaseService(mock_db).list_assigned(COMPLIANCE, "hq_main")
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_missing_permission_denied(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            with pytest.raises(PermissionDeniedError):
                await CaseService(mock_db).list_assigned(NO_PERM, "hq_main")


class TestInformationRequestListAssignedRealAuthorise:
    @pytest.mark.asyncio
    async def test_valid_user_passes(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            items, total = await InformationRequestService(mock_db).list_assigned(
                COMPLIANCE, "hq_main")
        assert items == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_missing_permission_denied(self, mock_db, empty_fetch):
        with patch("workbench.repos._fetch_all", empty_fetch["_fetch_all"]), \
             patch("workbench.repos._fetch_one", empty_fetch["_fetch_one"]):
            with pytest.raises(PermissionDeniedError):
                await InformationRequestService(mock_db).list_assigned(
                    NO_PERM, "hq_main")

    @pytest.mark.asyncio
    async def test_empty_status_instance_still_rejected(self, mock_db, empty_fetch):
        with pytest.raises(WorkflowStateError):
            await authorise(
                COMPLIANCE, "info_request:read_assigned",
                Resource(id="", status="", entity_type="information_request"))
