"""
services/schema_agent/models.py
Pydantic models for the Schema Understanding Agent.
"""
from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class SchemaMappingRequest(BaseModel):
    intent_categories: List[str]    # e.g. ["customer_analysis", "risk_analysis"]
    primary_entity: Optional[str] = None  # "customer" | "account" | "transaction" | …


class JoinPath(BaseModel):
    from_table: str
    to_table: str
    join_key: str
    join_type: str   # "INNER JOIN" | "LEFT JOIN"


class SchemaMappingResponse(BaseModel):
    relevant_domains: List[str]
    tables: List[str]
    key_columns: Dict
    join_paths: List[JoinPath]
    table_explanations: Optional[Dict[str, str]] = None
    confidence_scores: Optional[Dict[str, float]] = None


class SchemaSelectionRequest(BaseModel):
    query: str
    language: str = "en"
    domain: str
    task: str
    metrics: List[str] = []
    dimensions: List[str] = []
    filters_structured: List[Dict] = []
    limit_requested: Optional[int] = None
    requested_fields: List[str] = []



class SchemaSelectionResponse(BaseModel):
    candidate_tables: List[str]
    selected_tables: List[str]
    bridge_tables: List[str]
    excluded_tables: List[str]
    selected_columns: Dict[str, List[str]]
    join_paths: List[JoinPath]
    selection_reasons: Dict[str, str]
    confidence_scores: Dict[str, float]
    schema_confidence: float
    semantic_metadata_version: str
    schema_snapshot_id: str
    table_provenance: Dict[str, Dict[str, Any]] = {}
    column_provenance: Dict[str, Dict[str, Any]] = {}
    join_provenance: Dict[str, Dict[str, Any]] = {}
    missing_requested_fields: List[str] = []
    unsupported_reason: Optional[str] = None


