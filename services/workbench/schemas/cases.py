from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class CaseStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    UNDER_REVIEW = "under_review"
    AWAITING_INFORMATION = "awaiting_information"
    DECISION_PENDING = "decision_pending"
    AWAITING_COMPLIANCE_ACTION = "awaiting_compliance_action"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class CasePriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssignCaseRequest(BaseModel):
    assigned_to: str
    expected_version: int = Field(ge=1)
    reason: Optional[str] = None


class DecisionType(str, Enum):
    NO_ACTION = "no_action"
    WARNING = "warning"
    ENHANCED_DUE_DILIGENCE_RECOMMENDED = "enhanced_due_diligence_recommended"
    REPORT_TO_AUTHORITY_RECOMMENDED = "report_to_authority_recommended"
    ACCOUNT_ACTION_RECOMMENDED = "account_action_recommended"
    CLOSURE_RECOMMENDED = "closure_recommended"


class TransitionCaseRequest(BaseModel):
    target_status: str
    expected_version: int = Field(ge=1)
    resolution: Optional[str] = None


class RecordDecisionRequest(BaseModel):
    decision_type: DecisionType
    rationale: str = Field(min_length=1)
    is_final: bool = False
    supersedes_decision_id: Optional[str] = None
    expected_version: int = Field(ge=1)


class CaseResponse(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = None
    alert_id: Optional[str] = None
    investigation_id: Optional[str] = None
    scope_id: str
    status: str
    priority: str
    risk_level: Optional[str] = None
    regulatory_frameworks: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    created_by: str
    target_date: Optional[date] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    current_disposition_id: Optional[str] = None
    closure_approval_id: Optional[str] = None
    reopen_reason: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class CaseListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[CaseResponse]


class CaseMutationResponse(BaseModel):
    success: bool = True
    case: CaseResponse
    version: int


class CaseAdminView(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = None
    alert_id: Optional[str] = None
    investigation_id: Optional[str] = None
    scope_id: str
    status: str
    priority: str
    risk_level: Optional[str] = None
    regulatory_frameworks: Optional[List[str]] = None
    assigned_to: Optional[str] = None
    created_by: str
    target_date: Optional[date] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    reopen_reason: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class CaseAdminResponse(BaseModel):
    success: bool = True
    case: CaseAdminView
    version: int


class CaseDecisionResponse(BaseModel):
    success: bool = True
    case: CaseAdminView
    decision: dict
    version: int
