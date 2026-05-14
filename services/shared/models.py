"""
services/shared/models.py
Shared Pydantic data models used across all microservices.
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Any, Dict
from enum import Enum
import uuid


# ─── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ANALYST = "analyst"
    COMPLIANCE = "compliance"
    MANAGER = "manager"
    ADMIN = "admin"


class AuditStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    REJECTED = "rejected"
    PENDING = "pending"


class QueryStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


# ─── User & Auth Models ───────────────────────────────────────────────────────

class User(BaseModel):
    """Authenticated user context, populated from JWT claims."""
    user_id: str
    user_role: UserRole
    permissions: List[str] = Field(default_factory=list)

    class Config:
        use_enum_values = True


class TokenPayload(BaseModel):
    """JWT token payload claims."""
    sub: str                          # subject = user_id
    role: str                         # user role
    exp: Optional[int] = None         # expiry (unix timestamp)
    iat: Optional[int] = None         # issued at


class LoginRequest(BaseModel):
    """Login form body."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=1, max_length=100)


class LoginResponse(BaseModel):
    """Successful login response carrying the JWT."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    user_role: str
    expires_in: int = Field(description="Token TTL in seconds")


# ─── Audit Log Models ─────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    """
    Complete audit record written to the immutable audit_log table.
    Every API call or query execution produces one entry.
    """
    audit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    user_role: str
    action: str = Field(description="e.g. login, api_call, query_execute")
    query_intent: Optional[str] = None
    tables_accessed: Optional[List[str]] = None
    rows_accessed: int = 0
    execution_time_ms: int = 0
    status: AuditStatus = AuditStatus.SUCCESS
    ip_address: Optional[str] = None
    endpoint: Optional[str] = None
    http_method: Optional[str] = None
    query_signature: Optional[str] = None
    data_freshness: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        use_enum_values = True


class AuditLogResponse(BaseModel):
    """Response returned after a successful audit log INSERT."""
    logged: bool = True
    audit_id: str


# ─── Query Pipeline Models ────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """User query submitted to the orchestrator via API Gateway."""
    query: str = Field(..., min_length=3, max_length=2000)
    output_format: str = Field(default="json", pattern="^(json|csv|table)$")
    session_id: Optional[str] = None


class QueryResult(BaseModel):
    """Final result returned to the user after full pipeline execution."""
    status: QueryStatus
    data: Optional[List[Dict[str, Any]]] = None
    summary: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    audit_id: Optional[str] = None
    error: Optional[str] = None
    suggestions: Optional[List[str]] = None

    class Config:
        use_enum_values = True


# ─── Health Check Models ──────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Standard health check response for all services."""
    status: str = "healthy"
    service: str
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    checks: Optional[Dict[str, str]] = None
