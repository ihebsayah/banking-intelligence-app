"""Timeline service tests (TL1-TL2)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser, Resource

from workbench.exceptions import ResourceNotFound, WorkbenchError
from workbench.models import ActivityTimelineEntry
from workbench.schemas.timeline import TimelineEntryResponse
from workbench.services.entity_access import ParentContext
from workbench.services.timeline_service import TimelineService

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

ANALYST = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "timeline:read", "alert:read_assigned", "investigation:read_own",
])

AUTH_TARGET = "workbench.services.timeline_service.authorise"
FETCH_PARENT_TARGET = "workbench.services.timeline_service.fetch_parent"
ASSERT_READABLE_TARGET = "workbench.services.timeline_service.assert_entity_readable"


def make_entry(entity_type="investigation", entity_id="inv1", **kw):
    defaults = dict(timeline_id=UID(), entity_type=entity_type, entity_id=entity_id,
                    event_type="investigation.created", actor_id="user1",
                    occurred_at=NOW)
    defaults.update(kw)
    return ActivityTimelineEntry(**defaults)


def make_parent(entity_type="investigation", status="active"):
    return ParentContext(
        entity=MagicMock(),
        resource=Resource(id="inv1", status=status, assigned_to="user1",
                          scope_id="hq_main", version=1, entity_type=entity_type),
    )


class TestListForEntity:
    @pytest.mark.asyncio
    async def test_gates_read_and_serialises(self, mock_db):
        parent = make_parent()
        mock_list = AsyncMock(return_value=[
            make_entry(), make_entry(event_type="investigation.completed"),
        ])
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=parent)), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()) as mock_readable, \
             patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.TimelineRepo.list_for_entity", mock_list), \
             patch("workbench.repos.TimelineRepo.count_for_entity",
                   AsyncMock(return_value=2)):
            items, total = await TimelineService(mock_db).list_for_entity(
                ANALYST, "investigations", "inv1")
        assert total == 2
        assert all(isinstance(i, TimelineEntryResponse) for i in items)
        mock_readable.assert_awaited_once()
        assert mock_auth.await_args.args[1] == "timeline:read"
        assert mock_auth.await_args.args[2].entity_type == "investigation"
        assert mock_list.await_args.args[0] == "investigation"
        assert mock_list.await_args.args[1] == "inv1"

    @pytest.mark.asyncio
    async def test_event_type_and_pagination_passed_through(self, mock_db):
        parent = make_parent()
        mock_list = AsyncMock(return_value=[])
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=parent)), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.TimelineRepo.list_for_entity", mock_list), \
             patch("workbench.repos.TimelineRepo.count_for_entity",
                   AsyncMock(return_value=0)):
            await TimelineService(mock_db).list_for_entity(
                ANALYST, "investigations", "inv1",
                event_type="investigation.completed", page=2, per_page=25)
        assert mock_list.await_args.kwargs["event_type"] == "investigation.completed"
        assert mock_list.await_args.kwargs["limit"] == 25
        assert mock_list.await_args.kwargs["offset"] == 25

    @pytest.mark.asyncio
    async def test_invalid_entity_type_400(self, mock_db):
        with pytest.raises(WorkbenchError) as exc:
            await TimelineService(mock_db).list_for_entity(
                ANALYST, "widgets", "w1")
        assert exc.value.http_status == 400
        assert exc.value.code == "INVALID_ENTITY_TYPE"

    @pytest.mark.asyncio
    async def test_entity_not_found_404(self, mock_db):
        with patch(FETCH_PARENT_TARGET,
                   AsyncMock(side_effect=ResourceNotFound("investigation", "ghost"))):
            with pytest.raises(ResourceNotFound):
                await TimelineService(mock_db).list_for_entity(
                    ANALYST, "investigations", "ghost")


class TestListForUser:
    @pytest.mark.asyncio
    async def test_authorises_on_synthetic_resource_and_delegates(self, mock_db):
        mock_list = AsyncMock(return_value=[make_entry()])
        mock_count = AsyncMock(return_value=1)
        with patch(AUTH_TARGET, AsyncMock()) as mock_auth, \
             patch("workbench.repos.TimelineRepo.list_for_user", mock_list), \
             patch("workbench.repos.TimelineRepo.count_for_user", mock_count):
            items, total = await TimelineService(mock_db).list_for_user(
                ANALYST, entity_type="cases", since=NOW)
        assert total == 1
        assert mock_auth.await_args.args[1] == "timeline:read"
        res = mock_auth.await_args.args[2]
        assert res.entity_type == "timeline"
        assert res.id == "user1"
        assert mock_list.await_args.args[0] == "user1"
        assert mock_list.await_args.kwargs["entity_type"] == "compliance_case"
        assert mock_list.await_args.kwargs["since"] == NOW

    @pytest.mark.asyncio
    async def test_no_entity_type_passes_none(self, mock_db):
        mock_list = AsyncMock(return_value=[])
        with patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.TimelineRepo.list_for_user", mock_list), \
             patch("workbench.repos.TimelineRepo.count_for_user",
                   AsyncMock(return_value=0)):
            await TimelineService(mock_db).list_for_user(ANALYST)
        assert mock_list.await_args.kwargs["entity_type"] is None


class TestRouteRegistration:
    def test_exact_count_two(self):
        from workbench.routers.timeline import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/{entity_type}/{entity_id}/timeline", ("GET",)) in routes
        assert ("/api/v1/timeline", ("GET",)) in routes
        assert len(router.routes) == 2
