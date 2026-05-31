file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

old = """            payload = {
                "intent": intent_data.get("primary_category", "retrieve"),
                "primary_entity": entity_data.get("primary_entity", "customer"),
                "tables": tables if tables else schema_data.get("tables", ["customers"]),
                "join_paths": join_paths if join_paths else entity_data.get("join_structure", []),
                "limit": limit
            }"""

new = """            payload = {
                "intent": intent_data.get("primary_category", "retrieve"),
                "primary_entity": entity_data.get("primary_entity", "customer"),
                "limit": limit
            }
            if is_preset:
                payload["tables"] = tables if tables else ["customers"]
                payload["join_paths"] = join_paths
            else:
                payload["tables"] = tables if tables else schema_data.get("tables", ["customers"])
                payload["join_paths"] = join_paths if join_paths else entity_data.get("join_structure", [])
"""

content = content.replace(old, new)

with open(file_path, "w") as f:
    f.write(content)
