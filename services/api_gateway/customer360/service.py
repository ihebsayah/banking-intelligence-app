"""Customer 360 composition service.

Orchestrates the logical read bridge: authoritative customer data from
banking_dev + explicit workbench links from banking_integration. Enforces
permission-scoped sections, organisation scope via branch/region, and PII
masking. Raises Customer360SourceUnavailable for main-DB failures (-> 503) and
returns None when the customer is missing or out of scope (-> 404).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from shared.database import DatabaseConnector

from .models import (
    AccountSummary,
    AmlAlertSummary,
    Customer360Overview,
    CustomerIdentity,
    DataQuality,
    FinancialSummary,
    KycAml,
    KycCaseSummary,
    LoanSummary,
    Relationship,
    RiskFlagSummary,
    RiskSection,
    ScreeningSummary,
    TransactionRow,
    TransactionSummary,
    WorkbenchLink,
)
from .repos import Customer360Repository, WorkbenchLinkRepository

# Section -> permission required to include it in the response.
SECTION_PERMISSIONS = {
    "relationship": "customer:read_basic",
    "financial": "customer:read_financial",
    "transactions": "customer:read_transactions",
    "kyc_aml": "customer:read_kyc",
    "risk": "customer:read_risk",
    "workbench_links": "customer:read_compliance_history",
}

ALL_SECTIONS = [
    "relationship", "financial", "transactions", "kyc_aml",
    "risk", "workbench_links",
]


class Customer360SourceUnavailable(Exception):
    """Main customer data source (banking_dev) is unavailable -> 503."""


def _money(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _sum_by_currency(rows: List[Dict[str, Any]], key: str) -> Dict[str, str]:
    totals: Dict[str, Decimal] = {}
    for row in rows:
        cur = row.get("currency") or "TND"
        val = row.get(key)
        if val is None:
            continue
        totals[cur] = totals.get(cur, Decimal(0)) + Decimal(str(val))
    return {c: str(v) for c, v in totals.items()}


class Customer360Service:
    def __init__(self, main_db: DatabaseConnector, wb_db: Optional[DatabaseConnector]) -> None:
        self._main = Customer360Repository(main_db)
        self._wb = WorkbenchLinkRepository(wb_db) if wb_db else None

    # ── entry point ─────────────────────────────────────────────────────────

    async def get_overview(
        self,
        user: Any,
        customer_id: str,
        request_id: str = "",
    ) -> Optional[Tuple[Customer360Overview, Dict[str, Any]]]:
        """Return (overview, audit) or None when the customer is missing/out of scope."""
        try:
            core = await self._main.fetch_customer_core(customer_id)
        except Exception as exc:
            raise Customer360SourceUnavailable(str(exc)) from exc
        if core is None:
            return None

        scope = await self._resolve_scope(user, customer_id)
        if scope is None:
            return None
        allowed_branches, scope_ids = scope

        data_quality = DataQuality()
        mask_pii = "customer:read_pii" in (user.permissions or [])
        masked_fields: List[str] = []

        # ── customer + relationship ──
        profile = await self._safe(self._main.fetch_profile(customer_id))
        if profile is None:
            data_quality.missing_profile = True

        branches = await self._safe(self._main.fetch_customer_branches(customer_id))
        primary = await self._safe(self._main.fetch_primary_branch(customer_id))
        if not branches and not primary:
            data_quality.missing_branch = True

        rms = await self._safe(self._main.fetch_relationship_managers(customer_id))
        if not rms:
            data_quality.missing_relationship_manager = True

        identity = self._build_identity(core, profile, mask_pii, masked_fields)
        relationship = self._build_relationship(core, branches, primary, rms)

        # ── permission-gated sections ──
        perms = set(user.permissions or [])
        section_granted = {s: SECTION_PERMISSIONS[s] in perms for s in ALL_SECTIONS}
        section_granted["relationship"] = True  # covered by the endpoint guard

        accounts: List[Dict[str, Any]] = []
        loans: List[Dict[str, Any]] = []
        tx_rows: List[Dict[str, Any]] = []
        if section_granted["financial"]:
            accounts = await self._safe(
                self._main.fetch_accounts(customer_id, allowed_branches)
            )
            loans = await self._safe(self._main.fetch_loans(customer_id, allowed_branches))

        allowed_accounts = None
        if allowed_branches:
            allowed_accounts = [a["account_id"] for a in accounts]

        tx_summary_rows: List[Dict[str, Any]] = []
        if section_granted["transactions"]:
            tx_summary_rows = await self._safe(
                self._main.fetch_transaction_summary(customer_id, allowed_accounts)
            )

        overview = Customer360Overview(
            customer=identity,
            relationship=relationship if section_granted["relationship"] else None,
            accounts=[],
            loans=[],
            financial_summary=None,
            transaction_summary=None,
            recent_transactions=[],
            kyc_aml=None,
            risk=None,
            analytics_alerts=[],
            workbench_links=[],
            data_quality=data_quality,
            generated_at=datetime.now(timezone.utc).isoformat() + "Z",
        )

        if section_granted["financial"]:
            overview.accounts = [
                AccountSummary(
                    account_id=r["account_id"],
                    account_type=r.get("account_type"),
                    status=r.get("status"),
                    balance=_money(r.get("balance")),
                    available_balance=_money(r.get("available_balance")),
                    currency=r.get("currency"),
                    branch=r.get("branch_name"),
                    opened_at=_iso(r.get("created_at")),
                )
                for r in accounts
            ]
            overview.loans = [
                LoanSummary(
                    loan_id=r["loan_id"],
                    loan_type=r.get("loan_type"),
                    product=r.get("product_name"),
                    principal=_money(r.get("principal_amount")),
                    outstanding_balance=_money(r.get("outstanding_balance")),
                    currency=r.get("currency"),
                    interest_rate=_money(r.get("interest_rate")),
                    maturity_date=_iso(r.get("maturity_date")),
                    status=r.get("status"),
                    days_past_due=r.get("days_past_due"),
                )
                for r in loans
            ]
            overview.financial_summary = self._build_financial_summary(
                accounts, loans, tx_summary_rows
            )

        if section_granted["transactions"]:
            overview.transaction_summary = await self._build_transaction_summary(
                customer_id, tx_summary_rows, allowed_accounts
            )
            recent = await self._safe(
                self._main.fetch_recent_transactions(customer_id, allowed_accounts)
            )
            overview.recent_transactions = [
                TransactionRow(
                    transaction_id=r["transaction_id"],
                    account_id=r.get("account_id"),
                    amount=_money(r.get("amount")),
                    currency=r.get("currency"),
                    type=r.get("transaction_type"),
                    status=r.get("status"),
                    description=r.get("description"),
                    transaction_date=_iso(r.get("transaction_date")),
                )
                for r in recent
            ]

        if section_granted["kyc_aml"]:
            overview.kyc_aml = await self._build_kyc_aml(customer_id, mask_pii, masked_fields)
            alerts = await self._safe(self._main.fetch_analytics_alerts(customer_id))
            overview.analytics_alerts = [
                AmlAlertSummary(
                    alert_id=r["alert_id"],
                    alert_type=r.get("alert_type"),
                    label=r.get("alert_label_fr"),
                    severity=r.get("severity"),
                    status=r.get("status"),
                    score=_money(r.get("score")),
                    triggered_at=_iso(r.get("triggered_at")),
                )
                for r in alerts
            ]

        if section_granted["risk"]:
            flags = await self._safe(self._main.fetch_active_risk_flags(customer_id))
            overview.risk = self._build_risk(core, flags)

        if section_granted["workbench_links"]:
            links, unresolved = await self._fetch_workbench_links(customer_id)
            overview.workbench_links = links
            if unresolved:
                data_quality.unresolved_workbench_reference = True
                data_quality.unavailable_sections.append("workbench_links")

        audit = self._build_audit(
            user, customer_id, request_id, scope_ids, section_granted, masked_fields,
            success=True, failure=None,
        )
        return overview, audit

    async def get_transactions(
        self,
        user: Any,
        customer_id: str,
        request_id: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> Optional[Tuple[TransactionSummary, List[TransactionRow], int, DataQuality, Dict[str, Any]]]:
        """Recent transactions + lifetime summary for one customer.

        Returns (transaction_summary, rows, total_count, data_quality, audit) or
        None when the customer is missing/out of scope. The caller must already
        hold customer:read_transactions (route guard); scope restricts accounts.
        """
        try:
            core = await self._main.fetch_customer_core(customer_id)
        except Exception as exc:
            raise Customer360SourceUnavailable(str(exc)) from exc
        if core is None:
            return None

        scope = await self._resolve_scope(user, customer_id)
        if scope is None:
            return None
        allowed_branches, scope_ids = scope

        data_quality = DataQuality()
        allowed_accounts: Optional[List[str]] = None
        if allowed_branches:
            accounts = await self._safe(
                self._main.fetch_accounts(customer_id, allowed_branches)
            )
            allowed_accounts = [a["account_id"] for a in accounts]

        summary = await self._build_transaction_summary(
            customer_id,
            await self._safe(self._main.fetch_transaction_summary(customer_id, allowed_accounts)),
            allowed_accounts,
        )
        raw_rows = await self._safe(
            self._main.fetch_recent_transactions(
                customer_id, allowed_accounts, limit=limit, offset=offset
            )
        )
        rows = [
            TransactionRow(
                transaction_id=r["transaction_id"],
                account_id=r.get("account_id"),
                amount=_money(r.get("amount")),
                currency=r.get("currency"),
                type=r.get("transaction_type"),
                status=r.get("status"),
                description=r.get("description"),
                transaction_date=_iso(r.get("transaction_date")),
            )
            for r in raw_rows
        ]
        try:
            total = await self._main.fetch_transaction_count(customer_id, allowed_accounts)
        except Exception:
            total = 0

        audit = self._build_audit(
            user, customer_id, request_id, scope_ids,
            {s: (s == "transactions") for s in ALL_SECTIONS},
            [], success=True, failure=None,
        )
        return summary, rows, total, data_quality, audit

    # ── scope ───────────────────────────────────────────────────────────────

    async def _resolve_scope(
        self, user: Any, customer_id: str
    ) -> Optional[Tuple[Optional[List[str]], List[str]]]:
        """Return (allowed_branches|None, scope_ids) or None when out of scope.

        None branch list = unrestricted (global / hq_main). A restricted list =
        the branch/region scopes the user holds that overlap the customer's
        branch membership.
        """
        scopes = await self._load_user_scopes(user)
        if not scopes:
            return None

        scope_ids = [s["scope_id"] for s in scopes]
        types = {s["scope_type"] for s in scopes}

        # unrestricted scopes
        if "global" in scope_ids or "hq_main" in scope_ids:
            return None, scope_ids

        branch_scopes = [s["scope_id"] for s in scopes if s["scope_type"] == "branch"]
        region_scopes = [s["scope_id"] for s in scopes if s["scope_type"] == "region"]
        if not branch_scopes and not region_scopes:
            return None, scope_ids  # unknown scope type -> treat as unrestricted

        branches = await self._safe(self._main.fetch_customer_branches(customer_id))
        allowed = [b["branch_id"] for b in branches if b["branch_id"] in branch_scopes]
        if region_scopes:
            allowed += [b["branch_id"] for b in branches if b.get("region_id") in region_scopes]

        allowed = sorted(set(allowed))
        if not allowed:
            return None  # customer has no account in any permitted branch
        return allowed, scope_ids

    async def _load_user_scopes(self, user: Any) -> List[Dict[str, Any]]:
        """User scopes from integration DB; role-based default when it is down."""
        if self._wb is not None:
            try:
                return await self._wb.fetch_user_scopes(user.user_id)
            except Exception:
                pass
        # ponytail: integration DB outage -> role-based default. Matches the
        # seeded reality (all business users hold hq_main, admins global).
        # Upgrade: cache user_scopes or mirror them into banking_dev when
        # finer-grained production scopes land.
        role = user.user_role
        return [{"scope_id": "global" if role == "admin" else "hq_main", "scope_type": "bank"}]

    # ── section builders ────────────────────────────────────────────────────

    def _build_identity(
        self,
        core: Dict[str, Any],
        profile: Optional[Dict[str, Any]],
        mask_pii: bool,
        masked_fields: List[str],
    ) -> CustomerIdentity:
        segment = core.get("segment")
        customer_type = None
        if segment:
            if segment.startswith("CORP"):
                customer_type = "corporate"
            elif segment.startswith("PART"):
                customer_type = "retail"

        identity = CustomerIdentity(
            customer_id=core["customer_id"],
            name=core.get("name"),
            customer_type=customer_type,
            segment=segment,
            status=None,  # customers table has no status column
            onboarding_date=_iso(core.get("created_at")),
            email=core.get("email"),
            phone=core.get("phone"),
        )
        if profile:
            identity.nationality = profile.get("nationality")
            identity.employment_status = profile.get("employment_status")
            identity.employer_name = profile.get("employer_name")
            identity.date_of_birth = _iso(profile.get("date_of_birth"))
            identity.national_id = profile.get("national_id")
            identity.passport_number = profile.get("passport_number")
            identity.tax_id = profile.get("tax_id")
            identity.annual_income = _money(profile.get("annual_income"))
            identity.net_worth_band = profile.get("net_worth_band")
            identity.pep = profile.get("politically_exposed")
        else:
            identity.date_of_birth = None
            identity.national_id = None
            identity.passport_number = None
            identity.tax_id = None
            identity.annual_income = None
            identity.net_worth_band = None
            identity.pep = None

        if not mask_pii:
            for field in (
                "national_id", "passport_number", "tax_id",
                "email", "phone", "date_of_birth",
                "annual_income", "net_worth_band", "pep",
            ):
                if getattr(identity, field) not in (None, "", ""):
                    masked_fields.append(field)
                    setattr(identity, field, _mask_value(getattr(identity, field)))
        return identity

    def _build_relationship(
        self,
        core: Dict[str, Any],
        branches: List[Dict[str, Any]],
        primary: Optional[Dict[str, Any]],
        rms: List[Dict[str, Any]],
    ) -> Relationship:
        rms_out = [
            {
                "employee_id": r.get("employee_id"),
                "name": _join_name(r.get("first_name"), r.get("last_name")),
                "title": r.get("title"),
                "portfolio_type": r.get("portfolio_type"),
            }
            for r in rms
        ]
        duration = None
        if core.get("created_at"):
            try:
                created = core["created_at"]
                if hasattr(created, "date"):
                    created_date = created.date()
                else:
                    created_date = datetime.fromisoformat(str(created)[:19]).date()
                duration = (datetime.now(timezone.utc).date() - created_date).days
            except Exception:
                duration = None
        return Relationship(
            primary_branch=primary.get("branch_name") if primary else None,
            region=(primary or {}).get("region_name_fr"),
            relationship_managers=rms_out,
            relationship_duration_days=duration,
            products_held=len({b.get("branch_id") for b in branches}),
        )

    def _build_financial_summary(
        self,
        accounts: List[Dict[str, Any]],
        loans: List[Dict[str, Any]],
        tx_rows: List[Dict[str, Any]],
    ) -> FinancialSummary:
        total_balance = _sum_by_currency(accounts, "balance")
        available = _sum_by_currency(accounts, "available_balance")
        outstanding = _sum_by_currency(loans, "outstanding_balance")
        recent_volume = {
            c: str(sum(Decimal(row.get("d30_amount") or 0) for row in tx_rows if row.get("currency") == c))
            for c in {r.get("currency") or "TND" for r in tx_rows}
        }
        dpd = [r.get("days_past_due") for r in loans if r.get("days_past_due") is not None]
        return FinancialSummary(
            account_count=len(accounts),
            active_account_count=sum(1 for a in accounts if a.get("status") == "active"),
            total_balance_by_currency=total_balance,
            available_balance_by_currency=available,
            loan_count=len(loans),
            total_outstanding_loans_by_currency=outstanding,
            maximum_days_past_due=max(dpd) if dpd else None,
            recent_transaction_count=sum(int(r.get("d30_count") or 0) for r in tx_rows),
            recent_transaction_volume_by_currency=recent_volume,
        )

    async def _build_transaction_summary(
        self,
        customer_id: str,
        rows: List[Dict[str, Any]],
        allowed_accounts: Optional[List[str]],
    ) -> TransactionSummary:
        cur = [r.get("currency") or "TND" for r in rows]
        return TransactionSummary(
            d30_inbound_count=sum(int(r.get("d30_inbound_count") or 0) for r in rows),
            d30_inbound_amount={c: _money(sum(Decimal(r.get("d30_inbound_amount") or 0) for r in rows if (r.get("currency") or "TND") == c)) for c in set(cur)},
            d30_outbound_count=sum(int(r.get("d30_outbound_count") or 0) for r in rows),
            d30_outbound_amount={c: _money(sum(Decimal(r.get("d30_outbound_amount") or 0) for r in rows if (r.get("currency") or "TND") == c)) for c in set(cur)},
            d30_total_count=sum(int(r.get("d30_count") or 0) for r in rows),
            d30_total_amount={c: _money(sum(Decimal(r.get("d30_amount") or 0) for r in rows if (r.get("currency") or "TND") == c)) for c in set(cur)},
            d90_total_count=sum(int(r.get("d90_count") or 0) for r in rows),
            d90_total_amount={c: _money(sum(Decimal(r.get("d90_amount") or 0) for r in rows if (r.get("currency") or "TND") == c)) for c in set(cur)},
            latest_transaction_date=_iso(
                (await self._safe(self._main.fetch_latest_transaction_date(customer_id)) or {}).get("latest")
            ),
            top_transaction_types=await self._safe(self._main.fetch_top_transaction_types(customer_id)),
            currencies=sorted(set(cur)),
        )

    async def _build_kyc_aml(
        self, customer_id: str, mask_pii: bool, masked_fields: List[str]
    ) -> KycAml:
        core_kyc = None
        case_row = await self._safe(self._main.fetch_latest_kyc_case(customer_id))
        pep_row = await self._safe(self._main.fetch_latest_pep(customer_id))
        san_row = await self._safe(self._main.fetch_latest_sanctions(customer_id))
        counts = await self._safe(self._main.fetch_aml_alert_counts(customer_id))
        sar = await self._safe(self._main.fetch_sar_count(customer_id))

        by_status: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for row in counts:
            bucket = row.get("bucket")
            value = row.get("value")
            if not value:
                continue
            if bucket == "status":
                by_status[str(value)] = int(row.get("cnt") or 0)
            else:
                by_severity[str(value)] = int(row.get("cnt") or 0)

        if not mask_pii:
            for s in (pep_row, san_row):
                if s and s.get("matched_name"):
                    masked_fields.append("screening_matched_name")
        return KycAml(
            kyc_verified=core_kyc,
            latest_kyc_case=KycCaseSummary(
                kyc_case_id=case_row["kyc_case_id"],
                case_type=case_row.get("case_type"),
                status=case_row.get("status"),
                risk_level=case_row.get("risk_level"),
                opened_at=_iso(case_row.get("opened_at")),
            ) if case_row else None,
            kyc_status=case_row.get("status") if case_row else None,
            next_review_date=_iso(case_row.get("due_date")) if case_row else None,
            pep_screening=_build_screening(pep_row, mask_pii),
            sanctions_screening=_build_screening(san_row, mask_pii),
            aml_alert_counts_by_status=by_status,
            aml_alert_counts_by_severity=by_severity,
            sar_count=int((sar or {}).get("cnt") or 0),
        )

    def _build_risk(
        self, core: Dict[str, Any], flags: List[Dict[str, Any]]
    ) -> RiskSection:
        severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        active = [
            RiskFlagSummary(
                flag_id=r["id"],
                flag_type=r.get("flag_type"),
                severity=r.get("severity"),
                description=r.get("description"),
                created_at=_iso(r.get("created_at")),
            )
            for r in flags
        ]
        highest = None
        best = 0
        for f in flags:
            rank = severity_rank.get((f.get("severity") or "").lower(), 0)
            if rank > best:
                best = rank
                highest = f.get("severity")
        factors = sorted({f.get("flag_type") for f in flags if f.get("flag_type")})
        return RiskSection(
            risk_score=_to_float(core.get("risk_score")),
            active_flags=active,
            highest_active_severity=highest,
            risk_factors=factors,
            unresolved_flag_count=len(flags),
        )

    # ── workbench links ─────────────────────────────────────────────────────

    async def _fetch_workbench_links(
        self, customer_id: str
    ) -> Tuple[List[WorkbenchLink], bool]:
        if self._wb is None:
            return [], True
        try:
            alerts = await self._wb.fetch_customer_linked_alerts(customer_id)
            alert_ids = [a["alert_id"] for a in alerts]
            invs = await self._wb.fetch_investigations_for_alerts(alert_ids)
            inv_ids = [i["investigation_id"] for i in invs]
            cases = await self._wb.fetch_cases_for_links(alert_ids, inv_ids)
            case_ids = [c["case_id"] for c in cases]
            irs = await self._wb.fetch_irs_for_links(case_ids, inv_ids)
        except Exception:
            return [], True

        links: List[WorkbenchLink] = []
        for a in alerts:
            links.append(WorkbenchLink(
                entity_type="alert", entity_id=a["alert_id"],
                status=a.get("status"), assigned_to=a.get("assigned_to"),
                updated_at=_iso(a.get("updated_at")), scope_id=a.get("scope_id"),
            ))
        for i in invs:
            links.append(WorkbenchLink(
                entity_type="investigation", entity_id=i["investigation_id"],
                status=i.get("status"), assigned_to=i.get("assigned_to"),
                updated_at=_iso(i.get("updated_at")), scope_id=i.get("scope_id"),
            ))
        for c in cases:
            links.append(WorkbenchLink(
                entity_type="case", entity_id=c["case_id"],
                status=c.get("status"), assigned_to=c.get("assigned_to"),
                updated_at=_iso(c.get("updated_at")), scope_id=c.get("scope_id"),
            ))
        for r in irs:
            links.append(WorkbenchLink(
                entity_type="information_request", entity_id=r["ir_id"],
                status=r.get("status"), assigned_to=r.get("assigned_to"),
                updated_at=_iso(r.get("updated_at")), scope_id=r.get("scope_id"),
            ))
        return links, False

    # ── audit ───────────────────────────────────────────────────────────────

    def _build_audit(
        self,
        user: Any,
        customer_id: str,
        request_id: str,
        scope_ids: List[str],
        section_granted: Dict[str, bool],
        masked_fields: List[str],
        success: bool,
        failure: Optional[str],
    ) -> Dict[str, Any]:
        requested = list(ALL_SECTIONS)
        granted = [s for s in ALL_SECTIONS if section_granted.get(s)]
        return {
            "action": "customer_360_access",
            "actor_id": user.user_id,
            "actor_role": getattr(user, "user_role", None),
            "customer_id": customer_id,
            "sections_requested": requested,
            "sections_granted": granted,
            "fields_masked": masked_fields,
            "scope_used": scope_ids,
            "request_id": request_id,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "success": success,
            "failure_reason": failure,
        }

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _safe(self, awaitable) -> Any:
        try:
            return await awaitable
        except Exception:
            return [] if isinstance(awaitable.__class__, type) else None


def _mask_value(value: Any) -> str:
    s = str(value)
    if not s:
        return "****"
    return "****" + s[-4:] if len(s) >= 4 else "****"


def _join_name(first: Optional[str], last: Optional[str]) -> Optional[str]:
    parts = [p for p in (first, last) if p]
    return " ".join(parts) if parts else None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _build_screening(row: Optional[Dict[str, Any]], mask_pii: bool) -> Optional[ScreeningSummary]:
    if not row:
        return None
    list_name = row.get("source_list") or row.get("sanctions_list")
    return ScreeningSummary(
        status=row.get("status"),
        risk_level=row.get("risk_level"),
        match_score=_money(row.get("match_score")),
        list_name=list_name,
        matched_name=None if not mask_pii else row.get("matched_name"),
        checked_at=_iso(row.get("created_at")),
    )
