import requests

resp = requests.post("http://localhost:3000/api/query", json={"query": "Top 100 customers by balance", "format": "json"})
print(resp.text)
