from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class InvestigationStatus(str, Enum):
    OPEN = "open"
    ACTIVE = "active"
    AWAITING_INFORMATION = "awaiting_information"
    SUBMITTED = "submitted"
    RETURNED = "returned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InvestigationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UpdateInvestigationRequest(BaseModel):
    findings_text: Optional[str] = None
    findings_refs: Optional[List[Any]] = None
    conclusion: Optional[str] = None
    expected_version: int = Field(ge=1)


class TransitionInvestigationRequest(BaseModel):
    target_status: str
    return_reason: Optional[str] = None
    expected_version: int = Field(ge=1)


class CancelInvestigationRequest(BaseModel):
    cancel_reason: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class ReviewNotHarmfulRequest(BaseModel):
    rationale: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class EscalateInvestigationRequest(BaseModel):
    title: str = Field(min_length=1)
    priority: str = "medium"
    rationale: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class InvestigationResponse(BaseModel):
    investigation_id: str
    title: str
    description: Optional[str] = None
    alert_id: Optional[str] = None
    scope_id: str
    status: str
    priority: str
    assigned_to: Optional[str] = None
    created_by: str
    findings_text: Optional[str] = None
    findings_refs: Optional[List[Any]] = None
    conclusion: Optional[str] = None
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    return_reason: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class InvestigationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[InvestigationResponse]


class InvestigationMutationResponse(BaseModel):
    success: bool = True
    investigation: InvestigationResponse
    version: int


class EscalateInvestigationResponse(BaseModel):
    success: bool = True
    investigation: InvestigationResponse
    case_id: str
    version: int

