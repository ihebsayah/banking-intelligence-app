from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApprovalActionType(str, Enum):
    ALERT_DISMISSAL_CRITICAL_HIGH = "alert_dismissal_critical_high"
    CASE_CLOSURE_CRITICAL_HIGH = "case_closure_critical_high"
    DECISION_REPORT_TO_AUTHORITY = "decision_report_to_authority"
    CASE_REOPEN = "case_reopen"


class ApprovalEntityType(str, Enum):
    ALERT = "alert"
    COMPLIANCE_CASE = "compliance_case"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class CreateApprovalRequest(BaseModel):
    action_type: ApprovalActionType
    entity_type: ApprovalEntityType
    entity_id: str
    proposed_payload: Optional[Dict[str, Any]] = None
    rationale: str = Field(min_length=1)


class ApprovalDecisionVote(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class VoteApprovalRequest(BaseModel):
    decision: ApprovalDecisionVote
    rationale: Optional[str] = Field(default=None, min_length=1)


class ApprovalDecisionResponse(BaseModel):
    approval_decision_id: str
    approver_id: str
    decision: str
    rationale: Optional[str] = None
    decided_at: datetime


class ApprovalRequestResponse(BaseModel):
    approval_request_id: str
    action_type: str
    entity_type: str
    entity_id: str
    requested_by: str
    rationale: str
    required_approvals: int
    approval_count: int
    status: str
    expires_at: datetime
    executed_at: Optional[datetime] = None
    version: int
    created_at: datetime
    updated_at: datetime


class ApprovalRequestDetailResponse(ApprovalRequestResponse):
    decisions: List[ApprovalDecisionResponse] = []


class ApprovalRequestMutationResponse(BaseModel):
    success: bool = True
    approval_request: ApprovalRequestDetailResponse
    version: int


class ApprovalRequestListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ApprovalRequestResponse] = []
