"""
services/sql_agent/models.py
Pydantic models for SQL Generation Agent.

Phase 6B: Added detected_kpis (from intent agent) + semantic_warnings + semantic_trace
to carry metric injection results and join validation notes.
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
    # Phase 6B: KPIs detected by intent agent — used to inject metric_registry formulas
    detected_kpis: Optional[List[str]] = None


class SQLGenerationResponse(BaseModel):
    sql: str                    # parameterized SQL with ? placeholders
    parameters: List[Parameter] # bound parameters in order
    description: str            # human-readable description
    estimated_rows: int
    estimated_time_ms: int
    tables_used: List[str]
    is_parameterized: bool = True   # always True from this service
    # Phase 6B: non-blocking semantic notes (never cause errors)
    semantic_warnings: List[str] = []   # join paths skipped (not in registry), etc.
    semantic_trace: List[str] = []      # metric formulas injected, path resolutions
