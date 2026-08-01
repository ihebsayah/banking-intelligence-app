"""Pydantic schemas for admin outbox endpoints (AD1-AD2)."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel

from workbench.models import AuditOutboxEvent


class OutboxListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AuditOutboxEvent] = []


class OutboxRetryResponse(BaseModel):
    queued: bool = True
    outbox_id: str
