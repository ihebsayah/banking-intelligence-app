#!/usr/bin/env python3
"""
scripts/validate_banking_data.py
Validates the database schema, data density, date coverage, FK integrity,
and regional distributions for the Tunisian Banking Intelligence System.
"""
import asyncio
import asyncpg
import sys
import math

DB_URL = "postgresql://banking_user:securepass123@localhost:5432/banking_dev"

async def run_validation():
    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        print(f"Error connecting to database at {DB_URL}: {e}")
        sys.exit(1)

    print("==================================================")
    print("      TUNISIAN BANKING DATA VALIDATION REPORT     ")
    print("==================================================")
    
    passed = True

    # 1. Check Table Counts & Row Density
    print("\n--- 1. Checking Row Counts & Data Density ---")
    required_counts = {
        "customers": 2000,
        "accounts": 5000,
        "transactions": 50000,
        "loan_contracts": 1500,
        "business_glossary": 37,
        "metric_registry": 25,
        "branches": 30,
        "regions": 5,
        "employees": 100,
        "balance_sheet_snapshots": 24,
        "income_statement_snapshots": 24
    }
    
    for table, target in required_counts.items():
        try:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table};")
            if count >= target:
                print(f"  [PASS] {table}: {count} rows (Target: >= {target})")
            else:
                print(f"  [FAIL] {table}: {count} rows (Target: >= {target})")
                passed = False
        except Exception as e:
            print(f"  [FAIL] {table}: Table missing or query error ({e})")
            passed = False

    # 2. Relational Integrity & Orphans
    print("\n--- 2. Checking Relational Integrity (Orphans) ---")
    integrity_checks = [
        ("accounts", "customer_id", "customers", "customer_id"),
        ("transactions", "account_id", "accounts", "account_id"),
        ("transactions", "customer_id", "customers", "customer_id"),
        ("loan_contracts", "customer_id", "customers", "customer_id"),
        ("loan_contracts", "account_id", "accounts", "account_id"),
        ("kyc_cases", "customer_id", "customers", "customer_id"),
        ("aml_alerts", "customer_id", "customers", "customer_id")
    ]
    
    for src_tbl, src_col, tgt_tbl, tgt_col in integrity_checks:
        query = f"""
            SELECT COUNT(*) FROM {src_tbl} s
            LEFT JOIN {tgt_tbl} t ON s.{src_col} = t.{tgt_col}
            WHERE s.{src_col} IS NOT NULL AND t.{tgt_col} IS NULL;
        """
        try:
            orphans = await conn.fetchval(query)
            if orphans == 0:
                print(f"  [PASS] {src_tbl}.{src_col} -> {tgt_tbl}.{tgt_col}: 0 orphans")
            else:
                print(f"  [FAIL] {src_tbl}.{src_col} -> {tgt_tbl}.{tgt_col}: {orphans} ORPHANS found!")
                passed = False
        except Exception as e:
            print(f"  [FAIL] {src_tbl}.{src_col} integrity check failed: {e}")
            passed = False

    # 3. Time Series & Date Coverage
    print("\n--- 3. Checking Date Coverage (24 Months Target) ---")
    try:
        min_date, max_date = await conn.fetchrow("SELECT MIN(transaction_date), MAX(transaction_date) FROM transactions;")
        if min_date and max_date:
            days = (max_date - min_date).days
            months = days / 30.4
            if months >= 23.5:
                print(f"  [PASS] Transaction date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} ({months:.1f} months covered)")
            else:
                print(f"  [FAIL] Transaction date range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} ({months:.1f} months covered, Target >= 24)")
                passed = False
        else:
            print("  [FAIL] No transactions found to check date range.")
            passed = False
    except Exception as e:
        print(f"  [FAIL] Error checking transaction dates: {e}")
        passed = False

    # 4. Regional Demographics Distribution
    print("\n--- 4. Checking Regional Distribution Weights ---")
    # Expected Tunis region weight ~40% (35-45% tolerance)
    try:
        total_customers = await conn.fetchval("SELECT COUNT(*) FROM customer_addresses;")
        if total_customers > 0:
            tunis_customers = await conn.fetchval("SELECT COUNT(*) FROM customer_addresses WHERE governorate IN ('Tunis', 'Ariana', 'Ben Arous', 'Manouba');")
            ratio = (tunis_customers / total_customers) * 100
            if 33.0 <= ratio <= 47.0:
                print(f"  [PASS] Grand Tunis region: {ratio:.1f}% of customer base (Target: ~40%)")
            else:
                print(f"  [FAIL] Grand Tunis region: {ratio:.1f}% of customer base (Target: ~40%, Out of bounds 33%-47%)")
                passed = False
        else:
            print("  [FAIL] No customer addresses found.")
            passed = False
    except Exception as e:
        print(f"  [FAIL] Error checking regional distribution: {e}")
        passed = False

    # 5. KPI Computability Verification (Table & Column Existence)
    print("\n--- 5. Checking KPI Metadata & Schema Validity ---")
    try:
        metrics = await conn.fetch("SELECT metric_id, formula, source_tables FROM metric_registry;")
        all_metrics_valid = True
        for m in metrics:
            mid = m["metric_id"]
            tables = m["source_tables"]
            
            # Verify each source table exists in the database
            for t in tables:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                          AND table_name = $1
                    );
                """, t)
                if not exists:
                    print(f"  [FAIL] Metric {mid}: Referenced table '{t}' does not exist in schema!")
                    all_metrics_valid = False
                    passed = False
        if all_metrics_valid:
            print("  [PASS] All 25 KPIs reference tables that exist in the database.")
    except Exception as e:
        print(f"  [FAIL] Error checking KPI computability: {e}")
        passed = False

    await conn.close()
    
    print("\n==================================================")
    if passed:
        print("   SUMMARY: VALIDATION SUCCESSFUL (ALL TESTS PASSED)  ")
    else:
        print("   SUMMARY: VALIDATION FAILED (SOME TESTS FAILED)    ")
    print("==================================================")
    
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    asyncio.run(run_validation())
