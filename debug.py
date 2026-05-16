import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient() as client:
        # Step 1: Login
        resp = await client.post("http://localhost:8000/auth/token", data={"username": "alice", "password": "password123"})
        if resp.status_code != 200:
            print("Login failed:", resp.text)
            return
        token = resp.json()["access_token"]
        
        # Step 2: Query
        resp = await client.post(
            "http://localhost:8000/query",
            json={"query": "Top 10 customers by balance", "format": "json"},
            headers={"Authorization": f"Bearer {token}"}
        )
        print(json.dumps(resp.json(), indent=2))

asyncio.run(main())
