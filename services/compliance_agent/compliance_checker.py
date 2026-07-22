import asyncpg
import logging
from typing import List, Dict, Any

from config import Settings
from models import ComplianceResponse, Violation, MaskingRule

logger = logging.getLogger(__name__)

# Columns that always need PII masking under GDPR
_GDPR_PII_COLUMNS = {"ssn", "email", "phone", "national_id", "date_of_birth"}

# Columns that need card masking under PCI-DSS
_PCI_CARD_COLUMNS = {"credit_card", "card_number", "pan", "cvv"}

# Roles that may access card data
_PCI_ALLOWED_ROLES = {"compliance", "admin"}

# Tables that must be SOX-audited
_SOX_SENSITIVE_TABLES = {"accounts", "transactions", "risk_flags"}


class ComplianceChecker:
    """Evaluate queries against GDPR, PCI-DSS, SOX, AML, KYC rule sets."""

    def __init__(self, config: Settings):
        self.config = config
        self.pool: asyncpg.Pool = None

    async def initialize(self):
        self.pool = await asyncpg.create_pool(
            self.config.DATABASE_URL, min_size=1, max_size=3
        )
        logger.info("ComplianceChecker pool initialised")

    # ─────────────────────────────────────────────────────────────────────
    # Main entry
    # ─────────────────────────────────────────────────────────────────────

    async def check_compliance(
        self,
        user_id: str,
        user_role: str,
        query_intent: str,
        tables: List[str],
        columns: List[str],
    ) -> ComplianceResponse:
        violations: List[Violation] = []
        masking: List[MaskingRule] = []

        # ── GDPR checks ───────────────────────────────────────────────────
        for col in columns:
            if col.lower() in _GDPR_PII_COLUMNS:
                masking.append(
                    MaskingRule(
                        column=col,
                        mask_type="MASK_VALUE",
                        regulation="GDPR",
                    )
                )

        # ── PCI-DSS checks ────────────────────────────────────────────────
        for col in columns:
            if col.lower() in _PCI_CARD_COLUMNS:
                if user_role not in _PCI_ALLOWED_ROLES:
                    violations.append(
                        Violation(
                            rule="Restrict Card Data Access - PCI-DSS",
                            severity="critical",
                            reason=f"Role '{user_role}' may not access card data column '{col}'",
                            regulation="PCI-DSS",
                        )
                    )
                else:
                    # Allowed but must tokenise
                    masking.append(
                        MaskingRule(
                            column=col,
                            mask_type="MASK_LAST4",
                            regulation="PCI-DSS",
                        )
                    )

        # ── SOX checks ────────────────────────────────────────────────────
        sox_tables_accessed = _SOX_SENSITIVE_TABLES & {t.lower() for t in tables}
        if sox_tables_accessed:
            # Access is allowed but must be logged — violation only if SOX
            # segregation broken (same user creates AND approves = role 'maker_checker')
            if user_role == "maker_checker":
                violations.append(
                    Violation(
                        rule="Segregation of Duties - SOX",
                        severity="high",
                        reason="Role 'maker_checker' violates SOX segregation-of-duties",
                        regulation="SOX",
                    )
                )

        # ── AML checks ────────────────────────────────────────────────────
        if "transaction" in query_intent.lower() or any(
            "transaction" in t.lower() for t in tables
        ):
            # Flag: query unrestricted transaction data without compliance role
            if user_role not in {"compliance", "admin", "analyst"}:
                violations.append(
                    Violation(
                        rule="Monitor Large Transactions - AML",
                        severity="medium",
                        reason=f"Role '{user_role}' querying transaction data without AML clearance",
                        regulation="AML",
                    )
                )

        # ── KYC checks ────────────────────────────────────────────────────
        if "kyc" in query_intent.lower() and user_role not in {
            "compliance", "admin", "kyc_officer"
        }:
            violations.append(
                Violation(
                    rule="Enhanced Due Diligence - KYC",
                    severity="medium",
                    reason=f"Role '{user_role}' not authorised for KYC intent queries",
                    regulation="KYC",
                )
            )

        # ── DB-driven rules (if pool available) ───────────────────────────
        db_violations, db_masking = await self._check_db_rules(
            user_role, columns, tables
        )
        violations.extend(db_violations)
        masking.extend(db_masking)

        compliant = not any(
            v.severity in {"critical", "high"} for v in violations
        )

        return ComplianceResponse(
            compliant=compliant,
            violations=violations,
            masking_required=masking,
            regulations_checked=["GDPR", "PCI-DSS", "SOX", "AML", "KYC"],
            user_role=user_role,
            message="OK" if compliant else f"{len(violations)} violation(s) detected",
        )

    # ─────────────────────────────────────────────────────────────────────
    # DB-driven rule evaluation
    # ─────────────────────────────────────────────────────────────────────

    async def _check_db_rules(
        self,
        user_role: str,
        columns: List[str],
        tables: List[str],
    ):
        violations: List[Violation] = []
        masking: List[MaskingRule] = []

        if not self.pool:
            return violations, masking

        try:
            rules = await self.pool.fetch(
                "SELECT * FROM compliance_rules WHERE enabled = TRUE"
            )
            for rule in rules:
                rule_type = rule["rule_type"]
                condition = rule["condition"] or ""

                if rule_type == "data_masking":
                    for col in columns:
                        if self._col_matches(col, condition):
                            masking.append(
                                MaskingRule(
                                    column=col,
                                    mask_type=rule["action"],
                                    regulation=rule["regulation"],
                                )
                            )

                elif rule_type == "access_control":
                    if not self._role_allowed(user_role, condition):
                        violations.append(
                            Violation(
                                rule=rule["rule_name"],
                                severity="critical",
                                reason=f"Role '{user_role}' blocked by rule: {rule['rule_name']}",
                                regulation=rule["regulation"],
                            )
                        )

        except Exception as exc:
            logger.warning(f"DB rule check skipped: {exc}")

        return violations, masking

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    @staticmethod
    def _col_matches(column: str, condition: str) -> bool:
        """Check if column name is listed in a rule condition."""
        col = column.lower().strip()
        if "IN" in condition or "in" in condition:
            try:
                inner = condition.split("(")[1].split(")")[0]
                listed = [c.strip().lower() for c in inner.split(",")]
                return col in listed
            except IndexError:
                pass
        if "=" in condition:
            rhs = condition.split("=")[-1].strip().lower()
            return col == rhs
        return False

    @staticmethod
    def _role_allowed(user_role: str, condition: str) -> bool:
        """
        Return False if the condition denies this role.
        Condition example: "user_role NOT IN (compliance, admin)"
        means: deny roles that are NOT in the list — i.e., only
        compliance and admin are allowed.
        """
        role = user_role.lower()
        if "NOT IN" in condition or "not in" in condition:
            try:
                inner = condition.split("(")[1].split(")")[0]
                allowed_roles = [r.strip().lower() for r in inner.split(",")]
                return role in allowed_roles
            except IndexError:
                pass
        return True
