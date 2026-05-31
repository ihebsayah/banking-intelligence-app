import pytest
import sys
import os
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../services/shared")))

from services.orchestrator.orchestrator_agent import OrchestratorAgent

PRESET_QUERIES = [
    ("Top 10 customers by balance", {"limit": 10, "order_by": "accounts.balance DESC"}),
    ("Customers with kyc_verified = false", {"filters": {"kyc_verified": False}}),
    ("Average balance by customer segment", {"group_by": ["customers.segment"], "columns": ["customers.segment", "AVG(accounts.balance)"]}),
    ("Customer count by state", {"group_by": ["branches.state"], "columns": ["branches.state", "COUNT(customers.customer_id)"]}),
    ("Customers created this month", {"filters": {"customers.created_at": {">=": "2020-01-01"}}}),
    ("High-risk customers in New York", {"filters": {"customers.risk_score": {">=": 0.7}, "branches.state": "NY"}}),
    ("Customers with risk_score above 0.8", {"filters": {"risk_score": {">": 0.8}}}),
    ("AML flags by customer", {"filters": {"risk_flags.flag_type": "AML"}, "group_by": ["customers.customer_id"]}),
    ("Fraud detection flags this week", {"filters": {"risk_flags.flag_type": "FRAUD", "risk_flags.created_at": {">=": "2020-01-01"}}}),
    ("Customers with multiple compliance violations", {"group_by": ["customers.customer_id"], "order_by": "COUNT(risk_flags.id) DESC"}),
    ("Total revenue by product", {"group_by": ["accounts.account_type"], "columns": ["accounts.account_type", "SUM(accounts.balance)"]}),
    ("Average fees by account type", {"group_by": ["accounts.account_type"], "columns": ["accounts.account_type", "AVG(accounts.balance)"]}),
    ("Top 5 products by commission", {"limit": 5, "order_by": "accounts.balance DESC"}),
    ("Compliance violations this month", {"filters": {"risk_flags.created_at": {">=": "2020-01-01"}}}),
    ("KYC status by customer", {"group_by": ["customers.kyc_verified"]}),
    ("Transaction volume by branch", {"group_by": ["branches.branch_id"]}),
    ("Average transaction amount", {"columns": ["AVG(transactions.amount)"]})
]

@pytest.mark.asyncio
async def test_orchestrator_preset_queries_mapping():
    config = MagicMock()
    agent = OrchestratorAgent(config=config)
    
    intent_data = {"primary_category": "retrieve"}
    schema_data = {"tables": ["customers"]}
    entity_data = {"primary_entity": "customer", "join_structure": []}
    
    for query, expected in PRESET_QUERIES:
        with patch("services.orchestrator.orchestrator_agent.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"sql": "SELECT ...", "parameters": []}
            mock_client.post.return_value = mock_response
            
            res = await agent._call_sql_agent(intent_data, schema_data, entity_data, query)
            
            assert res["success"] is True, f"Failed for query: {query}"
            mock_client.post.assert_called_once()
            
            # Inspect the payload sent to SQL agent
            kwargs = mock_client.post.call_args[1]
            payload = kwargs["json"]
            
            for key, val in expected.items():
                assert key in payload, f"Expected {key} in payload for '{query}'"
                assert payload[key] == val, f"Mismatch in {key} for '{query}': expected {val}, got {payload[key]}"
