"""
services/sql_agent/plan_models.py
Pydantic models for QueryPlan, CompiledQuery, and analytical expressions.

Increment 2.6: CaseExpression, GrainSpec, fan-out detection, ExpectedAnswer.
Increment 3: MetricExecutionStrategy, ResultVerification, RepairAction,
             PlanRefinement metadata.
Increment 3.1: EmptyResultSemantics, VerificationSeverity, MetricValidationRules,
               PlanRepairRequest, ExecutionRetryPolicy, SQLMechanicalRepair.

Constraints:
  - Typed models throughout (no List[Dict] or Dict for plan structures)
  - schema_snapshot_id and semantic_metadata_version carried in both
    QueryPlan and CompiledQuery
  - Deterministic: same QueryPlan always yields same SQL/params/aliases
  - Compiler is a pure renderer (no inference)
"""
from typing import Dict, List, Optional, Literal, Union
from pydantic import BaseModel, Field


# ─── Column & join value objects ─────────────────────────────────────────────

class ColumnRef(BaseModel):
    """A validated column reference with its owning table."""
    table: str
    name: str

    @property
    def qualified(self) -> str:
        return f"{self.table}.{self.name}"


JoinCardinality = Literal["one_to_one", "many_to_one", "one_to_many", "many_to_many"]


class JoinSpec(BaseModel):
    """A registered, validated join between two tables."""
    from_table: str
    to_table: str
    join_type: Literal["INNER JOIN", "LEFT JOIN", "RIGHT JOIN"] = "INNER JOIN"
    join_key: str
    condition: str
    cardinality: JoinCardinality = "many_to_one"


# ─── Analytical expressions (typed) ─────────────────────────────────────────

class CaseExpression(BaseModel):
    """COUNT(CASE WHEN condition THEN 1 END) — conditional aggregation."""
    column: ColumnRef
    condition_column: str  # e.g. "kyc_verified"
    condition_value: object = True
    function: Literal["COUNT", "SUM"] = "COUNT"
    alias: str = ""

    def to_sql(self) -> str:
        val = repr(self.condition_value)
        inner = f"CASE WHEN {self.column.table}.{self.condition_column} = {val} THEN 1 END"
        return f"{self.function}({inner})"


class AggregateExpression(BaseModel):
    """COUNT, SUM, AVG, MIN, MAX over a column or COUNT(*)."""
    function: Literal["COUNT", "SUM", "AVG", "MIN", "MAX"]
    column: Optional[ColumnRef] = None  # None = COUNT(*)
    distinct: bool = False
    alias: str = ""

    def to_sql(self) -> str:
        col_sql = self.column.qualified if self.column else "*"
        distinct_kw = "DISTINCT " if self.distinct else ""
        func = self.function
        if func == "COUNT" and self.column is None:
            return "COUNT(*)"
        return f"{func}({distinct_kw}{col_sql})"


class RatioExpression(BaseModel):
    """numerator / denominator, optionally multiplied by 100 for percentages."""
    numerator: Union[AggregateExpression, CaseExpression]
    denominator: Union[AggregateExpression, CaseExpression]
    multiply_100: bool = False
    alias: str = ""
    aggregation_strategy: Literal[
        "same_relation", "independent_subqueries", "approved_metric_view"
    ] = "same_relation"

    def to_sql(self) -> str:
        num = self.numerator.to_sql()
        den = self.denominator.to_sql()
        expr = f"{num} / NULLIF({den}, 0)"
        if self.multiply_100:
            expr = f"ROUND(100.0 * {expr}, 2)"
        return expr


AnalyticalExpression = Union[AggregateExpression, RatioExpression, CaseExpression]


# ─── Grain specification ─────────────────────────────────────────────────────

class GrainSpec(BaseModel):
    """Tracks aggregation grain from source through to output."""
    source_table: str = ""
    source_grain: str = ""  # e.g. "row", "customer_id", "daily"
    aggregate_input_grain: str = ""  # grain of input to aggregate functions
    output_grain: str = ""  # grain of the result after GROUP BY
    temporal_grain: str = ""  # e.g. "daily", "monthly", "quarterly"
    identity_columns: List[str] = Field(default_factory=list)


# ─── Increment 3.1: ExpectedAnswer enums ─────────────────────────────────────

EmptyResultSemantics = Literal[
    "valid_no_match",       # empty result is acceptable (no matching data)
    "expect_scalar_zero",   # scalar should be 0 (e.g. count of nothing)
    "expect_scalar_null",   # scalar should be NULL
    "invalid",              # empty result is unexpected / error
]

VerificationSeverity = Literal["critical", "warning", "informational"]


# ─── Increment 3.1: MetricValidationRules ────────────────────────────────────

class MetricValidationRules(BaseModel):
    """Validation constraints for a metric value after execution."""
    value_type: Literal["numeric", "percentage", "ratio", "count"] = "numeric"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    nullable: bool = True
    finite_only: bool = True


# ─── Increment 3.1: Recovery models ─────────────────────────────────────────

class PlanRepairRequest(BaseModel):
    """Request to re-plan the query instead of repairing SQL.

    Produced by SQLMechanicalRepair when the error requires structural
    changes (removing tables, columns, or filters) that must go through
    the planner, not direct SQL mutation.
    """
    reason: str
    error_type: str
    requested_change: str  # e.g. "remove_table: fake_table"
    original_sql: str = ""
    original_error: str = ""


class ExecutionRetryPolicy(BaseModel):
    """Determines whether a transient error should trigger a retry."""
    max_retries: int = 1
    retryable_error_types: List[str] = Field(
        default_factory=lambda: ["deadlock", "timeout", "serialization_failure"]
    )

    def should_retry(self, error_type: str, attempt: int) -> bool:
        return attempt < self.max_retries and error_type in self.retryable_error_types


class SQLMechanicalRepair(BaseModel):
    """Semantics-preserving SQL fixes that do not alter query intent.

    Allowed repairs:
      - Add missing GROUP BY column
      - Fix unbalanced parentheses
      - Remove trailing semicolons

    Destructive repairs (removing JOINs, columns, filters) are NOT allowed;
    those produce PlanRepairRequest instead.
    """
    repair_id: str = ""
    description: str = ""
    repaired_sql: str = ""
    repair_type: str = ""  # "group_by_fix" | "syntax_fix" | "none"


# ─── Registered metric (from metric_registry) ────────────────────────────────

class MetricExecutionStrategy(BaseModel):
    """Metadata describing how a metric should be executed safely.

    Attributes:
      execution_strategy: how to run the metric
        - 'single_query': standard single-query with aggregation
        - 'independent_subqueries': separate aggregations joined at end
        - 'approved_metric_view': use a pre-built database view
      fan_out_safe: whether the metric's SQL is safe from join fan-out
      preaggregation_required: whether tables must be aggregated before joining
      allowed_join_patterns: which join cardinalities are safe for this metric
    """
    execution_strategy: Literal[
        "single_query", "independent_subqueries", "approved_metric_view"
    ] = "single_query"
    fan_out_safe: bool = True
    preaggregation_required: bool = False
    allowed_join_patterns: List[str] = Field(default_factory=lambda: ["many_to_one"])


class MetricReference(BaseModel):
    """An approved metric with its formula resolved from metric_registry."""
    metric_id: str
    alias: str
    formula: str
    source_tables: List[str] = Field(default_factory=list)
    grain_supported: bool = True
    execution_strategy: Optional[MetricExecutionStrategy] = None


# ─── Filter, time, sort ─────────────────────────────────────────────────────

class FilterSpec(BaseModel):
    """A single filter predicate to be rendered as WHERE ... = $N."""
    column: str
    operator: str
    value: object
    param_name: str = ""


class TimeRangeSpec(BaseModel):
    """Relative time constraint (e.g. last 30 days)."""
    type: Literal["relative", "none"] = "none"
    value: Optional[str] = None


class SortSpec(BaseModel):
    """ORDER BY specification."""
    column: str
    direction: Literal["ASC", "DESC"] = "ASC"


# ─── ExpectedAnswer ──────────────────────────────────────────────────────────

class ExpectedAnswer(BaseModel):
    """Describes the expected shape of the query result."""
    answer_type: str = ""  # scalar | detail_rows | grouped_rows | ranked_list | time_series | comparison | distribution
    expected_grain: List[str] = Field(default_factory=list)
    expected_metrics: List[str] = Field(default_factory=list)
    expected_dimensions: List[str] = Field(default_factory=list)
    ordering: Optional[str] = None
    aggregation_required: bool = False
    expected_columns: List[str] = Field(default_factory=list)
    # Increment 3.1: empty-result semantics
    empty_result_semantics: EmptyResultSemantics = "invalid"
    # Increment 3.1: per-metric validation rules
    metric_validation_rules: Dict[str, MetricValidationRules] = Field(default_factory=dict)


# ─── QueryPlan ────────────────────────────────────────────────────────────────

class QueryPlan(BaseModel):
    """
    Fully validated, deterministic query plan.

    The same QueryPlan instance always compiles to identical SQL,
    parameters, and column aliases.
    """
    # Identity & versioning
    schema_snapshot_id: str
    semantic_metadata_version: str

    # Intent
    task: str
    query_text: str = ""

    # Schema selection (from SchemaSelectionResponse)
    selected_tables: List[str]
    bridge_tables: List[str] = Field(default_factory=list)
    selected_columns: dict = Field(default_factory=dict)

    # Joins (validated against join_registry)
    joins: List[JoinSpec] = Field(default_factory=list)

    # Output projection (plain columns)
    requested_columns: List[ColumnRef] = Field(default_factory=list)

    # Registered metric formulas (from metric_registry)
    metrics: List[MetricReference] = Field(default_factory=list)

    # Implicit analytical expressions (resolved by builder from language)
    analytical_expressions: List[AnalyticalExpression] = Field(default_factory=list)

    # Grain tracking
    grain: Optional[GrainSpec] = None

    # Dimensions (for GROUP BY)
    dimensions: List[ColumnRef] = Field(default_factory=list)

    # Filters (each value will be bound as a parameter)
    filters: List[FilterSpec] = Field(default_factory=list)

    # Time constraint
    time_range: TimeRangeSpec = Field(default_factory=TimeRangeSpec)

    # Sort & limit
    sort: Optional[SortSpec] = None
    limit: int = 100

    # Expected answer shape (populated by builder)
    expected_answer: Optional[ExpectedAnswer] = None

    # Fan-out risk (set by builder when joins may duplicate fact rows)
    fan_out_risk: bool = False

    # Validation state
    missing_requested_fields: List[str] = Field(default_factory=list)
    unsupported_reason: Optional[str] = None


# ─── CompiledQuery ────────────────────────────────────────────────────────────

class BoundParameter(BaseModel):
    """A single bound parameter for asyncpg execution ($N convention)."""
    position: int
    value: object
    type: str  # "string" | "integer" | "float" | "boolean" | "date"


class CompiledQuery(BaseModel):
    """
    Output of DeterministicSQLCompiler.

    Contains parameterized SQL using asyncpg $N placeholders,
    ready for direct execution by query_executor.py.
    """
    sql: str
    parameters: List[BoundParameter] = Field(default_factory=list)
    tables_used: List[str] = Field(default_factory=list)
    column_aliases: dict = Field(default_factory=dict)
    schema_snapshot_id: str = ""
    semantic_metadata_version: str = ""
    description: str = ""


# ─── Increment 3: Result verification ───────────────────────────────────────

class VerificationCheck(BaseModel):
    """A single verification check result."""
    check_name: str
    passed: bool
    expected: str = ""
    actual: str = ""
    message: str = ""
    severity: VerificationSeverity = "warning"


class ResultVerification(BaseModel):
    """Verification result comparing dataset against ExpectedAnswer."""
    verified: bool
    checks: List[VerificationCheck] = Field(default_factory=list)
    row_count: int = 0
    column_count: int = 0
    repair_suggestions: List[str] = Field(default_factory=list)
    # Increment 3.1: severity summary
    critical_failures: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    informational: List[str] = Field(default_factory=list)


# ─── Increment 3: Repair actions ────────────────────────────────────────────

class RepairAction(BaseModel):
    """A single repair action to fix a failed query."""
    action_type: Literal[
        "add_group_by", "add_distinct", "add_where",
        "switch_subquery", "add_limit", "fix_null_filter",
        "retry_with_timeout",
        "plan_repair_request",  # Increment 3.1: destructive change → replan
    ]
    description: str
    plan_delta: dict = Field(default_factory=dict)
    is_destructive: bool = False  # Increment 3.1: true if removes tables/columns/filters


class PGRepairEngine(BaseModel):
    """Post-execution repair engine result."""
    repaired: bool
    original_error: str = ""
    repairs_applied: List[RepairAction] = Field(default_factory=list)
    retried_sql: str = ""
    # Increment 3.1: recovery splitting
    retry_attempted: bool = False
    mechanical_repair: Optional[SQLMechanicalRepair] = None
    plan_repair_request: Optional[PlanRepairRequest] = None


# ─── Increment 3: Plan refinement ───────────────────────────────────────────

class PlanRefinement(BaseModel):
    """Advisory refinement proposal for a QueryPlan after verification failure.

    Increment 3.1: Only produces proposals — never auto-applies changes.
    Caller must decide whether to accept each proposal.
    """
    reason: str
    original_plan_summary: str = ""
    refined_plan_summary: str = ""
    changes: List[str] = Field(default_factory=list)
    proposals: List[Dict[str, str]] = Field(default_factory=list)  # advisory-only


# ─── Increment 3: Execution trace ───────────────────────────────────────────

class ExecutionTrace(BaseModel):
    """Full trace of the execution lifecycle for debugging."""
    plan_hash: str = ""
    compiled_sql_length: int = 0
    original_sql_hash: str = ""  # SHA-256 of original compiled SQL
    attempted_sql_hash: str = ""  # SHA-256 of SQL after mechanical repair
    execution_time_ms: float = 0.0
    rows_returned: int = 0
    verification_passed: bool = False
    repairs_count: int = 0
    refinements_count: int = 0
    total_time_ms: float = 0.0
    retry_reason: str = ""  # why a retry was triggered
    mechanical_repair_id: str = ""  # ID of SQLMechanicalRepair applied
    critical_failures: List[str] = Field(default_factory=list)
    replanning_request: Optional[PlanRepairRequest] = None
    metadata_version: str = "3.1"
