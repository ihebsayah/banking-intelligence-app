"""Authorisation policy tests for approval actions."""
import pytest

from shared.authorise import (
    ApplicationUser, ConflictOfInterestError, PermissionDeniedError,
    ProhibitedComboError, Resource, ScopeDeniedError,
    WorkflowStateError, authorise,
)

ANALYST = ApplicationUser(user_id="analyst1", role="analyst", permissions=[
    "approval:request", "approval:read",
], scopes=["hq_main"])
COMPLIANCE = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "approval:request", "approval:approve", "approval:read",
], scopes=["hq_main"])
OTHER_COMPLIANCE = ApplicationUser(user_id="comp2", role="compliance", permissions=[
    "approval:approve", "approval:read",
], scopes=["hq_main"])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "approval:request", "approval:read",
], scopes=["hq_main"])


def approval_resource(status="pending", requester="comp1", scope_id="hq_main"):
    return Resource(id="ar1", status=status, assigned_to=requester,
                    scope_id=scope_id, version=1, entity_type="approval_request")


def alert_resource(status="acknowledged", assigned_to="analyst1", scope_id="hq_main"):
    return Resource(id="alert1", status=status, assigned_to=assigned_to,
                    scope_id=scope_id, version=1, entity_type="alert",
                    severity="critical")


def case_resource(status="resolved", assigned_to="comp1", scope_id="hq_main"):
    return Resource(id="case1", status=status, assigned_to=assigned_to,
                    scope_id=scope_id, version=2, entity_type="compliance_case",
                    risk_level="high", created_by="comp1")


class TestRequestApproval:
    @pytest.mark.asyncio
    async def test_analyst_can_request_on_acknowledged_alert(self):
        await authorise(ANALYST, "approval:request", alert_resource(status="acknowledged"))

    @pytest.mark.asyncio
    async def test_analyst_can_request_on_under_investigation_alert(self):
        await authorise(ANALYST, "approval:request", alert_resource(status="under_investigation"))

    @pytest.mark.asyncio
    async def test_analyst_cannot_request_on_new_alert(self):
        res = alert_resource(status="new")
        with pytest.raises(WorkflowStateError):
            await authorise(ANALYST, "approval:request", res)

    @pytest.mark.asyncio
    async def test_compliance_can_request_on_decision_pending_case(self):
        await authorise(COMPLIANCE, "approval:request", case_resource(status="decision_pending"))

    @pytest.mark.asyncio
    async def test_compliance_can_request_on_resolved_case(self):
        await authorise(COMPLIANCE, "approval:request", case_resource(status="resolved"))

    @pytest.mark.asyncio
    async def test_admin_can_request_reopen_on_closed_case(self):
        await authorise(ADMIN, "approval:request", case_resource(status="closed"))

    @pytest.mark.asyncio
    async def test_request_denied_out_of_scope(self):
        res = alert_resource(scope_id="branch_2")
        with pytest.raises(ScopeDeniedError):
            await authorise(ANALYST, "approval:request", res)

    @pytest.mark.asyncio
    async def test_lacks_permission(self):
        res = alert_resource()
        with pytest.raises(PermissionDeniedError):
            await authorise(OTHER_COMPLIANCE, "approval:request", res)


class TestVote:
    @pytest.mark.asyncio
    async def test_compliance_can_vote_on_pending(self):
        await authorise(OTHER_COMPLIANCE, "approval:approve",
                        approval_resource(requester="comp1"))

    @pytest.mark.asyncio
    async def test_analyst_prohibited(self):
        res = approval_resource(requester="comp1")
        with pytest.raises(ProhibitedComboError):
            await authorise(ANALYST, "approval:approve", res)

    @pytest.mark.asyncio
    async def test_requester_cannot_approve_own(self):
        res = approval_resource(requester="comp2")
        with pytest.raises(ConflictOfInterestError):
            await authorise(OTHER_COMPLIANCE, "approval:approve", res)

    @pytest.mark.asyncio
    async def test_approve_only_in_pending(self):
        for status in ("approved", "rejected", "expired", "cancelled"):
            res = approval_resource(status=status, requester="comp1")
            with pytest.raises(WorkflowStateError):
                await authorise(OTHER_COMPLIANCE, "approval:approve", res)

    @pytest.mark.asyncio
    async def test_approve_denied_out_of_scope(self):
        res = approval_resource(requester="comp1", scope_id="branch_2")
        with pytest.raises(ScopeDeniedError):
            await authorise(OTHER_COMPLIANCE, "approval:approve", res)


class TestRead:
    @pytest.mark.asyncio
    async def test_all_roles_read_all_statuses(self):
        for status in ("pending", "approved", "rejected", "expired", "cancelled"):
            await authorise(ANALYST, "approval:read", approval_resource(status=status))
            await authorise(COMPLIANCE, "approval:read", approval_resource(status=status))
            await authorise(ADMIN, "approval:read", approval_resource(status=status))

    @pytest.mark.asyncio
    async def test_read_denied_out_of_scope(self):
        res = approval_resource(scope_id="branch_2")
        with pytest.raises(ScopeDeniedError):
            await authorise(COMPLIANCE, "approval:read", res)
