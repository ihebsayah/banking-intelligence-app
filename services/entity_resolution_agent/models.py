"""
services/entity_resolution_agent/models.py
Pydantic models for Entity Resolution Agent.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class EntityResolutionRequest(BaseModel):
    primary_entity: str  # e.g. "customer", "account", "transaction"
    tables: List[str]    # tables returned by Schema Agent
    schema_subset: Optional[Dict[str, Any]] = None  # optional schema context


class JoinPath(BaseModel):
    from_table: str
    to_table: str
    join_key: str        # e.g. "customer_id"
    join_type: str = "INNER JOIN"
    condition: str       # e.g. "customers.customer_id = accounts.customer_id"


class EntityResolutionResponse(BaseModel):
    primary_entity: str
    primary_key: str                      # e.g. "customer_id"
    primary_table: str                    # e.g. "customers"
    tables_containing_entity: List[str]   # tables that have the FK
    join_structure: List[JoinPath]        # ordered join paths
    resolution_confidence: float = 1.0
    notes: str = ""
