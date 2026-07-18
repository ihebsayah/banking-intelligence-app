"""
services/shared/provenance.py
Shared Provenance model to track meta-information and confidence signals.
"""
from typing import Optional
from pydantic import BaseModel

class Provenance(BaseModel):
    source: str      # "metric_registry" | "business_glossary" | "column_metadata" | "join_registry" | "table_metadata" | "intent_inference" | "domain_mapping" | "entity_resolution"
    confidence: float
    reason: str      # e.g., "Synonym match: 'créances douteuses' -> 'NPL'"
    matched_term: Optional[str] = None
