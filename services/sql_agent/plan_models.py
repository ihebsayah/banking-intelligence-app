"""
services/sql_agent/plan_models.py
Pydantic models for QueryPlan, CompiledQuery, and analytical expressions.

Increment 2.6: Adds CaseExpression (conditional aggregation), GrainSpec
(grain tracking), entity-aware join cardinality, fan-out risk detection,
RatioExpression aggregation strategy, expanded ExpectedAnswer types.

Constraints:
  - Typed models throughout (no List[Dict] or Dict for plan structures)
  - schema_snapshot_id and semantic_metadata_version carried in both
    QueryPlan and CompiledQuery
  - Deterministic: same QueryPlan always yields same SQL/params/aliases
  - Compiler is a pure renderer (no inference)
"""
from typing import List, Optional, Literal, Union
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


# ─── Registered metric (from metric_registry) ────────────────────────────────

class MetricReference(BaseModel):
    """An approved metric with its formula resolved from metric_registry."""
    metric_id: str
    alias: str
    formula: str
    source_tables: List[str] = Field(default_factory=list)
    grain_supported: bool = True


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
