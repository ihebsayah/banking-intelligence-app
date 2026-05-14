"""
services/validation_agent/injection_tester.py
22 real SQL injection attack vectors for verification testing.
The /test_injections endpoint runs all of these through the validator.
All must be BLOCKED (blocked=22, vulnerable=0).
"""
from typing import List, Dict, Any

# ──────────────────────────────────────────────────────────────────────────────
# 22 REAL SQL INJECTION ATTACK VECTORS
# ──────────────────────────────────────────────────────────────────────────────
SQL_INJECTION_TESTS: List[Dict[str, Any]] = [
    # ── 1. Comment injection + DROP ───────────────────────────────────────────
    {
        "id": 1,
        "name": "Comment injection — DROP after comment",
        "sql": "SELECT * FROM customers; -- DROP TABLE customers",
        "category": "comment_injection",
    },
    # ── 2. Stacked query — DELETE ─────────────────────────────────────────────
    {
        "id": 2,
        "name": "Stacked query — DELETE",
        "sql": "SELECT * FROM customers; DELETE FROM customers WHERE 1=1",
        "category": "stacked_queries",
    },
    # ── 3. UNION SELECT injection ─────────────────────────────────────────────
    {
        "id": 3,
        "name": "UNION SELECT — credentials exfil",
        "sql": "SELECT customer_id FROM customers UNION SELECT password FROM users LIMIT 100",
        "category": "union_injection",
    },
    # ── 4. OR 1=1 bypass ──────────────────────────────────────────────────────
    {
        "id": 4,
        "name": "OR 1=1 — authentication bypass",
        "sql": "SELECT * FROM customers WHERE customer_id = ? OR 1=1 LIMIT 100",
        "category": "or_bypass",
    },
    # ── 5. Tautology — AND 1=1 ───────────────────────────────────────────────
    {
        "id": 5,
        "name": "AND 1=1 tautology",
        "sql": "SELECT * FROM accounts WHERE status = 'active' AND 1=1 LIMIT 100",
        "category": "tautology",
    },
    # ── 6. Time-based blind — SLEEP ──────────────────────────────────────────
    {
        "id": 6,
        "name": "Time-based blind — SLEEP(5)",
        "sql": "SELECT * FROM customers WHERE customer_id = 1 AND SLEEP(5) LIMIT 100",
        "category": "time_based_blind",
    },
    # ── 7. Time-based blind — BENCHMARK ──────────────────────────────────────
    {
        "id": 7,
        "name": "Time-based blind — BENCHMARK",
        "sql": "SELECT * FROM customers WHERE 1=BENCHMARK(1000000,MD5('test')) LIMIT 100",
        "category": "time_based_blind",
    },
    # ── 8. DROP TABLE ─────────────────────────────────────────────────────────
    {
        "id": 8,
        "name": "DROP TABLE attack",
        "sql": "DROP TABLE customers",
        "category": "ddl_attack",
    },
    # ── 9. INSERT injection ───────────────────────────────────────────────────
    {
        "id": 9,
        "name": "INSERT injection",
        "sql": "INSERT INTO customers (email) VALUES ('attacker@evil.com')",
        "category": "dml_attack",
    },
    # ── 10. UPDATE injection ──────────────────────────────────────────────────
    {
        "id": 10,
        "name": "UPDATE injection",
        "sql": "UPDATE customers SET credit_score = 999 WHERE 1=1",
        "category": "dml_attack",
    },
    # ── 11. Hex encoding bypass ───────────────────────────────────────────────
    {
        "id": 11,
        "name": "Hex encoding bypass",
        "sql": "SELECT * FROM customers WHERE customer_id = 0x31 LIMIT 100",
        "category": "encoding_bypass",
    },
    # ── 12. Boolean blind — OR TRUE ──────────────────────────────────────────
    {
        "id": 12,
        "name": "Boolean blind — OR TRUE",
        "sql": "SELECT * FROM customers WHERE status = 'inactive' OR TRUE LIMIT 100",
        "category": "boolean_blind",
    },
    # ── 13. Information schema access ─────────────────────────────────────────
    {
        "id": 13,
        "name": "INFORMATION_SCHEMA access",
        "sql": "SELECT table_name FROM INFORMATION_SCHEMA.TABLES LIMIT 100",
        "category": "schema_enumeration",
    },
    # ── 14. Subquery injection ────────────────────────────────────────────────
    {
        "id": 14,
        "name": "Subquery injection — exfil passwords",
        "sql": "SELECT * FROM customers WHERE customer_id = (SELECT id FROM users WHERE email='admin@bank.com') LIMIT 100",
        "category": "subquery_injection",
    },
    # ── 15. Block comment bypass ──────────────────────────────────────────────
    {
        "id": 15,
        "name": "Block comment bypass",
        "sql": "SELECT * FROM customers WHERE /*injected*/ 1=1 LIMIT 100",
        "category": "comment_bypass",
    },
    # ── 16. UNION ALL SELECT ──────────────────────────────────────────────────
    {
        "id": 16,
        "name": "UNION ALL SELECT injection",
        "sql": "SELECT customer_id FROM customers UNION ALL SELECT secret_key FROM api_keys LIMIT 100",
        "category": "union_injection",
    },
    # ── 17. System variable — @@version ──────────────────────────────────────
    {
        "id": 17,
        "name": "System variable — @@version",
        "sql": "SELECT @@version LIMIT 100",
        "category": "system_variable",
    },
    # ── 18. pg_sleep (PostgreSQL) ─────────────────────────────────────────────
    {
        "id": 18,
        "name": "PostgreSQL pg_sleep blind",
        "sql": "SELECT * FROM customers WHERE customer_id = 1 AND (SELECT pg_sleep(5)) IS NOT NULL LIMIT 100",
        "category": "time_based_blind",
    },
    # ── 19. CHAR() encoding bypass ────────────────────────────────────────────
    {
        "id": 19,
        "name": "CHAR() encoding bypass",
        "sql": "SELECT * FROM customers WHERE name = CHAR(65,100,109,105,110) LIMIT 100",
        "category": "encoding_bypass",
    },
    # ── 20. Inline comment stripping (MySQL) ──────────────────────────────────
    {
        "id": 20,
        "name": "Inline comment stripping -- bypass",
        "sql": "SELECT * FROM customers WHERE customer_id = 1 --' AND active=1 LIMIT 100",
        "category": "comment_injection",
    },
    # ── 21. LOAD DATA INFILE ──────────────────────────────────────────────────
    {
        "id": 21,
        "name": "LOAD DATA INFILE attack",
        "sql": "LOAD DATA INFILE '/etc/passwd' INTO TABLE customers",
        "category": "file_attack",
    },
    # ── 22. xp_cmdshell (MSSQL) ──────────────────────────────────────────────
    {
        "id": 22,
        "name": "xp_cmdshell OS command injection",
        "sql": "EXEC xp_cmdshell('whoami')",
        "category": "os_injection",
    },
]


class InjectionTester:
    """Runs all injection tests through the validator and reports results."""

    def __init__(self, validator):
        self.validator = validator

    def test_all_injections(self) -> Dict:
        from models import QueryValidationRequest

        results = []
        blocked = 0
        vulnerable = 0

        for tc in SQL_INJECTION_TESTS:
            req = QueryValidationRequest(
                sql=tc["sql"],
                parameters=[],
                user_role="analyst",
            )
            result = self.validator.validate(req)

            is_blocked = not result.safe  # injection = unsafe = blocked ✓

            if is_blocked:
                blocked += 1
            else:
                vulnerable += 1

            results.append({
                "id": tc["id"],
                "name": tc["name"],
                "category": tc["category"],
                "sql_snippet": tc["sql"][:80] + "..." if len(tc["sql"]) > 80 else tc["sql"],
                "blocked": is_blocked,
                "issues_detected": result.issues,
                "checks_failed": result.checks_failed,
            })

        return {
            "total_tests": len(SQL_INJECTION_TESTS),
            "blocked": blocked,
            "vulnerable": vulnerable,
            "block_rate": f"{blocked}/{len(SQL_INJECTION_TESTS)}",
            "all_blocked": vulnerable == 0,
            "results": results,
        }
