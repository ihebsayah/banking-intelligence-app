"""Pydantic schemas for notification endpoints (N1-N3)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    notification_id: str
    user_id: str
    notification_type: str
    title: str
    body: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class NotificationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    unread_count: int
    items: List[NotificationResponse] = []


class NotificationMutationResponse(BaseModel):
    success: bool = True
    notification: NotificationResponse


class MarkAllReadResponse(BaseModel):
    marked_read: int
