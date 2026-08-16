from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class InformationRequestStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESPONDED = "responded"
    ACCEPTED = "accepted"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class CreateInformationRequest(BaseModel):
    assigned_to: str
    question: str = Field(min_length=1)
    due_date: Optional[date] = None
    expected_case_version: Optional[int] = Field(default=None, ge=1)
    expected_investigation_version: Optional[int] = Field(default=None, ge=1)
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None


class AcknowledgeInformationRequest(BaseModel):
    expected_version: int = Field(ge=1)


class RespondInformationRequest(BaseModel):
    response_text: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class AcceptInformationRequest(BaseModel):
    acceptance_note: Optional[str] = None
    expected_version: int = Field(ge=1)


class ReturnInformationRequest(BaseModel):
    return_reason: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class CancelInformationRequest(BaseModel):
    cancel_reason: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class InformationRequestResponse(BaseModel):
    ir_id: str
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None
    created_by: str
    assigned_to: str
    question: str
    due_date: Optional[date] = None
    status: str
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
    version: int
    created_at: datetime
    updated_at: datetime


class InformationRequestAdminView(BaseModel):
    """Restricted view for admin — never exposes request/response content.

    Deliberately omits `question`, `assigned_to`, `response_text`,
    `acceptance_note`, `return_reason`, and `cancel_reason`.
    """

    ir_id: str
    case_id: Optional[str] = None
    investigation_id: Optional[str] = None
    created_by: str
    due_date: Optional[date] = None
    status: str
    responded_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    accepted_by: Optional[str] = None
    returned_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancelled_by: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class InformationRequestMutationResponse(BaseModel):
    success: bool = True
    information_request: Union[InformationRequestResponse, InformationRequestAdminView]
    version: int


class InformationRequestListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Union[InformationRequestResponse, InformationRequestAdminView]] = []
