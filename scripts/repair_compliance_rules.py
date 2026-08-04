#!/usr/bin/env python3
"""
scripts/repair_compliance_rules.py

Idempotent repair for the compliance_rules table:
  1. Creates a unique index on rule_name (if not exists)
  2. Deduplicates rows by rule_name, keeping the row with the smallest id
  3. Re-inserts the 12 canonical rules (ON CONFLICT NO-OP after dedupe)

Safe to run multiple times — produces the same 12-row result every time.

Usage:
  docker exec banking_postgres_main python /scripts/repair_compliance_rules.py
  # or locally:
  python scripts/repair_compliance_rules.py
"""
import os
import sys
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://banking_user:securepass123@localhost:5432/banking_dev",
)

CANONICAL_RULES = [
    ("Mask PII - GDPR",                      "GDPR",    "data_masking",   "column IN (ssn, email, phone, national_id)",                  "MASK_VALUE"),
    ("Right to be Forgotten - 3yr",           "GDPR",    "data_retention", "last_activity < NOW() - INTERVAL 3 YEAR",                    "DELETE_RECORD"),
    ("Data Portability on Request",           "GDPR",    "data_export",    "user_requests_export = true",                                "EXPORT_JSON"),
    ("Mask Card Numbers - PCI-DSS",           "PCI-DSS", "data_masking",   "column IN (credit_card, card_number, pan)",                  "MASK_LAST4"),
    ("Restrict Card Data Access - PCI-DSS",   "PCI-DSS", "access_control", "user_role NOT IN (compliance, admin)",                       "DENY_ACCESS"),
    ("Tokenize Card Data - PCI-DSS",          "PCI-DSS", "data_handling",  "column = credit_card",                                       "TOKENIZE"),
    ("Log All Sensitive Access - SOX",        "SOX",     "audit",          "table IN (accounts, transactions, risk_flags)",              "LOG_ACCESS"),
    ("Segregation of Duties - SOX",           "SOX",     "access_control", "user_role IN (maker_checker)",                               "DENY_ACCESS"),
    ("Change Management Approval - SOX",      "SOX",     "change_control", "schema_change = true",                                       "REQUIRE_APPROVAL"),
    ("Monitor Large Transactions - AML",      "AML",     "monitoring",     "amount > 10000",                                             "FLAG_TRANSACTION"),
    ("Sanctions Screening - AML",             "AML",     "screening",      "new_customer = true",                                        "SCREEN_NAMES"),
    ("Enhanced Due Diligence - KYC",          "KYC",     "due_diligence",  "pep_status = true",                                          "REQUIRE_EDD"),
]


def repair(conn):
    cur = conn.cursor()

    # Step 1: deduplicate — delete every duplicate, keeping the row with min(id)
    cur.execute("""
        DELETE FROM compliance_rules
        WHERE id::text NOT IN (
            SELECT MIN(id::text)
            FROM compliance_rules
            GROUP BY rule_name
        )
    """)
    deleted = cur.rowcount
    conn.commit()
    print(f"[1/3] Removed {deleted} duplicate row(s)")

    # Step 2: add unique index (idempotent — safe after dedupe)
    cur.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_compliance_rules_rule_name "
        "ON compliance_rules(rule_name)"
    )
    conn.commit()
    print("[2/3] Unique index on rule_name ready")

    # Step 3: upsert the 12 canonical rules
    cur.executemany("""
        INSERT INTO compliance_rules (rule_name, regulation, rule_type, condition, action, enabled)
        VALUES (%s, %s, %s, %s, %s, true)
        ON CONFLICT (rule_name) DO UPDATE
        SET regulation = EXCLUDED.regulation,
            rule_type  = EXCLUDED.rule_type,
            condition  = EXCLUDED.condition,
            action     = EXCLUDED.action,
            enabled    = true
    """, CANONICAL_RULES)
    conn.commit()
    print(f"[3/3] Upserted {len(CANONICAL_RULES)} canonical rule(s)")

    # Verify
    cur.execute("SELECT COUNT(*) FROM compliance_rules")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT rule_name) FROM compliance_rules")
    distinct = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM compliance_rules "
        "WHERE rule_name NOT IN ({})".format(",".join(["%s"] * len(CANONICAL_RULES))),
        [r[0] for r in CANONICAL_RULES],
    )
    non_canonical = cur.fetchone()[0]
    print(f"\nVerification: {total} rows, {distinct} distinct rule_name(s), "
          f"{non_canonical} non-canonical")
    assert total == len(CANONICAL_RULES), f"Expected {len(CANONICAL_RULES)} rows, got {total}"
    assert distinct == len(CANONICAL_RULES), f"Expected {len(CANONICAL_RULES)} distinct, got {distinct}"
    assert non_canonical == 0, f"Expected 0 non-canonical, got {non_canonical}"
    print("PASS — compliance_rules is clean")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else DATABASE_URL
    conn = psycopg2.connect(url)
    try:
        repair(conn)
    finally:
        conn.close()
