file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

# I will replace the end of the method
old = """            if order_by: payload["order_by"] = order_by
            if filters: payload["filters"] = filters
            if group_by: payload["group_by"] = group_by
            if columns: payload["columns"] = columns"""

new = """            if order_by: payload["order_by"] = order_by
            elif intent_data.get("order_by"): payload["order_by"] = intent_data.get("order_by")
            
            if filters: payload["filters"] = filters
            elif intent_data.get("filters"): payload["filters"] = intent_data.get("filters")
            
            if group_by: payload["group_by"] = group_by
            elif intent_data.get("group_by"): payload["group_by"] = intent_data.get("group_by")
            
            if columns: payload["columns"] = columns"""

content = content.replace(old, new)

with open(file_path, "w") as f:
    f.write(content)
