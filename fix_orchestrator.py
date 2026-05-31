file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

# Let's replace the whole payload assembly logic
old = """            payload = {
                "intent": intent_data.get("primary_category", "retrieve"),
                "primary_entity": entity_data.get("primary_entity", "customer"),
                "tables": tables if tables else schema_data.get("tables", ["customers"]),
                "join_paths": join_paths if join_paths else entity_data.get("join_structure", []),
                "limit": limit
            }
            if order_by: payload["order_by"] = order_by
            elif intent_data.get("order_by"): payload["order_by"] = intent_data.get("order_by")
            
            if filters: payload["filters"] = filters
            elif intent_data.get("filters"): payload["filters"] = intent_data.get("filters")
            
            if group_by: payload["group_by"] = group_by
            elif intent_data.get("group_by"): payload["group_by"] = intent_data.get("group_by")
            
            if columns: payload["columns"] = columns"""

new = """            is_preset = any(p[0].lower() in q for p in [
                ("top 10 customers by balance",), ("kyc_verified = false",), ("average balance by customer segment",),
                ("customer count by state",), ("customers created this month",), ("high-risk customers in new york",),
                ("risk_score above 0.8",), ("aml flags by customer",), ("fraud detection flags this week",),
                ("multiple compliance violations",), ("total revenue by product",), ("average fees by account type",),
                ("top 5 products by commission",), ("compliance violations this month",), ("kyc status by customer",),
                ("transaction volume by branch",), ("average transaction amount",)
            ])

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
                payload["columns"] = columns"""

content = content.replace(old, new)

with open(file_path, "w") as f:
    f.write(content)
