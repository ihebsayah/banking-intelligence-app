"""Pydantic schemas for the admin orphan-assignment endpoint (AD3)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class OrphanAssignee(BaseModel):
    user_id: str
    status: Optional[str] = None


class OrphanAssignmentItem(BaseModel):
    entity_id: str
    title: str
    status: str
    assigned_to: OrphanAssignee


class OrphanAssignmentsResponse(BaseModel):
    alerts: List[OrphanAssignmentItem] = []
    investigations: List[OrphanAssignmentItem] = []
    cases: List[OrphanAssignmentItem] = []
