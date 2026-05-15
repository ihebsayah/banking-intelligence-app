"""
services/execution_agent/models.py
Pydantic models for the Execution Agent — Week 4.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionRequest(BaseModel):
    """Input to /execute_query."""
    sql: str = Field(..., description="Validated, parameterized SQL query")
    parameters: List[Any] = Field(default_factory=list, description="Positional query params")
    signature: str = Field(..., description="HMAC signature from validation agent")
    user_role: str = Field(default="analyst", description="Role: analyst|manager|compliance|customer")
    format: str = Field(default="json", description="Output format: json|csv|table")
    user_id: Optional[str] = Field(default=None, description="User ID for row-level filters")


class ExecutionMetadata(BaseModel):
    """Metadata attached to every query result."""
    rows_returned: int
    execution_time_ms: float
    data_freshness: str = "real-time"           # real-time | cached
    source: str = "database"                    # database | cache
    columns_masked: List[str] = Field(default_factory=list)
    user_role: str = "analyst"
    query_hash: Optional[str] = None
    error: Optional[str] = None


class ExecutionResponse(BaseModel):
    """Response from /execute_query."""
    status: str                                 # success | error | rejected
    data: Any = None                            # list[dict] | str (csv/table) | None
    metadata: ExecutionMetadata
    message: Optional[str] = None
