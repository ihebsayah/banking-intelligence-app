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
