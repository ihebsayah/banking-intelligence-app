"""Unit of Work — atomic multi-repository transactions.

Usage:
    async with UnitOfWork(db) as uow:
        alert = await uow.alert_repo.create(alert, conn=uow.conn)
        await uow.timeline_repo.insert(entry, conn=uow.conn)
        await uow.outbox_repo.insert(event, conn=uow.conn)
    # auto-commits on success, rolls back on exception
"""
from __future__ import annotations

import asyncpg
from shared.database import DatabaseConnector

from .repos import (
    AlertRepo, ApprovalDecisionRepo, ApprovalRepo, AssignmentHistoryRepo,
    CaseRepo, CommentRepo, DecisionRepo, InfoRequestRepo,
    InvestigationRepo, NotificationRepo, OutboxRepo, TimelineRepo,
)


class UnitOfWork:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db
        self.conn: asyncpg.Connection | None = None

        self.alert_repo = AlertRepo(db)
        self.investigation_repo = InvestigationRepo(db)
        self.case_repo = CaseRepo(db)
        self.decision_repo = DecisionRepo(db)
        self.info_request_repo = InfoRequestRepo(db)
        self.approval_repo = ApprovalRepo(db)
        self.approval_decision_repo = ApprovalDecisionRepo(db)
        self.comment_repo = CommentRepo(db)
        self.timeline_repo = TimelineRepo(db)
        self.notification_repo = NotificationRepo(db)
        self.assignment_history_repo = AssignmentHistoryRepo(db)
        self.outbox_repo = OutboxRepo(db)

    async def __aenter__(self) -> UnitOfWork:
        pool = self._db._ensure_pool()
        self.conn = await pool.acquire()
        await self.conn.execute("BEGIN")
        return self

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object) -> None:
        if self.conn is None:
            return
        try:
            if exc_type is None:
                await self.conn.execute("COMMIT")
            else:
                await self.conn.execute("ROLLBACK")
        finally:
            await self._db._pool.release(self.conn)
            self.conn = None
