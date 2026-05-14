"""
services/schema_agent/models.py
Pydantic models for the Schema Understanding Agent.
"""
from pydantic import BaseModel
from typing import List, Dict, Optional


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
