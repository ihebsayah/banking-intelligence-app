file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

# Replace total revenue by product
old1 = """            elif "total revenue by product" in q:
                group_by = ["products.name"]
                columns = ["products.name", "SUM(accounts.balance)"]
                tables = ["products", "accounts"]
                join_paths = [{"from_table": "products", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "product_id", "condition": "products.product_id = accounts.product_id"}]"""

new1 = """            elif "total revenue by product" in q:
                group_by = ["accounts.account_type"]
                columns = ["accounts.account_type", "SUM(accounts.balance)"]
                tables = ["accounts"]"""

# Replace top 5 products by commission
old2 = """            elif "top 5 products by commission" in q:
                limit = 5
                order_by = "accounts.balance DESC"
                tables = ["products", "accounts"]
                join_paths = [{"from_table": "products", "to_table": "accounts", "join_type": "INNER JOIN", "join_key": "product_id", "condition": "products.product_id = accounts.product_id"}]"""

new2 = """            elif "top 5 products by commission" in q:
                limit = 5
                order_by = "accounts.balance DESC"
                tables = ["accounts"]"""

content = content.replace(old1, new1)
content = content.replace(old2, new2)

with open(file_path, "w") as f:
    f.write(content)
