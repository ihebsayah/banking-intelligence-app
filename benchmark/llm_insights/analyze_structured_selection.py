"""Post-process structured-selection benchmark results → §19-22 quality + latency metrics."""
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(vals):
    return statistics.mean(vals) * 100 if vals else 0.0


def f1(p, r):
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def main(results_path: str):
    with open(os.path.join(HERE, "cases.json"), encoding="utf-8") as f:
        cases = {c["id"]: c for c in json.load(f)["cases"]}
    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)
    rows = [r for r in data["cases"] if r.get("gate_use_llm")]

    llm_p, llm_r, det_p, det_r = [], [], [], []
    over_selected, under_selected = [], []
    agrees = []
    for r in rows:
        cid = r["case_id"]
        expected = set(cases[cid].get("expected_important_facts", []))
        if not expected:
            continue
        lsel = r.get("llm_summary_ids") or {}
        lid = set(lsel.get("summary", []) + lsel.get("obs", []) + lsel.get("recs", []) + lsel.get("lims", []))
        dsel = r.get("baseline") or {}
        did = set(dsel.get("det_summary_ids", []) + dsel.get("det_obs_ids", []) +
                  dsel.get("det_rec_ids", []) + dsel.get("det_lim_ids", []))
        lp = len(lid & expected) / len(lid) if lid else 0.0
        lr = len(lid & expected) / len(expected) if expected else 0.0
        dp = len(did & expected) / len(did) if did else 0.0
        dr = len(did & expected) / len(expected) if expected else 0.0
        llm_p.append(lp)
        llm_r.append(lr)
        det_p.append(dp)
        det_r.append(dr)
        over_selected.append(bool(lid - expected))
        under_selected.append(bool(expected - lid))
        agrees.append(lid == did)

    print("=== SELECTION QUALITY (LLM vs DET, per spec 19) ===")
    print(f"  LLM   precision={pct(llm_p):.1f}%  recall={pct(llm_r):.1f}%  F1={f1(pct(llm_p)/100, pct(llm_r)/100):.3f}")
    print(f"  DET   precision={pct(det_p):.1f}%  recall={pct(det_r):.1f}%  F1={f1(pct(det_p)/100, pct(det_r)/100):.3f}")
    print(f"  OVER_SELECTION_RATE   (LLM picked facts outside expected) = {pct(over_selected):.1f}%")
    print(f"  UNDER_SELECTION_RATE  (LLM missed at least one expected) = {pct(under_selected):.1f}%")
    print(f"  LLM == DET selection fraction = {pct(agrees):.1f}%")

    print("\n=== LATENCY (LLM attempts, spec 21) ===")
    wall = [r["wall_ms"] / 1000.0 for r in rows if r.get("wall_ms")]
    if wall:
        wall.sort()
        n = len(wall)
        q = lambda p: wall[min(n - 1, int(p * n))]
        print(f"  n={n}  p50={statistics.median(wall):.1f}s  p90={q(0.90):.1f}s  "
              f"p95={q(0.95):.1f}s  max={max(wall):.1f}s  mean={statistics.mean(wall):.1f}s")
    tok = [r.get("eval_count") for r in rows if r.get("eval_count")]
    tps = [r.get("token_sec") for r in rows if r.get("token_sec")]
    if tok:
        print(f"  completion tokens:  n={len(tok)}  mean={statistics.mean(tok):.1f}  min={min(tok)}  max={max(tok)}")
    if tps:
        print(f"  tokens/sec:         n={len(tps)}  mean={statistics.mean(tps):.2f}  p50={statistics.median(tps):.2f}")

    prov = [r.get("prompt_eval_count") for r in rows if r.get("prompt_eval_count") is not None]
    if prov:
        print(f"  prompt eval tokens: n={len(prov)} mean={statistics.mean(prov):.1f}")

    print("\n=== RENDER + SAFETY (structural) ===")
    safe = [r for r in rows if r.get("llm_metrics")]
    for key in ("structure_compliance", "id_validity", "type_correctness", "cap_respect",
                "correlation_non_causal", "anomaly_non_fraud"):
        vals = [r["llm_metrics"].get(key) for r in safe]
        print(f"  {key:<24} {pct([v for v in vals if v is not None]):.1f}%")

    print("\n=== GATE CONTROL (spec 20) ===")
    controls = [r for r in data["cases"] if not r.get("gate_use_llm")]
    print(f"  negative controls = {len(controls)}  (all deterministic, zero LLM calls: "
          f"{sum(1 for r in controls if r.get('mode') == 'deterministic')}/{len(controls)})")

    print("\n=== RAW DET SUMMARIES (quality spot-check) ===")
    for r in rows[:3]:
        det = r.get("baseline") or {}
        print(f"  [{r['case_id']}|{r['language']}] {det.get('det_summary', '')[:160]}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(HERE, "results", "step9_full_qwen25_structured_full_t0.0.json"))