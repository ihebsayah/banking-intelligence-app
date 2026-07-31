"""Authorisation policy tests for information request actions."""
import pytest

from shared.authorise import (
    ApplicationUser, OwnershipDeniedError, PermissionDeniedError,
    Resource, ScopeDeniedError, WorkflowStateError, authorise,
)

ANALYST = ApplicationUser(user_id="analyst1", role="analyst", permissions=[
    "info_request:respond", "info_request:read_assigned",
], scopes=["hq_main"])
COMPLIANCE = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "info_request:create", "info_request:read", "info_request:accept",
    "info_request:return", "info_request:cancel",
], scopes=["hq_main"])
OTHER_COMPLIANCE = ApplicationUser(user_id="comp2", role="compliance", permissions=[
    "info_request:create", "info_request:read", "info_request:accept",
    "info_request:return", "info_request:cancel",
], scopes=["hq_main"])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "info_request:read", "info_request:cancel",
], scopes=["hq_main"])


def ir_resource(status="open", assigned_to="analyst1", created_by="comp1", scope_id="hq_main"):
    return Resource(id="ir1", status=status, assigned_to=assigned_to,
                    scope_id=scope_id, version=1, entity_type="information_request",
                    created_by=created_by)


def case_resource(status="under_review", assigned_to="comp1", created_by="comp1"):
    return Resource(id="case1", status=status, assigned_to=assigned_to,
                    scope_id="hq_main", version=2, entity_type="compliance_case",
                    created_by=created_by)


class TestRespond:
    @pytest.mark.asyncio
    async def test_assigned_analyst_allowed(self):
        await authorise(ANALYST, "info_request:respond", ir_resource())

    @pytest.mark.asyncio
    async def test_other_analyst_denied(self):
        res = ir_resource(assigned_to="analyst2")
        with pytest.raises(OwnershipDeniedError):
            await authorise(ANALYST, "info_request:respond", res)

    @pytest.mark.asyncio
    async def test_respond_workflow_states(self):
        for status in ("open", "acknowledged", "returned"):
            await authorise(ANALYST, "info_request:respond", ir_resource(status=status))
        for status in ("responded", "accepted", "cancelled"):
            with pytest.raises(WorkflowStateError):
                await authorise(ANALYST, "info_request:respond", ir_resource(status=status))


class TestAccept:
    @pytest.mark.asyncio
    async def test_creator_allowed(self):
        await authorise(COMPLIANCE, "info_request:accept",
                        ir_resource(status="responded", created_by="comp1"))

    @pytest.mark.asyncio
    async def test_non_creator_denied(self):
        res = ir_resource(status="responded", created_by="comp2")
        with pytest.raises(OwnershipDeniedError):
            await authorise(COMPLIANCE, "info_request:accept", res)

    @pytest.mark.asyncio
    async def test_analyst_lacks_permission(self):
        res = ir_resource(status="responded", created_by="comp1")
        with pytest.raises(PermissionDeniedError):
            await authorise(ANALYST, "info_request:accept", res)

    @pytest.mark.asyncio
    async def test_only_from_responded(self):
        res = ir_resource(status="open", created_by="comp1")
        with pytest.raises(WorkflowStateError):
            await authorise(COMPLIANCE, "info_request:accept", res)


class TestReturn:
    @pytest.mark.asyncio
    async def test_creator_allowed(self):
        await authorise(COMPLIANCE, "info_request:return",
                        ir_resource(status="responded", created_by="comp1"))

    @pytest.mark.asyncio
    async def test_non_creator_denied(self):
        res = ir_resource(status="responded", created_by="comp2")
        with pytest.raises(OwnershipDeniedError):
            await authorise(COMPLIANCE, "info_request:return", res)


class TestCancel:
    @pytest.mark.asyncio
    async def test_creator_allowed(self):
        await authorise(COMPLIANCE, "info_request:cancel", ir_resource(created_by="comp1"))

    @pytest.mark.asyncio
    async def test_non_creator_compliance_denied(self):
        res = ir_resource(created_by="comp1")
        with pytest.raises(OwnershipDeniedError):
            await authorise(OTHER_COMPLIANCE, "info_request:cancel", res)

    @pytest.mark.asyncio
    async def test_admin_bypasses_ownership(self):
        await authorise(ADMIN, "info_request:cancel", ir_resource(created_by="comp2"))

    @pytest.mark.asyncio
    async def test_analyst_lacks_permission(self):
        with pytest.raises(PermissionDeniedError):
            await authorise(ANALYST, "info_request:cancel", ir_resource())

    @pytest.mark.asyncio
    async def test_only_from_open_or_acknowledged(self):
        for status in ("open", "acknowledged"):
            await authorise(COMPLIANCE, "info_request:cancel", ir_resource(status=status))
        for status in ("responded", "accepted", "returned", "cancelled"):
            with pytest.raises(WorkflowStateError):
                await authorise(COMPLIANCE, "info_request:cancel", ir_resource(status=status))


class TestCreate:
    @pytest.mark.asyncio
    async def test_case_owner_allowed_on_under_review(self):
        await authorise(COMPLIANCE, "info_request:create", case_resource())

    @pytest.mark.asyncio
    async def test_non_owner_denied(self):
        res = case_resource(assigned_to="comp2")
        with pytest.raises(OwnershipDeniedError):
            await authorise(COMPLIANCE, "info_request:create", res)

    @pytest.mark.asyncio
    async def test_case_must_be_under_review(self):
        for status in ("open", "assigned", "awaiting_information", "decision_pending",
                       "resolved", "closed", "cancelled"):
            with pytest.raises(WorkflowStateError):
                await authorise(COMPLIANCE, "info_request:create", case_resource(status=status))


class TestRead:
    @pytest.mark.asyncio
    async def test_assigned_read_for_analyst(self):
        await authorise(ANALYST, "info_request:read_assigned", ir_resource())

    @pytest.mark.asyncio
    async def test_global_read_for_compliance(self):
        await authorise(COMPLIANCE, "info_request:read", ir_resource(assigned_to="analyst2"))

    @pytest.mark.asyncio
    async def test_admin_global_read(self):
        await authorise(ADMIN, "info_request:read", ir_resource(assigned_to="analyst2"))


class TestScope:
    @pytest.mark.asyncio
    async def test_out_of_scope_denied(self):
        res = ir_resource(scope_id="eu_main")
        with pytest.raises(ScopeDeniedError):
            await authorise(COMPLIANCE, "info_request:read", res)
