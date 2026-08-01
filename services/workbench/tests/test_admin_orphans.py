"""Admin orphan-assignment endpoint tests (AD3)."""
from unittest.mock import AsyncMock, patch

import pytest

from shared.authorise import ApplicationUser, PermissionDeniedError

from workbench.schemas.admin_orphans import OrphanAssignmentsResponse
from workbench.services.admin_orphan_service import AdminOrphanService
from workbench.routers.admin_orphans import router

AUTH_TARGET = "workbench.services.admin_orphan_service.authorise"
REPO_TARGET = "workbench.repos.OrphanRepo.orphan_assignments"

ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "admin:orphan_monitor",
])
ANALYST = ApplicationUser(user_id="a1", role="analyst", permissions=[])
COMPLIANCE = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "case:read",
])
MANAGER = ApplicationUser(user_id="m1", role="manager", permissions=[
    "read:branch_data",
])
SYSTEM = ApplicationUser(user_id="system_001", role="system", permissions=[])


def make_rows():
    return [
        {"entity_type": "alert", "entity_id": "a1", "title": "Alert A",
         "status": "assigned", "assigned_user_id": "s1",
         "assigned_user_status": "suspended"},
        {"entity_type": "alert", "entity_id": "a2", "title": "Alert B",
         "status": "acknowledged", "assigned_user_id": "s2",
         "assigned_user_status": "active"},
        {"entity_type": "investigation", "entity_id": "i1", "title": "Inv 1",
         "status": "open", "assigned_user_id": "s1",
         "assigned_user_status": "suspended"},
        {"entity_type": "investigation", "entity_id": "i2", "title": "Inv 2",
         "status": "completed", "assigned_user_id": "s1",
         "assigned_user_status": "suspended"},
        {"entity_type": "compliance_case", "entity_id": "c1", "title": "Case 1",
         "status": "under_review", "assigned_user_id": "s1",
         "assigned_user_status": "suspended"},
    ]


class TestAuthorization:
    @pytest.mark.asyncio
    async def test_admin_allowed(self, mock_db):
        with patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch(REPO_TARGET, AsyncMock(return_value=make_rows())):
            resp = await AdminOrphanService(mock_db).list(ADMIN)
        assert isinstance(resp, OrphanAssignmentsResponse)
        assert mock_auth.await_args.args[1] == "admin:orphan_monitor"
        assert mock_auth.await_args.args[2].entity_type == "orphan_assignment"

    @pytest.mark.parametrize("user", [
        ANALYST, COMPLIANCE, MANAGER, SYSTEM,
        ApplicationUser(user_id="admin2", role="admin", permissions=[]),
    ], ids=["analyst", "compliance", "manager", "system", "admin-no-permission"])
    @pytest.mark.asyncio
    async def test_denied_without_permission(self, mock_db, user):
        with patch(REPO_TARGET, AsyncMock(return_value=[])):
            with pytest.raises(PermissionDeniedError):
                await AdminOrphanService(mock_db).list(user)


class TestDetection:
    @pytest.mark.asyncio
    async def test_groups_by_entity_type(self, mock_db):
        with patch(AUTH_TARGET, AsyncMock()), \
             patch(REPO_TARGET, AsyncMock(return_value=make_rows())):
            resp = await AdminOrphanService(mock_db).list(ADMIN)
        assert [i.entity_id for i in resp.alerts] == ["a1", "a2"]
        assert [i.entity_id for i in resp.investigations] == ["i1", "i2"]
        assert [i.entity_id for i in resp.cases] == ["c1"]

    @pytest.mark.asyncio
    async def test_terminal_status_reported_per_contract(self, mock_db):
        with patch(AUTH_TARGET, AsyncMock()), \
             patch(REPO_TARGET, AsyncMock(return_value=make_rows())):
            resp = await AdminOrphanService(mock_db).list(ADMIN)
        assert [i.status for i in resp.investigations] == ["open", "completed"]

    @pytest.mark.asyncio
    async def test_empty_when_no_orphans(self, mock_db):
        with patch(AUTH_TARGET, AsyncMock()), \
             patch(REPO_TARGET, AsyncMock(return_value=[])):
            resp = await AdminOrphanService(mock_db).list(ADMIN)
        assert resp.alerts == [] and resp.investigations == [] and resp.cases == []

    @pytest.mark.asyncio
    async def test_assignee_status_carried(self, mock_db):
        with patch(AUTH_TARGET, AsyncMock()), \
             patch(REPO_TARGET, AsyncMock(return_value=make_rows())):
            resp = await AdminOrphanService(mock_db).list(ADMIN)
        assert resp.alerts[0].assigned_to.model_dump() == {"user_id": "s1", "status": "suspended"}
        assert resp.alerts[1].assigned_to.status == "active"


class TestResponseSecurity:
    @pytest.mark.asyncio
    async def test_restricted_dto_only(self, mock_db):
        with patch(AUTH_TARGET, AsyncMock()), \
             patch(REPO_TARGET, AsyncMock(return_value=make_rows())):
            resp = await AdminOrphanService(mock_db).list(ADMIN)
        item = resp.cases[0]
        assert set(item.model_dump().keys()) == {"entity_id", "title", "status", "assigned_to"}
        assert set(item.assigned_to.model_dump().keys()) == {"user_id", "status"}
        for key in ("findings_text", "rationale", "question", "response_text",
                    "description", "identity_provider_subject"):
            assert key not in item.model_dump()

    @pytest.mark.asyncio
    async def test_no_pagination_fields(self, mock_db):
        assert set(OrphanAssignmentsResponse.model_fields.keys()) == {
            "alerts", "investigations", "cases",
        }


class TestRouteRegistration:
    def test_exactly_one_route_get_only(self):
        assert len(router.routes) == 1
        r = router.routes[0]
        assert r.path == "/api/v1/admin/orphan-assignments"
        assert {"GET"} == set(r.methods)
