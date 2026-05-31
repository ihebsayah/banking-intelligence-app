import asyncio
from unittest.mock import MagicMock
from services.orchestrator.orchestrator_agent import OrchestratorAgent

async def run():
    agent = OrchestratorAgent(config=MagicMock())
    q = "total revenue by product"
    intent_data = {"primary_category": "customer_analysis", "filters": {"products.customer_id": "123"}}
    schema_data = {"tables": ["accounts"]}
    entity_data = {"primary_entity": "product", "join_structure": []}
    
    # Let's see what variables are set inside the hardcoded block:
    limit = 100
    order_by = ""
    filters = {}
    group_by = []
    columns = []
    tables = []
    join_paths = []
    
    is_preset = any(p[0].lower() in q for p in [
        ("top 10 customers by balance",), ("kyc_verified = false",), ("average balance by customer segment",),
        ("customer count by state",), ("customers created this month",), ("high-risk customers in new york",),
        ("risk_score above 0.8",), ("aml flags by customer",), ("fraud detection flags this week",),
        ("multiple compliance violations",), ("total revenue by product",), ("average fees by account type",),
        ("top 5 products by commission",), ("compliance violations this month",), ("kyc status by customer",),
        ("transaction volume by branch",), ("average transaction amount",)
    ])
    
    # Execute the hardcoded block for this query
    if "total revenue by product" in q:
        group_by = ["accounts.account_type"]
        columns = ["accounts.account_type", "SUM(accounts.balance)"]
        tables = ["accounts"]
    
    payload = {
        "intent": intent_data.get("primary_category", "retrieve"),
        "primary_entity": entity_data.get("primary_entity", "customer"),
        "tables": tables if tables else schema_data.get("tables", ["customers"]),
        "join_paths": join_paths if join_paths else entity_data.get("join_structure", []),
        "limit": limit
    }
    
    if is_preset:
        if order_by: payload["order_by"] = order_by
        if filters: payload["filters"] = filters
        if group_by: payload["group_by"] = group_by
        if columns: payload["columns"] = columns
    else:
        payload["order_by"] = order_by if order_by else intent_data.get("order_by")
        payload["filters"] = filters if filters else intent_data.get("filters")
        payload["group_by"] = group_by if group_by else intent_data.get("group_by")
        payload["columns"] = columns
        
    print("PAYLOAD:", payload)

asyncio.run(run())
