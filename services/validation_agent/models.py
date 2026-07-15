"""
services/validation_agent/models.py
Pydantic models for Validation Agent.

Phase 6B: Added semantic_warnings to carry non-blocking semantic layer checks
(unknown table, unsupported formula, suspicious join). Never affects 'safe' verdict.
"""
from typing import List, Optional, Any
from pydantic import BaseModel


class QueryValidationRequest(BaseModel):
    sql: str
    parameters: List[Any] = []
    user_role: str = "analyst"  # "analyst" | "admin" | "readonly"
    # Phase 6B: optional upstream semantic warnings to carry through
    upstream_semantic_warnings: List[str] = []
    request_id: Optional[str] = None
    nonce: Optional[str] = None


class QueryValidationResponse(BaseModel):
    safe: bool
    confidence: float          # 0.0–1.0
    issues: List[str]          # list of detected problems (security — may block)
    checks_passed: List[str]   # names of checks that passed
    checks_failed: List[str]   # names of checks that failed
    signature: Optional[str]   # HMAC signature if safe
    sanitized_sql: Optional[str] = None  # normalized SQL (for logging)
    # Phase 6B: non-blocking semantic observations (never cause safe=False)
    semantic_warnings: List[str] = []
