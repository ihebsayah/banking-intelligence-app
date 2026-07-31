"""Comment service tests (CM1-CM3) plus the shared entity-access helpers."""
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.authorise import ApplicationUser, Resource

from workbench.exceptions import (
    IdempotencyMismatch, ResourceNotFound, VersionConflict, WorkbenchError,
)
from workbench.models import (
    ComplianceCase, Comment, InformationRequest, Investigation,
)
from workbench.schemas.comments import (
    CommentMetadataView, CommentMutationResponse, CommentResponse,
    CreateCommentRequest, RedactCommentRequest,
)
from workbench.services.comment_service import CommentService
from workbench.services.entity_access import (
    ParentContext, assert_entity_readable, fetch_parent, resolve_entity_type,
)

UID = lambda: str(uuid.uuid4())
NOW = datetime.now(timezone.utc)

ANALYST = ApplicationUser(user_id="user1", role="analyst", permissions=[
    "comment:read", "comment:create", "alert:read_assigned",
])
COMPLIANCE = ApplicationUser(user_id="comp1", role="compliance", permissions=[
    "comment:read", "comment:create", "comment:view_internal_content",
    "case:read_assigned", "case:read",
])
ADMIN = ApplicationUser(user_id="admin1", role="admin", permissions=[
    "comment:read", "comment:redact", "comment:view_metadata",
])

UOW_TARGET = "workbench.services.comment_service.UnitOfWork"
AUTH_TARGET = "workbench.services.comment_service.authorise"
FETCH_PARENT_TARGET = "workbench.services.comment_service.fetch_parent"
ASSERT_READABLE_TARGET = "workbench.services.comment_service.assert_entity_readable"

HASH = lambda body: __import__("hashlib").sha256(
    json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def make_comment(**kw):
    defaults = dict(comment_id=UID(), entity_type="investigation", entity_id="inv1",
                    content="Need more transaction data", author_id="user1",
                    is_internal=False, is_redacted=False, redacted_at=None,
                    redacted_by=None, original_content_hash=None,
                    redaction_reason=None, version=1,
                    created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Comment(**defaults)


def make_parent(entity_type="investigation", status="active"):
    return ParentContext(
        entity=MagicMock(),
        resource=Resource(id="inv1", status=status, assigned_to="user1",
                          scope_id="hq_main", version=1, entity_type=entity_type),
    )


def make_uow_mock():
    uow = MagicMock()
    uow.conn = MagicMock()
    uow_mock = MagicMock()
    uow_mock.__aenter__ = AsyncMock(return_value=uow)
    uow_mock.__aexit__ = AsyncMock(return_value=None)
    return uow_mock


class TestEntityAccess:
    @pytest.mark.asyncio
    async def test_resolve_entity_type_mapping(self):
        assert resolve_entity_type("alerts") == "alert"
        assert resolve_entity_type("investigations") == "investigation"
        assert resolve_entity_type("cases") == "compliance_case"
        assert resolve_entity_type("information-requests") == "information_request"

    @pytest.mark.asyncio
    async def test_resolve_entity_type_invalid(self):
        with pytest.raises(WorkbenchError) as ei:
            resolve_entity_type("decisions")
        assert ei.value.code == "INVALID_ENTITY_TYPE"
        assert ei.value.http_status == 400

    @pytest.mark.asyncio
    async def test_fetch_parent_case(self, mock_db):
        case = ComplianceCase(case_id="case1", title="T", created_by="comp1",
                              scope_id="hq_main", status="open", version=1)
        with patch("workbench.repos.CaseRepo.fetch_by_id",
                   AsyncMock(return_value=case)):
            parent = await fetch_parent(mock_db, "compliance_case", "case1")
        assert parent.resource.entity_type == "compliance_case"
        assert parent.resource.scope_id == "hq_main"
        assert parent.resource.status == "open"

    @pytest.mark.asyncio
    async def test_fetch_parent_information_request_uses_case_scope(self, mock_db):
        ir = InformationRequest(ir_id="ir1", case_id="case1", created_by="comp1",
                                assigned_to="analyst1", question="Q", status="open",
                                version=1)
        case = ComplianceCase(case_id="case1", title="T", created_by="comp1",
                              scope_id="branch_x", status="open", version=1)
        with patch("workbench.repos.InfoRequestRepo.fetch_by_id",
                   AsyncMock(return_value=ir)), \
             patch("workbench.repos.CaseRepo.fetch_by_id",
                   AsyncMock(return_value=case)):
            parent = await fetch_parent(mock_db, "information_request", "ir1")
        assert parent.resource.scope_id == "branch_x"
        assert parent.resource.entity_type == "information_request"

    @pytest.mark.asyncio
    async def test_fetch_parent_not_found(self, mock_db):
        with patch("workbench.repos.InvestigationRepo.fetch_by_id",
                   AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await fetch_parent(mock_db, "investigation", "ghost")

    @pytest.mark.asyncio
    async def test_assert_readable_assigned_path(self, mock_db):
        parent = make_parent()
        with patch("workbench.services.entity_access.authorise", AsyncMock()) as auth:
            await assert_entity_readable(ANALYST, parent, mock_db)
        assert auth.await_count == 1

    @pytest.mark.asyncio
    async def test_assert_readable_falls_back_to_broad(self, mock_db):
        parent = make_parent(entity_type="compliance_case")
        from shared.authorise import OwnershipDeniedError
        side_effects = [OwnershipDeniedError()]

        async def fake_authorise(user, action, resource, db=None, request_context=None):
            if side_effects:
                raise side_effects.pop(0)

        with patch("workbench.services.entity_access.authorise", fake_authorise):
            await assert_entity_readable(COMPLIANCE, parent, mock_db)

    @pytest.mark.asyncio
    async def test_assert_readable_404_on_total_denial(self, mock_db):
        parent = make_parent()
        from shared.authorise import (
            OwnershipDeniedError, PermissionDeniedError,
        )
        calls = {"n": 0}

        async def fake_authorise(user, action, resource, db=None, request_context=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise OwnershipDeniedError()
            raise PermissionDeniedError(action)

        with patch("workbench.services.entity_access.authorise", fake_authorise):
            with pytest.raises(ResourceNotFound):
                await assert_entity_readable(ANALYST, parent, mock_db)


class TestList:
    @pytest.mark.asyncio
    async def test_analyst_excludes_internal_comments(self, mock_db):
        public = make_comment()
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.list_for_entity",
                   AsyncMock(return_value=[public])), \
             patch("workbench.repos.CommentRepo.count_for_entity",
                   AsyncMock(return_value=1)):
            items, total = await CommentService(mock_db).list_for_entity(
                ANALYST, "investigations", "inv1", 1, 50)
        assert len(items) == 1
        assert isinstance(items[0], CommentResponse)
        assert total == 1

    @pytest.mark.asyncio
    async def test_analyst_filters_internal_at_repo_level(self, mock_db):
        mock_list = AsyncMock(return_value=[])
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.list_for_entity", mock_list), \
             patch("workbench.repos.CommentRepo.count_for_entity", AsyncMock(return_value=0)):
            await CommentService(mock_db).list_for_entity(ANALYST, "investigations", "inv1")
        assert mock_list.await_args.kwargs["include_internal"] is False

    @pytest.mark.asyncio
    async def test_compliance_sees_internal_content(self, mock_db):
        internal = make_comment(is_internal=True)
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.list_for_entity",
                   AsyncMock(return_value=[internal])), \
             patch("workbench.repos.CommentRepo.count_for_entity",
                   AsyncMock(return_value=1)):
            items, total = await CommentService(mock_db).list_for_entity(
                COMPLIANCE, "investigations", "inv1")
        assert isinstance(items[0], CommentResponse)
        assert items[0].content == internal.content
        assert total == 1

    @pytest.mark.asyncio
    async def test_admin_gets_metadata_view_for_internal(self, mock_db):
        internal = make_comment(is_internal=True)
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.list_for_entity",
                   AsyncMock(return_value=[internal])), \
             patch("workbench.repos.CommentRepo.count_for_entity",
                   AsyncMock(return_value=1)):
            items, total = await CommentService(mock_db).list_for_entity(
                ADMIN, "investigations", "inv1")
        assert isinstance(items[0], CommentMetadataView)
        assert not hasattr(items[0], "content")
        assert total == 1

    @pytest.mark.asyncio
    async def test_admin_full_view_for_public(self, mock_db):
        public = make_comment()
        with patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.list_for_entity",
                   AsyncMock(return_value=[public])), \
             patch("workbench.repos.CommentRepo.count_for_entity",
                   AsyncMock(return_value=1)):
            items, _ = await CommentService(mock_db).list_for_entity(
                ADMIN, "investigations", "inv1")
        assert isinstance(items[0], CommentResponse)

    @pytest.mark.asyncio
    async def test_invalid_entity_type(self, mock_db):
        with pytest.raises(WorkbenchError) as ei:
            await CommentService(mock_db).list_for_entity(
                ANALYST, "decisions", "x")
        assert ei.value.http_status == 400

    @pytest.mark.asyncio
    async def test_entity_not_found(self, mock_db):
        from shared.authorise import PermissionDeniedError

        async def fake_authorise(user, action, resource, db=None, request_context=None):
            raise PermissionDeniedError(action)

        with patch(FETCH_PARENT_TARGET,
                   AsyncMock(side_effect=ResourceNotFound("investigation", "ghost"))):
            with pytest.raises(ResourceNotFound):
                await CommentService(mock_db).list_for_entity(
                    ANALYST, "investigations", "ghost")


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_public_comment(self, mock_db):
        req = CreateCommentRequest(content="Looks suspicious", is_internal=False)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 0 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await CommentService(mock_db).create(
                ANALYST, "investigations", "inv1", req)
        assert result.comment.content == "Looks suspicious"
        assert result.comment.author_id == "user1"
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_create_internal_comment(self, mock_db):
        req = CreateCommentRequest(content="Internal note", is_internal=True)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 0 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await CommentService(mock_db).create(
                COMPLIANCE, "investigations", "inv1", req)
        assert result.comment.is_internal is True

    @pytest.mark.asyncio
    async def test_create_authorises_comment_create(self, mock_db):
        req = CreateCommentRequest(content="Note", is_internal=False)
        uow_mock = make_uow_mock()
        auth = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, auth), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 0 1")), \
             patch("workbench.repos.TimelineRepo.insert", AsyncMock()), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            await CommentService(mock_db).create(ANALYST, "investigations", "inv1", req)
        actions = [a.args[1] for a in auth.await_args_list]
        assert "comment:create" in actions

    @pytest.mark.asyncio
    async def test_create_writes_timeline_and_outbox(self, mock_db):
        req = CreateCommentRequest(content="Note", is_internal=False)
        uow_mock = make_uow_mock()
        mock_timeline = AsyncMock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(ASSERT_READABLE_TARGET, AsyncMock()), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._execute", AsyncMock(return_value="INSERT 0 1")), \
             patch("workbench.repos.TimelineRepo.insert", mock_timeline), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await CommentService(mock_db).create(ANALYST, "investigations", "inv1", req)
        assert mock_timeline.await_count == 1
        assert mock_timeline.await_args.args[0].event_type == "comment.created"
        assert mock_outbox.await_count == 1
        assert mock_outbox.await_args.args[0].event_type == "comment.created"

    @pytest.mark.asyncio
    async def test_create_invalid_entity_type(self, mock_db):
        req = CreateCommentRequest(content="Note")
        with pytest.raises(WorkbenchError) as ei:
            await CommentService(mock_db).create(ANALYST, "bad", "x", req)
        assert ei.value.http_status == 400

    @pytest.mark.asyncio
    async def test_create_entity_not_found(self, mock_db):
        req = CreateCommentRequest(content="Note")
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch(FETCH_PARENT_TARGET,
                   AsyncMock(side_effect=ResourceNotFound("alert", "ghost"))):
            with pytest.raises(ResourceNotFound):
                await CommentService(mock_db).create(ANALYST, "alerts", "ghost", req)

    @pytest.mark.asyncio
    async def test_create_idempotent_replay(self, mock_db):
        req = CreateCommentRequest(content="Note", is_internal=False)
        uow_mock = make_uow_mock()
        resp = CommentMutationResponse(
            comment=CommentResponse(**make_comment().model_dump()), version=1)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=MagicMock(
                       request_body_sha256=HASH(req.model_dump()),
                       response_status=201, response_body=resp.model_dump_json()))):
            result = await CommentService(mock_db).create(
                ANALYST, "investigations", "inv1", req, idempotency_key="key1")
        assert result.version == 1

    @pytest.mark.asyncio
    async def test_create_idempotency_mismatch(self, mock_db):
        req = CreateCommentRequest(content="Note", is_internal=False)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos.IdempotencyRepo.lookup",
                   AsyncMock(return_value=MagicMock(
                       request_body_sha256="deadbeef"))):
            with pytest.raises(IdempotencyMismatch):
                await CommentService(mock_db).create(
                    ANALYST, "investigations", "inv1", req, idempotency_key="key1")


class TestRedact:
    @pytest.mark.asyncio
    async def test_redact_replaces_content(self, mock_db):
        c = make_comment(content="Sensitive finding")
        req = RedactCommentRequest(redact_reason="Privacy breach", expected_version=1)
        uow_mock = make_uow_mock()
        mock_update = AsyncMock(side_effect=lambda c, v, conn=None: c)
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.update", mock_update), \
             patch("workbench.repos.OutboxRepo.insert", AsyncMock()):
            result = await CommentService(mock_db).redact(ADMIN, c.comment_id, req)
        assert result.comment.content == "[REDACTED — Privacy breach]"
        assert result.comment.is_redacted is True
        assert result.comment.redacted_by == "admin1"
        assert result.comment.redaction_reason == "Privacy breach"
        assert result.version == 2
        stored = mock_update.await_args.args[0]
        assert stored.original_content_hash == HASH("Sensitive finding")

    @pytest.mark.asyncio
    async def test_redact_emits_audit_event(self, mock_db):
        c = make_comment()
        req = RedactCommentRequest(redact_reason="Privacy breach", expected_version=1)
        uow_mock = make_uow_mock()
        mock_outbox = AsyncMock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos._execute", AsyncMock(return_value="UPDATE 1")), \
             patch("workbench.repos.OutboxRepo.insert", mock_outbox):
            await CommentService(mock_db).redact(ADMIN, c.comment_id, req)
        assert mock_outbox.await_args.args[0].event_type == "comment.redacted"

    @pytest.mark.asyncio
    async def test_redact_not_found(self, mock_db):
        req = RedactCommentRequest(redact_reason="Reason", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            with pytest.raises(ResourceNotFound):
                await CommentService(mock_db).redact(ADMIN, "ghost", req)

    @pytest.mark.asyncio
    async def test_redact_stale_version(self, mock_db):
        c = make_comment()
        req = RedactCommentRequest(redact_reason="Reason", expected_version=1)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(AUTH_TARGET, AsyncMock()), \
             patch("workbench.repos.CommentRepo.update", AsyncMock(return_value=None)):
            with pytest.raises(VersionConflict):
                await CommentService(mock_db).redact(ADMIN, c.comment_id, req)

    @pytest.mark.asyncio
    async def test_redact_already_redacted_is_idempotent(self, mock_db):
        c = make_comment(is_redacted=True, content="[REDACTED — old]",
                         redacted_by="admin1", version=3)
        req = RedactCommentRequest(redact_reason="New reason", expected_version=3)
        uow_mock = make_uow_mock()
        with patch(UOW_TARGET, return_value=uow_mock), \
             patch("workbench.repos._fetch_one", AsyncMock(return_value=c.model_dump())), \
             patch(FETCH_PARENT_TARGET, AsyncMock(return_value=make_parent())), \
             patch(AUTH_TARGET, AsyncMock()):
            result = await CommentService(mock_db).redact(ADMIN, c.comment_id, req)
        assert result.version == 3


class TestRouteRegistration:
    def test_exact_count_three(self):
        from workbench.routers.comments import router
        routes = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
        assert ("/api/v1/{entity_type}/{entity_id}/comments", ("GET",)) in routes
        assert ("/api/v1/{entity_type}/{entity_id}/comments", ("POST",)) in routes
        assert ("/api/v1/comments/{comment_id}/redact", ("PATCH",)) in routes
        assert len(router.routes) == 3
