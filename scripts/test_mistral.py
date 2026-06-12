import asyncio
import sys
sys.path.insert(0, "/Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system")
from services.shared.config import Settings
from services.shared.mistral_client import MistralClient

async def test():
    config = Settings()
    client = MistralClient(
        base_url=config.MISTRAL_API_URL,
        model=config.MISTRAL_MODEL,
        timeout=10,
        max_tokens=100
    )
    if await client.check_health():
        print("Healthy!")
        res = await client.generate("Say hello!")
        print(res)
    else:
        print("Not healthy")

asyncio.run(test())
