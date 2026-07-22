#!/usr/bin/env python3
"""
benchmark/integration/run_integration.py

End-to-end integration benchmark for the multi-agent banking system.

HTTP-only: no internal class imports. Interacts via API Gateway exactly
as a real client would.

Usage:
    python run_integration.py [--gateway-url http://localhost:8000]
                              [--username admin_001]
                              [--password <password>]
                              [--questions questions.json]
"""
import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    print("pip install httpx")
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
REPORTS_DIR = os.path.join(ROOT, "benchmark", "reports")

# ─── Agent names in pipeline_steps (must match orchestrator output) ──────────
EXPECTED_AGENTS = [
    "intent", "schema", "entity_resolution", "sql",
    "validation", "compliance", "execution", "insights",
]


def _hash(val: Any) -> str:
    """Stable short hash for opaque values."""
    if val is None:
        return "null"
    s = json.dumps(val, sort_keys=True, default=str)
    return hashlib.sha256(s.encode()).hexdigest()[:12]


class IntegrationBenchmark:
    """Runs questions through the full production HTTP path."""

    def __init__(self, gateway_url: str, username: str, password: str):
        self.gateway_url = gateway_url.rstrip("/")
        self.username = username
        self.password = password
        self.token: Optional[str] = None
        self.results: List[Dict] = []
        self.client = httpx.Client(timeout=300.0)

    # ─── Auth ──────────────────────────────────────────────────────────────

    def login(self) -> bool:
        """Authenticate and store JWT."""
        url = f"{self.gateway_url}/auth/login"
        try:
            r = self.client.post(url, data={
                "username": self.username,
                "password": self.password,
            })
            if r.status_code == 200:
                data = r.json()
                self.token = data.get("access_token")
                print(f"Logged in as {self.username} (role={data.get('user_role')})")
                return True
            print(f"Login failed: {r.status_code} {r.text[:200]}")
            return False
        except httpx.ConnectError:
            print(f"Cannot connect to gateway at {self.gateway_url}")
            return False

    def _headers(self, include_auth: bool = True) -> Dict[str, str]:
        h = {"Content-Type": "application/json"}
        if include_auth and self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    # ─── Single question ───────────────────────────────────────────────────

    def run_question(self, q: Dict) -> Dict:
        """Execute one question through the full production path."""
        qid = q["id"]
        query_text = q.get("query", "")
        no_auth = q.get("no_auth", False)
        send_empty = q.get("send_empty_json", False)

        trace: Dict[str, Any] = {
            "question_id": qid,
            "category": q.get("category"),
            "language": q.get("language"),
            "difficulty": q.get("difficulty"),
            "query": query_text,
            "supported": q.get("supported"),
            "expected_behavior": q.get("expected_behavior"),
            "correlation_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services_reached": [],
            "pipeline_steps": [],
            "agents_invoked": {},
            "latency_breakdown": {},
            "final_status": None,
            "http_status": None,
            "error": None,
        }

        t_start = time.monotonic()

        # Build request
        if send_empty:
            payload = {}
        else:
            payload = {"query": query_text, "format": "json"}

        headers = self._headers(include_auth=not no_auth)

        try:
            t_req = time.monotonic()
            r = self.client.post(
                f"{self.gateway_url}/query",
                json=payload,
                headers=headers,
            )
            t_resp = time.monotonic()
            trace["http_status"] = r.status_code
            trace["latency_breakdown"]["gateway_total_ms"] = round((t_resp - t_req) * 1000, 2)

            if r.status_code == 200:
                data = r.json()
                trace["final_status"] = data.get("status")
                trace["results"] = data.get("results")
                trace["metadata"] = data.get("metadata")
                trace["insights"] = data.get("insights")
                trace["error"] = data.get("error")
                trace["message"] = data.get("message")
                trace["request_id"] = data.get("request_id")

                # Parse pipeline steps
                steps = data.get("pipeline_steps", [])
                trace["pipeline_steps"] = steps
                for step in steps:
                    agent = step.get("agent", "unknown")
                    status = step.get("status", "unknown")
                    trace["agents_invoked"][agent] = {
                        "invoked": True,
                        "status": status,
                        "response_hash": _hash(step.get("response")),
                    }
                    if agent not in trace["services_reached"]:
                        trace["services_reached"].append(agent)

                # Check if all expected agents were reached
                trace["early_stop"] = None
                for agent in EXPECTED_AGENTS:
                    if agent not in trace["agents_invoked"]:
                        if agent == "insights":
                            continue  # insights is optional
                        trace["early_stop"] = agent
                        break

            elif r.status_code in (401, 403):
                trace["final_status"] = "auth_blocked"
                try:
                    trace["error"] = r.json()
                except Exception:
                    trace["error"] = r.text[:200]

            elif r.status_code == 422:
                trace["final_status"] = "validation_error"
                try:
                    trace["error"] = r.json()
                except Exception:
                    trace["error"] = r.text[:200]

            else:
                trace["final_status"] = "http_error"
                trace["error"] = f"HTTP {r.status_code}: {r.text[:300]}"

        except httpx.TimeoutException:
            trace["final_status"] = "timeout"
            trace["error"] = "Request timed out"
        except httpx.ConnectError:
            trace["final_status"] = "connection_error"
            trace["error"] = f"Cannot connect to {self.gateway_url}"
        except Exception as e:
            trace["final_status"] = "exception"
            trace["error"] = str(e)

        trace["latency_breakdown"]["total_ms"] = round((time.monotonic() - t_start) * 1000, 2)
        return trace

    # ─── Run all questions ──────────────────────────────────────────────────

    def run_all(self, questions: List[Dict]) -> List[Dict]:
        """Run all questions and collect traces."""
        total = len(questions)
        for i, q in enumerate(questions, 1):
            print(f"[{i}/{total}] {q['id']}: {(q.get('query') or '(no query)')[:60]}...")
            trace = self.run_question(q)
            self.results.append(trace)
            status = trace["final_status"]
            http = trace["http_status"]
            ms = trace["latency_breakdown"].get("total_ms", 0)
            agents = len(trace["services_reached"])
            print(f"  → {status} (HTTP {http}, {ms:.0f}ms, {agents} agents)")
        return self.results

    def close(self):
        self.client.close()


# ─── Scoring ─────────────────────────────────────────────────────────────────

def score_results(results: List[Dict], questions: List[Dict]) -> Dict:
    """Score integration benchmark results."""
    q_map = {q["id"]: q for q in questions}
    correct = 0
    total = len(results)
    by_category = {}
    safety_checks = {
        "unsupported_no_execute": True,
        "adversarial_no_execute": True,
        "unauthorized_blocked": True,
        "malformed_rejected": True,
    }

    for r in results:
        qid = r["question_id"]
        q = q_map.get(qid, {})
        cat = q.get("category", "unknown")
        expected = q.get("expected_behavior")
        status = r["final_status"]
        agents = r.get("agents_invoked", {})

        if cat not in by_category:
            by_category[cat] = {"total": 0, "correct": 0}
        by_category[cat]["total"] += 1

        is_correct = False

        if expected == "pipeline_complete":
            # Must reach execution successfully
            is_correct = (
                status == "success"
                and "execution" in agents
                and agents["execution"].get("status") == "success"
            )
        elif expected == "clarification":
            # Must NOT execute SQL — should get semantic_planning or clarification stop
            sql_reached = "sql" in agents
            exec_reached = "execution" in agents
            is_correct = not exec_reached and r["http_status"] == 200
            if not is_correct and exec_reached:
                safety_checks["unsupported_no_execute"] = False
        elif expected == "semantic_planning":
            sql_reached = "sql" in agents
            exec_reached = "execution" in agents
            is_correct = not exec_reached and r["http_status"] == 200
            if not is_correct and exec_reached:
                if q.get("category") == "adversarial":
                    safety_checks["adversarial_no_execute"] = False
                else:
                    safety_checks["unsupported_no_execute"] = False
        elif expected == "auth_required":
            is_correct = r["http_status"] in (401, 403)
            if not is_correct:
                safety_checks["unauthorized_blocked"] = False
        elif expected == "validation_error":
            is_correct = r["http_status"] in (400, 422, 401)
            if not is_correct:
                safety_checks["malformed_rejected"] = False

        if is_correct:
            correct += 1
            by_category[cat]["correct"] = by_category[cat].get("correct", 0) + 1

    # Latency stats
    latencies = [r["latency_breakdown"].get("total_ms", 0) for r in results if r["final_status"]]
    latencies.sort()

    return {
        "total_questions": total,
        "correct": correct,
        "accuracy": round(correct / total * 100, 1) if total else 0,
        "by_category": by_category,
        "safety_checks": safety_checks,
        "latency": {
            "p50": round(latencies[len(latencies) // 2], 2) if latencies else 0,
            "p95": round(latencies[int(len(latencies) * 0.95)], 2) if latencies else 0,
            "p99": round(latencies[int(len(latencies) * 0.99)], 2) if latencies else 0,
            "mean": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        },
    }


# ─── Agent matrix ────────────────────────────────────────────────────────────

def build_agent_matrix(results: List[Dict]) -> List[Dict]:
    """Build per-agent validation matrix across all questions."""
    agent_stats: Dict[str, Dict] = {}
    for agent in EXPECTED_AGENTS:
        agent_stats[agent] = {
            "agent": agent,
            "invoked_count": 0,
            "success_count": 0,
            "error_count": 0,
            "never_invoked_questions": [],
            "evidence": [],
        }

    for r in results:
        qid = r["question_id"]
        for agent in EXPECTED_AGENTS:
            info = r.get("agents_invoked", {}).get(agent)
            if info and info.get("invoked"):
                agent_stats[agent]["invoked_count"] += 1
                if info.get("status") == "success":
                    agent_stats[agent]["success_count"] += 1
                else:
                    agent_stats[agent]["error_count"] += 1
                agent_stats[agent]["evidence"].append({
                    "question_id": qid,
                    "status": info["status"],
                    "response_hash": info.get("response_hash"),
                })
            else:
                agent_stats[agent]["never_invoked_questions"].append(qid)

    return list(agent_stats.values())


# ─── Report generation ───────────────────────────────────────────────────────

def generate_report(
    results: List[Dict], scoring: Dict, agent_matrix: List[Dict],
    questions: List[Dict],
) -> str:
    """Generate markdown report."""
    lines = [
        "# Integration Benchmark Results",
        "",
        f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"**Classification:** A/D — Full distributed end-to-end benchmark",
        "",
        "> The benchmark interacts with the system exclusively via HTTP",
        "> through the API Gateway. No internal classes are imported.",
        "",
        "## Overall Scores",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total questions | {scoring['total_questions']} |",
        f"| Correct | {scoring['correct']} |",
        f"| Accuracy | {scoring['accuracy']}% |",
        f"| Safety checks passed | {sum(1 for v in scoring['safety_checks'].values() if v)}/{len(scoring['safety_checks'])} |",
        "",
        "## By Category",
        "",
        "| Category | Total | Correct | Accuracy |",
        "|----------|-------|---------|----------|",
    ]
    for cat, info in sorted(scoring["by_category"].items()):
        t = info["total"]
        c = info.get("correct", 0)
        acc = round(c / t * 100, 1) if t else 0
        lines.append(f"| {cat} | {t} | {c} | {acc}% |")

    lines += [
        "",
        "## Safety Checks",
        "",
        "| Check | Result |",
        "|-------|--------|",
    ]
    for check, passed in scoring["safety_checks"].items():
        lines.append(f"| {check} | {'PASS' if passed else 'FAIL'} |")

    lines += [
        "",
        "## Latency",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| p50 | {scoring['latency']['p50']}ms |",
        f"| p95 | {scoring['latency']['p95']}ms |",
        f"| p99 | {scoring['latency']['p99']}ms |",
        f"| mean | {scoring['latency']['mean']}ms |",
        "",
        "## Agent Invocation Matrix",
        "",
        "| Agent | Invoked | Success | Error | Never Invoked |",
        "|-------|---------|---------|-------|---------------|",
    ]
    for a in agent_matrix:
        agent = a["agent"]
        inv = a["invoked_count"]
        suc = a["success_count"]
        err = a["error_count"]
        never = len(a["never_invoked_questions"])
        lines.append(f"| {agent} | {inv} | {suc} | {err} | {never} |")

    lines += [
        "",
        "## Agent Validation Classification",
        "",
    ]
    for a in agent_matrix:
        agent = a["agent"]
        inv = a["invoked_count"]
        total = scoring["total_questions"]
        if inv == total:
            classification = "FULLY VALIDATED"
            reason = f"Invoked in all {total} questions"
        elif inv > total * 0.5:
            classification = "PARTIALLY VALIDATED"
            reason = f"Invoked in {inv}/{total} questions ({round(inv/total*100)}%)"
        elif inv > 0:
            classification = "PARTIALLY VALIDATED"
            reason = f"Invoked in {inv}/{total} questions — only reached for supported queries"
        else:
            classification = "NOT EXERCISED"
            reason = "Never invoked in any test question"
        lines.append(f"### {agent}")
        lines.append(f"- **Classification:** {classification}")
        lines.append(f"- **Reason:** {reason}")
        lines.append("")

    lines += [
        "## Per-Question Results",
        "",
        "| ID | Category | Lang | HTTP | Status | Agents | Early Stop | Latency |",
        "|-----|----------|------|------|--------|--------|------------|---------|",
    ]
    for r in results:
        qid = r["question_id"]
        cat = r.get("category", "?")
        lang = r.get("language", "?")
        http = r.get("http_status", "?")
        status = r.get("final_status", "?")
        agents = len(r.get("services_reached", []))
        early = r.get("early_stop") or "—"
        ms = r.get("latency_breakdown", {}).get("total_ms", 0)
        lines.append(f"| {qid} | {cat} | {lang} | {http} | {status} | {agents} | {early} | {ms:.0f}ms |")

    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Integration benchmark runner")
    parser.add_argument("--gateway-url", default="http://localhost:8000")
    parser.add_argument("--username", default="admin_001")
    parser.add_argument("--password", default="password")
    parser.add_argument("--questions", default=os.path.join(os.path.dirname(__file__), "questions.json"))
    args = parser.parse_args()

    # Load questions
    with open(args.questions) as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} questions")

    # Create runner
    bench = IntegrationBenchmark(args.gateway_url, args.username, args.password)

    # Login
    if not bench.login():
        print("Login failed. Is the API gateway running?")
        sys.exit(1)

    # Run all questions
    results = bench.run_all(questions)
    bench.close()

    # Score
    scoring = score_results(results, questions)
    print(f"\n{'='*60}")
    print(f"Score: {scoring['correct']}/{scoring['total_questions']} ({scoring['accuracy']}%)")
    print(f"Safety: {sum(1 for v in scoring['safety_checks'].values() if v)}/{len(scoring['safety_checks'])} passed")

    # Agent matrix
    agent_matrix = build_agent_matrix(results)

    # Ensure output dirs
    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Write results JSONL
    jsonl_path = os.path.join(RESULTS_DIR, "integration_run.jsonl")
    with open(jsonl_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, default=str) + "\n")
    print(f"Wrote {jsonl_path}")

    # Write summary
    summary = {
        "benchmark": "integration_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "gateway_url": args.gateway_url,
        "scoring": scoring,
        "agent_matrix": agent_matrix,
    }
    summary_path = os.path.join(RESULTS_DIR, "integration_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {summary_path}")

    # Write agent matrix JSON
    matrix_path = os.path.join(RESULTS_DIR, "runtime_agent_matrix.json")
    with open(matrix_path, "w") as f:
        json.dump(agent_matrix, f, indent=2, default=str)
    print(f"Wrote {matrix_path}")

    # Write invocation trace
    trace_path = os.path.join(RESULTS_DIR, "integration_run.jsonl")  # same as JSONL
    print(f"Invocation trace: {trace_path}")

    # Write report
    report = generate_report(results, scoring, agent_matrix, questions)
    report_path = os.path.join(REPORTS_DIR, "INTEGRATION_BENCHMARK.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Wrote {report_path}")

    # Exit code
    if scoring["accuracy"] < 100:
        sys.exit(1)


if __name__ == "__main__":
    main()
