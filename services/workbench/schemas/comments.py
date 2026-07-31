"""Pydantic schemas for comment endpoints (CM1-CM3)."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Union

from pydantic import BaseModel, Field


class CreateCommentRequest(BaseModel):
    content: str = Field(min_length=1)
    is_internal: bool = False


class RedactCommentRequest(BaseModel):
    redact_reason: str = Field(min_length=1)
    expected_version: int = Field(ge=1)


class CommentResponse(BaseModel):
    comment_id: str
    entity_type: str
    entity_id: str
    content: str
    author_id: str
    is_internal: bool
    is_redacted: bool
    redacted_at: Optional[datetime] = None
    redacted_by: Optional[str] = None
    redaction_reason: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class CommentMetadataView(BaseModel):
    """Admin view for internal comments — existence metadata, never content.

    Mirrors the InformationRequestAdminView convention: admin holds
    `comment:view_metadata` (not `comment:view_internal_content`), so internal
    comment text is deliberately omitted from this serialisation.
    """

    comment_id: str
    entity_type: str
    entity_id: str
    author_id: str
    is_internal: bool
    is_redacted: bool
    redacted_at: Optional[datetime] = None
    redacted_by: Optional[str] = None
    version: int
    created_at: datetime
    updated_at: datetime


class CommentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Union[CommentResponse, CommentMetadataView]] = []


class CommentMutationResponse(BaseModel):
    success: bool = True
    comment: Union[CommentResponse, CommentMetadataView]
    version: int
