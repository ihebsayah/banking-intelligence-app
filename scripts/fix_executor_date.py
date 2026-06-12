import re

file_path = "services/execution_agent/query_executor.py"
with open(file_path, "r") as f:
    content = f.read()

# We need to add datetime logic to _convert_placeholders
old_code = """    # Already postgres-style? Just unwrap any ParameterValue objects
    if re.search(r'\$\d+', sql):
        pg_params = []
        for p in parameters:
            pg_params.append(p.value if hasattr(p, 'value') else p)
        return sql, pg_params

    idx = 0
    pg_params = []
    result = []
    for char in sql:
        if char == "?":
            if idx < len(parameters):
                p = parameters[idx]
                if hasattr(p, "value"):
                    p = p.value
                pg_params.append(p)
                idx += 1
                result.append(f"${idx}")
            else:
                result.append(char)
        else:
            result.append(char)
    return "".join(result), pg_params"""

new_code = """    from datetime import datetime
    
    def _parse_val(val):
        if isinstance(val, str) and re.match(r"^\d{4}-\d{2}-\d{2}", val):
            try:
                # if it has time, parse time, else just date
                if len(val) > 10:
                    return datetime.fromisoformat(val.replace("Z", "+00:00"))
                else:
                    return datetime.strptime(val[:10], "%Y-%m-%d").date()
            except ValueError:
                pass
        return val

    # Already postgres-style? Just unwrap any ParameterValue objects
    if re.search(r'\$\d+', sql):
        pg_params = []
        for p in parameters:
            val = p.value if hasattr(p, 'value') else p
            pg_params.append(_parse_val(val))
        return sql, pg_params

    idx = 0
    pg_params = []
    result = []
    for char in sql:
        if char == "?":
            if idx < len(parameters):
                p = parameters[idx]
                val = p.value if hasattr(p, "value") else p
                pg_params.append(_parse_val(val))
                idx += 1
                result.append(f"${idx}")
            else:
                result.append(char)
        else:
            result.append(char)
    return "".join(result), pg_params"""

content = content.replace(old_code, new_code)

with open(file_path, "w") as f:
    f.write(content)

