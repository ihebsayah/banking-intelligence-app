"""Pydantic request/response schemas for alert endpoints."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────────

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(str, Enum):
    NEW = "new"
    ASSIGNED = "assigned"
    ACKNOWLEDGED = "acknowledged"
    UNDER_INVESTIGATION = "under_investigation"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ── Request Schemas ────────────────────────────────────────────────────────────

class AssignAlertRequest(BaseModel):
    assigned_to: str
    expected_version: int = Field(ge=1)
    reason: Optional[str] = None


class AcknowledgeAlertRequest(BaseModel):
    expected_version: int = Field(ge=1)


class DismissAlertRequest(BaseModel):
    dismissed_reason: str
    expected_version: int = Field(ge=1)
    approval_request_id: Optional[str] = None


class InvestigateAlertRequest(BaseModel):
    title: str
    description: Optional[str] = None
    expected_version: int = Field(ge=1)


class EscalateAlertRequest(BaseModel):
    title: str
    description: Optional[str] = None
    priority: AlertSeverity = AlertSeverity.MEDIUM
    expected_version: int = Field(ge=1)


# ── Response Schemas ───────────────────────────────────────────────────────────

class AlertResponse(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    title: str
    description: Optional[str] = None
    source_rule_type: Optional[str] = None
    source_rule_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    resolved_customer_id: Optional[str] = None
    scope_id: str
    status: str
    assigned_to: Optional[str] = None
    dismissed_reason: Optional[str] = None
    dismissed_at: Optional[datetime] = None
    dismissed_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    version: int


class AlertAdminResponse(BaseModel):
    """Metadata-only view for admin users outside direct scope."""
    alert_id: str
    alert_type: str
    severity: str
    status: str
    assigned_to: Optional[str] = None
    scope_id: str
    created_at: datetime
    version: int


class AlertListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AlertResponse]


class MutationResponse(BaseModel):
    success: bool = True
    alert: AlertResponse
    version: int


class EscalateResponse(BaseModel):
    success: bool = True
    alert: AlertResponse
    case_id: str
    version: int


class InvestigateResponse(BaseModel):
    success: bool = True
    alert: AlertResponse
    investigation_id: str
    version: int
