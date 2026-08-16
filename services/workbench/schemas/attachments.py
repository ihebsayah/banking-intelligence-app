from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class AttachmentResponse(BaseModel):
    attachment_id: str
    investigation_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    sha256_hash: str
    description: Optional[str] = None
    uploaded_by: str
    uploaded_at: datetime


class AttachmentListResponse(BaseModel):
    total: int
    items: List[AttachmentResponse]
