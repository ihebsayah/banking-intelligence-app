#!/usr/bin/env python3
"""
tests/week3_local_test.py
Local (no-Docker) test runner for Week 3 agents.
Uses importlib to load each service in isolation — no module collision.

Run: python3 tests/week3_local_test.py
"""
import sys
import os
import importlib.util
import importlib.machinery

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_module(name: str, path: str):
    """Load a Python module from absolute file path with a unique module name."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_service_module(service: str, filename: str, alias: str = None):
    """Load service/<service>/<filename>.py as module alias."""
    path = os.path.join(BASE, "services", service, filename + ".py")
    alias = alias or f"{service}__{filename}"
    return load_module(alias, path)


# ──────────────────────────────────────────────────────────────────────────────
# ENTITY RESOLUTION — 10 test cases
# ──────────────────────────────────────────────────────────────────────────────
def run_entity_resolution_tests():
    print("\n" + "═" * 60)
    print("ENTITY RESOLUTION AGENT — 10 TEST CASES")
    print("═" * 60)

    SVC = "entity_resolution_agent"
    svc_dir = os.path.join(BASE, "services", SVC)
    if svc_dir not in sys.path:
        sys.path.insert(0, svc_dir)

    # Load dependencies first, register as bare names for internal imports
    load_service_module(SVC, "models",             "era_models")
    load_service_module(SVC, "semantic_id_mapper", "era_mapper")
    sys.modules["models"]             = sys.modules["era_models"]
    sys.modules["semantic_id_mapper"] = sys.modules["era_mapper"]
    er_mod = load_service_module(SVC, "entity_resolver", "era_resolver")

    EntityResolutionRequest = sys.modules["era_models"].EntityResolutionRequest
    EntityResolver = er_mod.EntityResolver
    resolver = EntityResolver()

    test_cases = [
        {"id": 1, "entity": "customer", "tables": ["customers", "accounts"],
         "expect_key": "customer_id", "expect_joins": 1},
        {"id": 2, "entity": "customer", "tables": ["customers", "accounts", "transactions"],
         "expect_key": "customer_id", "expect_joins": 2},
        {"id": 3, "entity": "customer", "tables": ["customers", "risk_flags"],
         "expect_key": "customer_id", "expect_joins": 1},
        {"id": 4, "entity": "account", "tables": ["accounts", "transactions"],
         "expect_key": "account_id", "expect_joins": 1},
        {"id": 5, "entity": "account", "tables": ["accounts", "products"],
         "expect_key": "account_id", "expect_joins": 1},
        {"id": 6, "entity": "transaction", "tables": ["transactions"],
         "expect_key": "transaction_id", "expect_joins": 0},
        {"id": 7, "entity": "branch", "tables": ["branches"],
         "expect_key": "branch_id", "expect_joins": 0},
        {"id": 8, "entity": "branch", "tables": ["branches", "accounts"],
         "expect_key": "branch_id", "expect_joins": 1},
        {"id": 9, "entity": "customer", "tables": ["customers", "accounts", "transactions", "risk_flags"],
         "expect_key": "customer_id", "expect_joins": 3},
        {"id": 10, "entity": "loan", "tables": ["loans", "customers", "accounts", "branches"],
         "expect_key": "loan_id", "expect_joins": 3},
    ]

    passed = 0
    for tc in test_cases:
        req = EntityResolutionRequest(primary_entity=tc["entity"], tables=tc["tables"])
        res = resolver.resolve(req)
        key_ok = res.primary_key == tc["expect_key"]
        joins_ok = len(res.join_structure) == tc["expect_joins"]
        ok = key_ok and joins_ok
        if ok:
            passed += 1
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  Test {tc['id']:2d}: {status} | entity={tc['entity']} | "
              f"key={res.primary_key}(expect:{tc['expect_key']}) | "
              f"joins={len(res.join_structure)}(expect:{tc['expect_joins']})")
        if ok and res.join_structure:
            for j in res.join_structure:
                print(f"          JOIN: {j.condition}")

    print(f"\n  RESULT: {passed}/10 passed {'✅' if passed == 10 else '❌'}")
    return passed


# ──────────────────────────────────────────────────────────────────────────────
# SQL GENERATION — 5 test cases
# ──────────────────────────────────────────────────────────────────────────────
def run_sql_generation_tests():
    print("\n" + "═" * 60)
    print("SQL GENERATION AGENT — 5 TEST CASES")
    print("═" * 60)

    SVC = "sql_agent"
    svc_dir = os.path.join(BASE, "services", SVC)
    if svc_dir not in sys.path:
        sys.path.insert(0, svc_dir)

    sql_models_mod = load_service_module(SVC, "models", "sql_models")
    # Ensure builder can find its models via bare import
    sys.modules["models"] = sql_models_mod
    sql_builder_mod = load_service_module(SVC, "sql_builder", "sql_builder")

    SQLGenerationRequest = sql_models_mod.SQLGenerationRequest
    JoinPathInput = sql_models_mod.JoinPathInput
    SQLBuilder = sql_builder_mod.SQLBuilder
    builder = SQLBuilder()

    test_cases = [
        {
            "id": 1,
            "name": "Simple SELECT — customers",
            "request": SQLGenerationRequest(
                intent="retrieve",
                primary_entity="customer",
                tables=["customers"],
                columns=["customer_id", "first_name", "last_name", "email"],
            ),
        },
        {
            "id": 2,
            "name": "SELECT with JOIN — customers + accounts",
            "request": SQLGenerationRequest(
                intent="retrieve",
                primary_entity="customer",
                tables=["customers", "accounts"],
                join_paths=[JoinPathInput(
                    from_table="customers", to_table="accounts",
                    join_key="customer_id", join_type="INNER JOIN",
                    condition="customers.customer_id = accounts.customer_id",
                )],
                columns=["customers.customer_id", "customers.first_name", "accounts.balance"],
            ),
        },
        {
            "id": 3,
            "name": "SELECT with WHERE — balance > ?",
            "request": SQLGenerationRequest(
                intent="filter",
                primary_entity="account",
                tables=["accounts"],
                filters={"balance": {">": 1000}},
                columns=["account_id", "account_number", "balance"],
            ),
        },
        {
            "id": 4,
            "name": "SELECT with GROUP BY — aggregate",
            "request": SQLGenerationRequest(
                intent="aggregate",
                primary_entity="account",
                tables=["accounts"],
                group_by=["branch_id"],
                columns=["branch_id"],
                limit=50,
            ),
        },
        {
            "id": 5,
            "name": "Multiple JOINs — customers + accounts + transactions",
            "request": SQLGenerationRequest(
                intent="retrieve",
                primary_entity="customer",
                tables=["customers", "accounts", "transactions"],
                join_paths=[
                    JoinPathInput(
                        from_table="customers", to_table="accounts",
                        join_key="customer_id", join_type="INNER JOIN",
                        condition="customers.customer_id = accounts.customer_id",
                    ),
                    JoinPathInput(
                        from_table="accounts", to_table="transactions",
                        join_key="account_id", join_type="INNER JOIN",
                        condition="accounts.account_id = transactions.account_id",
                    ),
                ],
                filters={"transactions.amount": {">": 500}},
                limit=200,
            ),
        },
    ]

    passed = 0
    for tc in test_cases:
        try:
            res = builder.build(tc["request"])
            has_limit = "LIMIT" in res.sql.upper()
            has_placeholder = ("?" in res.sql) if res.parameters else True
            ok = has_limit and res.is_parameterized
            if ok:
                passed += 1
            status = "✅ PASS" if ok else "❌ FAIL"
            print(f"\n  Test {tc['id']}: {status} — {tc['name']}")
            print(f"  SQL:\n{res.sql}")
            if res.parameters:
                print(f"  Params: {[(p.name, p.value) for p in res.parameters]}")
            print(f"  has_LIMIT={has_limit} | is_parameterized={res.is_parameterized}")
        except Exception as exc:
            print(f"\n  Test {tc['id']}: ❌ FAIL — {exc}")
            import traceback; traceback.print_exc()

    print(f"\n  RESULT: {passed}/5 passed {'✅' if passed == 5 else '❌'}")
    return passed


# ──────────────────────────────────────────────────────────────────────────────
# INJECTION TESTS — 22 attack vectors
# ──────────────────────────────────────────────────────────────────────────────
def run_injection_tests():
    print("\n" + "═" * 60)
    print("VALIDATION AGENT — 22 INJECTION TESTS")
    print("═" * 60)

    SVC = "validation_agent"
    svc_dir = os.path.join(BASE, "services", SVC)
    if svc_dir not in sys.path:
        sys.path.insert(0, svc_dir)

    val_models_mod = load_service_module(SVC, "models", "val_models")
    sys.modules["models"] = val_models_mod
    validator_mod = load_service_module(SVC, "query_validator", "val_validator")
    tester_mod = load_service_module(SVC, "injection_tester", "val_tester")


    QueryValidator = validator_mod.QueryValidator
    InjectionTester = tester_mod.InjectionTester
    validator = QueryValidator()
    tester = InjectionTester(validator)
    result = tester.test_all_injections()

    for r in result["results"]:
        status = "🛡️ BLOCKED" if r["blocked"] else "🚨 VULNERABLE"
        print(f"  [{r['id']:2d}] {status} | {r['name']}")
        if not r["blocked"]:
            print(f"        SQL: {r['sql_snippet']}")
            print(f"        Issues: {r['issues_detected']}")

    print(f"\n  RESULT: blocked={result['blocked']} vulnerable={result['vulnerable']}")
    if result["all_blocked"]:
        print("  ✅ ALL INJECTIONS BLOCKED — 100% secure")
    else:
        print(f"  ❌ CRITICAL: {result['vulnerable']} injection(s) NOT blocked!")
    return result["blocked"], result["vulnerable"]


# ──────────────────────────────────────────────────────────────────────────────
# GOOD QUERIES — must all PASS validation
# ──────────────────────────────────────────────────────────────────────────────
def run_good_query_tests():
    print("\n" + "═" * 60)
    print("VALIDATION AGENT — GOOD QUERIES (must all PASS)")
    print("═" * 60)

    QueryValidator = sys.modules["val_validator"].QueryValidator
    QueryValidationRequest = sys.modules["val_models"].QueryValidationRequest
    validator = QueryValidator()

    good_queries = [
        "SELECT customer_id, first_name FROM customers WHERE customer_id = ? LIMIT 100",
        "SELECT account_id, balance FROM accounts WHERE balance > ? LIMIT 50",
        "SELECT customers.customer_id, accounts.balance FROM customers INNER JOIN accounts ON customers.customer_id = accounts.customer_id WHERE accounts.status = ? LIMIT 100",
        "SELECT branch_id, COUNT(*) FROM accounts GROUP BY branch_id LIMIT 100",
    ]

    passed = 0
    for i, sql in enumerate(good_queries, 1):
        req = QueryValidationRequest(sql=sql, parameters=["test"])
        res = validator.validate(req)
        if res.safe:
            passed += 1
        status = "✅ PASS" if res.safe else "❌ FAIL"
        sig = "✓ signed" if res.signature else "✗ no sig"
        print(f"  Test {i}: {status} | {sig} | conf={res.confidence}")
        if not res.safe:
            print(f"        Issues: {res.issues}")

    print(f"\n  RESULT: {passed}/4 good queries passed {'✅' if passed == 4 else '❌'}")
    return passed


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "█" * 60)
    print("  WEEK 3 LOCAL TEST SUITE")
    print("█" * 60)

    entity_passed = run_entity_resolution_tests()
    sql_passed = run_sql_generation_tests()
    blocked, vulnerable = run_injection_tests()
    good_passed = run_good_query_tests()

    print("\n" + "█" * 60)
    print("  WEEK 3 SUMMARY")
    print("█" * 60)
    print(f"  Entity Resolution:  {entity_passed}/10 {'✅' if entity_passed == 10 else '❌'}")
    print(f"  SQL Generation:     {sql_passed}/5  {'✅' if sql_passed == 5 else '❌'}")
    print(f"  Injection Blocking: {blocked}/22 {'✅' if vulnerable == 0 else '❌ CRITICAL'}")
    print(f"  Good Query Pass:    {good_passed}/4 {'✅' if good_passed == 4 else '❌'}")

    all_ok = (entity_passed == 10 and sql_passed == 5
              and vulnerable == 0 and good_passed == 4)

    print("\n" + ("✅ WEEK 3 COMPLETE — All acceptance criteria met!"
                  if all_ok else
                  "❌ Some tests failed — review output above"))
    print("█" * 60 + "\n")
    sys.exit(0 if all_ok else 1)
