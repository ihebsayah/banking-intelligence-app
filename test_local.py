import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    "http://localhost:8001/process_query",
    data=json.dumps({
        "query": "Customer count by state",
        "user_role": "analyst",
        "user_id": "test",
        "format": "json"
    }).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, context=ctx) as response:
        print(response.read().decode())
except Exception as e:
    print(e.read().decode() if hasattr(e, 'read') else str(e))
