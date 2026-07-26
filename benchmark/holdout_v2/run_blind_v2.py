#!/usr/bin/env python3
"""Execute blind benchmark V2 via HTTP API Gateway."""
import json
import time
import requests
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE = "http://localhost:8000"
BATCH_SIZE = 5
USERNAME = "admin_001"
PASSWORD = "password"

_token_cache = {"token": None, "expires": 0}

def get_token():
    now = time.time()
    if _token_cache["token"] and _token_cache["expires"] > now + 30:
        return _token_cache["token"]
    resp = requests.post(f"{API_BASE}/auth/login", data={"username": USERNAME, "password": PASSWORD}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires"] = now + data.get("expires_in", 28800)
    return _token_cache["token"]

def extract_pipeline_info(data: dict) -> dict:
    """Extract key info from the API response."""
    steps = data.get("pipeline_steps", [])
    step_agents = [s.get("agent") for s in steps if s.get("status") == "success"]
    
    intent_step = next((s for s in steps if s.get("agent") == "intent"), {})
    intent_resp = intent_step.get("response", {})
    
    insights_step = next((s for s in steps if s.get("agent") == "insights"), {})
    insights_resp = insights_step.get("response", {})
    
    clarification = intent_resp.get("clarification_question")
    intent_confidence = intent_resp.get("intent_confidence", 0)
    supported = intent_resp.get("supported_capability", True)
    risk_level = intent_resp.get("risk_level", "unknown")
    
    if data.get("error"):
        pipeline_stage = "error"
    elif clarification:
        pipeline_stage = "clarification"
    elif not supported:
        pipeline_stage = "unsupported"
    elif "insights" in step_agents and insights_resp.get("status") == "success":
        pipeline_stage = "pipeline_complete"
    elif "execution" in step_agents:
        pipeline_stage = "execution_complete"
    else:
        pipeline_stage = "partial"
    
    answer = ""
    if insights_resp.get("summary"):
        answer = insights_resp["summary"]
    elif data.get("message"):
        answer = data["message"]
    
    confidence = insights_resp.get("confidence", intent_confidence)
    
    return {
        "pipeline_stage": pipeline_stage,
        "answer": answer[:500],
        "confidence": confidence,
        "clarification": clarification or "",
        "intent_confidence": intent_confidence,
        "supported_capability": supported,
        "risk_level": risk_level,
        "pipeline_agents": step_agents,
        "rows_returned": data.get("metadata", {}).get("rows_returned", 0),
        "error_detail": data.get("error"),
    }

def execute_query(question: str, qid: str) -> dict:
    session_id = str(uuid.uuid4())[:8]
    start = time.time()
    try:
        token = get_token()
        resp = requests.post(
            f"{API_BASE}/query",
            json={"query": question, "session_id": session_id},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=120
        )
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            data = resp.json()
            info = extract_pipeline_info(data)
            return {
                "id": qid,
                "query": question,
                "status": "success",
                "api_status": data.get("status"),
                **info,
                "elapsed_seconds": round(elapsed, 2)
            }
        else:
            return {
                "id": qid,
                "query": question,
                "status": f"http_{resp.status_code}",
                "pipeline_stage": "http_error",
                "error_detail": resp.text[:200],
                "elapsed_seconds": round(elapsed, 2)
            }
    except Exception as e:
        return {
            "id": qid,
            "query": question,
            "status": "exception",
            "pipeline_stage": "exception",
            "error_detail": str(e)[:200],
            "elapsed_seconds": round(time.time() - start, 2)
        }

def main():
    with open("benchmark/holdout_v2/blind_v2_questions.json") as f:
        questions = json.load(f)
    
    # Pre-authenticate
    print("Authenticating...")
    get_token()
    print("Token acquired.\n")
    
    results = []
    total = len(questions)
    
    for i in range(0, total, BATCH_SIZE):
        batch = questions[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"Batch {batch_num}/{total_batches}: questions {i+1}-{min(i+BATCH_SIZE, total)}")
        
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
            futures = {
                executor.submit(execute_query, q["query"], q["id"]): q
                for q in batch
            }
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                icon = "✓" if result["status"] == "success" else "✗"
                stage = result.get("pipeline_stage", "unknown")
                conf = result.get("confidence", "")
                lat = result.get("elapsed_seconds", 0)
                print(f"  [{icon}] {result['id']}: stage={stage} conf={conf} {lat}s")
        
        if i + BATCH_SIZE < total:
            time.sleep(0.3)
    
    # Sort by ID for consistent output
    results.sort(key=lambda r: r["id"])
    
    # Save raw results
    with open("benchmark/holdout_v2/blind_v2_run.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    
    # Compute summary
    total_q = len(results)
    success = sum(1 for r in results if r["status"] == "success")
    pipeline_complete = sum(1 for r in results if r.get("pipeline_stage") == "pipeline_complete")
    execution_complete = sum(1 for r in results if r.get("pipeline_stage") == "execution_complete")
    clarification = sum(1 for r in results if r.get("pipeline_stage") == "clarification")
    unsupported = sum(1 for r in results if r.get("pipeline_stage") == "unsupported")
    http_errors = sum(1 for r in results if r["status"] != "success")
    
    conf_vals = [r.get("confidence", 0) for r in results if r["status"] == "success" and r.get("confidence")]
    avg_confidence = round(sum(conf_vals) / max(len(conf_vals), 1), 3)
    
    lat_vals = [r.get("elapsed_seconds", 0) for r in results]
    avg_latency = round(sum(lat_vals) / max(len(lat_vals), 1), 2)
    p50_latency = round(sorted(lat_vals)[len(lat_vals)//2], 2) if lat_vals else 0
    p95_latency = round(sorted(lat_vals)[int(len(lat_vals)*0.95)], 2) if lat_vals else 0
    
    summary = {
        "total": total_q,
        "success_http": success,
        "http_error_rate": round((http_errors / max(total_q, 1)) * 100, 1),
        "pipeline_complete": pipeline_complete,
        "execution_complete": execution_complete,
        "clarification": clarification,
        "unsupported": unsupported,
        "http_errors": http_errors,
        "pipeline_complete_rate": round((pipeline_complete / max(total_q, 1)) * 100, 1),
        "avg_confidence": avg_confidence,
        "avg_latency_seconds": avg_latency,
        "p50_latency_seconds": p50_latency,
        "p95_latency_seconds": p95_latency,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    
    with open("benchmark/holdout_v2/blind_v2_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"BLIND BENCHMARK V2 - EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total questions:    {total_q}")
    print(f"HTTP success:       {success} ({summary['http_error_rate']}% error rate)")
    print(f"Pipeline complete:  {pipeline_complete} ({summary['pipeline_complete_rate']}%)")
    print(f"Execution complete: {execution_complete}")
    print(f"Clarification:      {clarification}")
    print(f"Unsupported:        {unsupported}")
    print(f"HTTP errors:        {http_errors}")
    print(f"Avg confidence:     {avg_confidence}")
    print(f"Avg latency:        {avg_latency}s")
    print(f"P50 latency:        {p50_latency}s")
    print(f"P95 latency:        {p95_latency}s")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
