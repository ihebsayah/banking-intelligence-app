"""Authorisation policy tests for comment, timeline, and notification actions (2B.9).

Covers the state-machine wiring added for 2B.9: comment/timeline actions gate
on the parent entity status (EC05), notifications use the synthetic unread/read
states, and the bare timeline:read check uses the synthetic "active" state.
"""
import pytest

from shared.authorise import (
    ApplicationUser, PermissionDeniedError, Resource,
    WorkflowStateError, authorise,
)

ANALYST = ApplicationUser(user_id="analyst1", role="analyst", permissions=[
    "comment:read", "comment:create", "timeline:read",
    "notification:read", "notification:update",
    "alert:read_assigned", "investigation:read_own", "case:read_assigned",
], scopes=["hq_main"])
COMPLIANCE = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "comment:read", "comment:create", "comment:view_internal_content",
    "timeline:read", "notification:read", "notification:update",
    "case:read_assigned", "case:read",
], scopes=["hq_main"])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "comment:read", "comment:redact", "comment:view_metadata",
    "timeline:read", "notification:read", "notification:update",
    "case:read",
], scopes=["hq_main"])
NO_COMMENT_PERM = ApplicationUser(user_id="none1", role="analyst", permissions=[
    "timeline:read", "alert:read_assigned",
], scopes=["hq_main"])


def case_resource(status="under_review"):
    return Resource(id="case1", status=status, assigned_to="comp1",
                    scope_id="hq_main", version=2, entity_type="compliance_case",
                    risk_level="medium", created_by="comp1")


def alert_resource(status="assigned"):
    return Resource(id="alert1", status=status, assigned_to="analyst1",
                    scope_id="hq_main", version=1, entity_type="alert",
                    severity="medium", created_by=None)


class TestCommentCreateWorkflow:
    @pytest.mark.asyncio
    async def test_allowed_on_open_case(self):
        await authorise(COMPLIANCE, "comment:create", case_resource(status="open"))

    @pytest.mark.asyncio
    async def test_allowed_on_active_alert(self):
        await authorise(ANALYST, "comment:create", alert_resource(status="assigned"))

    @pytest.mark.asyncio
    async def test_ec05_closed_case_rejected(self):
        with pytest.raises(WorkflowStateError) as ei:
            await authorise(COMPLIANCE, "comment:create", case_resource(status="closed"))
        assert ei.value.http_status == 409

    @pytest.mark.asyncio
    async def test_cancelled_case_rejected(self):
        with pytest.raises(WorkflowStateError):
            await authorise(COMPLIANCE, "comment:create", case_resource(status="cancelled"))

    @pytest.mark.asyncio
    async def test_missing_permission_rejected(self):
        with pytest.raises(PermissionDeniedError):
            await authorise(NO_COMMENT_PERM, "comment:create", alert_resource())


class TestCommentReadWorkflow:
    @pytest.mark.asyncio
    async def test_read_allowed_on_closed_case(self):
        await authorise(COMPLIANCE, "comment:read", case_resource(status="closed"))

    @pytest.mark.asyncio
    async def test_read_allowed_on_cancelled_case(self):
        await authorise(COMPLIANCE, "comment:read", case_resource(status="cancelled"))

    @pytest.mark.asyncio
    async def test_missing_permission_rejected(self):
        with pytest.raises(PermissionDeniedError):
            await authorise(NO_COMMENT_PERM, "comment:read", alert_resource())


class TestCommentRedact:
    @pytest.mark.asyncio
    async def test_admin_allowed_in_any_case_state(self):
        for status in ("open", "assigned", "under_review", "awaiting_information",
                       "decision_pending", "awaiting_compliance_action",
                       "resolved", "closed", "cancelled"):
            await authorise(ADMIN, "comment:redact", case_resource(status=status))

    @pytest.mark.asyncio
    async def test_compliance_lacks_redact_permission(self):
        with pytest.raises(PermissionDeniedError):
            await authorise(COMPLIANCE, "comment:redact", case_resource())


class TestTimelineRead:
    @pytest.mark.asyncio
    async def test_allowed_on_parent_entity(self):
        await authorise(ANALYST, "timeline:read", alert_resource())

    @pytest.mark.asyncio
    async def test_bare_timeline_action_has_a_state_home(self):
        res = Resource(id="analyst1", status="active", entity_type="timeline")
        await authorise(ANALYST, "timeline:read", res)

    @pytest.mark.asyncio
    async def test_missing_permission_rejected(self):
        user = ApplicationUser(user_id="x", role="analyst",
                               permissions=["comment:read"], scopes=["hq_main"])
        with pytest.raises(PermissionDeniedError):
            await authorise(user, "timeline:read", alert_resource())


class TestNotificationActions:
    @pytest.mark.asyncio
    async def test_read_allowed_on_unread_and_read(self):
        for status in ("unread", "read"):
            res = Resource(id="analyst1", status=status, entity_type="notification")
            await authorise(ANALYST, "notification:read", res)

    @pytest.mark.asyncio
    async def test_update_allowed(self):
        res = Resource(id="analyst1", status="unread", entity_type="notification")
        await authorise(ANALYST, "notification:update", res)

    @pytest.mark.asyncio
    async def test_missing_permission_rejected(self):
        user = ApplicationUser(user_id="x", role="analyst",
                               permissions=[], scopes=["hq_main"])
        res = Resource(id="x", status="unread", entity_type="notification")
        with pytest.raises(PermissionDeniedError):
            await authorise(user, "notification:read", res)
