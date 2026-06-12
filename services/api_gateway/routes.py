"""
services/api_gateway/routes.py
Route definitions for the Banking Intelligence API Gateway.

Endpoints (existing):
  POST /auth/login   → authenticate, return JWT
  GET  /health       → liveness probe
  POST /query        → submit NL query through full pipeline

Portal Endpoints (new):
  Dashboard:   GET /dashboard/overview, /dashboard/kpis, /dashboard/recent-activity
               GET /dashboard/charts/{chart_id}
  KPI Center:  GET /kpi/catalog, /kpi/values, /kpi/trends, /kpi/metrics
  Risk Center: GET /risk/overview, /risk/flags, /risk/segments, /risk/summary
  Compliance:  GET /compliance/overview, /compliance/rules, /compliance/violations
               GET /audit/logs
  Reports:     GET /reports, POST /reports/generate
  Profile:     GET /users/me, GET /auth/me
  Admin:       GET /admin/users, /admin/roles, /admin/permissions

RBAC:
  - analyst/manager : dashboard, kpi, risk, reports
  - compliance      : compliance, audit
  - admin           : admin endpoints + all others
"""
import time
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from shared.config import get_settings
from shared.database import DatabaseConnector
from shared.errors import AuthenticationError, TokenExpiredError, InvalidTokenError
from shared.logger import get_logger
from shared.models import (
    AuditLogEntry,
    AuditLogResponse,
    AuditStatus,
    HealthResponse,
    LoginResponse,
    User,
    UserRole,
)
from auth import authenticate_user_db, create_access_token, verify_token

logger = get_logger(__name__, "api-gateway")
settings = get_settings()
router = APIRouter()
security = HTTPBearer(auto_error=False)

ORCHESTRATOR_URL = "http://orchestrator-agent:8001"


# ─── DB accessor helpers ──────────────────────────────────────────────────────

def _get_db(request: Request) -> Optional[DatabaseConnector]:
    return getattr(request.app.state, "db", None)


def _get_audit_db(request: Request) -> Optional[DatabaseConnector]:
    return getattr(request.app.state, "audit_db", None)


def _require_db(request: Request) -> DatabaseConnector:
    db = _get_db(request)
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "DB_UNAVAILABLE", "message": "Database connection not available"},
        )
    return db


def _require_audit_db(request: Request) -> DatabaseConnector:
    db = _get_audit_db(request)
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "AUDIT_DB_UNAVAILABLE", "message": "Audit database connection not available"},
        )
    return db


# ─── Request / Response Models ────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str
    format: str = "json"


class KPIMetric(BaseModel):
    kpi_id: str
    name: str
    value: float
    metric_type: str  # currency | percentage | count | ratio
    trend: float = 0.0
    trend_direction: str = "stable"  # up | down | stable
    last_updated: str
    data_freshness: str = "real-time"


class ChartDataPoint(BaseModel):
    label: str
    value: float


class ChartResponse(BaseModel):
    chart_id: str
    chart_type: str  # line | bar | pie | area
    title: str
    data: List[ChartDataPoint]
    last_updated: str


class DashboardOverview(BaseModel):
    total_customers: int
    total_accounts: int
    active_accounts: int
    total_deposits: float
    monthly_transactions: int
    high_risk_customers: int
    last_updated: str


class RecentActivity(BaseModel):
    transaction_id: str
    customer_id: str
    account_id: str
    amount: float
    transaction_type: str
    status: str
    description: str
    transaction_date: str


class RiskOverview(BaseModel):
    total_flags: int
    critical_flags: int
    high_flags: int
    medium_flags: int
    low_flags: int
    average_risk_score: float
    high_risk_customer_count: int
    kyc_incomplete_count: int
    last_updated: str


class RiskFlag(BaseModel):
    flag_id: str
    customer_id: str
    flag_type: str
    severity: str
    description: str
    resolved: bool
    created_at: str


class PaginatedRiskFlags(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[RiskFlag]


class RiskSegment(BaseModel):
    segment: str
    customer_count: int
    avg_risk_score: float
    total_balance: float


class ComplianceOverview(BaseModel):
    gdpr_status: str
    pci_status: str
    aml_alerts_count: int
    kyc_status: str
    active_violations_count: int
    total_rules: int
    enabled_rules: int
    last_updated: str


class ComplianceRule(BaseModel):
    rule_id: str
    rule_name: str
    regulation: str
    rule_type: str
    condition: str
    action: str
    enabled: bool
    created_at: str


class ComplianceViolation(BaseModel):
    violation_id: str
    query_id: Optional[str]
    user_id: Optional[str]
    violation_type: str
    severity: str
    description: str
    regulation: str
    detected_at: str
    status: str
    resolution_notes: Optional[str]


class AuditLogRow(BaseModel):
    id: str
    audit_id: str
    timestamp: str
    user_id: str
    user_role: str
    action: str
    status: str
    ip_address: Optional[str]
    endpoint: Optional[str]
    http_method: Optional[str]
    execution_time_ms: int
    error_message: Optional[str]


class PaginatedAuditLogs(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[AuditLogRow]


class Report(BaseModel):
    report_id: str
    report_type: str
    regulation: str
    report_period_start: Optional[str]
    report_period_end: Optional[str]
    generated_at: str
    status: str
    submitted_to: Optional[str]
    submitted_at: Optional[str]


class PaginatedReports(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[Report]


class ReportGenerateRequest(BaseModel):
    report_type: str = Field(..., description="e.g. aml_summary, kyc_status, transaction_volume")
    regulation: str = Field(..., description="e.g. AML, KYC, GDPR, PCI-DSS, SOX")
    period_start: Optional[date] = None
    period_end: Optional[date] = None


class AdminUserRow(BaseModel):
    user_id: str
    email: str
    name: Optional[str]
    role: str
    bank_id: str
    created_at: str
    last_login: str
    status: str


class RoleInfo(BaseModel):
    role: str
    user_count: int
    permissions: List[str]


class PermissionInfo(BaseModel):
    permission: str
    roles: List[str]
    description: str


# ─── Auth Dependency ──────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """FastAPI dependency — extracts and validates Bearer JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_REQUIRED", "message": "Authorization header missing"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id, user_role = verify_token(credentials.credentials)
        return User(user_id=user_id, user_role=user_role)
    except TokenExpiredError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.to_dict(),
                            headers={"WWW-Authenticate": "Bearer"})
    except InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.to_dict(),
                            headers={"WWW-Authenticate": "Bearer"})


# ─── RBAC Helper ─────────────────────────────────────────────────────────────

ROLE_GROUPS = {
    "business": {UserRole.ANALYST, UserRole.MANAGER, UserRole.ADMIN, "analyst", "manager", "admin"},
    "compliance": {UserRole.COMPLIANCE, UserRole.ADMIN, "compliance", "admin"},
    "admin": {UserRole.ADMIN, "admin"},
}


def require_roles(*roles: str):
    """Returns a dependency that enforces the user has one of the listed role group keys."""
    allowed: set = set()
    for r in roles:
        allowed |= ROLE_GROUPS.get(r, {r})

    async def _check(user: User = Depends(get_current_user)) -> User:
        role_val = user.user_role if isinstance(user.user_role, str) else user.user_role.value
        if role_val not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "INSUFFICIENT_PERMISSIONS",
                    "message": f"This endpoint requires one of: {list(roles)}",
                    "your_role": role_val,
                },
            )
        return user

    return _check


# ─── Internal helper: log to audit service ───────────────────────────────────

async def _send_audit_log(entry: AuditLogEntry) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{settings.AUDIT_AGENT_URL}/log_access",
                json=entry.model_dump(mode="json"),
            )
    except Exception as exc:
        logger.error("Failed to send audit log", extra={"audit_id": entry.audit_id, "error": str(exc)})


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _row_str(row: dict, key: str, default: Any = None) -> Optional[str]:
    val = row.get(key, default)
    if val is None:
        return default
    return str(val) if not isinstance(val, str) else val


# ═══════════════════════════════════════════════════════════════════════════════
# ─── EXISTING ROUTES ─────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse, summary="Liveness probe", tags=["monitoring"])
async def health() -> HealthResponse:
    return HealthResponse(service="api-gateway")


@router.post(
    "/auth/login",
    response_model=LoginResponse,
    summary="Authenticate and receive JWT",
    tags=["authentication"],
)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
) -> LoginResponse:
    start_time = time.monotonic()
    ip_address = request.client.host if request.client else "unknown"

    db = _get_db(request)
    user = await authenticate_user_db(username, password, db)
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    if not user:
        await _send_audit_log(AuditLogEntry(
            user_id=username, user_role="unknown", action="login",
            status=AuditStatus.REJECTED, ip_address=ip_address,
            endpoint="/auth/login", http_method="POST",
            execution_time_ms=elapsed_ms, error_message="Invalid credentials",
        ))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "AUTH_FAILED", "message": "Invalid username or password"},
        )

    token, expires_in = create_access_token(user.user_id, user.user_role)
    await _send_audit_log(AuditLogEntry(
        user_id=user.user_id, user_role=user.user_role, action="login",
        status=AuditStatus.SUCCESS, ip_address=ip_address,
        endpoint="/auth/login", http_method="POST", execution_time_ms=elapsed_ms,
    ))
    logger.info("User login successful", extra={"user_id": user.user_id, "role": user.user_role})
    return LoginResponse(access_token=token, user_id=user.user_id,
                         user_role=user.user_role, expires_in=expires_in)


@router.post("/query", summary="Submit natural language query", tags=["query"])
async def submit_query(
    request: Request,
    body: QueryRequest,
    user: User = Depends(get_current_user),
) -> dict:
    start_time = time.monotonic()
    ip_address = request.client.host if request.client else "unknown"
    logger.info("Query received", extra={"user_id": user.user_id, "role": user.user_role, "query": body.query[:80]})

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ORCHESTRATOR_URL}/process_query",
                json={"query": body.query, "user_role": user.user_role,
                      "user_id": user.user_id, "format": body.format},
            )
            pipeline_result = response.json()
    except httpx.TimeoutException:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        await _send_audit_log(AuditLogEntry(user_id=user.user_id, user_role=user.user_role,
            action="nl_query", status=AuditStatus.ERROR, ip_address=ip_address,
            endpoint="/query", http_method="POST", execution_time_ms=elapsed_ms,
            error_message="Orchestrator timeout"))
        raise HTTPException(status_code=504, detail={"error": "PIPELINE_TIMEOUT",
            "message": "Query pipeline timed out. Try a simpler query."})
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error("Orchestrator error: %s", exc, exc_info=True)
        await _send_audit_log(AuditLogEntry(user_id=user.user_id, user_role=user.user_role,
            action="nl_query", status=AuditStatus.ERROR, ip_address=ip_address,
            endpoint="/query", http_method="POST", execution_time_ms=elapsed_ms, error_message=str(exc)))
        raise HTTPException(status_code=503, detail={"error": "PIPELINE_UNAVAILABLE",
            "message": "Query pipeline is temporarily unavailable."})

    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    pipeline_status = pipeline_result.get("status", "unknown")
    audit_status = AuditStatus.SUCCESS if pipeline_status == "success" else AuditStatus.ERROR
    await _send_audit_log(AuditLogEntry(user_id=user.user_id, user_role=user.user_role,
        action="nl_query", status=audit_status, ip_address=ip_address,
        endpoint="/query", http_method="POST", execution_time_ms=elapsed_ms,
        metadata={"query": body.query[:200], "format": body.format, "pipeline_status": pipeline_status}))

    pipeline = pipeline_result.get("pipeline", {})
    pipeline_steps = []
    for step_name in ["intent", "schema", "entity_resolution", "sql", "validation", "compliance"]:
        if step_name in pipeline:
            step_data = pipeline[step_name]
            is_success = step_data and (isinstance(step_data, dict) and not step_data.get("error"))
            pipeline_steps.append({"agent": step_name, "status": "success" if is_success else "error", "response": step_data})
    if "results" in pipeline_result:
        pipeline_steps.append({"agent": "execution", "status": "success" if pipeline_result.get("status") == "success" else "error",
            "response": {"rows_returned": len(pipeline_result.get("results", []))}})
    if "insights" in pipeline_result and pipeline_result.get("insights"):
        pipeline_steps.append({"agent": "insights", "status": "success", "response": pipeline_result.get("insights")})

    return {
        "status": pipeline_result.get("status"),
        "results": pipeline_result.get("results"),
        "metadata": pipeline_result.get("metadata", {}),
        "pipeline_steps": pipeline_steps,
        "insights": pipeline_result.get("insights"),
        "message": pipeline_result.get("message"),
        "error": pipeline_result.get("error"),
        "request_id": pipeline_result.get("request_id"),
        "debug_url": pipeline_result.get("debug_url"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ─── DASHBOARD ENDPOINTS ──────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/dashboard/overview",
    response_model=DashboardOverview,
    summary="High-level dashboard financial overview",
    tags=["dashboard"],
)
async def dashboard_overview(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> DashboardOverview:
    db = _require_db(request)
    row = await db.fetch_one("""
        SELECT
            COUNT(DISTINCT c.customer_id)                                  AS total_customers,
            COUNT(DISTINCT a.account_id)                                   AS total_accounts,
            COUNT(DISTINCT CASE WHEN a.status = 'active' THEN a.account_id END) AS active_accounts,
            COALESCE(SUM(a.balance), 0)                                    AS total_deposits,
            (SELECT COUNT(*) FROM transactions
              WHERE transaction_date >= NOW() - INTERVAL '30 days')        AS monthly_transactions,
            COUNT(DISTINCT CASE WHEN c.risk_score >= 0.7 THEN c.customer_id END) AS high_risk_customers
        FROM customers c
        LEFT JOIN accounts a ON a.customer_id = c.customer_id
    """)
    if not row:
        row = {}
    return DashboardOverview(
        total_customers=row.get("total_customers", 0) or 0,
        total_accounts=row.get("total_accounts", 0) or 0,
        active_accounts=row.get("active_accounts", 0) or 0,
        total_deposits=float(row.get("total_deposits", 0) or 0),
        monthly_transactions=row.get("monthly_transactions", 0) or 0,
        high_risk_customers=row.get("high_risk_customers", 0) or 0,
        last_updated=_now_iso(),
    )


@router.get(
    "/dashboard/kpis",
    response_model=List[KPIMetric],
    summary="Computed dashboard KPI values from real tables",
    tags=["dashboard"],
)
async def dashboard_kpis(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> List[KPIMetric]:
    db = _require_db(request)

    stats = await db.fetch_one("""
        SELECT
            COALESCE(SUM(a.balance), 0)                                 AS total_deposits,
            COALESCE(SUM(CASE WHEN t.transaction_date >= NOW() - INTERVAL '30 days'
                         THEN ABS(t.amount) * 0.002 ELSE 0 END), 0)    AS monthly_revenue,
            COUNT(DISTINCT CASE WHEN a.status = 'active' THEN c.customer_id END) AS active_customers,
            COALESCE(AVG(c.risk_score), 0)                              AS avg_risk_score
        FROM customers c
        LEFT JOIN accounts a  ON a.customer_id = c.customer_id
        LEFT JOIN transactions t ON t.customer_id = c.customer_id
    """)
    if not stats:
        stats = {}

    # Prev-period totals for trend calculation (30-60 days ago)
    prev = await db.fetch_one("""
        SELECT COALESCE(SUM(ABS(amount)) * 0.002, 0) AS prev_revenue
        FROM transactions
        WHERE transaction_date BETWEEN NOW() - INTERVAL '60 days' AND NOW() - INTERVAL '30 days'
    """)
    prev_rev = float((prev or {}).get("prev_revenue", 0))
    curr_rev = float(stats.get("monthly_revenue", 0))
    rev_trend = round(((curr_rev - prev_rev) / prev_rev * 100) if prev_rev > 0 else 0, 2)

    now_iso = _now_iso()
    return [
        KPIMetric(
            kpi_id="total_deposits",
            name="Total Deposits",
            value=round(float(stats.get("total_deposits", 0)), 2),
            metric_type="currency",
            trend=2.3,  # static trend placeholder — real trend needs historical snapshot table
            trend_direction="up",
            last_updated=now_iso,
            data_freshness="real-time",
        ),
        KPIMetric(
            kpi_id="monthly_revenue",
            name="Monthly Fee Income",
            value=round(curr_rev, 2),
            metric_type="currency",
            trend=rev_trend,
            trend_direction="up" if rev_trend > 0 else ("down" if rev_trend < 0 else "stable"),
            last_updated=now_iso,
            data_freshness="real-time",
        ),
        KPIMetric(
            kpi_id="active_customers",
            name="Active Customers",
            value=float(stats.get("active_customers", 0)),
            metric_type="count",
            trend=0.0,
            trend_direction="stable",
            last_updated=now_iso,
            data_freshness="real-time",
        ),
        KPIMetric(
            kpi_id="avg_risk_score",
            name="Average Risk Score",
            value=round(float(stats.get("avg_risk_score", 0)), 4),
            metric_type="ratio",
            trend=0.0,
            trend_direction="stable",
            last_updated=now_iso,
            data_freshness="real-time",
        ),
    ]


@router.get(
    "/dashboard/recent-activity",
    response_model=List[RecentActivity],
    summary="Latest 10 transactions across all accounts",
    tags=["dashboard"],
)
async def dashboard_recent_activity(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    user: User = Depends(require_roles("business")),
) -> List[RecentActivity]:
    db = _require_db(request)
    rows = await db.fetch_all("""
        SELECT transaction_id, customer_id, account_id, amount,
               transaction_type, status, description, transaction_date
        FROM transactions
        ORDER BY transaction_date DESC
        LIMIT $1
    """, [limit])
    return [
        RecentActivity(
            transaction_id=r["transaction_id"],
            customer_id=r["customer_id"],
            account_id=r["account_id"],
            amount=float(r.get("amount", 0)),
            transaction_type=r.get("transaction_type", ""),
            status=r.get("status", ""),
            description=r.get("description", ""),
            transaction_date=str(r.get("transaction_date", "")),
        )
        for r in rows
    ]


@router.get(
    "/dashboard/charts/{chart_id}",
    response_model=ChartResponse,
    summary="Chart data by ID: revenue_trend | risk_levels | concentration | growth_rate",
    tags=["dashboard"],
)
async def dashboard_chart(
    chart_id: str,
    request: Request,
    user: User = Depends(require_roles("business")),
) -> ChartResponse:
    db = _require_db(request)
    now = _now_iso()

    if chart_id == "revenue_trend":
        rows = await db.fetch_all("""
            SELECT TO_CHAR(DATE_TRUNC('month', transaction_date), 'Mon') AS label,
                   ROUND(COALESCE(SUM(ABS(amount)) * 0.002, 0)::numeric, 2)  AS value
            FROM transactions
            WHERE transaction_date >= NOW() - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', transaction_date)
            ORDER BY DATE_TRUNC('month', transaction_date)
        """)
        return ChartResponse(chart_id=chart_id, chart_type="line",
            title="Monthly Fee Revenue Trend", data=[ChartDataPoint(label=r["label"], value=float(r["value"])) for r in rows],
            last_updated=now)

    elif chart_id == "risk_levels":
        rows = await db.fetch_all("""
            SELECT severity AS label, COUNT(*) AS value
            FROM risk_flags
            GROUP BY severity
            ORDER BY CASE severity WHEN 'low' THEN 1 WHEN 'medium' THEN 2 WHEN 'high' THEN 3 WHEN 'critical' THEN 4 END
        """)
        return ChartResponse(chart_id=chart_id, chart_type="pie",
            title="Risk Flag Distribution by Severity",
            data=[ChartDataPoint(label=r["label"].capitalize(), value=float(r["value"])) for r in rows],
            last_updated=now)

    elif chart_id == "concentration":
        rows = await db.fetch_all("""
            SELECT c.segment AS label, ROUND(SUM(a.balance)::numeric, 2) AS value
            FROM customers c
            JOIN accounts a ON a.customer_id = c.customer_id
            WHERE a.status = 'active'
            GROUP BY c.segment
            ORDER BY value DESC
            LIMIT 8
        """)
        return ChartResponse(chart_id=chart_id, chart_type="bar",
            title="Deposit Concentration by Segment",
            data=[ChartDataPoint(label=r["label"], value=float(r["value"])) for r in rows],
            last_updated=now)

    elif chart_id == "growth_rate":
        rows = await db.fetch_all("""
            SELECT TO_CHAR(DATE_TRUNC('month', created_at), 'Mon') AS label,
                   COUNT(*) AS value
            FROM customers
            WHERE created_at >= NOW() - INTERVAL '12 months'
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY DATE_TRUNC('month', created_at)
        """)
        return ChartResponse(chart_id=chart_id, chart_type="area",
            title="New Customer Growth",
            data=[ChartDataPoint(label=r["label"], value=float(r["value"])) for r in rows],
            last_updated=now)

    else:
        raise HTTPException(status_code=404, detail={"error": "CHART_NOT_FOUND",
            "message": f"Unknown chart_id '{chart_id}'. Valid: revenue_trend, risk_levels, concentration, growth_rate"})


# ═══════════════════════════════════════════════════════════════════════════════
# ─── KPI CENTER ───────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/kpi/catalog", summary="List KPI definitions", tags=["kpi"])
async def kpi_catalog(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> List[dict]:
    db = _require_db(request)
    rows = await db.fetch_all("SELECT * FROM kpi_definitions ORDER BY category, kpi_id")
    return [dict(r) for r in rows]


@router.get(
    "/kpi/values",
    response_model=List[KPIMetric],
    summary="Current computed values for all KPIs",
    tags=["kpi"],
)
async def kpi_values(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> List[KPIMetric]:
    """Re-uses the same logic as /dashboard/kpis but adds KYC rate and risk flag count."""
    db = _require_db(request)
    stats = await db.fetch_one("""
        SELECT
            COALESCE(SUM(a.balance), 0)                                              AS total_deposits,
            COALESCE(SUM(CASE WHEN t.transaction_date >= NOW() - INTERVAL '30 days'
                         THEN ABS(t.amount) * 0.002 ELSE 0 END), 0)                 AS monthly_revenue,
            COUNT(DISTINCT CASE WHEN a.status = 'active' THEN c.customer_id END)    AS active_customers,
            COALESCE(AVG(c.risk_score), 0)                                           AS avg_risk_score,
            ROUND(100.0 * COUNT(DISTINCT CASE WHEN c.kyc_verified THEN c.customer_id END)
                / NULLIF(COUNT(DISTINCT c.customer_id), 0), 2)                       AS kyc_compliance_rate
        FROM customers c
        LEFT JOIN accounts a  ON a.customer_id = c.customer_id
        LEFT JOIN transactions t ON t.customer_id = c.customer_id
    """)
    risk_count = await db.fetch_one("SELECT COUNT(*) AS total FROM risk_flags WHERE resolved = FALSE")
    now = _now_iso()
    s = stats or {}
    return [
        KPIMetric(kpi_id="total_deposits", name="Total Deposits",
            value=round(float(s.get("total_deposits", 0)), 2), metric_type="currency",
            trend=0.0, trend_direction="stable", last_updated=now),
        KPIMetric(kpi_id="monthly_revenue", name="Monthly Fee Income",
            value=round(float(s.get("monthly_revenue", 0)), 2), metric_type="currency",
            trend=0.0, trend_direction="stable", last_updated=now),
        KPIMetric(kpi_id="active_customers", name="Active Customers",
            value=float(s.get("active_customers", 0)), metric_type="count",
            trend=0.0, trend_direction="stable", last_updated=now),
        KPIMetric(kpi_id="avg_risk_score", name="Average Risk Score",
            value=round(float(s.get("avg_risk_score", 0)), 4), metric_type="ratio",
            trend=0.0, trend_direction="stable", last_updated=now),
        KPIMetric(kpi_id="kyc_compliance_rate", name="KYC Compliance Rate",
            value=round(float(s.get("kyc_compliance_rate", 0)), 2), metric_type="percentage",
            trend=0.0, trend_direction="stable", last_updated=now),
        KPIMetric(kpi_id="total_risk_flags", name="Open Risk Flags",
            value=float((risk_count or {}).get("total", 0)), metric_type="count",
            trend=0.0, trend_direction="stable", last_updated=now),
    ]


@router.get(
    "/kpi/metrics",
    response_model=List[KPIMetric],
    summary="KPI metrics (alias — same as /kpi/values, consumed by KpiPage)",
    tags=["kpi"],
)
async def kpi_metrics(request: Request, user: User = Depends(require_roles("business"))) -> List[KPIMetric]:
    return await kpi_values(request=request, user=user)


@router.get("/kpi/trends", summary="Monthly KPI trend data for charting", tags=["kpi"])
async def kpi_trends(
    request: Request,
    months: int = Query(default=12, ge=1, le=24),
    user: User = Depends(require_roles("business")),
) -> dict:
    db = _require_db(request)
    rows = await db.fetch_all("""
        SELECT
            TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS month,
            ROUND(SUM(ABS(amount)) * 0.002::numeric, 2)              AS fee_revenue,
            COUNT(*)                                                   AS transaction_count,
            ROUND(AVG(ABS(amount))::numeric, 2)                       AS avg_transaction_size
        FROM transactions
        WHERE transaction_date >= NOW() - ($1 || ' months')::INTERVAL
        GROUP BY DATE_TRUNC('month', transaction_date)
        ORDER BY DATE_TRUNC('month', transaction_date)
    """, [months])
    return {"months": months, "trends": [dict(r) for r in rows], "last_updated": _now_iso()}


# ═══════════════════════════════════════════════════════════════════════════════
# ─── RISK CENTER ──────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/risk/overview",
    response_model=RiskOverview,
    summary="High-level risk summary statistics",
    tags=["risk"],
)
async def risk_overview(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> RiskOverview:
    db = _require_db(request)
    flags = await db.fetch_one("""
        SELECT
            COUNT(*) FILTER (WHERE NOT resolved)                          AS total_flags,
            COUNT(*) FILTER (WHERE severity = 'critical' AND NOT resolved) AS critical_flags,
            COUNT(*) FILTER (WHERE severity = 'high'     AND NOT resolved) AS high_flags,
            COUNT(*) FILTER (WHERE severity = 'medium'   AND NOT resolved) AS medium_flags,
            COUNT(*) FILTER (WHERE severity = 'low'      AND NOT resolved) AS low_flags
        FROM risk_flags
    """)
    customers = await db.fetch_one("""
        SELECT
            COALESCE(AVG(risk_score), 0)                                   AS avg_risk,
            COUNT(*) FILTER (WHERE risk_score >= 0.7)                      AS high_risk_count,
            COUNT(*) FILTER (WHERE kyc_verified = FALSE)                   AS kyc_incomplete
        FROM customers
    """)
    f = flags or {}
    c = customers or {}
    return RiskOverview(
        total_flags=int(f.get("total_flags", 0) or 0),
        critical_flags=int(f.get("critical_flags", 0) or 0),
        high_flags=int(f.get("high_flags", 0) or 0),
        medium_flags=int(f.get("medium_flags", 0) or 0),
        low_flags=int(f.get("low_flags", 0) or 0),
        average_risk_score=round(float(c.get("avg_risk", 0) or 0), 4),
        high_risk_customer_count=int(c.get("high_risk_count", 0) or 0),
        kyc_incomplete_count=int(c.get("kyc_incomplete", 0) or 0),
        last_updated=_now_iso(),
    )


@router.get(
    "/risk/flags",
    response_model=PaginatedRiskFlags,
    summary="Paginated list of risk flags with optional severity filter",
    tags=["risk"],
)
async def risk_flags(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    severity: Optional[str] = Query(default=None, description="Filter: low | medium | high | critical"),
    resolved: Optional[bool] = Query(default=None, description="Filter by resolved status"),
    user: User = Depends(require_roles("business")),
) -> PaginatedRiskFlags:
    db = _require_db(request)
    offset = (page - 1) * page_size

    filters, params = [], []
    if severity:
        params.append(severity)
        filters.append(f"severity = ${len(params)}")
    if resolved is not None:
        params.append(resolved)
        filters.append(f"resolved = ${len(params)}")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""

    count_row = await db.fetch_one(f"SELECT COUNT(*) AS n FROM risk_flags {where}", params)
    total = int((count_row or {}).get("n", 0))

    params_with_paging = params + [page_size, offset]
    rows = await db.fetch_all(f"""
        SELECT id::text AS flag_id, customer_id, flag_type, severity,
               description, resolved, created_at
        FROM risk_flags
        {where}
        ORDER BY created_at DESC
        LIMIT ${len(params_with_paging) - 1} OFFSET ${len(params_with_paging)}
    """, params_with_paging)

    return PaginatedRiskFlags(
        total=total, page=page, page_size=page_size,
        items=[
            RiskFlag(
                flag_id=r["flag_id"], customer_id=r["customer_id"],
                flag_type=r.get("flag_type", ""), severity=r.get("severity", ""),
                description=r.get("description", ""), resolved=r.get("resolved", False),
                created_at=str(r.get("created_at", "")),
            ) for r in rows
        ],
    )


@router.get(
    "/risk/segments",
    response_model=List[RiskSegment],
    summary="Risk metrics grouped by customer segment",
    tags=["risk"],
)
async def risk_segments(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> List[RiskSegment]:
    db = _require_db(request)
    rows = await db.fetch_all("""
        SELECT c.segment,
               COUNT(DISTINCT c.customer_id)          AS customer_count,
               ROUND(AVG(c.risk_score)::numeric, 4)   AS avg_risk_score,
               ROUND(COALESCE(SUM(a.balance), 0)::numeric, 2) AS total_balance
        FROM customers c
        LEFT JOIN accounts a ON a.customer_id = c.customer_id AND a.status = 'active'
        GROUP BY c.segment
        ORDER BY avg_risk_score DESC
    """)
    return [
        RiskSegment(segment=r.get("segment", ""), customer_count=int(r.get("customer_count", 0)),
                    avg_risk_score=float(r.get("avg_risk_score", 0)),
                    total_balance=float(r.get("total_balance", 0)))
        for r in rows
    ]


@router.get(
    "/risk/summary",
    summary="Portfolio risk level distribution and average score",
    tags=["risk"],
)
async def risk_summary(
    request: Request,
    user: User = Depends(require_roles("business")),
) -> dict:
    db = _require_db(request)
    rows = await db.fetch_all("""
        SELECT severity, COUNT(*) AS n
        FROM risk_flags WHERE resolved = FALSE
        GROUP BY severity
    """)
    distribution = {r["severity"]: int(r["n"]) for r in rows}

    stats = await db.fetch_one("""
        SELECT
            COUNT(*) FILTER (WHERE risk_score >= 0.7)   AS high_risk_customers,
            COUNT(*) FILTER (WHERE risk_score >= 0.9)   AS critical_customers,
            COALESCE(AVG(risk_score), 0)                AS avg_risk_score
        FROM customers
    """)
    s = stats or {}
    return {
        "risk_level_distribution": distribution,
        "total_high_risk_customers": int(s.get("high_risk_customers", 0) or 0),
        "critical_alerts_count": int(s.get("critical_customers", 0) or 0),
        "average_risk_score": round(float(s.get("avg_risk_score", 0) or 0), 4),
        "last_updated": _now_iso(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ─── COMPLIANCE CENTER ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/compliance/overview",
    response_model=ComplianceOverview,
    summary="Regulatory compliance summary by regulation",
    tags=["compliance"],
)
async def compliance_overview(
    request: Request,
    user: User = Depends(require_roles("compliance")),
) -> ComplianceOverview:
    db = _require_db(request)
    rules = await db.fetch_one("""
        SELECT COUNT(*) AS total,
               COUNT(*) FILTER (WHERE enabled) AS enabled_count
        FROM compliance_rules
    """)
    violations = await db.fetch_one("""
        SELECT COUNT(*) AS total_violations,
               COUNT(*) FILTER (WHERE regulation = 'AML') AS aml_count
        FROM compliance_violations WHERE status = 'open'
    """)
    kyc_row = await db.fetch_one("""
        SELECT COUNT(*) FILTER (WHERE NOT kyc_verified) AS kyc_incomplete FROM customers
    """)

    r = rules or {}
    v = violations or {}
    k = kyc_row or {}
    aml_count = int(v.get("aml_count", 0) or 0)
    violations_total = int(v.get("total_violations", 0) or 0)
    kyc_incomplete = int(k.get("kyc_incomplete", 0) or 0)

    return ComplianceOverview(
        gdpr_status="compliant" if violations_total == 0 else "warning",
        pci_status="compliant",
        aml_alerts_count=aml_count,
        kyc_status="warning" if kyc_incomplete > 0 else "compliant",
        active_violations_count=violations_total,
        total_rules=int(r.get("total", 0) or 0),
        enabled_rules=int(r.get("enabled_count", 0) or 0),
        last_updated=_now_iso(),
    )


@router.get(
    "/compliance/report",
    summary="Compliance report (alias — consumed by CompliancePage)",
    tags=["compliance"],
)
async def compliance_report(
    request: Request,
    user: User = Depends(require_roles("compliance")),
) -> dict:
    overview = await compliance_overview(request=request, user=user)
    return overview.model_dump()


@router.get(
    "/compliance/rules",
    response_model=List[ComplianceRule],
    summary="Active compliance rules, optionally filtered by regulation",
    tags=["compliance"],
)
async def compliance_rules(
    request: Request,
    regulation: Optional[str] = Query(default=None, description="Filter: GDPR | PCI-DSS | SOX | AML | KYC"),
    enabled_only: bool = Query(default=True),
    user: User = Depends(require_roles("compliance")),
) -> List[ComplianceRule]:
    db = _require_db(request)
    params, filters = [], []
    if regulation:
        params.append(regulation)
        filters.append(f"regulation = ${len(params)}")
    if enabled_only:
        filters.append("enabled = TRUE")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    rows = await db.fetch_all(f"""
        SELECT id::text AS rule_id, rule_name, regulation, rule_type,
               condition, action, enabled, created_at
        FROM compliance_rules {where}
        ORDER BY regulation, rule_name
    """, params)
    return [
        ComplianceRule(rule_id=r["rule_id"], rule_name=r["rule_name"],
            regulation=r.get("regulation", ""), rule_type=r.get("rule_type", ""),
            condition=r.get("condition", ""), action=r.get("action", ""),
            enabled=r.get("enabled", True), created_at=str(r.get("created_at", "")))
        for r in rows
    ]


@router.get(
    "/compliance/violations",
    summary="Open compliance violations with date/regulation filters",
    tags=["compliance"],
)
async def compliance_violations(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    regulation: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="ISO date e.g. 2026-01-01"),
    date_to: Optional[str] = Query(default=None),
    user: User = Depends(require_roles("compliance")),
) -> dict:
    db = _require_db(request)
    offset = (page - 1) * page_size
    params, filters = [], []
    if regulation:
        params.append(regulation); filters.append(f"regulation = ${len(params)}")
    if severity:
        params.append(severity); filters.append(f"severity = ${len(params)}")
    if date_from:
        params.append(date_from); filters.append(f"detected_at >= ${len(params)}::timestamp")
    if date_to:
        params.append(date_to); filters.append(f"detected_at <= ${len(params)}::timestamp")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    count_row = await db.fetch_one(f"SELECT COUNT(*) AS n FROM compliance_violations {where}", params)
    total = int((count_row or {}).get("n", 0))
    params_paged = params + [page_size, offset]
    rows = await db.fetch_all(f"""
        SELECT id::text AS violation_id, query_id, user_id, violation_type,
               severity, description, regulation, detected_at, status, resolution_notes
        FROM compliance_violations {where}
        ORDER BY detected_at DESC
        LIMIT ${len(params_paged) - 1} OFFSET ${len(params_paged)}
    """, params_paged)
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {
                "violation_id": r["violation_id"], "query_id": r.get("query_id"),
                "user_id": r.get("user_id"), "violation_type": r.get("violation_type", ""),
                "severity": r.get("severity", ""), "description": r.get("description", ""),
                "regulation": r.get("regulation", ""), "detected_at": str(r.get("detected_at", "")),
                "status": r.get("status", ""), "resolution_notes": r.get("resolution_notes"),
            } for r in rows
        ],
    }


# ─── Audit Logs ───────────────────────────────────────────────────────────────

@router.get(
    "/audit/logs",
    response_model=PaginatedAuditLogs,
    summary="Paginated audit log entries from the audit database",
    tags=["audit"],
)
async def audit_logs(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    user_id_filter: Optional[str] = Query(default=None, alias="user_id"),
    action: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None, description="ISO timestamp"),
    date_to: Optional[str] = Query(default=None),
    user: User = Depends(require_roles("compliance")),
) -> PaginatedAuditLogs:
    audit_db = _require_audit_db(request)
    offset = (page - 1) * page_size
    params, filters = [], []
    if user_id_filter:
        params.append(user_id_filter); filters.append(f"user_id = ${len(params)}")
    if action:
        params.append(action); filters.append(f"action = ${len(params)}")
    if date_from:
        params.append(date_from); filters.append(f"timestamp >= ${len(params)}::timestamp")
    if date_to:
        params.append(date_to); filters.append(f"timestamp <= ${len(params)}::timestamp")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    count_row = await audit_db.fetch_one(f"SELECT COUNT(*) AS n FROM audit_log {where}", params)
    total = int((count_row or {}).get("n", 0))
    params_paged = params + [page_size, offset]
    rows = await audit_db.fetch_all(f"""
        SELECT id::text, audit_id, timestamp, user_id, user_role, action,
               status, ip_address, endpoint, http_method, execution_time_ms, error_message
        FROM audit_log {where}
        ORDER BY timestamp DESC
        LIMIT ${len(params_paged) - 1} OFFSET ${len(params_paged)}
    """, params_paged)
    return PaginatedAuditLogs(
        total=total, page=page, page_size=page_size,
        items=[
            AuditLogRow(
                id=str(r.get("id", "")), audit_id=r.get("audit_id", ""),
                timestamp=str(r.get("timestamp", "")), user_id=r.get("user_id", ""),
                user_role=r.get("user_role", ""), action=r.get("action", ""),
                status=r.get("status", ""), ip_address=r.get("ip_address"),
                endpoint=r.get("endpoint"), http_method=r.get("http_method"),
                execution_time_ms=int(r.get("execution_time_ms", 0) or 0),
                error_message=r.get("error_message"),
            ) for r in rows
        ],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ─── REPORTS CENTER ───────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/reports",
    response_model=PaginatedReports,
    summary="Paginated list of generated regulatory reports",
    tags=["reports"],
)
async def list_reports(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    regulation: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    user: User = Depends(require_roles("business")),
) -> PaginatedReports:
    db = _require_db(request)
    offset = (page - 1) * page_size
    params, filters = [], []
    if regulation:
        params.append(regulation); filters.append(f"regulation = ${len(params)}")
    if status_filter:
        params.append(status_filter); filters.append(f"status = ${len(params)}")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    count_row = await db.fetch_one(f"SELECT COUNT(*) AS n FROM regulatory_reports {where}", params)
    total = int((count_row or {}).get("n", 0))
    params_paged = params + [page_size, offset]
    rows = await db.fetch_all(f"""
        SELECT id::text AS report_id, report_type, regulation,
               report_period_start, report_period_end, generated_at,
               status, submitted_to, submitted_at
        FROM regulatory_reports {where}
        ORDER BY generated_at DESC
        LIMIT ${len(params_paged) - 1} OFFSET ${len(params_paged)}
    """, params_paged)
    return PaginatedReports(
        total=total, page=page, page_size=page_size,
        items=[
            Report(
                report_id=r["report_id"], report_type=r.get("report_type", ""),
                regulation=r.get("regulation", ""),
                report_period_start=str(r["report_period_start"]) if r.get("report_period_start") else None,
                report_period_end=str(r["report_period_end"]) if r.get("report_period_end") else None,
                generated_at=str(r.get("generated_at", "")), status=r.get("status", ""),
                submitted_to=r.get("submitted_to"),
                submitted_at=str(r["submitted_at"]) if r.get("submitted_at") else None,
            ) for r in rows
        ],
    )


@router.post(
    "/reports/generate",
    summary="Generate a new regulatory report from real aggregated data",
    tags=["reports"],
    status_code=status.HTTP_201_CREATED,
)
async def generate_report(
    body: ReportGenerateRequest,
    request: Request,
    user: User = Depends(require_roles("business")),
) -> dict:
    db = _require_db(request)

    # Build report content from real data
    if body.report_type in ("aml_summary", "transaction_volume"):
        data_rows = await db.fetch_all("""
            SELECT transaction_type, status,
                   COUNT(*) AS tx_count,
                   ROUND(SUM(ABS(amount))::numeric, 2) AS total_amount
            FROM transactions
            WHERE ($1::date IS NULL OR transaction_date >= $1::date)
              AND ($2::date IS NULL OR transaction_date <= $2::date)
            GROUP BY transaction_type, status
            ORDER BY total_amount DESC
        """, [str(body.period_start) if body.period_start else None,
              str(body.period_end) if body.period_end else None])
        import json
        content = json.dumps([dict(r) for r in data_rows], default=str)

    elif body.report_type == "kyc_status":
        data_rows = await db.fetch_all("""
            SELECT kyc_verified, segment, COUNT(*) AS customer_count,
                   ROUND(AVG(risk_score)::numeric, 4) AS avg_risk
            FROM customers
            GROUP BY kyc_verified, segment
            ORDER BY segment
        """)
        import json
        content = json.dumps([dict(r) for r in data_rows], default=str)

    elif body.report_type == "risk_exposure":
        data_rows = await db.fetch_all("""
            SELECT rf.severity, rf.flag_type, COUNT(*) AS flag_count,
                   ROUND(AVG(c.risk_score)::numeric, 4) AS avg_risk
            FROM risk_flags rf
            JOIN customers c ON c.customer_id = rf.customer_id
            WHERE rf.resolved = FALSE
            GROUP BY rf.severity, rf.flag_type
            ORDER BY rf.severity DESC
        """)
        import json
        content = json.dumps([dict(r) for r in data_rows], default=str)

    else:
        import json
        content = json.dumps({"message": f"Custom report type: {body.report_type}"})

    # Persist the report to regulatory_reports
    row = await db.fetch_one("""
        INSERT INTO regulatory_reports
            (report_type, regulation, report_period_start, report_period_end,
             report_content, status)
        VALUES ($1, $2, $3, $4, $5, 'draft')
        RETURNING id::text AS report_id, generated_at
    """, [
        body.report_type, body.regulation,
        str(body.period_start) if body.period_start else None,
        str(body.period_end) if body.period_end else None,
        content,
    ])

    r = row or {}
    return {
        "report_id": r.get("report_id", str(uuid.uuid4())),
        "report_type": body.report_type,
        "regulation": body.regulation,
        "status": "draft",
        "generated_at": str(r.get("generated_at", _now_iso())),
        "message": f"Report '{body.report_type}' generated successfully.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ─── PROFILE & AUTH/ME ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

async def _fetch_user_profile(user_id: str, db) -> dict:
    """Shared helper to fetch user profile from DB or return JWT-derived fallback."""
    if db:
        try:
            row = await db.fetch_one("""
                SELECT user_id, email, name, role, bank_id, created_at, last_login, status
                FROM users WHERE user_id = $1
            """, [user_id])
            if row:
                return {
                    "user_id": row["user_id"],
                    "email": row.get("email", f"{user_id}@bankintel.hq"),
                    "name": row.get("name", user_id),
                    "role": row["role"],
                    "bank_id": row.get("bank_id", "hq_main"),
                    "created_at": str(row.get("created_at", "")),
                    "last_login": str(row.get("last_login", "")),
                    "status": row.get("status", "active"),
                }
        except Exception as exc:
            logger.warning("Failed to fetch user profile from DB", extra={"error": str(exc)})

    # Fallback: derive from JWT claims
    return {
        "user_id": user_id,
        "email": f"{user_id}@bankintel.hq",
        "name": user_id.replace("_", " ").title(),
        "role": "analyst",
        "bank_id": "hq_main",
        "created_at": "",
        "last_login": _now_iso(),
        "status": "active",
    }


@router.get(
    "/users/me",
    summary="Current user profile from the users table",
    tags=["profile"],
)
async def get_user_me(request: Request, user: User = Depends(get_current_user)) -> dict:
    return await _fetch_user_profile(user.user_id, _get_db(request))


@router.get(
    "/auth/me",
    summary="Alias: current user profile (consumed by profileApi.ts)",
    tags=["profile"],
)
async def get_auth_me(request: Request, user: User = Depends(get_current_user)) -> dict:
    return await _fetch_user_profile(user.user_id, _get_db(request))


# ═══════════════════════════════════════════════════════════════════════════════
# ─── ADMIN CENTER ─────────────────────────────────────────════════════════════
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/admin/users",
    response_model=List[AdminUserRow],
    summary="All system users (admin only)",
    tags=["admin"],
)
async def admin_users(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    role_filter: Optional[str] = Query(default=None, alias="role"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    user: User = Depends(require_roles("admin")),
) -> List[AdminUserRow]:
    db = _require_db(request)
    offset = (page - 1) * page_size
    params, filters = [], []
    if role_filter:
        params.append(role_filter); filters.append(f"role = ${len(params)}")
    if status_filter:
        params.append(status_filter); filters.append(f"status = ${len(params)}")
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params_paged = params + [page_size, offset]
    rows = await db.fetch_all(f"""
        SELECT user_id, email, name, role, bank_id, created_at, last_login, status
        FROM users {where}
        ORDER BY created_at DESC
        LIMIT ${len(params_paged) - 1} OFFSET ${len(params_paged)}
    """, params_paged)
    return [
        AdminUserRow(user_id=r["user_id"], email=r.get("email", ""),
            name=r.get("name"), role=r["role"], bank_id=r.get("bank_id", "hq_main"),
            created_at=str(r.get("created_at", "")), last_login=str(r.get("last_login", "")),
            status=r.get("status", "active"))
        for r in rows
    ]


@router.get(
    "/admin/roles",
    response_model=List[RoleInfo],
    summary="System roles with user counts (admin only)",
    tags=["admin"],
)
async def admin_roles(
    request: Request,
    user: User = Depends(require_roles("admin")),
) -> List[RoleInfo]:
    db = _require_db(request)
    rows = await db.fetch_all("""
        SELECT role, COUNT(*) AS user_count
        FROM users
        GROUP BY role
        ORDER BY role
    """)

    ROLE_PERMISSIONS = {
        "analyst":    ["read:customers", "read:accounts", "read:transactions", "read:risk_flags"],
        "manager":    ["read:customers", "read:accounts", "read:transactions", "read:branch_data", "read:risk_summary"],
        "compliance": ["read:customers", "read:accounts", "read:transactions", "read:risk_flags", "read:audit_logs", "read:pii"],
        "admin":      ["read:customers", "read:accounts", "read:transactions", "read:risk_flags", "read:audit_logs", "read:pii", "admin:users", "admin:roles"],
    }
    return [
        RoleInfo(role=r["role"], user_count=int(r["user_count"]),
                 permissions=ROLE_PERMISSIONS.get(r["role"], []))
        for r in rows
    ]


@router.get(
    "/admin/permissions",
    response_model=List[PermissionInfo],
    summary="System permission definitions and which roles hold them (admin only)",
    tags=["admin"],
)
async def admin_permissions(
    request: Request,
    user: User = Depends(require_roles("admin")),
) -> List[PermissionInfo]:
    PERMISSIONS = [
        {"permission": "read:customers",     "roles": ["analyst", "manager", "compliance", "admin"], "description": "Read customer records"},
        {"permission": "read:accounts",      "roles": ["analyst", "manager", "compliance", "admin"], "description": "Read account data"},
        {"permission": "read:transactions",  "roles": ["analyst", "manager", "compliance", "admin"], "description": "Read transaction records"},
        {"permission": "read:risk_flags",    "roles": ["analyst", "compliance", "admin"],            "description": "Read risk flag entries"},
        {"permission": "read:branch_data",   "roles": ["manager", "admin"],                         "description": "Read branch metrics"},
        {"permission": "read:risk_summary",  "roles": ["manager", "admin"],                         "description": "Read aggregated risk summaries"},
        {"permission": "read:audit_logs",    "roles": ["compliance", "admin"],                       "description": "Read immutable audit logs"},
        {"permission": "read:pii",           "roles": ["compliance", "admin"],                       "description": "Access unmasked PII fields"},
        {"permission": "admin:users",        "roles": ["admin"],                                    "description": "Manage system users"},
        {"permission": "admin:roles",        "roles": ["admin"],                                    "description": "Manage role assignments"},
    ]
    return [PermissionInfo(**p) for p in PERMISSIONS]
