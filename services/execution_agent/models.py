"""
services/execution_agent/models.py
Pydantic models for the Execution Agent — Week 4.
Increment 3: Added plan metadata for verification pipeline.
Increment 3.1: Split status into execution_status, verification_status, retry_status.
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
    # Increment 3: plan metadata for verification
    expected_answer: Optional[Dict[str, Any]] = Field(default=None, description="ExpectedAnswer from QueryPlan")
    plan_metrics: Optional[List[str]] = Field(default=None, description="Metric aliases from QueryPlan")
    plan_dimensions: Optional[List[str]] = Field(default=None, description="Dimension columns from QueryPlan")
    plan_grain: Optional[Dict[str, Any]] = Field(default=None, description="GrainSpec from QueryPlan")


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
    # Increment 3: verification metadata
    verification: Optional[Dict[str, Any]] = None
    repairs_applied: int = 0
    refinements_applied: int = 0
    # Increment 3.1: split statuses
    execution_status: str = "success"    # success | error | timeout
    verification_status: str = "passed"  # passed | warning | critical | skipped
    retry_status: str = "none"           # none | retried | mechanical_repair | replan_requested
    # Increment 3.1: execution trace
    execution_trace: Optional[Dict[str, Any]] = None


class ExecutionResponse(BaseModel):
    """Response from /execute_query."""
    status: str                                 # success | error | rejected | repaired
    data: Any = None                            # list[dict] | str (csv/table) | None
    metadata: ExecutionMetadata
    message: Optional[str] = None
