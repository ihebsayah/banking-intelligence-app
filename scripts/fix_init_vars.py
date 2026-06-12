file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

old = """            limit = 100
            order_by = None
            filters = None
            group_by = None
            columns = None
            tables = None
            join_paths = None"""

new = """            limit = 100
            order_by = ""
            filters = {}
            group_by = []
            columns = []
            tables = []
            join_paths = []"""

content = content.replace(old, new)

with open(file_path, "w") as f:
    f.write(content)
