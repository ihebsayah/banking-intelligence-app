file_path = "services/sql_agent/sql_builder.py"
with open(file_path, "r") as f:
    content = f.read()

if "import re" not in content:
    content = "import re\n" + content
    with open(file_path, "w") as f:
        f.write(content)
