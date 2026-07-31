"""Timeline service — workflow logic for TL1 and TL2.

TL1 resolves the parent entity and gates on its read permission plus
timeline:read. TL2 aggregates the current user's own entities only.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from shared.authorise import (
    ApplicationUser, RequestContext, Resource, authorise,
)
from shared.database import DatabaseConnector

from workbench.repos import TimelineRepo
from workbench.schemas.timeline import TimelineEntryResponse

from .entity_access import assert_entity_readable, fetch_parent, resolve_entity_type


class TimelineService:
    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── TL1 — GET /{entity_type}/{entity_id}/timeline ─────────────────────────

    async def list_for_entity(
        self, user: ApplicationUser, entity_type: str, entity_id: str,
        event_type: Optional[str] = None, page: int = 1, per_page: int = 50,
    ) -> Tuple[List[TimelineEntryResponse], int]:
        canonical = resolve_entity_type(entity_type)
        parent = await fetch_parent(self._db, canonical, entity_id)
        await assert_entity_readable(user, parent, self._db)
        await authorise(user, "timeline:read", parent.resource, self._db)

        limit = min(per_page, 100)
        entries = await TimelineRepo(self._db).list_for_entity(
            canonical, entity_id, event_type=event_type,
            limit=limit, offset=(page - 1) * limit)
        total = await TimelineRepo(self._db).count_for_entity(
            canonical, entity_id, event_type=event_type)
        return [TimelineEntryResponse(**e.model_dump()) for e in entries], total

    # ── TL2 — GET /timeline (own entities only) ───────────────────────────────

    async def list_for_user(
        self, user: ApplicationUser, entity_type: Optional[str] = None,
        since: Optional[datetime] = None, page: int = 1, per_page: int = 50,
    ) -> Tuple[List[TimelineEntryResponse], int]:
        await authorise(user, "timeline:read",
                        Resource(id=user.user_id, status="active",
                                 entity_type="timeline"),
                        self._db, RequestContext())

        canonical = resolve_entity_type(entity_type) if entity_type else None
        limit = min(per_page, 100)
        entries = await TimelineRepo(self._db).list_for_user(
            user.user_id, entity_type=canonical, since=since,
            limit=limit, offset=(page - 1) * limit)
        total = await TimelineRepo(self._db).count_for_user(
            user.user_id, entity_type=canonical, since=since)
        return [TimelineEntryResponse(**e.model_dump()) for e in entries], total
