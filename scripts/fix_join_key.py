import json

file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

# We need to add "join_key": "..." to all join_paths
replacements = {
    '"condition": "customers.customer_id = accounts.customer_id"': '"join_key": "customer_id", "condition": "customers.customer_id = accounts.customer_id"',
    '"condition": "accounts.branch_id = branches.branch_id"': '"join_key": "branch_id", "condition": "accounts.branch_id = branches.branch_id"',
    '"condition": "customers.customer_id = risk_flags.customer_id"': '"join_key": "customer_id", "condition": "customers.customer_id = risk_flags.customer_id"',
    '"condition": "products.product_id = accounts.product_id"': '"join_key": "product_id", "condition": "products.product_id = accounts.product_id"',
    '"condition": "branches.branch_id = accounts.branch_id"': '"join_key": "branch_id", "condition": "branches.branch_id = accounts.branch_id"',
    '"condition": "accounts.account_id = transactions.account_id"': '"join_key": "account_id", "condition": "accounts.account_id = transactions.account_id"',
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(file_path, "w") as f:
    f.write(content)

