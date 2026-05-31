import re

file_path = "services/sql_agent/sql_builder.py"
with open(file_path, "r") as f:
    content = f.read()

# Add a check for date strings in _infer_type
old_infer = """def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    return "string\""""

new_infer = """def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return "date"
    return "string\""""

content = content.replace(old_infer, new_infer)

with open(file_path, "w") as f:
    f.write(content)
