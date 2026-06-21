#!/usr/bin/env python3
"""
scripts/apply_all_migrations.py
Applies all schema and seed migrations to the banking database.
"""
import asyncio
import asyncpg
import os
import sys

DB_URL = "postgresql://banking_user:securepass123@localhost:5432/banking_dev"

MIGRATION_FILES = [
    "init/02-users-kpis.sql",
    "init/03-semantic-layer.sql",
    "init/04-loan-domain.sql",
    "init/05-kyc-aml-domain.sql",
    "init/06-finance-gl-domain.sql",
    "init/07-org-customer-ext.sql",
    "init/08-semantic-layer-seed.sql",
    "init/09-tunisian-banking-data-seed.sql"
]

async def apply_migrations():
    print(f"Connecting to database at {DB_URL}...")
    try:
        conn = await asyncpg.connect(DB_URL)
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)
        
    for migration in MIGRATION_FILES:
        if not os.path.exists(migration):
            print(f"[ERROR] Migration file not found: {migration}")
            await conn.close()
            sys.exit(1)
            
        print(f"Applying migration: {migration}...")
        with open(migration, "r", encoding="utf-8") as f:
            sql = f.read()
            
        try:
            # We wrap execution in a transaction block
            async with conn.transaction():
                await conn.execute(sql)
            print(f"  [SUCCESS] Applied {migration}")
        except Exception as e:
            print(f"  [ERROR] Failed to apply {migration}: {e}")
            await conn.close()
            sys.exit(1)
            
    print("\nAll migrations and data seeds applied successfully!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(apply_migrations())
