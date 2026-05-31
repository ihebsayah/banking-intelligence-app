import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from services.orchestrator.orchestrator_agent import OrchestratorAgent

async def run():
    config = MagicMock()
    agent = OrchestratorAgent(config=config)
    intent_data = {"primary_category": "retrieve"}
    schema_data = {"tables": ["customers"]}
    entity_data = {"primary_entity": "customer", "join_structure": []}
    
    with patch("services.orchestrator.orchestrator_agent.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"sql": "SELECT ...", "parameters": []}
        mock_client.post.return_value = mock_response
        
        await agent._call_sql_agent(intent_data, schema_data, entity_data, "Customer count by state")
        kwargs = mock_client.post.call_args[1]
        print(kwargs["json"]["join_paths"])

asyncio.run(run())
