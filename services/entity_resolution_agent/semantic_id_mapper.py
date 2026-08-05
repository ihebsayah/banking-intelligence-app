"""
services/entity_resolution_agent/semantic_id_mapper.py
Hardcoded semantic entity → primary key → tables mapping.
JOIN on semantic business key (customer_id), NOT structural table.id.
"""
from typing import List, Optional, Dict, Tuple

# ──────────────────────────────────────────────────────────────────────────────
# SEMANTIC ENTITY → PRIMARY KEY MAPPING
# Maps business entity names to their canonical primary-key column name
# ──────────────────────────────────────────────────────────────────────────────
ENTITY_TO_PRIMARY_KEY: Dict[str, str] = {
    "customer":    "customer_id",
    "customers":   "customer_id",
    "account":     "account_id",
    "accounts":    "account_id",
    "transaction": "transaction_id",
    "transactions":"transaction_id",
    "branch":      "branch_id",
    "branches":    "branch_id",
    "product":     "product_id",
    "products":    "product_id",
    "risk":        "id",
    "risk_flags":  "id",
    "loan":        "loan_id",
    "loans":       "loan_id",
    "loan_contract": "loan_id",
    "loan_contracts": "loan_id",
    "provision":   "provision_id",
    "provisions":  "provision_id",
    "employee":    "employee_id",
    "employees":   "employee_id",
    "fee_income":  "fee_income_id",
    "kyc_case":    "kyc_case_id",
    "kyc_cases":   "kyc_case_id",
    "aml_alert":   "alert_id",
    "aml_alerts":  "alert_id",
    "compliance_violation": "id",
    "compliance_violations": "id",
    "suspicious_activity_report": "sar_id",
    "suspicious_activity_reports": "sar_id",
}

# ──────────────────────────────────────────────────────────────────────────────
# TABLE → COLUMNS CONTAINING ENTITY FOREIGN KEYS
# Lists which business-key columns each table owns (PK or FK)
# ──────────────────────────────────────────────────────────────────────────────
TABLE_ENTITY_COLUMNS: Dict[str, List[str]] = {
    "customers":        ["customer_id"],
    "accounts":         ["account_id", "customer_id", "branch_id"],
    "transactions":     ["transaction_id", "account_id", "customer_id"],
    "branches":         ["branch_id"],
    "products":         ["product_id"],
    "risk_flags":       ["id", "customer_id", "account_id"],
    "loan_contracts":   ["loan_id", "customer_id", "account_id", "branch_id"],
    "loans":            ["loan_id", "customer_id", "account_id", "branch_id"],
    "employees":        ["employee_id", "branch_id"],
    "fee_income":       ["fee_income_id", "customer_id", "account_id"],
    "kyc_cases":        ["kyc_case_id", "customer_id"],
    "aml_alerts":       ["alert_id", "customer_id", "transaction_id"],
    "provisions":       ["provision_id", "loan_id"],
    "non_performing_loans": ["npl_id", "loan_id"],
}

# ──────────────────────────────────────────────────────────────────────────────
# SEMANTIC JOIN MAPPING
# (from_table, to_table) → join_key used to connect them
# ──────────────────────────────────────────────────────────────────────────────
SEMANTIC_JOIN_MAP: Dict[Tuple[str, str], str] = {
    # customer joins
    ("customers",    "accounts"):     "customer_id",
    ("customers",    "transactions"): "customer_id",
    ("customers",    "risk_flags"):   "customer_id",
    ("customers",    "loan_contracts"):"customer_id",
    ("customers",    "loans"):        "customer_id",
    ("customers",    "kyc_cases"):    "customer_id",
    ("customers",    "aml_alerts"):   "customer_id",
    # account joins
    ("accounts",     "transactions"): "account_id",
    ("accounts",     "branches"):     "branch_id",
    ("accounts",     "loan_contracts"):"account_id",
    ("accounts",     "loans"):        "account_id",
    ("accounts",     "risk_flags"):   "account_id",
    ("accounts",     "fee_income"):   "account_id",
    # branch joins
    ("branches",     "accounts"):     "branch_id",
    ("branches",     "employees"):    "branch_id",
    ("branches",     "loan_contracts"):"branch_id",
    ("branches",     "loans"):        "branch_id",
    # loan joins
    ("loan_contracts","customers"):   "customer_id",
    ("loan_contracts","accounts"):    "account_id",
    ("loan_contracts","branches"):    "branch_id",
    ("loan_contracts","provisions"):  "loan_id",
    ("loan_contracts","non_performing_loans"): "loan_id",
    ("loans",        "customers"):    "customer_id",
    ("loans",        "accounts"):     "account_id",
    ("loans",        "branches"):     "branch_id",
    # risk joins
    ("risk_flags",   "customers"):    "customer_id",
    ("risk_flags",   "accounts"):     "account_id",
    # employee joins
    ("employees",    "branches"):     "branch_id",
    # fee income joins
    ("fee_income",   "accounts"):     "account_id",
    ("fee_income",   "customers"):    "customer_id",
    # provision joins
    ("provisions",   "loan_contracts"):"loan_id",
    ("provisions",   "loans"):        "loan_id",
    # kyc joins
    ("kyc_cases",    "customers"):    "customer_id",
    # aml joins
    ("aml_alerts",   "customers"):    "customer_id",
    ("aml_alerts",   "transactions"): "transaction_id",
}

# ──────────────────────────────────────────────────────────────────────────────
# PRIMARY TABLE for each entity (the "source of truth" table)
# ──────────────────────────────────────────────────────────────────────────────
ENTITY_PRIMARY_TABLE: Dict[str, str] = {
    "customer":    "customers",
    "customers":   "customers",
    "account":     "accounts",
    "accounts":    "accounts",
    "transaction": "transactions",
    "transactions":"transactions",
    "branch":      "branches",
    "branches":    "branches",
    "product":     "products",
    "products":    "products",
    "risk":        "risk_flags",
    "risk_flags":  "risk_flags",
    "loan":        "loan_contracts",
    "loans":       "loan_contracts",
    "loan_contract":"loan_contracts",
    "loan_contracts":"loan_contracts",
    "provision":   "provisions",
    "provisions":  "provisions",
    "employee":    "employees",
    "employees":   "employees",
    "fee_income":  "fee_income",
    "kyc_case":    "kyc_cases",
    "kyc_cases":   "kyc_cases",
    "aml_alert":   "aml_alerts",
    "aml_alerts":  "aml_alerts",
    "compliance_violation": "compliance_violations",
    "compliance_violations": "compliance_violations",
    "suspicious_activity_report": "suspicious_activity_reports",
    "suspicious_activity_reports": "suspicious_activity_reports",
}


def get_primary_key(entity: str) -> str:
    """Return canonical PK column name for entity."""
    entity_lower = entity.lower()
    if entity_lower in ENTITY_TO_PRIMARY_KEY:
        return ENTITY_TO_PRIMARY_KEY[entity_lower]
    # fallback: append _id
    return f"{entity_lower}_id"


def get_primary_table(entity: str) -> str:
    """Return the main table for an entity (e.g. customer → customers)."""
    entity_lower = entity.lower()
    return ENTITY_PRIMARY_TABLE.get(entity_lower, f"{entity_lower}s")


def get_tables_containing_key(join_key: str, tables: List[str]) -> List[str]:
    """Return subset of tables that have the given join_key column."""
    result = []
    for table in tables:
        cols = TABLE_ENTITY_COLUMNS.get(table, [])
        if join_key in cols:
            result.append(table)
    return result


def find_join_key(from_table: str, to_table: str) -> Optional[str]:
    """Find semantic join key between two tables (tries both directions)."""
    key = SEMANTIC_JOIN_MAP.get((from_table, to_table))
    if key:
        return key
    key = SEMANTIC_JOIN_MAP.get((to_table, from_table))
    return key


def build_join_structure(primary_table: str, join_key: str, other_tables: List[str]):
    """
    Build ordered join paths from primary_table to each other table.
    Returns list of join dicts.
    """
    from models import JoinPath  # local import to avoid circular

    joins = []
    for table in other_tables:
        if table == primary_table:
            continue
        key = find_join_key(primary_table, table) or join_key
        condition = f"{primary_table}.{key} = {table}.{key}"
        joins.append(JoinPath(
            from_table=primary_table,
            to_table=table,
            join_key=key,
            join_type="INNER JOIN",
            condition=condition,
        ))
    return joins
