"""Quick-screen harness for compact models (STEP 7).

Runs a small, high-signal subset of the 46-case benchmark on a candidate model
and reports per-case mode/reason plus a compact JSON raw transcript, so a model
can be judged (and, if structurally failing, rejected) quickly before the full
46-case run.

Uses the EXACT production prompts, payloads, Gate and GroundingValidator so the
screen is directly comparable to the full benchmark (STEP 5 runner).

Usage:
  python3 benchmark/llm_insights/quick_screen.py --model qwen3:4b \
      --temps 0.0 --timeout 180 --label native_qwen3_4b --cases anom_b02 multi_f01
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INSIGHTS_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "services", "insights_agent"))
sys.path.insert(0, HERE)
sys.path.insert(0, INSIGHTS_DIR)

from benchmark_runner import (  # noqa: E402
    hydrate, call_ollama, classify, _build_facts, _collect_allowed_numbers,
    VerifiedFactPayload,
)
from necessity_gate import NecessityGate, DeterministicFormatter  # noqa: E402

DEFAULT_BASE = os.environ.get("OLLAMA_API_URL", "http://localhost:11434")

DEFAULT_SCREEN = ["stress_n02", "anom_b02", "multi_f04", "multi_f01", "multi_f02"]


def run_one(case, model, temperature, base, timeout, max_tokens, gate):
    fp = hydrate(case["fact_package"], case.get("query_intent", ""), case.get("query_text", ""))
    decision = gate.evaluate(fp.query_intent, fp.query_text, fp)
    facts = _build_facts(fp)
    payload = VerifiedFactPayload(facts, _collect_allowed_numbers(facts))
    payload_json = payload.json()
    formatter = DeterministicFormatter()
    det_summary = formatter.format(fp, decision, {})

    if not decision.use_llm:
        return {
            "case_id": case["id"], "category": case["category"], "language": case["language"],
            "gate_use_llm": False, "mode": "deterministic", "reason": "GATE_DETERMINISTIC",
            "payload_facts": len(facts), "wall_ms": None, "token_sec": None,
            "eval_count": None, "prompt_eval_count": None,
        }

    telemetry = call_ollama(base, model, payload_json, fp.query_text, temperature, max_tokens, timeout)
    mode, reason, out = classify(telemetry.get("raw", ""), payload)
    token_sec = None
    if telemetry.get("eval_count") and telemetry.get("eval_ms"):
        token_sec = round(telemetry["eval_count"] / (telemetry["eval_ms"] / 1000.0), 1)

    return {
        "case_id": case["id"], "category": case["category"], "language": case["language"],
        "gate_use_llm": True, "mode": mode, "reason": reason,
        "payload_facts": len(facts),
        "load_duration_ms": telemetry.get("load_duration_ms"),
        "wall_ms": telemetry.get("wall_ms"),
        "eval_count": telemetry.get("eval_count"),
        "prompt_eval_count": telemetry.get("prompt_eval_count"),
        "token_sec": token_sec,
        "error": telemetry.get("error"),
        "llm_summary": (out.summary if (mode == "llm" and out) else ""),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--temps", nargs="+", type=float, default=[0.0])
    ap.add_argument("--cases", nargs="+", default=DEFAULT_SCREEN)
    ap.add_argument("--max-tokens", type=int, default=512)
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--cases-file", default=os.path.join(HERE, "cases.json"))
    ap.add_argument("--label", default="qs")
    args = ap.parse_args()

    with open(args.cases_file, encoding="utf-8") as f:
        all_cases = json.load(f)["cases"]
    by_id = {c["id"]: c for c in all_cases}
    gate = NecessityGate()
    selected = [by_id[cid] for cid in args.cases if cid in by_id]

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    for temp in args.temps:
        rows = [run_one(c, args.model, temp, args.base, args.timeout,
                        args.max_tokens, gate) for c in selected]
        out = {"model": args.model, "temperature": temp, "cases": rows}
        path = os.path.join(HERE, "results", f"{args.label}_t{temp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"[{args.model}|t={temp}]")
        for r in rows:
            status = "--" if not r["gate_use_llm"] else ("LLM OK" if r["mode"] == "llm" else f"fb:{r['reason']}")
            print(f"  {r['case_id']:<14} {r['category']:<13} {r['language']:<3} {status}"
                  f"  wall={r.get('wall_ms')}ms tok/s={r.get('token_sec')}")
            if r.get("llm_summary"):
                print(f"      summary: {r['llm_summary'][:130]}")
        print(f"  ➤ wrote {path}")


if __name__ == "__main__":
    main()
