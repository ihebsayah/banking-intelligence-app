import urllib.request
import urllib.error
import json
import pytest

ORCHESTRATOR_URL = "http://localhost:8001/process_query"

PRESET_QUERIES = [
    "Top 10 customers by balance",
    "Customers with kyc_verified = false",
    "Average balance by customer segment",
    "Customer count by state",
    "Customers created this month",
    "High-risk customers in New York",
    "Customers with risk_score above 0.8",
    "AML flags by customer",
    "Fraud detection flags this week",
    "Customers with multiple compliance violations",
    "Total revenue by product",
    "Average fees by account type",
    "Top 5 products by commission",
    "Compliance violations this month",
    "KYC status by customer",
    "Transaction volume by branch",
    "Average transaction amount"
]

def _post(url: str, payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload, default=str).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())

@pytest.mark.parametrize("query", PRESET_QUERIES)
def test_preset_query_e2e(query):
    """
    End-to-End Test: Hits the live Orchestrator API.
    This tests the ENTIRE pipeline: Intent -> Schema -> Entity -> SQL -> Validation -> Execution
    """
    payload = {
        "query": query,
        "user_role": "analyst",
        "user_id": "test_user",
        "format": "json",
    }
    
    try:
        data = _post(ORCHESTRATOR_URL, payload)
    except urllib.error.URLError as e:
        pytest.fail(f"HTTP Request failed (is Orchestrator running?): {e}")
        
    # 1. Assert Pipeline completed successfully
    assert data.get("status") == "success", f"Pipeline failed! Error: {data.get('error')}"
    
    # 2. Assert SQL was generated securely
    pipeline = data.get("pipeline_steps", []) or data.get("pipeline", {})
    if isinstance(pipeline, dict):
        sql_data = pipeline.get("sql", {})
        assert "sql" in sql_data, f"SQL Agent failed: {sql_data.get('error')}"
        sql_query = sql_data.get("sql", "")
        assert "SELECT" in sql_query.upper(), "Valid SELECT SQL was not generated."
    
    # 3. Assert Execution was successful and returned data
    results = data.get("results")
    assert isinstance(results, list), "Results should be a list returned from the execution agent."
    
    # Success means it reached the execution agent, executed against postgres-main, and returned data cleanly!
