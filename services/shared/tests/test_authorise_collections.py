"""Authorisation policy tests for collection/list reads (L1-L4).

The four assigned-list endpoints (alerts, investigations, cases, information
requests) authorise a synthetic collection resource (entity_type="collection",
status="active") so the read passes the workflow gate without a real entity
instance. These tests exercise the real authorise() engine directly.

Regression guards:
- all four list/read actions are permitted on the collection resource;
- instance mutations with an empty status still fail (workflow/ownership);
- the collection map admits only the four list/read actions.
"""
import pytest

from shared.authorise import (
    ActionUnknownError, ApplicationUser, OwnershipDeniedError,
    PermissionDeniedError, Resource, ScopeDeniedError, WorkflowStateError,
    authorise,
)

ANALYST = ApplicationUser(user_id="analyst1", role="analyst", permissions=[
    "alert:read_assigned", "investigation:read_own",
    "case:read_assigned", "info_request:read_assigned",
    "alert:acknowledge", "alert:transition", "case:reopen",
    "timeline:read", "info_request:read", "info_request:create",
], scopes=["hq_main"])
NO_PERM = ApplicationUser(user_id="analyst2", role="analyst", permissions=[
    "workbench:access",
], scopes=["hq_main"])
MANAGER = ApplicationUser(user_id="manager1", role="manager", permissions=[
    "workbench:access",
], scopes=["hq_main"])

LIST_ACTIONS = [
    "alert:read_assigned", "investigation:read_own",
    "case:read_assigned", "info_request:read_assigned",
]


def collection_resource(scope_id=None):
    return Resource(id="assigned", status="active", entity_type="collection",
                    scope_id=scope_id)


def empty_status_instance(entity_type="alert", **kw):
    return Resource(id="", status="", entity_type=entity_type, **kw)


class TestCollectionReads:
    @pytest.mark.asyncio
    async def test_all_four_list_actions_allowed(self):
        for action in LIST_ACTIONS:
            await authorise(ANALYST, action, collection_resource())

    @pytest.mark.asyncio
    async def test_missing_permission_denied(self):
        for action in LIST_ACTIONS:
            with pytest.raises(PermissionDeniedError):
                await authorise(NO_PERM, action, collection_resource())

    @pytest.mark.asyncio
    async def test_manager_without_permission_denied(self):
        for action in LIST_ACTIONS:
            with pytest.raises(PermissionDeniedError):
                await authorise(MANAGER, action, collection_resource())

    @pytest.mark.asyncio
    async def test_scope_still_applies(self):
        res = collection_resource(scope_id="eu_main")
        with pytest.raises(ScopeDeniedError):
            await authorise(ANALYST, "alert:read_assigned", res)

    @pytest.mark.asyncio
    async def test_unknown_action_fails(self):
        with pytest.raises(ActionUnknownError):
            await authorise(ANALYST, "bogus:action", collection_resource())


class TestCollectionMapIsNarrow:
    @pytest.mark.asyncio
    async def test_non_list_action_rejected(self):
        with pytest.raises(WorkflowStateError):
            await authorise(ANALYST, "timeline:read", collection_resource())

    @pytest.mark.asyncio
    async def test_other_read_action_rejected(self):
        with pytest.raises(WorkflowStateError):
            await authorise(ANALYST, "info_request:read", collection_resource())

    @pytest.mark.asyncio
    async def test_workflow_mutation_rejected(self):
        with pytest.raises(WorkflowStateError):
            await authorise(ANALYST, "case:reopen", collection_resource())


class TestMutationsStillStateGated:
    @pytest.mark.asyncio
    async def test_workflow_gated_mutation_with_empty_status(self):
        with pytest.raises(WorkflowStateError):
            await authorise(ANALYST, "alert:transition",
                            empty_status_instance(entity_type="alert"))

    @pytest.mark.asyncio
    async def test_ownership_gated_mutation_with_empty_status(self):
        with pytest.raises(OwnershipDeniedError):
            await authorise(ANALYST, "alert:acknowledge",
                            empty_status_instance(entity_type="alert"))

    @pytest.mark.asyncio
    async def test_instance_read_still_requires_real_status(self):
        with pytest.raises(WorkflowStateError):
            await authorise(ANALYST, "info_request:read_assigned",
                            empty_status_instance(entity_type="information_request"))
