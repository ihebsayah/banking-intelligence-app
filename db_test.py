import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect("postgresql://banking_user:securepass123@localhost:5432/banking_dev")
    count = await conn.fetchval("SELECT count(*) FROM accounts")
    print("Total accounts:", count)
    
    rows = await conn.fetch("SELECT account_id FROM accounts LIMIT 10")
    print("Sample accounts:", [r['account_id'] for r in rows])
    
    await conn.close()

asyncio.run(main())
