"""
services/validation_agent/models.py
Pydantic models for Validation Agent.
"""
from typing import List, Optional, Any
from pydantic import BaseModel


class QueryValidationRequest(BaseModel):
    sql: str
    parameters: List[Any] = []
    user_role: str = "analyst"  # "analyst" | "admin" | "readonly"


class QueryValidationResponse(BaseModel):
    safe: bool
    confidence: float          # 0.0–1.0
    issues: List[str]          # list of detected problems
    checks_passed: List[str]   # names of checks that passed
    checks_failed: List[str]   # names of checks that failed
    signature: Optional[str]   # HMAC signature if safe
    sanitized_sql: Optional[str] = None  # normalized SQL (for logging)
