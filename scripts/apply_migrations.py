import asyncio
import asyncpg
import os

async def main():
    migration_path = "init/02-users-kpis.sql"
    with open(migration_path, "r") as f:
        sql = f.read()
    
    conn = await asyncpg.connect("postgresql://banking_user:securepass123@localhost:5432/banking_dev")
    print("Applying migrations...")
    await conn.execute(sql)
    print("Migrations applied successfully!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
