#!/usr/bin/env python3
"""
Correctness evaluation for Benchmark V2 blind run.

Loads blind_v2_run.jsonl (actual results) and blind_v2_questions.json (expected behavior),
matches by ID, and computes routing correctness per category.
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

RESULTS_FILE = Path(__file__).parent / "blind_v2_run.jsonl"
QUESTIONS_FILE = Path(__file__).parent / "blind_v2_questions.json"
REPORT_FILE = Path(__file__).parent / "evaluation_report.md"


def load_results(path: Path) -> dict[str, dict]:
    results = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            results[row["id"]] = row
    return results


def load_questions(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


# Map expected_behavior from questions to the pipeline_stage values that count as "correct"
# For pipeline_complete: the system MUST route to the full pipeline
# For all rejection categories: the system MUST NOT route to full pipeline (any non-pipeline_stage is correct)
EXPECTED_TO_CATEGORY = {
    "pipeline_complete": "pipeline_complete",
    "clarification": "clarification",
    "semantic_planning": "unsupported",
    "auth_required": "auth_required",
    "validation_error": "validation_error",
}


def is_routed_to_pipeline(result: dict) -> bool:
    return result.get("pipeline_stage") == "pipeline_complete"


def evaluate(questions: list[dict], results: dict[str, dict]):
    # Build per-category stats
    categories: dict[str, dict] = {}
    for cat in EXPECTED_TO_CATEGORY.values():
        categories[cat] = {"total": 0, "correct": 0, "failures": []}

    all_evaluated = []

    for q in questions:
        qid = q["id"]
        expected_behavior = q["expected_behavior"]
        category_label = EXPECTED_TO_CATEGORY.get(expected_behavior, expected_behavior)

        if qid not in results:
            categories[category_label]["total"] += 1
            categories[category_label]["failures"].append({
                "id": qid,
                "query": q.get("query"),
                "expected": category_label,
                "actual_stage": "MISSING",
                "reason": "No result found in run output",
            })
            all_evaluated.append({**q, "correct": False, "actual_stage": "MISSING"})
            continue

        result = results[qid]
        actual_stage = result.get("pipeline_stage", "unknown")
        routed = is_routed_to_pipeline(result)

        categories[category_label]["total"] += 1

        if category_label == "pipeline_complete":
            correct = routed
        else:
            # Any rejection (non-pipeline_complete) is correct for rejection categories
            correct = not routed

        if correct:
            categories[category_label]["correct"] += 1
        else:
            error_detail = result.get("error_detail") or ""
            if category_label == "pipeline_complete":
                reason = f"Expected pipeline_complete but got '{actual_stage}'"
                if error_detail:
                    reason += f": {error_detail}"
            else:
                reason = f"Expected rejection but query was routed to full pipeline (pipeline_complete)"
                if result.get("answer"):
                    reason += f" — answer: {result['answer'][:120]}..."

            categories[category_label]["failures"].append({
                "id": qid,
                "query": q.get("query"),
                "expected": category_label,
                "actual_stage": actual_stage,
                "reason": reason,
            })

        all_evaluated.append({**q, "correct": correct, "actual_stage": actual_stage})

    return categories, all_evaluated


def build_report(categories: dict, evaluated: list[dict], total_questions: int) -> str:
    total_correct = sum(c["correct"] for c in categories.values())
    overall_accuracy = total_correct / total_questions * 100 if total_questions else 0

    lines = []
    lines.append("# Benchmark V2 — Correctness Evaluation Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Questions file:** `blind_v2_questions.json`")
    lines.append(f"**Results file:** `blind_v2_run.jsonl`")
    lines.append(f"**Total questions:** {total_questions}")
    lines.append("")

    # ── Overall accuracy ──
    lines.append("## Overall Accuracy")
    lines.append("")
    lines.append(f"**{total_correct}/{total_questions}** queries routed correctly — **{overall_accuracy:.1f}%**")
    lines.append("")

    # ── Per-category breakdown ──
    lines.append("## Per-Category Accuracy")
    lines.append("")
    lines.append("| Category | Correct | Total | Accuracy |")
    lines.append("|---|---|---|---|")
    for cat_label in ["pipeline_complete", "clarification", "unsupported", "auth_required", "validation_error"]:
        c = categories[cat_label]
        acc = c["correct"] / c["total"] * 100 if c["total"] else 0
        lines.append(f"| {cat_label} | {c['correct']} | {c['total']} | {acc:.1f}% |")
    lines.append("")

    # ── Per-question results ──
    lines.append("## Per-Question Results")
    lines.append("")
    lines.append("| ID | Category | Expected | Actual Stage | Correct |")
    lines.append("|---|---|---|---|---|")
    for e in evaluated:
        status = "PASS" if e["correct"] else "FAIL"
        lines.append(f"| {e['id']} | {e.get('category', '?')} | {EXPECTED_TO_CATEGORY.get(e['expected_behavior'], e['expected_behavior'])} | {e['actual_stage']} | {status} |")
    lines.append("")

    # ── Failures ──
    all_failures = []
    for cat_label in ["pipeline_complete", "clarification", "unsupported", "auth_required", "validation_error"]:
        all_failures.extend(categories[cat_label]["failures"])

    lines.append("## Failed Queries")
    lines.append("")
    if not all_failures:
        lines.append("No failures — all queries routed correctly.")
    else:
        lines.append(f"**{len(all_failures)} failures**")
        lines.append("")
        for f in all_failures:
            lines.append(f"### {f['id']} — Expected: {f['expected']}")
            lines.append("")
            query_display = f['query'] if f['query'] else "(null/empty)"
            lines.append(f"- **Query:** `{query_display}`")
            lines.append(f"- **Actual stage:** `{f['actual_stage']}`")
            lines.append(f"- **Reason:** {f['reason']}")
            lines.append("")

    return "\n".join(lines)


def main():
    questions = load_questions(QUESTIONS_FILE)
    results = load_results(RESULTS_FILE)

    print(f"Loaded {len(questions)} questions and {len(results)} results")

    categories, evaluated = evaluate(questions, results)

    # Print summary to stdout
    total_questions = len(questions)
    total_correct = sum(c["correct"] for c in categories.values())
    overall_accuracy = total_correct / total_questions * 100 if total_questions else 0

    print(f"\n{'='*60}")
    print(f"OVERALL ACCURACY: {total_correct}/{total_questions} ({overall_accuracy:.1f}%)")
    print(f"{'='*60}")
    print(f"\n{'Category':<20} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print(f"{'-'*48}")
    for cat_label in ["pipeline_complete", "clarification", "unsupported", "auth_required", "validation_error"]:
        c = categories[cat_label]
        acc = c["correct"] / c["total"] * 100 if c["total"] else 0
        print(f"{cat_label:<20} {c['correct']:>8} {c['total']:>8} {acc:>9.1f}%")

    # Print failures
    all_failures = []
    for cat_label in ["pipeline_complete", "clarification", "unsupported", "auth_required", "validation_error"]:
        all_failures.extend(categories[cat_label]["failures"])

    if all_failures:
        print(f"\n{'='*60}")
        print(f"FAILURES ({len(all_failures)} total)")
        print(f"{'='*60}")
        for f in all_failures:
            print(f"  {f['id']} [{f['expected']}] — {f['reason']}")

    # Write markdown report
    report = build_report(categories, evaluated, total_questions)
    REPORT_FILE.write_text(report, encoding="utf-8")
    print(f"\nFull report saved to: {REPORT_FILE}")


if __name__ == "__main__":
    main()
