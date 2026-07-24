#!/usr/bin/env python3
"""
benchmark/holdout/run_holdout.py

Single-shot holdout execution. 160 questions through the full production HTTP path.
Reuses the integration benchmark runner infrastructure.
"""
import json, os, sys, time
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "benchmark", "integration"))
from run_integration import IntegrationBenchmark, score_results, build_agent_matrix, generate_report

QUESTIONS_FILE = os.path.join(ROOT, "benchmark", "holdout", "holdout_questions.json")
RESULTS_DIR = os.path.join(ROOT, "benchmark", "results")
REPORTS_DIR = os.path.join(ROOT, "benchmark", "reports")


def main():
    with open(QUESTIONS_FILE) as f:
        questions = json.load(f)
    print(f"Loaded {len(questions)} holdout questions")

    bench = IntegrationBenchmark("http://localhost:8000", "admin_001", "password")
    if not bench.login():
        print("Login failed. Is the API gateway running?")
        sys.exit(1)

    results = bench.run_all(questions)
    bench.close()

    scoring = score_results(results, questions)
    print(f"\n{'='*60}")
    print(f"HOLOUT SCORE: {scoring['correct']}/{scoring['total_questions']} ({scoring['accuracy']}%)")
    print(f"Safety: {sum(1 for v in scoring['safety_checks'].values() if v)}/{len(scoring['safety_checks'])} passed")

    agent_matrix = build_agent_matrix(results)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    jsonl_path = os.path.join(RESULTS_DIR, "holdout_run.jsonl")
    with open(jsonl_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, default=str) + "\n")
    print(f"Wrote {jsonl_path}")

    summary = {
        "benchmark": "holdout_v1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question_count": len(questions),
        "scoring": scoring,
        "agent_matrix": agent_matrix,
    }
    summary_path = os.path.join(RESULTS_DIR, "holdout_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {summary_path}")

    matrix_path = os.path.join(RESULTS_DIR, "holdout_agent_matrix.json")
    with open(matrix_path, "w") as f:
        json.dump(agent_matrix, f, indent=2, default=str)
    print(f"Wrote {matrix_path}")

    report = generate_report(results, scoring, agent_matrix, questions)
    report_path = os.path.join(REPORTS_DIR, "HOLDOUT_BENCHMARK.md")
    with open(report_path, "w") as f:
        f.write(report)
    print(f"Wrote {report_path}")

    if scoring["accuracy"] < 100:
        sys.exit(1)


if __name__ == "__main__":
    main()
