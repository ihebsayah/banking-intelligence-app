"""
services/intent_agent/models.py
Pydantic models for the Intent Recognition Agent.
"""
from pydantic import BaseModel
from typing import List, Optional, Dict


class IntentRequest(BaseModel):
    query: str


class AmbiguityItem(BaseModel):
    question: str
    description: str


class IntentResponse(BaseModel):
    primary_category: str
    secondary_categories: List[str]
    confidence: float          # 0.0 – 1.0
    explicit_constraints: Dict
    ambiguities: List[str]
    requires_clarification: bool
    detected_kpis: Optional[List[str]] = None

    # Phase 6C extensions (optional for backward compatibility)
    language: Optional[str] = None
    domain: Optional[str] = None
    task: Optional[str] = None
    metrics: Optional[List[str]] = None
    dimensions: Optional[List[str]] = None
    filters_structured: Optional[List[Dict]] = None
    time_range: Optional[Dict] = None
    sort_structured: Optional[List[Dict]] = None
    limit_requested: Optional[int] = None
    intent_confidence: Optional[float] = None
    entity_confidence: Optional[float] = None
    metric_confidence: Optional[float] = None
    clarification_question: Optional[str] = None
    requested_fields: Optional[List[str]] = None

    # Request-gating fields
    supported_capability: Optional[bool] = True
    risk_level: Optional[str] = "safe"  # safe | suspicious | adversarial
    rejection_reason: Optional[str] = None

    # Step 11 hardening (additive, backward-compatible)
    intent_evidence_score: Optional[float] = None  # calibrated certainty, not density
    ambiguity_codes: Optional[List[str]] = None    # machine-readable reason codes
    decision: Optional[str] = None                 # AUTO_ACCEPT | CLARIFY | REJECT
    top1_score: Optional[int] = None
    top2_score: Optional[int] = None
    absolute_margin: Optional[int] = None
    relative_margin: Optional[float] = None


