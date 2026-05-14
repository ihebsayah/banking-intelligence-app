"""
services/sql_agent/models.py
Pydantic models for SQL Generation Agent.
"""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel


class Parameter(BaseModel):
    name: str           # e.g. "balance_threshold"
    value: Any          # the bound value
    type: str           # "string" | "integer" | "float" | "boolean"


class JoinPathInput(BaseModel):
    from_table: str
    to_table: str
    join_key: str
    join_type: str = "INNER JOIN"
    condition: str      # e.g. "customers.customer_id = accounts.customer_id"


class SQLGenerationRequest(BaseModel):
    intent: str                         # "retrieve" | "aggregate" | "filter" | ...
    primary_entity: str                 # "customer" | "account" | ...
    tables: List[str]                   # tables to include
    join_paths: List[JoinPathInput] = []
    filters: Optional[Dict[str, Any]] = None   # {"balance": {">": 1000}}
    group_by: Optional[List[str]] = None
    order_by: Optional[str] = None
    limit: Optional[int] = 100
    columns: Optional[List[str]] = None  # specific columns, or None = *


class SQLGenerationResponse(BaseModel):
    sql: str                    # parameterized SQL with ? placeholders
    parameters: List[Parameter] # bound parameters in order
    description: str            # human-readable description
    estimated_rows: int
    estimated_time_ms: int
    tables_used: List[str]
    is_parameterized: bool = True  # always True from this service
