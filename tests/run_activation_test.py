#!/usr/bin/env python3
"""
tests/run_activation_test.py
Automated run of representative queries under semantic-enabled vs legacy modes.
Saves results and cleans up environment.
"""
import time
import json
import requests
import subprocess
import os

BASE_URL = "http://localhost:8000"

QUERIES = [
    {
        "name": "KPI Formula Resolution",
        "query": "What is our average portfolio risk score?",
        "format": "json"
    },
    {
        "name": "Safe Entity Join Discovery",
        "query": "Show customer names and their account balance",
        "format": "json"
    },
    {
        "name": "Unsafe Entity Join Prevention",
        "query": "Show customer name and audit log action",
        "format": "json"
    }
]

def run_cmd(cmd):
    print(f"Running: {cmd}")
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error: {res.stderr}")
    return res.stdout

def toggle_semantic_layer(enable: bool):
    with open("docker-compose.yml", "r") as f:
        content = f.read()
    
    if enable:
        content = content.replace("SEMANTIC_LAYER_ENABLED=false", "SEMANTIC_LAYER_ENABLED=true")
        print("Toggled SEMANTIC_LAYER_ENABLED to true")
    else:
        content = content.replace("SEMANTIC_LAYER_ENABLED=true", "SEMANTIC_LAYER_ENABLED=false")
        print("Toggled SEMANTIC_LAYER_ENABLED to false")
        
    with open("docker-compose.yml", "w") as f:
        f.write(content)

def wait_for_healthy():
    print("Waiting for agents to become healthy (this can take up to 2-3 mins due to container pip install)...")
    for i in range(120):
        try:
            r1 = requests.get("http://localhost:8004/health", timeout=2).json()
            r2 = requests.get("http://localhost:8005/health", timeout=2).json()
            if r1.get("status") == "healthy" and r2.get("status") == "healthy":
                print(f"Agents are healthy and ready on iteration {i}!")
                return True
        except Exception as exc:
            if i % 10 == 0:
                print(f"  [iteration {i}] Still waiting: {exc}")
        time.sleep(2)
    print("Timeout waiting for healthy agents")
    return False

def get_auth_token():
    print("Getting auth token for analyst_001...")
    res = requests.post(
        f"{BASE_URL}/auth/login",
        data={"username": "analyst_001", "password": "password"}
    )
    res.raise_for_status()
    token = res.json()["access_token"]
    print(f"Acquired token: {token[:25]}...")
    return token

def run_queries(token, label):
    results = []
    headers = {"Authorization": f"Bearer {token}"}
    for q in QUERIES:
        print(f"[{label}] Querying: '{q['query']}'")
        try:
            res = requests.post(
                f"{BASE_URL}/query",
                headers=headers,
                json=q
            )
            data = res.json()
            results.append({
                "query_name": q["name"],
                "query_text": q["query"],
                "status": res.status_code,
                "response": data
            })
        except Exception as e:
            results.append({
                "query_name": q["name"],
                "query_text": q["query"],
                "error": str(e)
            })
    return results

def main():
    # 1. Clean up first and make sure it's false
    toggle_semantic_layer(False)
    run_cmd("docker compose up -d")
    if not wait_for_healthy():
        return
        
    token = get_auth_token()
    
    # 2. Run in LEGACY mode (semantic layer disabled)
    print("\n--- Running Legacy Mode Queries ---")
    legacy_results = run_queries(token, "LEGACY")
    
    # 3. Enable SEMANTIC layer
    print("\n--- Enabling Semantic Layer ---")
    toggle_semantic_layer(True)
    run_cmd("docker compose up -d")
    # Wait for restart
    time.sleep(5)
    if not wait_for_healthy():
        toggle_semantic_layer(False)
        run_cmd("docker compose up -d")
        return
        
    # Get agent status
    semantic_agent_status = {
        "schema_agent": requests.get("http://localhost:8003/semantic/health").json(),
        "entity_resolution_agent": requests.get("http://localhost:8004/semantic/health").json(),
        "sql_agent": requests.get("http://localhost:8005/semantic/health").json()
    }
    
    # 4. Run in SEMANTIC mode (semantic layer enabled)
    print("\n--- Running Semantic Mode Queries ---")
    semantic_results = run_queries(token, "SEMANTIC")
    
    # 5. Clean up and restore to false
    print("\n--- Restoring Legacy Mode Default ---")
    toggle_semantic_layer(False)
    run_cmd("docker compose up -d")
    
    # Save results file
    output = {
        "legacy_queries": legacy_results,
        "semantic_queries": semantic_results,
        "semantic_agent_status": semantic_agent_status
    }
    
    with open("tests/PHASE_6B1_QUERY_TEST_RESULTS.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nVerification query tests complete. Results saved to tests/PHASE_6B1_QUERY_TEST_RESULTS.json")

if __name__ == "__main__":
    main()
