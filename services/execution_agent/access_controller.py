"""
services/execution_agent/access_controller.py
Role-based access control: row filters + column visibility + PII masking rules.

Roles:
  analyst        — sees all rows, masked PII columns
  manager        — sees all rows (branch-scoped in real deployments), masked PII
  compliance     — sees all rows, ALL columns unmasked
  customer       — sees only their own rows, limited columns
"""
from typing import Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# ROW-LEVEL FILTERS
# These WHERE-clause fragments are appended to queries per role.
# In a real system these would use the actual user_id / branch_id from JWT.
# ──────────────────────────────────────────────────────────────────────────────

_ROW_FILTERS: Dict[str, Optional[str]] = {
    "analyst":    None,                       # no extra filter — see all
    "manager":    None,                       # simplified; prod: WHERE branch_id = :bid
    "compliance": None,                       # see everything
    "customer":   "WHERE customer_id = :uid", # only own data
}

# ──────────────────────────────────────────────────────────────────────────────
# VISIBLE COLUMNS PER ROLE
# None = all columns visible
# ──────────────────────────────────────────────────────────────────────────────

_VISIBLE_COLUMNS: Dict[str, Optional[List[str]]] = {
    "analyst": [
        "customer_id", "first_name", "last_name",
        "balance", "risk_score", "segment",
        "account_id", "account_number", "account_type", "status",
        "transaction_id", "amount", "transaction_date", "transaction_type",
        "branch_id", "branch_name", "region",
        "product_id", "product_name", "category",
    ],
    "manager": [
        "customer_id", "first_name", "last_name",
        "balance", "risk_score", "segment",
        "account_id", "account_number", "account_type", "status",
        "transaction_id", "amount", "transaction_date", "transaction_type",
        "branch_id", "branch_name", "region",
    ],
    "compliance": None,                       # all columns, no masking
    "customer": [
        "first_name", "last_name",
        "balance", "account_type", "account_number",
        "transaction_date", "amount", "transaction_type",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# PII COLUMNS — masked for all roles except compliance
# ──────────────────────────────────────────────────────────────────────────────

PII_COLUMNS = {
    "ssn", "social_security_number",
    "credit_card", "credit_card_number", "card_number",
    "email", "email_address",
    "credit_score",
    "password", "password_hash",
    "phone", "phone_number",
    "date_of_birth", "dob",
}


class AccessController:
    """Enforces role-based access rules."""

    def get_row_filter(self, user_role: str) -> Optional[str]:
        """Return a SQL fragment (or None) to restrict rows for this role."""
        return _ROW_FILTERS.get(user_role.lower(), None)

    def get_visible_columns(self, user_role: str) -> Optional[List[str]]:
        """Return the list of columns this role may see (None = all)."""
        return _VISIBLE_COLUMNS.get(user_role.lower(), _VISIBLE_COLUMNS["analyst"])

    def should_mask_pii(self, user_role: str) -> bool:
        """Compliance sees raw PII; everyone else gets masked values."""
        return user_role.lower() != "compliance"

    def filter_columns(self, row: Dict, user_role: str) -> Dict:
        """Remove columns the role cannot see from a result row."""
        visible = self.get_visible_columns(user_role)
        if visible is None:
            return row
        return {k: v for k, v in row.items() if k.lower() in visible}
