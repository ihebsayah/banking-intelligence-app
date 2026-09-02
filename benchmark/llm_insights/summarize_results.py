"""Summarize benchmark results JSON files into report tables (STEP 5).

Usage: python3 benchmark/llm_insights/summarize_results.py [glob of results/*.json]
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "results")


def load_all(pattern):
    files = sorted(glob.glob(os.path.join(RESULTS, pattern)))
    out = {}
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        key = f"{data['model']}|t={data['temperature']}"
        out[key] = data
    return out


def show_summaries(data):
    print("\n=== PER-MODEL / PER-TEMP SUMMARY ===")
    for key, d in data.items():
        s = d["summary"]
        print(f"\n[{key}]  ({os.path.basename(d['__path__']) if '__path__' in d else ''})")
        for k in ("n_llm_attempts", "n_grounded_llm", "n_negative_controls",
                  "valid_json_rate", "grounding_pass_rate", "unsupported_numeric_rate",
                  "unknown_fact_ref_rate", "forbidden_claim_rate",
                  "recommendation_grounding_rate", "avg_fact_coverage",
                  "useful_llm_response_rate", "timeouts", "transport_failures",
                  "fallback_count"):
            print(f"  {k}: {s.get(k)}")
        print(f"  reasons: {s.get('reasons')}")
        print(f"  latency wall ms: {s.get('latency_wall_ms')}")


def show_failures(data):
    print("\n=== PER-CASE FAILURES (non-grounded) ===")
    for key, d in data.items():
        print(f"\n[{key}]")
        for r in d["cases"]:
            if r["gate_use_llm"] and r["mode"] != "llm":
                print(f"  {r['case_id']:<18} {r['reason']}")


def main():
    pattern = sys.argv[1] if len(sys.argv) > 1 else "live*.json"
    data = load_all(pattern)
    # attach source filename for readability
    for f in glob.glob(os.path.join(RESULTS, pattern)):
        j = json.load(open(f, encoding="utf-8"))
        data[f"{j['model']}|t={j['temperature']}"].setdefault("__path__", os.path.basename(f))
    if not data:
        print(f"No results matched {pattern} in {RESULTS}")
        return
    show_summaries(data)
    show_failures(data)


if __name__ == "__main__":
    main()
