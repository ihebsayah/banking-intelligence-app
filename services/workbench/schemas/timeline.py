"""Pydantic schemas for timeline endpoints (TL1-TL2)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TimelineEntryResponse(BaseModel):
    timeline_id: str
    entity_type: str
    entity_id: str
    event_type: str
    actor_id: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    occurred_at: datetime


class TimelineListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[TimelineEntryResponse] = []
