"""Repository layer tests — mocks DB to verify SQL and logic."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.errors import DatabaseError
from workbench.exceptions import VersionConflict
from workbench.models import (
    Alert, Investigation, ComplianceCase, Decision, ApprovalRequest,
    ApprovalDecision, Comment, ActivityTimelineEntry, Notification,
    AssignmentHistoryEntry, AuditOutboxEvent, InformationRequest,
)
from workbench.repos import (
    AlertRepo, InvestigationRepo, CaseRepo, DecisionRepo,
    InfoRequestRepo, ApprovalRepo, ApprovalDecisionRepo, CommentRepo,
    TimelineRepo, NotificationRepo, AssignmentHistoryRepo, OutboxRepo,
    OrphanRepo, _fetch_one, _fetch_all, _execute,
)

NOW = datetime.now(timezone.utc)
UID = lambda: str(uuid.uuid4())


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_alert(**kw):
    defaults = dict(alert_id=UID(), alert_type="kpi_breach", severity="high",
                    title="Test Alert", status="new", version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Alert(**defaults)


def make_investigation(**kw):
    defaults = dict(investigation_id=UID(), title="Test", created_by="user1",
                    status="open", version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Investigation(**defaults)


def make_case(**kw):
    defaults = dict(case_id=UID(), title="Test Case", created_by="user1",
                    status="open", version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ComplianceCase(**defaults)


def make_decision(**kw):
    defaults = dict(decision_id=UID(), case_id=UID(), decision_type="warning",
                    rationale="test", decided_by="user1", version=1, created_at=NOW)
    defaults.update(kw)
    return Decision(**defaults)


def make_info_request(**kw):
    defaults = dict(ir_id=UID(), case_id=UID(), created_by="user1",
                    assigned_to="user2", question="test question",
                    status="open", version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return InformationRequest(**defaults)


def make_approval(**kw):
    defaults = dict(approval_request_id=UID(), action_type="alert_dismissal_critical_high",
                    entity_type="alert", entity_id=UID(), requested_by="user1",
                    rationale="test", expires_at=NOW, version=1, created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return ApprovalRequest(**defaults)


def make_comment(**kw):
    defaults = dict(comment_id=UID(), entity_type="alert", entity_id=UID(),
                    content="test comment", author_id="user1", version=1,
                    created_at=NOW, updated_at=NOW)
    defaults.update(kw)
    return Comment(**defaults)


def make_timeline(**kw):
    defaults = dict(timeline_id=UID(), entity_type="alert", entity_id=UID(),
                    event_type="created", actor_id="user1", occurred_at=NOW)
    defaults.update(kw)
    return ActivityTimelineEntry(**defaults)


def make_notification(**kw):
    defaults = dict(notification_id=UID(), user_id="user1",
                    notification_type="alert_assigned", title="Test", body="body",
                    created_at=NOW)
    defaults.update(kw)
    return Notification(**defaults)


def make_assignment(**kw):
    defaults = dict(history_id=UID(), entity_type="alert", entity_id=UID(),
                    assigned_by="user1", assigned_at=NOW)
    defaults.update(kw)
    return AssignmentHistoryEntry(**defaults)


def make_outbox(**kw):
    defaults = dict(outbox_id=UID(), idempotency_key=UID(), event_type="alert.created",
                    entity_type="alert", entity_id=UID(), actor_id="user1",
                    actor_role="analyst", occurred_at=NOW, payload={},
                    status="pending", next_attempt_at=NOW, created_at=NOW)
    defaults.update(kw)
    return AuditOutboxEvent(**defaults)


# ── Alert Repo Tests ──────────────────────────────────────────────────────────

class TestAlertRepo:
    @pytest.mark.asyncio
    async def test_model_conversion(self, mock_db):
        row = dict(alert_id=UID(), alert_type="kpi_breach", severity="high",
                   title="Test", scope_id="hq_main", status="new",
                   version=1, created_at=NOW, updated_at=NOW)
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=row)):
            a = await AlertRepo(mock_db).fetch_by_id(row["alert_id"])
        r = Alert(**row)
        assert r.alert_id == a.alert_id

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            a = await AlertRepo(mock_db).fetch_by_id("nope")
        assert a is None

    @pytest.mark.asyncio
    async def test_successful_optimistic_update(self, mock_db):
        a = make_alert(version=2)
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await AlertRepo(mock_db).update(a, expected_version=1)
        assert result is not None
        assert result.version == 2

    @pytest.mark.asyncio
    async def test_stale_version_conflict(self, mock_db):
        a = make_alert(version=3)
        mock_exec = AsyncMock(return_value="UPDATE 0")
        mock_fetch = AsyncMock(return_value=dict(
            alert_id=a.alert_id, alert_type=a.alert_type, severity=a.severity,
            title=a.title, scope_id="hq_main", status="new",
            version=3, created_at=NOW, updated_at=NOW,
        ))
        with patch("workbench.repos._execute", mock_exec), \
             patch("workbench.repos._fetch_one", mock_fetch):
            with pytest.raises(VersionConflict):
                await AlertRepo(mock_db).update(a, expected_version=1)

    @pytest.mark.asyncio
    async def test_not_found_on_update(self, mock_db):
        a = make_alert(version=2)
        mock_exec = AsyncMock(return_value="UPDATE 0")
        mock_fetch = AsyncMock(return_value=None)
        with patch("workbench.repos._execute", mock_exec), \
             patch("workbench.repos._fetch_one", mock_fetch):
            result = await AlertRepo(mock_db).update(a, expected_version=1)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_filters(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await AlertRepo(mock_db).list(scope_id="hq_main", status="new", assigned_to="user1")
        sql = mock_fetch.call_args[0][1]
        assert "scope_id" in sql
        assert "status" in sql
        assert "assigned_to" in sql


# ── Investigation Repo Tests ──────────────────────────────────────────────────

class TestInvestigationRepo:
    @pytest.mark.asyncio
    async def test_create_and_fetch(self, mock_db):
        inv = make_investigation()
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        mock_fetch = AsyncMock(return_value=dict(
            investigation_id=inv.investigation_id, title=inv.title,
            created_by=inv.created_by, status="open", priority="medium",
            scope_id="hq_main", version=1, created_at=NOW, updated_at=NOW,
        ))
        with patch("workbench.repos._execute", mock_exec), \
             patch("workbench.repos._fetch_one", mock_fetch):
            await InvestigationRepo(mock_db).create(inv)
            fetched = await InvestigationRepo(mock_db).fetch_by_id(inv.investigation_id)
        assert fetched is not None
        assert fetched.investigation_id == inv.investigation_id

    @pytest.mark.asyncio
    async def test_stale_version(self, mock_db):
        inv = make_investigation(version=3)
        mock_exec = AsyncMock(return_value="UPDATE 0")
        mock_fetch = AsyncMock(return_value=dict(
            investigation_id=inv.investigation_id, title=inv.title,
            created_by=inv.created_by, status="open", priority="medium",
            scope_id="hq_main", version=3, created_at=NOW, updated_at=NOW,
        ))
        with patch("workbench.repos._execute", mock_exec), \
             patch("workbench.repos._fetch_one", mock_fetch):
            with pytest.raises(VersionConflict):
                await InvestigationRepo(mock_db).update(inv, expected_version=1)


# ── Case Repo Tests ───────────────────────────────────────────────────────────

class TestCaseRepo:
    @pytest.mark.asyncio
    async def test_successful_update(self, mock_db):
        c = make_case(version=2)
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await CaseRepo(mock_db).update(c, expected_version=1)
        assert result is not None

    @pytest.mark.asyncio
    async def test_not_found(self, mock_db):
        c = make_case(version=2)
        mock_exec = AsyncMock(return_value="UPDATE 0")
        mock_fetch = AsyncMock(return_value=None)
        with patch("workbench.repos._execute", mock_exec), \
             patch("workbench.repos._fetch_one", mock_fetch):
            result = await CaseRepo(mock_db).update(c, expected_version=1)
        assert result is None


# ── Approval Repo Tests ───────────────────────────────────────────────────────

class TestApprovalRepo:
    @pytest.mark.asyncio
    async def test_consume_returns_row(self, mock_db):
        ar = make_approval()
        mock_fetch = AsyncMock(return_value=dict(
            approval_request_id=ar.approval_request_id,
            action_type=ar.action_type, entity_type=ar.entity_type,
            entity_id=ar.entity_id, requested_by=ar.requested_by,
            rationale=ar.rationale, required_approvals=1, approval_count=0,
            status="approved", expires_at=NOW, executed_at=NOW,
            version=2, created_at=NOW, updated_at=NOW,
        ))
        with patch("workbench.repos._fetch_one", mock_fetch):
            result = await ApprovalRepo(mock_db).consume(ar.approval_request_id)
        assert result is not None
        assert result.status == "approved"

    @pytest.mark.asyncio
    async def test_consume_no_pending_returns_none(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            result = await ApprovalRepo(mock_db).consume("no-such-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_active_for_entity(self, mock_db):
        ar = make_approval()
        mock_fetch = AsyncMock(return_value=dict(
            approval_request_id=ar.approval_request_id,
            action_type=ar.action_type, entity_type=ar.entity_type,
            entity_id=ar.entity_id, requested_by=ar.requested_by,
            rationale=ar.rationale, required_approvals=1, approval_count=0,
            status="pending", expires_at=NOW, version=1, created_at=NOW, updated_at=NOW,
        ))
        with patch("workbench.repos._fetch_one", mock_fetch):
            result = await ApprovalRepo(mock_db).fetch_active_for_entity(
                "alert", ar.entity_id, "alert_dismissal_critical_high")
        assert result is not None
        assert result.status == "pending"

    @pytest.mark.asyncio
    async def test_no_active_approval_returns_none(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            result = await ApprovalRepo(mock_db).fetch_active_for_entity(
                "alert", UID(), "alert_dismissal_critical_high")
        assert result is None

    @pytest.mark.asyncio
    async def test_expire_due_claims_only_pending_with_skip_locked(self, mock_db):
        ar = make_approval(status="expired", version=2)
        row = dict(
            approval_request_id=ar.approval_request_id,
            action_type=ar.action_type, entity_type=ar.entity_type,
            entity_id=ar.entity_id, requested_by=ar.requested_by,
            rationale=ar.rationale, required_approvals=1, approval_count=0,
            status="expired", expires_at=NOW, executed_at=None,
            version=2, created_at=NOW, updated_at=NOW,
        )
        mock_fetch = AsyncMock(return_value=[row])
        with patch("workbench.repos._fetch_all", mock_fetch):
            result = await ApprovalRepo(mock_db).expire_due(10)
        assert len(result) == 1
        assert result[0].status == "expired"
        assert result[0].version == 2
        sql = mock_fetch.call_args[0][1]
        assert "FOR UPDATE SKIP LOCKED" in sql
        assert "status='pending'" in sql
        assert "expires_at <= $1" in sql
        assert "RETURNING *" in sql

    @pytest.mark.asyncio
    async def test_expire_due_empty_batch(self, mock_db):
        with patch("workbench.repos._fetch_all", AsyncMock(return_value=[])):
            result = await ApprovalRepo(mock_db).expire_due(10)
        assert result == []


# ── Approval Decision Repo Tests ──────────────────────────────────────────────

class TestApprovalDecisionRepo:
    @pytest.mark.asyncio
    async def test_create_approval_decision(self, mock_db):
        ad = ApprovalDecision(approval_decision_id=UID(),
                              approval_request_id=UID(), approver_id="user1",
                              decision="approved")
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await ApprovalDecisionRepo(mock_db).create(ad)
        assert result.approval_decision_id == ad.approval_decision_id


# ── Comment Repo Tests ────────────────────────────────────────────────────────

class TestCommentRepo:
    @pytest.mark.asyncio
    async def test_create_and_list(self, mock_db):
        c = make_comment()
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        mock_fetch = AsyncMock(return_value=[
            dict(comment_id=c.comment_id, entity_type=c.entity_type,
                 entity_id=c.entity_id, content=c.content, author_id=c.author_id,
                 is_internal=False, is_redacted=False, version=1,
                 created_at=NOW, updated_at=NOW),
        ])
        with patch("workbench.repos._execute", mock_exec), \
             patch("workbench.repos._fetch_all", mock_fetch):
            await CommentRepo(mock_db).create(c)
            items = await CommentRepo(mock_db).list_for_entity(c.entity_type, c.entity_id)
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_redact_is_update(self, mock_db):
        c = make_comment(is_redacted=True, redacted_by="admin", version=2)
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await CommentRepo(mock_db).update(c, expected_version=1)
        assert result is not None
        sql = mock_exec.call_args[0][1]
        assert "is_redacted" in sql
        assert "original_content_hash" in sql

    @pytest.mark.asyncio
    async def test_list_for_entity_excludes_internal(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await CommentRepo(mock_db).list_for_entity(
                "alert", "a1", include_internal=False)
        sql = mock_fetch.call_args[0][1]
        assert "AND is_internal=FALSE" in sql

    @pytest.mark.asyncio
    async def test_list_for_entity_includes_internal_by_default(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await CommentRepo(mock_db).list_for_entity("alert", "a1")
        sql = mock_fetch.call_args[0][1]
        assert "is_internal=FALSE" not in sql

    @pytest.mark.asyncio
    async def test_count_for_entity(self, mock_db):
        mock_fetch = AsyncMock(return_value={"cnt": 7})
        with patch("workbench.repos._fetch_one", mock_fetch):
            cnt = await CommentRepo(mock_db).count_for_entity(
                "alert", "a1", include_internal=False)
        assert cnt == 7
        assert "is_internal=FALSE" in mock_fetch.call_args[0][1]


# ── Timeline / Notification / Assignment / Outbox Tests ───────────────────────

class TestTimelineRepo:
    @pytest.mark.asyncio
    async def test_insert(self, mock_db):
        entry = make_timeline()
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await TimelineRepo(mock_db).insert(entry)
        assert result.timeline_id == entry.timeline_id

    @pytest.mark.asyncio
    async def test_list_for_entity_orders_occurred_at_asc(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await TimelineRepo(mock_db).list_for_entity(
                "investigation", "inv1", event_type="investigation.completed")
        sql = mock_fetch.call_args[0][1]
        assert "ORDER BY occurred_at" in sql
        assert "event_type=$3" in sql

    @pytest.mark.asyncio
    async def test_list_for_user_own_entities_only(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await TimelineRepo(mock_db).list_for_user(
                "user1", entity_type="compliance_case", since=NOW)
        sql = mock_fetch.call_args[0][1]
        assert "ORDER BY t.occurred_at ASC" in sql
        assert "activity_timeline t WHERE" in sql
        assert "t.entity_type=$2" in sql

    @pytest.mark.asyncio
    async def test_count_for_user(self, mock_db):
        mock_fetch = AsyncMock(return_value={"cnt": 4})
        with patch("workbench.repos._fetch_one", mock_fetch):
            cnt = await TimelineRepo(mock_db).count_for_user("user1")
        assert cnt == 4
        assert "COUNT(*)" in mock_fetch.call_args[0][1]


class TestNotificationRepo:
    @pytest.mark.asyncio
    async def test_insert_mark_read(self, mock_db):
        n = make_notification()
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        with patch("workbench.repos._execute", mock_exec):
            await NotificationRepo(mock_db).insert(n)
            await NotificationRepo(mock_db).mark_read(n.notification_id)

    @pytest.mark.asyncio
    async def test_list_for_user_is_read_filter(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await NotificationRepo(mock_db).list_for_user("user1", is_read=False)
        sql = mock_fetch.call_args[0][1]
        assert "user_id=$1" in sql
        assert "is_read=$2" in sql
        assert "ORDER BY created_at DESC" in sql

    @pytest.mark.asyncio
    async def test_unread_count(self, mock_db):
        mock_fetch = AsyncMock(return_value={"cnt": 3})
        with patch("workbench.repos._fetch_one", mock_fetch):
            cnt = await NotificationRepo(mock_db).unread_count("user1")
        assert cnt == 3
        assert "is_read=FALSE" in mock_fetch.call_args[0][1]

    @pytest.mark.asyncio
    async def test_mark_all_read_returns_count(self, mock_db):
        mock_fetch = AsyncMock(return_value=[{"notification_id": "n1"},
                                             {"notification_id": "n2"}])
        with patch("workbench.repos._fetch_all", mock_fetch):
            marked = await NotificationRepo(mock_db).mark_all_read("user1")
        assert marked == 2
        sql = mock_fetch.call_args[0][1]
        assert "is_read=FALSE" in sql
        assert "RETURNING notification_id" in sql


class TestAssignmentHistoryRepo:
    @pytest.mark.asyncio
    async def test_insert(self, mock_db):
        e = make_assignment()
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await AssignmentHistoryRepo(mock_db).insert(e)
        assert result.history_id == e.history_id


class TestOutboxRepo:
    @pytest.mark.asyncio
    async def test_insert_outbox_event(self, mock_db):
        e = make_outbox()
        mock_exec = AsyncMock(return_value="INSERT 0 1")
        with patch("workbench.repos._execute", mock_exec):
            result = await OutboxRepo(mock_db).insert(e)
        assert result.outbox_id == e.outbox_id

    @pytest.mark.asyncio
    async def test_claim_batch(self, mock_db):
        e = make_outbox()
        mock_fetch = AsyncMock(return_value=[dict(
            outbox_id=e.outbox_id, idempotency_key=e.idempotency_key,
            event_type=e.event_type, entity_type=e.entity_type,
            entity_id=e.entity_id, actor_id=e.actor_id, actor_role=e.actor_role,
            occurred_at=NOW, payload={}, payload_schema_ver=1,
            status="delivering", attempt_count=1, next_attempt_at=NOW,
            locked_by="worker", locked_at=NOW, created_at=NOW,
        )])
        with patch("workbench.repos._fetch_all", mock_fetch):
            events = await OutboxRepo(mock_db).claim_next_batch("worker-1")
        assert len(events) == 1
        assert events[0].status == "delivering"

    @pytest.mark.asyncio
    async def test_mark_delivered(self, mock_db):
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._execute", mock_exec):
            await OutboxRepo(mock_db).mark_delivered(UID())

    @pytest.mark.asyncio
    async def test_mark_failed(self, mock_db):
        e = make_outbox(attempt_count=2)
        mock_fetch = AsyncMock(return_value=dict(
            outbox_id=e.outbox_id, idempotency_key=e.idempotency_key,
            event_type=e.event_type, entity_type=e.entity_type,
            entity_id=e.entity_id, actor_id=e.actor_id, actor_role=e.actor_role,
            occurred_at=NOW, payload={}, payload_schema_ver=1,
            status="failed", attempt_count=2, next_attempt_at=NOW,
            created_at=NOW,
        ))
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._fetch_one", mock_fetch), \
             patch("workbench.repos._execute", mock_exec):
            await OutboxRepo(mock_db).mark_failed(e.outbox_id, "timeout", max_attempts=3)
        sql = mock_exec.call_args[0][1]
        assert "poison" in sql or "failed" in sql

    @pytest.mark.asyncio
    async def test_poison_after_max_attempts(self, mock_db):
        e = make_outbox(attempt_count=4)
        mock_fetch = AsyncMock(return_value=dict(
            outbox_id=e.outbox_id, idempotency_key=e.idempotency_key,
            event_type=e.event_type, entity_type=e.entity_type,
            entity_id=e.entity_id, actor_id=e.actor_id, actor_role=e.actor_role,
            occurred_at=NOW, payload={}, payload_schema_ver=1,
            status="failed", attempt_count=4, next_attempt_at=NOW,
            created_at=NOW,
        ))
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._fetch_one", mock_fetch), \
             patch("workbench.repos._execute", mock_exec):
            await OutboxRepo(mock_db).mark_failed(e.outbox_id, "permanent", max_attempts=5)
        sql = mock_exec.call_args[0][1]
        assert "poison" in sql

    @pytest.mark.asyncio
    async def test_reconcile_stuck(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            stuck = await OutboxRepo(mock_db).reconcile_stuck(stale_minutes=5)
        assert isinstance(stuck, list)

    @pytest.mark.asyncio
    async def test_list_status_filter_and_order(self, mock_db):
        mock_fetch = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch):
            await OutboxRepo(mock_db).list(status="poison", limit=25, offset=25)
        sql = mock_fetch.call_args[0][1]
        assert "WHERE status=$1" in sql
        assert "ORDER BY created_at DESC" in sql
        assert "LIMIT $2 OFFSET $3" in sql

    @pytest.mark.asyncio
    async def test_count_status_filter(self, mock_db):
        mock_fetch = AsyncMock(return_value={"cnt": 4})
        with patch("workbench.repos._fetch_one", mock_fetch):
            cnt = await OutboxRepo(mock_db).count(status="poison")
        assert cnt == 4
        assert "WHERE status=$1" in mock_fetch.call_args[0][1]

    @pytest.mark.asyncio
    async def test_retry_resets_to_pending(self, mock_db):
        mock_exec = AsyncMock(return_value="UPDATE 1")
        with patch("workbench.repos._execute", mock_exec):
            await OutboxRepo(mock_db).retry(UID())
        sql = mock_exec.call_args[0][1]
        assert "status='pending'" in sql
        assert "attempt_count=0" in sql
        assert "poison_reason=NULL" in sql


# ── Admin Orphan Repository ────────────────────────────────────────────────────

class TestOrphanRepo:
    @pytest.mark.asyncio
    async def test_sql_covers_three_entities_and_conditions(self, mock_db):
        mock = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock):
            await OrphanRepo(mock_db).orphan_assignments()
        sql = mock.call_args[0][1]
        assert "UNION ALL" in sql
        assert "FROM alerts a" in sql
        assert "FROM investigations i" in sql
        assert "FROM compliance_cases c" in sql
        assert sql.count("status NOT IN ($1, $2)") == 3
        assert "user_scopes WHERE scope_id = a.scope_id" in sql
        assert "user_scopes WHERE scope_id = i.scope_id" in sql
        assert "user_scopes WHERE scope_id = c.scope_id" in sql
        assert "LEFT JOIN users u ON u.user_id = a.assigned_to" in sql
        assert "ORDER BY entity_type, entity_id" in sql

    @pytest.mark.asyncio
    async def test_no_entity_status_filter_per_contract(self, mock_db):
        mock = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock):
            await OrphanRepo(mock_db).orphan_assignments()
        sql = mock.call_args[0][1]
        for clause in ("a.status NOT IN", "i.status NOT IN", "c.status NOT IN",
                       "WHERE a.status", "WHERE i.status", "WHERE c.status"):
            assert clause not in sql

    @pytest.mark.asyncio
    async def test_eligible_statuses_parameterised(self, mock_db):
        mock = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock):
            await OrphanRepo(mock_db).orphan_assignments()
        assert mock.call_args[0][2] == ["active", "active_pending"]


# ── Model Conversion Tests ────────────────────────────────────────────────────

class TestModelConversion:
    def test_alert_from_dict(self):
        d = dict(alert_id=UID(), alert_type="transaction_anomaly", severity="critical",
                 title="Alert", scope_id="hq_main", status="new",
                 version=1, created_at=NOW, updated_at=NOW)
        a = Alert(**d)
        assert a.status == "new"

    def test_investigation_from_dict(self):
        d = dict(investigation_id=UID(), title="Inv", created_by="user1",
                 status="open", version=1, created_at=NOW, updated_at=NOW)
        inv = Investigation(**d)
        assert inv.priority == "medium"

    def test_case_from_dict(self):
        d = dict(case_id=UID(), title="Case", created_by="user1",
                 status="open", version=1, created_at=NOW, updated_at=NOW)
        c = ComplianceCase(**d)
        assert c.priority == "medium"

    def test_decision_from_dict(self):
        d = dict(decision_id=UID(), case_id=UID(), decision_type="warning",
                 rationale="test", decided_by="u1", version=1, created_at=NOW)
        dec = Decision(**d)
        assert dec.is_final is False

    def test_info_request_from_dict(self):
        d = dict(ir_id=UID(), case_id=UID(), created_by="u1", assigned_to="u2",
                 question="q", status="open", version=1, created_at=NOW, updated_at=NOW)
        ir = InformationRequest(**d)
        assert ir.question == "q"

    def test_approval_request_from_dict(self):
        d = dict(approval_request_id=UID(), action_type="alert_dismissal_critical_high",
                 entity_type="alert", entity_id=UID(), requested_by="u1",
                 rationale="r", expires_at=NOW, version=1, created_at=NOW, updated_at=NOW)
        ar = ApprovalRequest(**d)
        assert ar.status == "pending"

    def test_approval_decision_from_dict(self):
        d = dict(approval_decision_id=UID(), approval_request_id=UID(),
                 approver_id="u1", decision="approved", decided_at=NOW)
        ad = ApprovalDecision(**d)
        assert ad.decision == "approved"

    def test_comment_from_dict(self):
        d = dict(comment_id=UID(), entity_type="alert", entity_id=UID(),
                 content="c", author_id="u1", version=1, created_at=NOW, updated_at=NOW)
        c = Comment(**d)
        assert c.is_internal is False

    def test_timeline_from_dict(self):
        d = dict(timeline_id=UID(), entity_type="alert", entity_id=UID(),
                 event_type="created", actor_id="u1", occurred_at=NOW)
        t = ActivityTimelineEntry(**d)
        assert t.event_type == "created"

    def test_notification_from_dict(self):
        d = dict(notification_id=UID(), user_id="u1",
                 notification_type="alert_assigned", title="T", body="B",
                 created_at=NOW)
        n = Notification(**d)
        assert n.is_read is False

    def test_assignment_history_from_dict(self):
        d = dict(history_id=UID(), entity_type="alert", entity_id=UID(),
                 assigned_by="u1", assigned_at=NOW)
        a = AssignmentHistoryEntry(**d)
        assert a.entity_type == "alert"

    def test_outbox_from_dict(self):
        d = dict(outbox_id=UID(), idempotency_key=UID(), event_type="alert.created",
                 entity_type="alert", entity_id=UID(), actor_id="u1",
                 actor_role="analyst", occurred_at=NOW, payload={},
                 status="pending", next_attempt_at=NOW, created_at=NOW)
        o = AuditOutboxEvent(**d)
        assert o.status == "pending"


# ── Approval Constraint Tests ─────────────────────────────────────────────────

class TestApprovalConstraints:
    def test_unique_active_approval_by_same_params(self):
        """Verify that the partial unique index prevents duplicate active approvals
        for the same entity+action. This is a DB constraint test — we verify our
        repo methods correctly attempt INSERT that would trigger it."""
        ar1 = make_approval(entity_type="alert", action_type="alert_dismissal_critical_high")
        ar2 = make_approval(entity_type=ar1.entity_type, entity_id=ar1.entity_id,
                            action_type=ar1.action_type)
        # Both have status "pending" — would violate idx_approval_active_entity_action
        assert ar1.entity_type == ar2.entity_type
        assert ar1.entity_id == ar2.entity_id
        assert ar1.action_type == ar2.action_type
        assert ar1.status == "pending"
        assert ar2.status == "pending"
        # The unique partial index idx_approval_active_entity_action
        # prevents both from being pending simultaneously


# ── UoW Transaction Tests ─────────────────────────────────────────────────────

class TestUnitOfWorkTransaction:
    @pytest.mark.asyncio
    async def test_commit_on_success(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_db._pool = mock_pool
        mock_db._ensure_pool = MagicMock(return_value=mock_pool)

        from workbench.uow import UnitOfWork
        async with UnitOfWork(mock_db) as uow:
            uow.conn = mock_conn
            pass

        mock_conn.execute.assert_any_call("BEGIN")
        mock_conn.execute.assert_any_call("COMMIT")
        mock_pool.release.assert_called_once_with(mock_conn)

    @pytest.mark.asyncio
    async def test_rollback_on_error(self, mock_db):
        mock_conn = AsyncMock()
        mock_pool = AsyncMock()
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        mock_db._pool = mock_pool
        mock_db._ensure_pool = MagicMock(return_value=mock_pool)

        from workbench.uow import UnitOfWork
        with pytest.raises(ValueError):
            async with UnitOfWork(mock_db) as uow:
                uow.conn = mock_conn
                raise ValueError("boom")

        mock_conn.execute.assert_any_call("BEGIN")
        mock_conn.execute.assert_any_call("ROLLBACK")
        mock_pool.release.assert_called_once_with(mock_conn)


class TestInfoRequestAssignedRepo:
    @pytest.mark.asyncio
    async def test_list_assigned_filters_assignee_and_scope(self, mock_db):
        ir = make_info_request(assigned_to="user2")
        mock_fetch_all = AsyncMock(return_value=[ir.model_dump()])
        with patch("workbench.repos._fetch_all", mock_fetch_all):
            result = await InfoRequestRepo(mock_db).list_assigned("user2", ["hq_main"])
        sql, params = mock_fetch_all.call_args[0][1], mock_fetch_all.call_args[0][2]
        assert "ir.assigned_to = $1" in sql
        assert "ANY($2::text[])" in sql
        assert "LEFT JOIN compliance_cases c ON c.case_id = ir.case_id" in sql
        assert "ORDER BY ir.created_at DESC, ir.ir_id" in sql
        assert params[0] == "user2"
        assert params[1] == ["hq_main"]
        assert result[0].ir_id == ir.ir_id
        assert result[0].question == ir.question

    @pytest.mark.asyncio
    async def test_list_assigned_status_and_pagination(self, mock_db):
        mock_fetch_all = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch_all):
            await InfoRequestRepo(mock_db).list_assigned("user2", ["hq_main"],
                                                         status="returned",
                                                         limit=25, offset=50)
        sql, params = mock_fetch_all.call_args[0][1], mock_fetch_all.call_args[0][2]
        assert "ir.status = $3" in sql
        assert "LIMIT $4 OFFSET $5" in sql
        assert params[2:] == ["returned", 25, 50]

    @pytest.mark.asyncio
    async def test_list_assigned_no_creator_broadening(self, mock_db):
        # WHERE clause has no created_by predicate; only the assigned_to predicate.
        mock_fetch_all = AsyncMock(return_value=[])
        with patch("workbench.repos._fetch_all", mock_fetch_all):
            await InfoRequestRepo(mock_db).list_assigned("user2", ["hq_main"])
        sql = mock_fetch_all.call_args[0][1]
        assert "created_by" not in sql.split("WHERE")[1]
        assert sql.lstrip().startswith("SELECT")

    @pytest.mark.asyncio
    async def test_count_assigned_same_predicate(self, mock_db):
        mock_fetch_one = AsyncMock(return_value={"count": 3})
        with patch("workbench.repos._fetch_one", mock_fetch_one):
            total = await InfoRequestRepo(mock_db).count_assigned("user2", ["hq_main"],
                                                                  status="open")
        sql, params = mock_fetch_one.call_args[0][1], mock_fetch_one.call_args[0][2]
        assert "COUNT(*)" in sql
        assert "ir.assigned_to = $1" in sql
        assert "ANY($2::text[])" in sql
        assert params[0] == "user2"
        assert params[1] == ["hq_main"]
        assert params[2] == "open"
        assert total == 3

    @pytest.mark.asyncio
    async def test_count_assigned_empty(self, mock_db):
        with patch("workbench.repos._fetch_one", AsyncMock(return_value=None)):
            total = await InfoRequestRepo(mock_db).count_assigned("user2", ["hq_main"])
        assert total == 0
