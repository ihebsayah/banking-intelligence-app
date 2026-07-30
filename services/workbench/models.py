"""Pydantic models for Phase 2B operational entities.

Maps 1:1 to tables created in 0004_add_operational_entities.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Alert(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    title: str
    description: Optional[str] = None
    source_rule_type: Optional[str] = None
    source_rule_id: Optional[str] = None
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[str] = None
    scope_id: str = "hq_main"
    status: str = "new"
    assigned_to: Optional[str] = None
    dismissed_reason: Optional[str] = None
    dismissed_at: Optional[datetime] = None
    dismissed_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    dismissal_approval_id: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Investigation(BaseModel):
    investigation_id: str
    title: str
    description: Optional[str] = None
    alert_id: Optional[str] = None
    scope_id: str = "hq_main"
    status: str = "open"
    priority: str = "medium"
    assigned_to: Optional[str] = None
    created_by: str
    findings_text: Optional[str] = None
    findings_refs: Optional[List[Any]] = None
    conclusion: Optional[str] = None
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    return_reason: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ComplianceCase(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = None
    alert_id: Optional[str] = None
    investigation_id: Optional[str] = None
    scope_id: str = "hq_main"
    status: str = "open"
    priority: str = "medium"
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
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Decision(BaseModel):
    decision_id: str
    case_id: str
    decision_type: str
    rationale: str
    decided_by: str
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    is_final: bool = False
    supersedes_decision_id: Optional[str] = None
    approval_id: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InformationRequest(BaseModel):
    ir_id: str
    case_id: str
    investigation_id: Optional[str] = None
    created_by: str
    assigned_to: str
    question: str
    due_date: Optional[date] = None
    status: str = "open"
    response_text: Optional[str] = None
    responded_at: Optional[datetime] = None
    acceptance_note: Optional[str] = None
    return_reason: Optional[str] = None
    accepted_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    accepted_by: Optional[str] = None
    returned_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    cancel_reason: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalRequest(BaseModel):
    approval_request_id: str
    action_type: str
    entity_type: str
    entity_id: str
    requested_by: str
    rationale: str
    required_approvals: int = 1
    approval_count: int = 0
    status: str = "pending"
    expires_at: datetime
    executed_at: Optional[datetime] = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalDecision(BaseModel):
    approval_decision_id: str
    approval_request_id: str
    approver_id: str
    decision: str
    rationale: Optional[str] = None
    decided_at: datetime = Field(default_factory=datetime.utcnow)


class Comment(BaseModel):
    comment_id: str
    entity_type: str
    entity_id: str
    content: str
    author_id: str
    is_internal: bool = False
    is_redacted: bool = False
    redacted_at: Optional[datetime] = None
    redacted_by: Optional[str] = None
    original_content_hash: Optional[str] = None
    redaction_reason: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ActivityTimelineEntry(BaseModel):
    timeline_id: str
    entity_type: str
    entity_id: str
    event_type: str
    actor_id: str
    old_value: Optional[Dict[str, Any]] = None
    new_value: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(BaseModel):
    notification_id: str
    user_id: str
    notification_type: str
    title: str
    body: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    is_read: bool = False
    read_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AssignmentHistoryEntry(BaseModel):
    history_id: str
    entity_type: str
    entity_id: str
    assigned_from: Optional[str] = None
    assigned_to: Optional[str] = None
    assigned_by: str
    reason: Optional[str] = None
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class IdempotencyRecord(BaseModel):
    idempotency_key: str
    request_method: str
    request_path: str
    request_body_sha256: str
    response_status: int
    response_body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditOutboxEvent(BaseModel):
    outbox_id: str
    idempotency_key: str
    event_type: str
    entity_type: str
    entity_id: str
    actor_id: str
    actor_role: str
    occurred_at: datetime
    payload: Dict[str, Any]
    payload_schema_ver: int = 1
    status: str = "pending"
    attempt_count: int = 0
    last_attempt_at: Optional[datetime] = None
    next_attempt_at: datetime = Field(default_factory=datetime.utcnow)
    last_error: Optional[str] = None
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    poison_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
