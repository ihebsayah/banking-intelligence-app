"""Repositories for the Customer 360 logical read bridge.

Customer360Repository    — authoritative reads from banking_dev.
WorkbenchLinkRepository  — narrow operational reads from banking_integration.

Both are read-only, parameterised ($1, $2, ...), bounded, and never fan out
balances/loans against transaction cardinality. The two databases never share
a connection or a transaction — composition is done by the service layer.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from shared.database import DatabaseConnector

_RECENT_TX_LIMIT = 20
_ANALYTICS_ALERT_LIMIT = 5
_WORKBENCH_LINK_LIMIT = 50


def _money(value: Any) -> Optional[str]:
    """Decimal -> exact string (precision-safe JSON); None stays None."""
    if value is None:
        return None
    return str(value)


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


class Customer360Repository:
    """Deterministic, bounded reads against banking_dev (main bank data)."""

    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    # ── customer core ───────────────────────────────────────────────────────

    async def fetch_customer_core(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            """
            SELECT customer_id, name, email, phone, kyc_verified, risk_score,
                   segment, created_at
              FROM customers
             WHERE customer_id = $1
            """,
            [customer_id],
        )

    async def fetch_profile(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            """
            SELECT date_of_birth, nationality, national_id, passport_number,
                   employment_status, employer_name, annual_income,
                   income_currency, net_worth_band, politically_exposed,
                   pep_details, tax_id
              FROM customer_profiles
             WHERE customer_id = $1
            """,
            [customer_id],
        )

    # ── relationship ────────────────────────────────────────────────────────

    async def fetch_relationship_managers(self, customer_id: str) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT rm.portfolio_type, rm.assigned_date,
                   e.employee_id, e.first_name, e.last_name, e.title, e.email
              FROM relationship_managers rm
              LEFT JOIN employees e ON e.employee_id = rm.employee_id
             WHERE rm.customer_id = $1
             ORDER BY rm.assigned_date NULLS LAST, rm.rm_id
            """,
            [customer_id],
        )

    async def fetch_customer_branches(self, customer_id: str) -> List[Dict[str, Any]]:
        """Every branch the customer holds an account at (for scope + primary)."""
        return await self._db.fetch_all(
            """
            SELECT DISTINCT a.branch_id, b.name AS branch_name, b.region_id,
                   r.region_name_fr
              FROM accounts a
              JOIN branches b ON b.branch_id = a.branch_id
              LEFT JOIN regions r ON r.region_id = b.region_id
             WHERE a.customer_id = $1
             ORDER BY a.branch_id
            """,
            [customer_id],
        )

    async def fetch_primary_branch(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Deterministic primary branch = branch of the largest-balance account."""
        return await self._db.fetch_one(
            """
            SELECT a.branch_id, b.name AS branch_name, b.region_id,
                   r.region_name_fr
              FROM accounts a
              JOIN branches b ON b.branch_id = a.branch_id
              LEFT JOIN regions r ON r.region_id = b.region_id
             WHERE a.customer_id = $1
             ORDER BY a.balance DESC NULLS LAST, a.branch_id
             LIMIT 1
            """,
            [customer_id],
        )

    # ── accounts / loans / transactions ─────────────────────────────────────

    async def fetch_accounts(
        self,
        customer_id: str,
        allowed_branches: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [customer_id]
        branch_filter = ""
        if allowed_branches:
            branch_filter = " AND a.branch_id = ANY($2)"
            params.append(allowed_branches)
        return await self._db.fetch_all(
            f"""
            SELECT a.account_id, a.account_type, a.status, a.balance,
                   a.available_balance, a.currency, a.branch_id,
                   b.name AS branch_name, a.created_at
              FROM accounts a
              LEFT JOIN branches b ON b.branch_id = a.branch_id
             WHERE a.customer_id = $1
             {branch_filter}
             ORDER BY a.account_id
            """,
            params,
        )

    async def fetch_customer_metadata_counts(
        self,
        customer_id: str,
        allowed_branches: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Admin metadata-only counts. Deliberately selects NO balance/amount
        columns so a metadata viewer never touches monetary values."""
        params: List[Any] = [customer_id]
        account_filter = ""
        loan_filter = ""
        if allowed_branches:
            account_filter = " AND a.branch_id = ANY($2)"
            loan_filter = " AND lc.branch_id = ANY($2)"
            params.append(allowed_branches)
        row = await self._db.fetch_one(
            f"""
            SELECT
              (SELECT COUNT(*) FROM accounts a
                WHERE a.customer_id = $1 {account_filter}) AS account_count,
              (SELECT COUNT(*) FROM accounts a
                WHERE a.customer_id = $1 AND a.status = 'active' {account_filter}) AS active_account_count,
              (SELECT COUNT(DISTINCT a.account_type) FROM accounts a
                WHERE a.customer_id = $1 {account_filter}) AS product_count,
              (SELECT COUNT(*) FROM loan_contracts lc
                WHERE lc.customer_id = $1 {loan_filter}) AS loan_count
            """,
            params,
        )
        return row or {}

    async def fetch_loans(
        self,
        customer_id: str,
        allowed_branches: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [customer_id]
        branch_filter = ""
        if allowed_branches:
            branch_filter = " AND lc.branch_id = ANY($2)"
            params.append(allowed_branches)
        return await self._db.fetch_all(
            f"""
            SELECT lc.loan_id, lc.loan_type, lc.principal_amount,
                   lc.outstanding_balance, lc.currency, lc.interest_rate,
                   lc.maturity_date, lc.status, lc.days_past_due,
                   lp.name AS product_name
              FROM loan_contracts lc
              LEFT JOIN loan_products lp ON lp.loan_product_id = lc.loan_product_id
             WHERE lc.customer_id = $1
             {branch_filter}
             ORDER BY lc.loan_id
            """,
            params,
        )

    async def fetch_transaction_summary(
        self,
        customer_id: str,
        allowed_accounts: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [customer_id]
        account_filter = ""
        if allowed_accounts:
            account_filter = " AND t.account_id = ANY($2)"
            params.append(allowed_accounts)
        return await self._db.fetch_all(
            f"""
            SELECT COALESCE(a.currency, 'TND') AS currency,
                   COUNT(*) FILTER (WHERE t.transaction_date >= NOW() - INTERVAL '30 days') AS d30_count,
                   COALESCE(SUM(t.amount) FILTER (WHERE t.transaction_date >= NOW() - INTERVAL '30 days'), 0) AS d30_amount,
                   COUNT(*) FILTER (WHERE t.amount > 0 AND t.transaction_date >= NOW() - INTERVAL '30 days') AS d30_inbound_count,
                   COALESCE(SUM(t.amount) FILTER (WHERE t.amount > 0 AND t.transaction_date >= NOW() - INTERVAL '30 days'), 0) AS d30_inbound_amount,
                   COUNT(*) FILTER (WHERE t.amount < 0 AND t.transaction_date >= NOW() - INTERVAL '30 days') AS d30_outbound_count,
                   COALESCE(SUM(t.amount) FILTER (WHERE t.amount < 0 AND t.transaction_date >= NOW() - INTERVAL '30 days'), 0) AS d30_outbound_amount,
                   COUNT(*) FILTER (WHERE t.transaction_date >= NOW() - INTERVAL '90 days') AS d90_count,
                   COALESCE(SUM(t.amount) FILTER (WHERE t.transaction_date >= NOW() - INTERVAL '90 days'), 0) AS d90_amount
              FROM transactions t
              LEFT JOIN accounts a ON a.account_id = t.account_id
             WHERE t.customer_id = $1
             {account_filter}
             GROUP BY 1
             ORDER BY 1
            """,
            params,
        )

    async def fetch_recent_transactions(
        self,
        customer_id: str,
        allowed_accounts: Optional[List[str]] = None,
        limit: int = _RECENT_TX_LIMIT,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [customer_id]
        account_filter = ""
        if allowed_accounts:
            account_filter = " AND t.account_id = ANY($2)"
            params.append(allowed_accounts)
        params += [limit, offset]
        return await self._db.fetch_all(
            f"""
            SELECT t.transaction_id, t.account_id, t.amount,
                   COALESCE(a.currency, 'TND') AS currency, t.transaction_type,
                   t.status, t.description, t.transaction_date
              FROM transactions t
              LEFT JOIN accounts a ON a.account_id = t.account_id
             WHERE t.customer_id = $1
             {account_filter}
             ORDER BY t.transaction_date DESC, t.transaction_id DESC
             LIMIT ${len(params) - 1} OFFSET ${len(params)}
            """,
            params,
        )

    async def fetch_transaction_count(
        self,
        customer_id: str,
        allowed_accounts: Optional[List[str]] = None,
    ) -> int:
        params: List[Any] = [customer_id]
        account_filter = ""
        if allowed_accounts:
            account_filter = " AND t.account_id = ANY($2)"
            params.append(allowed_accounts)
        row = await self._db.fetch_one(
            f"""
            SELECT COUNT(*) AS cnt
              FROM transactions t
             WHERE t.customer_id = $1
             {account_filter}
            """,
            params,
        )
        return int((row or {}).get("cnt") or 0)

    async def fetch_latest_transaction_date(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            "SELECT MAX(transaction_date) AS latest FROM transactions WHERE customer_id = $1",
            [customer_id],
        )

    async def fetch_top_transaction_types(self, customer_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT transaction_type, COUNT(*) AS cnt
              FROM transactions
             WHERE customer_id = $1
             GROUP BY transaction_type
             ORDER BY cnt DESC
             LIMIT $2
            """,
            [customer_id, limit],
        )

    # ── kyc / aml / risk ────────────────────────────────────────────────────

    async def fetch_latest_kyc_case(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            """
            SELECT kyc_case_id, case_type, status, risk_level, due_date, opened_at
              FROM kyc_cases
             WHERE customer_id = $1
             ORDER BY opened_at DESC NULLS LAST, kyc_case_id DESC
             LIMIT 1
            """,
            [customer_id],
        )

    async def fetch_latest_pep(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            """
            SELECT status, risk_level, match_score, source_list, matched_name, created_at
              FROM pep_screening
             WHERE customer_id = $1
             ORDER BY created_at DESC, screening_id DESC
             LIMIT 1
            """,
            [customer_id],
        )

    async def fetch_latest_sanctions(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            """
            SELECT status, risk_level, match_score, sanctions_list, matched_name, created_at
              FROM sanctions_screening
             WHERE customer_id = $1
             ORDER BY created_at DESC, screening_id DESC
             LIMIT 1
            """,
            [customer_id],
        )

    async def fetch_aml_alert_counts(self, customer_id: str) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT 'status' AS bucket, status AS value, COUNT(*) AS cnt
              FROM aml_alerts
             WHERE customer_id = $1
             GROUP BY status
            UNION ALL
            SELECT 'severity' AS bucket, severity AS value, COUNT(*) AS cnt
              FROM aml_alerts
             WHERE customer_id = $1
             GROUP BY severity
            """,
            [customer_id],
        )

    async def fetch_sar_count(self, customer_id: str) -> Optional[Dict[str, Any]]:
        return await self._db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM suspicious_activity_reports WHERE customer_id = $1",
            [customer_id],
        )

    async def fetch_active_risk_flags(self, customer_id: str) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT id, flag_type, severity, description, created_at
              FROM risk_flags
             WHERE customer_id = $1 AND resolved = false
             ORDER BY created_at DESC, id
            """,
            [customer_id],
        )

    async def fetch_analytics_alerts(
        self,
        customer_id: str,
        limit: int = _ANALYTICS_ALERT_LIMIT,
    ) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT alert_id, alert_type, alert_label_fr, severity, status, score, triggered_at
              FROM aml_alerts
             WHERE customer_id = $1
             ORDER BY triggered_at DESC NULLS LAST, alert_id DESC
             LIMIT $2
            """,
            [customer_id, limit],
        )


class WorkbenchLinkRepository:
    """Narrow operational reads against banking_integration.

    Only records whose linkage to the customer is EXPLICIT
    (related_entity_type='customer' AND related_entity_id=$1) are returned.
    No linkage is inferred from free text, descriptions, or findings.
    """

    def __init__(self, db: DatabaseConnector) -> None:
        self._db = db

    async def fetch_user_scopes(self, user_id: str) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT us.scope_id, COALESCE(os.scope_type, 'branch') AS scope_type
              FROM user_scopes us
              LEFT JOIN organisation_scopes os ON os.scope_id = us.scope_id
             WHERE us.user_id = $1
            """,
            [user_id],
        )

    async def fetch_customer_linked_alerts(self, customer_id: str) -> List[Dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT alert_id, alert_type, severity, status, title, assigned_to,
                   scope_id, updated_at
              FROM alerts
             WHERE related_entity_type = 'customer'
               AND related_entity_id = $1
             ORDER BY updated_at DESC
             LIMIT $2
            """,
            [customer_id, _WORKBENCH_LINK_LIMIT],
        )

    async def fetch_investigations_for_alerts(self, alert_ids: List[str]) -> List[Dict[str, Any]]:
        if not alert_ids:
            return []
        return await self._db.fetch_all(
            """
            SELECT investigation_id, status, priority, assigned_to, alert_id, scope_id, updated_at
              FROM investigations
             WHERE alert_id = ANY($1::uuid[])
             ORDER BY updated_at DESC
             LIMIT $2
            """,
            [alert_ids, _WORKBENCH_LINK_LIMIT],
        )

    async def fetch_cases_for_links(
        self,
        alert_ids: List[str],
        investigation_ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not alert_ids and not investigation_ids:
            return []
        if alert_ids and not investigation_ids:
            filter_sql = "WHERE alert_id = ANY($1::uuid[])"
            params: List[Any] = [alert_ids, _WORKBENCH_LINK_LIMIT]
        elif investigation_ids and not alert_ids:
            filter_sql = "WHERE investigation_id = ANY($1::uuid[])"
            params = [investigation_ids, _WORKBENCH_LINK_LIMIT]
        else:
            filter_sql = (
                "WHERE alert_id = ANY($1::uuid[]) OR investigation_id = ANY($2::uuid[])"
            )
            params = [alert_ids, investigation_ids, _WORKBENCH_LINK_LIMIT]
        return await self._db.fetch_all(
            f"""
            SELECT case_id, status, priority, risk_level, assigned_to, alert_id,
                   investigation_id, scope_id, updated_at
              FROM compliance_cases
             {filter_sql}
             ORDER BY updated_at DESC
             LIMIT ${len(params)}
            """,
            params,
        )

    async def fetch_irs_for_links(
        self,
        case_ids: List[str],
        investigation_ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not case_ids and not investigation_ids:
            return []
        if case_ids and not investigation_ids:
            filter_sql = "WHERE case_id = ANY($1::uuid[])"
            params: List[Any] = [case_ids, _WORKBENCH_LINK_LIMIT]
        elif investigation_ids and not case_ids:
            filter_sql = "WHERE investigation_id = ANY($1::uuid[])"
            params = [investigation_ids, _WORKBENCH_LINK_LIMIT]
        else:
            filter_sql = "WHERE case_id = ANY($1::uuid[]) OR investigation_id = ANY($2::uuid[])"
            params = [case_ids, investigation_ids, _WORKBENCH_LINK_LIMIT]
        return await self._db.fetch_all(
            f"""
            SELECT ir_id, case_id, investigation_id, status, assigned_to, scope_id, updated_at
              FROM information_requests
             {filter_sql}
             ORDER BY updated_at DESC
             LIMIT ${len(params)}
            """,
            params,
        )
