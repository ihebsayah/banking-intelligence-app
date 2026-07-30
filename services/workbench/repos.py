"""Repository layer for Phase 2B operational entities.

Each repository accepts an optional asyncpg connection for use inside
a UnitOfWork. Without a connection, methods auto-acquire from the pool.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypeVar

import asyncpg
from shared.database import DatabaseConnector
from shared.errors import DatabaseError

from .models import (
    ActivityTimelineEntry, Alert, ApprovalDecision, ApprovalRequest,
    AssignmentHistoryEntry, AuditOutboxEvent, Comment, ComplianceCase,
    Decision, InformationRequest, Investigation, Notification,
)

T = TypeVar("T")

_ROW = Dict[str, Any]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _execute(db: DatabaseConnector, sql: str, params: list, conn: asyncpg.Connection | None = None) -> str:
    if conn:
        return await conn.execute(sql, *params)
    return await db.execute(sql, params)


async def _fetch_one(db: DatabaseConnector, sql: str, params: list, conn: asyncpg.Connection | None = None) -> _ROW | None:
    if conn:
        r = await conn.fetchrow(sql, *params)
        return dict(r) if r else None
    return await db.fetch_one(sql, params)


async def _fetch_all(db: DatabaseConnector, sql: str, params: list, conn: asyncpg.Connection | None = None) -> list[_ROW]:
    if conn:
        rows = await conn.fetch(sql, *params)
        return [dict(r) for r in rows]
    return await db.fetch_all(sql, params)


# ── Alert Repository ──────────────────────────────────────────────────────────

class AlertRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, alert_id: str, conn: asyncpg.Connection | None = None) -> Alert | None:
        r = await _fetch_one(self._db, "SELECT * FROM alerts WHERE alert_id = $1", [alert_id], conn)
        return Alert(**r) if r else None

    async def list(self, scope_id: str | None = None, status: str | None = None,
                   assigned_to: str | None = None, limit: int = 50, offset: int = 0,
                   conn: asyncpg.Connection | None = None) -> list[Alert]:
        parts = ["SELECT * FROM alerts WHERE 1=1"]
        params: list = []
        i = 1
        if scope_id:
            parts.append(f"AND scope_id = ${i}"); params.append(scope_id); i += 1
        if status:
            parts.append(f"AND status = ${i}"); params.append(status); i += 1
        if assigned_to:
            parts.append(f"AND assigned_to = ${i}"); params.append(assigned_to); i += 1
        parts.append(f"ORDER BY created_at DESC LIMIT ${i} OFFSET ${i+1}")
        params.extend([limit, offset])
        rows = await _fetch_all(self._db, " ".join(parts), params, conn)
        return [Alert(**r) for r in rows]

    async def create(self, alert: Alert, conn: asyncpg.Connection | None = None) -> Alert:
        await _execute(self._db, """
            INSERT INTO alerts (alert_id, alert_type, severity, title, description,
                source_rule_type, source_rule_id, related_entity_type, related_entity_id,
                scope_id, status, assigned_to, version, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        """, [
            alert.alert_id, alert.alert_type, alert.severity, alert.title, alert.description,
            alert.source_rule_type, alert.source_rule_id, alert.related_entity_type, alert.related_entity_id,
            alert.scope_id, alert.status, alert.assigned_to, alert.version,
            alert.created_at, alert.updated_at,
        ], conn)
        return alert

    async def update(self, alert: Alert, expected_version: int, conn: asyncpg.Connection | None = None) -> Alert | None:
        if alert.version != expected_version + 1:
            raise DatabaseError("Optimistic lock: version mismatch")
        r = await _execute(self._db, """
            UPDATE alerts SET alert_type=$1, severity=$2, title=$3, description=$4,
                source_rule_type=$5, source_rule_id=$6, related_entity_type=$7,
                related_entity_id=$8, scope_id=$9, status=$10, assigned_to=$11,
                dismissed_reason=$12, dismissed_at=$13, dismissed_by=$14,
                resolved_at=$15, resolved_by=$16, dismissal_approval_id=$17,
                version=$18, updated_at=$19
            WHERE alert_id=$20 AND version=$21
        """, [
            alert.alert_type, alert.severity, alert.title, alert.description,
            alert.source_rule_type, alert.source_rule_id, alert.related_entity_type,
            alert.related_entity_id, alert.scope_id, alert.status, alert.assigned_to,
            alert.dismissed_reason, alert.dismissed_at, alert.dismissed_by,
            alert.resolved_at, alert.resolved_by, alert.dismissal_approval_id,
            alert.version, alert.updated_at,
            alert.alert_id, expected_version,
        ], conn)
        if r == "UPDATE 0":
            existing = await self.fetch_by_id(alert.alert_id, conn)
            if existing is None:
                return None  # not found
            raise DatabaseError("Optimistic lock: stale version")
        return alert


# ── Investigation Repository ───────────────────────────────────────────────────

class InvestigationRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, investigation_id: str, conn: asyncpg.Connection | None = None) -> Investigation | None:
        r = await _fetch_one(self._db, "SELECT * FROM investigations WHERE investigation_id = $1", [investigation_id], conn)
        return Investigation(**r) if r else None

    async def list(self, scope_id: str | None = None, status: str | None = None,
                   assigned_to: str | None = None, limit: int = 50, offset: int = 0,
                   conn: asyncpg.Connection | None = None) -> list[Investigation]:
        parts = ["SELECT * FROM investigations WHERE 1=1"]
        params: list = []
        i = 1
        if scope_id:
            parts.append(f"AND scope_id = ${i}"); params.append(scope_id); i += 1
        if status:
            parts.append(f"AND status = ${i}"); params.append(status); i += 1
        if assigned_to:
            parts.append(f"AND assigned_to = ${i}"); params.append(assigned_to); i += 1
        parts.append(f"ORDER BY created_at DESC LIMIT ${i} OFFSET ${i+1}")
        params.extend([limit, offset])
        rows = await _fetch_all(self._db, " ".join(parts), params, conn)
        return [Investigation(**r) for r in rows]

    async def create(self, inv: Investigation, conn: asyncpg.Connection | None = None) -> Investigation:
        await _execute(self._db, """
            INSERT INTO investigations (investigation_id, title, description, alert_id,
                scope_id, status, priority, assigned_to, created_by, version, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """, [
            inv.investigation_id, inv.title, inv.description, inv.alert_id,
            inv.scope_id, inv.status, inv.priority, inv.assigned_to,
            inv.created_by, inv.version, inv.created_at, inv.updated_at,
        ], conn)
        return inv

    async def update(self, inv: Investigation, expected_version: int, conn: asyncpg.Connection | None = None) -> Investigation | None:
        if inv.version != expected_version + 1:
            raise DatabaseError("Optimistic lock: version mismatch")
        r = await _execute(self._db, """
            UPDATE investigations SET title=$1, description=$2, alert_id=$3, scope_id=$4,
                status=$5, priority=$6, assigned_to=$7, findings_text=$8, findings_refs=$9::jsonb,
                conclusion=$10, started_at=$11, submitted_at=$12, completed_at=$13,
                return_reason=$14, version=$15, updated_at=$16
            WHERE investigation_id=$17 AND version=$18
        """, [
            inv.title, inv.description, inv.alert_id, inv.scope_id,
            inv.status, inv.priority, inv.assigned_to, inv.findings_text,
            inv.findings_refs, inv.conclusion, inv.started_at, inv.submitted_at,
            inv.completed_at, inv.return_reason, inv.version, inv.updated_at,
            inv.investigation_id, expected_version,
        ], conn)
        if r == "UPDATE 0":
            existing = await self.fetch_by_id(inv.investigation_id, conn)
            if existing is None:
                return None
            raise DatabaseError("Optimistic lock: stale version")
        return inv


# ── Compliance Case Repository ─────────────────────────────────────────────────

class CaseRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, case_id: str, conn: asyncpg.Connection | None = None) -> ComplianceCase | None:
        r = await _fetch_one(self._db, "SELECT * FROM compliance_cases WHERE case_id = $1", [case_id], conn)
        return ComplianceCase(**r) if r else None

    async def list(self, scope_id: str | None = None, status: str | None = None,
                   assigned_to: str | None = None, limit: int = 50, offset: int = 0,
                   conn: asyncpg.Connection | None = None) -> list[ComplianceCase]:
        parts = ["SELECT * FROM compliance_cases WHERE 1=1"]
        params: list = []
        i = 1
        if scope_id:
            parts.append(f"AND scope_id = ${i}"); params.append(scope_id); i += 1
        if status:
            parts.append(f"AND status = ${i}"); params.append(status); i += 1
        if assigned_to:
            parts.append(f"AND assigned_to = ${i}"); params.append(assigned_to); i += 1
        parts.append(f"ORDER BY created_at DESC LIMIT ${i} OFFSET ${i+1}")
        params.extend([limit, offset])
        rows = await _fetch_all(self._db, " ".join(parts), params, conn)
        return [ComplianceCase(**r) for r in rows]

    async def create(self, case: ComplianceCase, conn: asyncpg.Connection | None = None) -> ComplianceCase:
        await _execute(self._db, """
            INSERT INTO compliance_cases (case_id, title, description, alert_id,
                investigation_id, scope_id, status, priority, risk_level,
                regulatory_frameworks, assigned_to, created_by, target_date,
                version, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::text[],$11,$12,$13,$14,$15,$16)
        """, [
            case.case_id, case.title, case.description, case.alert_id,
            case.investigation_id, case.scope_id, case.status, case.priority,
            case.risk_level, case.regulatory_frameworks, case.assigned_to,
            case.created_by, case.target_date, case.version, case.created_at, case.updated_at,
        ], conn)
        return case

    async def update(self, case: ComplianceCase, expected_version: int, conn: asyncpg.Connection | None = None) -> ComplianceCase | None:
        if case.version != expected_version + 1:
            raise DatabaseError("Optimistic lock: version mismatch")
        r = await _execute(self._db, """
            UPDATE compliance_cases SET title=$1, description=$2, alert_id=$3,
                investigation_id=$4, scope_id=$5, status=$6, priority=$7, risk_level=$8,
                regulatory_frameworks=$9::text[], assigned_to=$10, target_date=$11,
                resolution=$12, resolved_at=$13, resolved_by=$14, closed_at=$15,
                closed_by=$16, current_disposition_id=$17, closure_approval_id=$18,
                reopen_reason=$19, version=$20, updated_at=$21
            WHERE case_id=$22 AND version=$23
        """, [
            case.title, case.description, case.alert_id, case.investigation_id,
            case.scope_id, case.status, case.priority, case.risk_level,
            case.regulatory_frameworks, case.assigned_to, case.target_date,
            case.resolution, case.resolved_at, case.resolved_by, case.closed_at,
            case.closed_by, case.current_disposition_id, case.closure_approval_id,
            case.reopen_reason, case.version, case.updated_at,
            case.case_id, expected_version,
        ], conn)
        if r == "UPDATE 0":
            existing = await self.fetch_by_id(case.case_id, conn)
            if existing is None:
                return None
            raise DatabaseError("Optimistic lock: stale version")
        return case


# ── Decision Repository ────────────────────────────────────────────────────────

class DecisionRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, decision_id: str, conn: asyncpg.Connection | None = None) -> Decision | None:
        r = await _fetch_one(self._db, "SELECT * FROM decisions WHERE decision_id = $1", [decision_id], conn)
        return Decision(**r) if r else None

    async def list_by_case(self, case_id: str, conn: asyncpg.Connection | None = None) -> list[Decision]:
        rows = await _fetch_all(self._db, "SELECT * FROM decisions WHERE case_id = $1 ORDER BY decided_at DESC", [case_id], conn)
        return [Decision(**r) for r in rows]

    async def create(self, d: Decision, conn: asyncpg.Connection | None = None) -> Decision:
        await _execute(self._db, """
            INSERT INTO decisions (decision_id, case_id, decision_type, rationale,
                decided_by, decided_at, is_final, supersedes_decision_id,
                approval_id, version, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        """, [
            d.decision_id, d.case_id, d.decision_type, d.rationale,
            d.decided_by, d.decided_at, d.is_final, d.supersedes_decision_id,
            d.approval_id, d.version, d.created_at,
        ], conn)
        return d

    async def update(self, d: Decision, expected_version: int, conn: asyncpg.Connection | None = None) -> Decision | None:
        if d.version != expected_version + 1:
            raise DatabaseError("Optimistic lock: version mismatch")
        r = await _execute(self._db, """
            UPDATE decisions SET decision_type=$1, rationale=$2, decided_by=$3,
                decided_at=$4, is_final=$5, supersedes_decision_id=$6,
                approval_id=$7, version=$8
            WHERE decision_id=$9 AND version=$10
        """, [
            d.decision_type, d.rationale, d.decided_by, d.decided_at,
            d.is_final, d.supersedes_decision_id, d.approval_id,
            d.version, d.decision_id, expected_version,
        ], conn)
        if r == "UPDATE 0":
            existing = await self.fetch_by_id(d.decision_id, conn)
            if existing is None:
                return None
            raise DatabaseError("Optimistic lock: stale version")
        return d


# ── Information Request Repository ─────────────────────────────────────────────

class InfoRequestRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, ir_id: str, conn: asyncpg.Connection | None = None) -> InformationRequest | None:
        r = await _fetch_one(self._db, "SELECT * FROM information_requests WHERE ir_id = $1", [ir_id], conn)
        return InformationRequest(**r) if r else None

    async def list_by_case(self, case_id: str, conn: asyncpg.Connection | None = None) -> list[InformationRequest]:
        rows = await _fetch_all(self._db, "SELECT * FROM information_requests WHERE case_id = $1 ORDER BY created_at DESC", [case_id], conn)
        return [InformationRequest(**r) for r in rows]

    async def create(self, ir: InformationRequest, conn: asyncpg.Connection | None = None) -> InformationRequest:
        await _execute(self._db, """
            INSERT INTO information_requests (ir_id, case_id, investigation_id,
                created_by, assigned_to, question, due_date, status, version,
                created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        """, [
            ir.ir_id, ir.case_id, ir.investigation_id, ir.created_by,
            ir.assigned_to, ir.question, ir.due_date, ir.status,
            ir.version, ir.created_at, ir.updated_at,
        ], conn)
        return ir

    async def update(self, ir: InformationRequest, expected_version: int, conn: asyncpg.Connection | None = None) -> InformationRequest | None:
        if ir.version != expected_version + 1:
            raise DatabaseError("Optimistic lock: version mismatch")
        r = await _execute(self._db, """
            UPDATE information_requests SET case_id=$1, investigation_id=$2,
                created_by=$3, assigned_to=$4, question=$5, due_date=$6, status=$7,
                response_text=$8, responded_at=$9, acceptance_note=$10,
                return_reason=$11, accepted_at=$12, returned_at=$13,
                accepted_by=$14, returned_by=$15, cancelled_at=$16,
                cancelled_by=$17, cancel_reason=$18, version=$19, updated_at=$20
            WHERE ir_id=$21 AND version=$22
        """, [
            ir.case_id, ir.investigation_id, ir.created_by, ir.assigned_to,
            ir.question, ir.due_date, ir.status, ir.response_text,
            ir.responded_at, ir.acceptance_note, ir.return_reason,
            ir.accepted_at, ir.returned_at, ir.accepted_by, ir.returned_by,
            ir.cancelled_at, ir.cancelled_by, ir.cancel_reason,
            ir.version, ir.updated_at, ir.ir_id, expected_version,
        ], conn)
        if r == "UPDATE 0":
            existing = await self.fetch_by_id(ir.ir_id, conn)
            if existing is None:
                return None
            raise DatabaseError("Optimistic lock: stale version")
        return ir


# ── Approval Request Repository ────────────────────────────────────────────────

class ApprovalRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, approval_request_id: str, conn: asyncpg.Connection | None = None) -> ApprovalRequest | None:
        r = await _fetch_one(self._db, "SELECT * FROM approval_requests WHERE approval_request_id = $1", [approval_request_id], conn)
        return ApprovalRequest(**r) if r else None

    async def fetch_active_for_entity(self, entity_type: str, entity_id: str, action_type: str,
                                      conn: asyncpg.Connection | None = None) -> ApprovalRequest | None:
        r = await _fetch_one(self._db, """
            SELECT * FROM approval_requests
            WHERE entity_type=$1 AND entity_id=$2 AND action_type=$3 AND status='pending'
            ORDER BY created_at DESC LIMIT 1
        """, [entity_type, entity_id, action_type], conn)
        return ApprovalRequest(**r) if r else None

    async def create(self, ar: ApprovalRequest, conn: asyncpg.Connection | None = None) -> ApprovalRequest:
        await _execute(self._db, """
            INSERT INTO approval_requests (approval_request_id, action_type, entity_type,
                entity_id, requested_by, rationale, required_approvals, approval_count,
                status, expires_at, version, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
        """, [
            ar.approval_request_id, ar.action_type, ar.entity_type,
            ar.entity_id, ar.requested_by, ar.rationale, ar.required_approvals,
            ar.approval_count, ar.status, ar.expires_at, ar.version,
            ar.created_at, ar.updated_at,
        ], conn)
        return ar

    async def consume(self, approval_request_id: str, conn: asyncpg.Connection | None = None) -> ApprovalRequest | None:
        """Atomically mark an approval as executed (consumed)."""
        r = await _fetch_one(self._db, """
            UPDATE approval_requests SET status='approved', executed_at=$1, version=version+1, updated_at=$1
            WHERE approval_request_id=$2 AND status='pending'
            RETURNING *
        """, [_now(), approval_request_id], conn)
        return ApprovalRequest(**r) if r else None


# ── Approval Decision Repository ───────────────────────────────────────────────

class ApprovalDecisionRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def create(self, ad: ApprovalDecision, conn: asyncpg.Connection | None = None) -> ApprovalDecision:
        await _execute(self._db, """
            INSERT INTO approval_decisions (approval_decision_id, approval_request_id,
                approver_id, decision, rationale, decided_at)
            VALUES ($1,$2,$3,$4,$5,$6)
        """, [
            ad.approval_decision_id, ad.approval_request_id,
            ad.approver_id, ad.decision, ad.rationale, ad.decided_at,
        ], conn)
        return ad

    async def list_for_request(self, approval_request_id: str, conn: asyncpg.Connection | None = None) -> list[ApprovalDecision]:
        rows = await _fetch_all(self._db,
            "SELECT * FROM approval_decisions WHERE approval_request_id = $1 ORDER BY decided_at",
            [approval_request_id], conn)
        return [ApprovalDecision(**r) for r in rows]


# ── Comment Repository ─────────────────────────────────────────────────────────

class CommentRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_by_id(self, comment_id: str, conn: asyncpg.Connection | None = None) -> Comment | None:
        r = await _fetch_one(self._db, "SELECT * FROM comments WHERE comment_id = $1", [comment_id], conn)
        return Comment(**r) if r else None

    async def list_for_entity(self, entity_type: str, entity_id: str,
                              conn: asyncpg.Connection | None = None) -> list[Comment]:
        rows = await _fetch_all(self._db,
            "SELECT * FROM comments WHERE entity_type=$1 AND entity_id=$2 ORDER BY created_at",
            [entity_type, entity_id], conn)
        return [Comment(**r) for r in rows]

    async def create(self, c: Comment, conn: asyncpg.Connection | None = None) -> Comment:
        await _execute(self._db, """
            INSERT INTO comments (comment_id, entity_type, entity_id, content, author_id,
                is_internal, is_redacted, version, created_at, updated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """, [
            c.comment_id, c.entity_type, c.entity_id, c.content, c.author_id,
            c.is_internal, c.is_redacted, c.version, c.created_at, c.updated_at,
        ], conn)
        return c

    async def update(self, c: Comment, expected_version: int, conn: asyncpg.Connection | None = None) -> Comment | None:
        if c.version != expected_version + 1:
            raise DatabaseError("Optimistic lock: version mismatch")
        r = await _execute(self._db, """
            UPDATE comments SET content=$1, is_internal=$2, is_redacted=$3,
                redacted_at=$4, redacted_by=$5, original_content_hash=$6,
                redaction_reason=$7, version=$8, updated_at=$9
            WHERE comment_id=$10 AND version=$11
        """, [
            c.content, c.is_internal, c.is_redacted, c.redacted_at,
            c.redacted_by, c.original_content_hash, c.redaction_reason,
            c.version, c.updated_at, c.comment_id, expected_version,
        ], conn)
        if r == "UPDATE 0":
            existing = await self.fetch_by_id(c.comment_id, conn)
            if existing is None:
                return None
            raise DatabaseError("Optimistic lock: stale version")
        return c


# ── Timeline Repository ────────────────────────────────────────────────────────

class TimelineRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def list_for_entity(self, entity_type: str, entity_id: str,
                              conn: asyncpg.Connection | None = None) -> list[ActivityTimelineEntry]:
        rows = await _fetch_all(self._db,
            "SELECT * FROM activity_timeline WHERE entity_type=$1 AND entity_id=$2 ORDER BY occurred_at",
            [entity_type, entity_id], conn)
        return [ActivityTimelineEntry(**r) for r in rows]

    async def insert(self, entry: ActivityTimelineEntry, conn: asyncpg.Connection | None = None) -> ActivityTimelineEntry:
        await _execute(self._db, """
            INSERT INTO activity_timeline (timeline_id, entity_type, entity_id, event_type,
                actor_id, old_value, new_value, metadata, occurred_at)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9)
        """, [
            entry.timeline_id, entry.entity_type, entry.entity_id, entry.event_type,
            entry.actor_id, entry.old_value, entry.new_value, entry.metadata,
            entry.occurred_at,
        ], conn)
        return entry


# ── Notification Repository ────────────────────────────────────────────────────

class NotificationRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def list_for_user(self, user_id: str, unread_only: bool = False,
                            limit: int = 50, conn: asyncpg.Connection | None = None) -> list[Notification]:
        if unread_only:
            rows = await _fetch_all(self._db,
                "SELECT * FROM notifications WHERE user_id=$1 AND is_read=FALSE ORDER BY created_at DESC LIMIT $2",
                [user_id, limit], conn)
        else:
            rows = await _fetch_all(self._db,
                "SELECT * FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT $2",
                [user_id, limit], conn)
        return [Notification(**r) for r in rows]

    async def insert(self, n: Notification, conn: asyncpg.Connection | None = None) -> Notification:
        await _execute(self._db, """
            INSERT INTO notifications (notification_id, user_id, notification_type,
                title, body, entity_type, entity_id, is_read, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """, [
            n.notification_id, n.user_id, n.notification_type,
            n.title, n.body, n.entity_type, n.entity_id, n.is_read, n.created_at,
        ], conn)
        return n

    async def mark_read(self, notification_id: str, conn: asyncpg.Connection | None = None) -> None:
        await _execute(self._db,
            "UPDATE notifications SET is_read=TRUE, read_at=$1 WHERE notification_id=$2",
            [_now(), notification_id], conn)


# ── Assignment History Repository ──────────────────────────────────────────────

class AssignmentHistoryRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def list_for_entity(self, entity_type: str, entity_id: str,
                              conn: asyncpg.Connection | None = None) -> list[AssignmentHistoryEntry]:
        rows = await _fetch_all(self._db,
            "SELECT * FROM assignment_history WHERE entity_type=$1 AND entity_id=$2 ORDER BY assigned_at DESC",
            [entity_type, entity_id], conn)
        return [AssignmentHistoryEntry(**r) for r in rows]

    async def insert(self, entry: AssignmentHistoryEntry, conn: asyncpg.Connection | None = None) -> AssignmentHistoryEntry:
        await _execute(self._db, """
            INSERT INTO assignment_history (history_id, entity_type, entity_id,
                assigned_from, assigned_to, assigned_by, reason, assigned_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """, [
            entry.history_id, entry.entity_type, entry.entity_id,
            entry.assigned_from, entry.assigned_to, entry.assigned_by,
            entry.reason, entry.assigned_at,
        ], conn)
        return entry


# ── Audit Outbox Repository ────────────────────────────────────────────────────

class OutboxRepo:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def insert(self, event: AuditOutboxEvent, conn: asyncpg.Connection | None = None) -> AuditOutboxEvent:
        await _execute(self._db, """
            INSERT INTO audit_outbox (outbox_id, idempotency_key, event_type,
                entity_type, entity_id, actor_id, actor_role, occurred_at,
                payload, payload_schema_ver, status, next_attempt_at, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10,$11,$12,$13)
        """, [
            event.outbox_id, event.idempotency_key, event.event_type,
            event.entity_type, event.entity_id, event.actor_id, event.actor_role,
            event.occurred_at, event.payload, event.payload_schema_ver,
            event.status, event.next_attempt_at, event.created_at,
        ], conn)
        return event

    async def claim_next_batch(self, worker_id: str, batch_size: int = 10,
                               conn: asyncpg.Connection | None = None) -> list[AuditOutboxEvent]:
        rows = await _fetch_all(self._db, """
            UPDATE audit_outbox SET status='delivering', locked_by=$1, locked_at=$2,
                last_attempt_at=$2, attempt_count=attempt_count+1
            WHERE outbox_id IN (
                SELECT outbox_id FROM audit_outbox
                WHERE status IN ('pending','failed') AND next_attempt_at <= NOW()
                ORDER BY next_attempt_at ASC
                LIMIT $3
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        """, [worker_id, _now(), batch_size], conn)
        return [AuditOutboxEvent(**r) for r in rows]

    async def mark_delivered(self, outbox_id: str, conn: asyncpg.Connection | None = None) -> None:
        await _execute(self._db,
            "UPDATE audit_outbox SET status='delivered', delivered_at=$1 WHERE outbox_id=$2",
            [_now(), outbox_id], conn)

    async def mark_failed(self, outbox_id: str, error: str, max_attempts: int = 5,
                          conn: asyncpg.Connection | None = None) -> None:
        event = await self.fetch_by_id(outbox_id, conn)
        if event is None:
            return
        attempt = event.attempt_count + 1
        delay = min(60 * (2 ** (attempt - 1)), 3600)
        if attempt >= max_attempts:
            await _execute(self._db, """
                UPDATE audit_outbox SET status='poison', last_error=$1,
                    poison_reason=$2, next_attempt_at=NULL
                WHERE outbox_id=$3
            """, [error, f"Failed after {attempt} attempts", outbox_id], conn)
        else:
            await _execute(self._db, """
                UPDATE audit_outbox SET last_error=$1, status='failed',
                    next_attempt_at=$2
                WHERE outbox_id=$3
            """, [error, _now().replace(second=delay), outbox_id], conn)

    async def fetch_by_id(self, outbox_id: str, conn: asyncpg.Connection | None = None) -> AuditOutboxEvent | None:
        r = await _fetch_one(self._db, "SELECT * FROM audit_outbox WHERE outbox_id = $1", [outbox_id], conn)
        return AuditOutboxEvent(**r) if r else None

    async def reconcile_stuck(self, stale_minutes: int = 5,
                              conn: asyncpg.Connection | None = None) -> list[AuditOutboxEvent]:
        from datetime import timedelta
        cutoff = _now() - timedelta(minutes=stale_minutes)
        rows = await _fetch_all(self._db, """
            UPDATE audit_outbox SET status='failed', last_error='Reconciled: stuck in delivering'
            WHERE status='delivering' AND locked_at < $1
            RETURNING *
        """, [cutoff], conn)
        return [AuditOutboxEvent(**r) for r in rows]

    async def count_poison(self, conn: asyncpg.Connection | None = None) -> int:
        r = await _fetch_one(self._db, "SELECT COUNT(*) AS cnt FROM audit_outbox WHERE status='poison'", [], conn)
        return r["cnt"] if r else 0
