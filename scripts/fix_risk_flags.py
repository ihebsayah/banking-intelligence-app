file_path = "services/orchestrator/orchestrator_agent.py"
with open(file_path, "r") as f:
    content = f.read()

content = content.replace('risk_flags.flagged_at', 'risk_flags.created_at')
content = content.replace('risk_flags.risk_id', 'risk_flags.id')

with open(file_path, "w") as f:
    f.write(content)
