from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class ComplianceRequest(BaseModel):
    user_id: str
    user_role: str
    query_intent: str
    tables: List[str] = []
    columns: List[str] = []


class Violation(BaseModel):
    rule: str
    severity: str          # critical, high, medium, low
    reason: str
    regulation: str = ""


class MaskingRule(BaseModel):
    column: str
    mask_type: str         # MASK_VALUE, MASK_LAST4, TOKENIZE
    regulation: str


class ComplianceResponse(BaseModel):
    compliant: bool
    violations: List[Violation] = []
    masking_required: List[MaskingRule] = []
    regulations_checked: List[str] = []
    user_role: str = ""
    message: str = ""
