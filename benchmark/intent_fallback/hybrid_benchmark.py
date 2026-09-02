"""
Step 10: Hybrid benchmark — deterministic Intent Agent alone vs
deterministic + conditional semantic fallback.

Usage:
    python benchmark/intent_fallback/hybrid_benchmark.py [--quick] [--model qwen2.5:3b]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import os
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "intent_agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))

# Force offline mode so we don't try to fetch the DB during benchmarks
os.environ.setdefault("SEMANTIC_LAYER_ENABLED", "false")

from intent_recognizer import IntentRecognizer
from intent_benchmark import CASES, IntentCase
from semantic_resolver import SemanticResolver, make_fallback_decision, hybrid_resolve


def resolve_case(recognizer, case: IntentCase) -> dict:
    return recognizer.recognize_sync(case.query)


def correctness(output: dict, case: IntentCase) -> dict:
    """Evaluate intent/clarification correctness for a case.

    SEMANTIC_RESOLUTION_SUCCESS = correct intent OR correct clarification.
    For security cases (injection/sql_injection/unsupported), what matters is
    that the query is BLOCKED (not that intent is right).
    """
    intent_correct = output["primary_category"] == case.expected_intent
    clarification_correct = output["requires_clarification"] == case.requires_clarification

    is_security = case.category in ("injection", "sql_injection", "unsupported")
    if is_security:
        blocked = not output.get("supported_capability", True) or \
                  output.get("risk_level", "safe") in ("adversarial", "suspicious")
        return {
            "intent_correct": intent_correct,
            "clarification_correct": clarification_correct,
            "semantic_success": blocked,   # security handled = success
            "security_correct": blocked,
        }
    # For a case that SHOULD clarify, success = it clarifies (or matches intent).
    if case.requires_clarification:
        success = clarification_correct
    else:
        success = intent_correct
    return {
        "intent_correct": intent_correct,
        "clarification_correct": clarification_correct,
        "semantic_success": success,
    }


def main():
    quick = "--quick" in sys.argv[1:]
    model = "qwen2.5:3b"
    for i, a in enumerate(sys.argv):
        if a == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]

    enabled = "--no-llm" not in sys.argv
    resolver = SemanticResolver(model=model, enabled=enabled)

    if not resolver.available():
        print(f"[WARN] Ollama unavailable or resolver disabled. LLM output will be 'unknown'.")
        print("       Set --no-llm to skip LLM, or start Ollama to benchmark for real.\n")

    recognizer = IntentRecognizer(semantic_layer_enabled=False)

    cases = CASES
    if quick:
        quick_ids = {"D01","D02","N01","N03","O01","O02","O03","N05","G01","G04","H04","I05","K01","J02","M02"}
        cases = [c for c in CASES if c.id in quick_ids]

    print("=" * 78)
    print(f"STEP 10 H Y B R I D   B E N C H M A R K  ({model}, LLM={enabled})")
    print(f"Cases: {len(cases)}  {'QUICK SCREEN' if quick else 'FULL'}")
    print("=" * 78)

    rows = []
    for case in cases:
        det = resolve_case(recognizer, case)
        hybrid = hybrid_resolve(case.query, det, resolver)

        det_ev = correctness(det, case)
        hyp_ev = correctness(hybrid, case)

        rows.append({
            "id": case.id,
            "query": case.query,
            "category": case.category,
            "language": case.language,
            "expected_intent": case.expected_intent,
            "det_intent": det.get("primary_category"),
            "det_correct": det_ev["intent_correct"],
            "det_clar_correct": det_ev["clarification_correct"],
            "det_success": det_ev["semantic_success"],
            "det_conf": det.get("confidence"),
            "hyb_intent": hybrid.get("primary_category"),
            "hyb_correct": hyp_ev["intent_correct"],
            "hyb_clar_correct": hyp_ev["clarification_correct"],
            "hyb_success": hyp_ev["semantic_success"],
            "fallback_triggered": hybrid.get("fallback_triggered", False),
            "agreement": hybrid.get("agreement"),
            "clar_reason": hybrid.get("clarification_reason"),
            "missing_context": hybrid.get("missing_context"),
            "llm_latency_ms": hybrid.get("latency_ms_extra", 0),
            "security_correct": det_ev.get("security_correct", hyp_ev.get("security_correct", True)),
        })

    # ── Metrics ─────────────────────────────────────────────────────────────
    total = len(rows)
    det_acc = sum(1 for r in rows if r["det_correct"]) / total
    hyb_acc = sum(1 for r in rows if r["hyb_correct"]) / total
    det_clar = sum(1 for r in rows if r["det_clar_correct"]) / total
    hyb_clar = sum(1 for r in rows if r["hyb_clar_correct"]) / total
    det_succ = sum(1 for r in rows if r["det_success"]) / total
    hyb_succ = sum(1 for r in rows if r["hyb_success"]) / total

    # Errors fixed / broken (by semantic success)
    fixed = [r for r in rows if not r["det_success"] and r["hyb_success"]]
    broken = [r for r in rows if r["det_success"] and not r["hyb_success"]]

    # Fallback rate
    triggered = [r for r in rows if r["fallback_triggered"]]
    fallback_rate = len(triggered) / total if total else 0

    # Clarification precision/recall on clarification cases
    clar_cases = [r for r in rows if r["category"] in
                  ("ambiguous", "multi_intent", "followup", "unclear_entity",
                   "banking_ambiguous", "colloquial_fr", "implicit")]
    clar_needed = [r for r in clar_cases if r["id"] in {c.id for c in CASES if c.requires_clarification}]
    hl = set()

    # Simpler: which rows needed clarification
    needed_ids = {c.id for c in CASES if c.requires_clarification}
    det_clar_ok = [r for r in rows if r["id"] in needed_ids and r["det_clar_correct"]]
    hyb_clar_ok = [r for r in rows if r["id"] in needed_ids and r["hyb_clar_correct"]]

    # Latency metrics
    llm_lat = [r["llm_latency_ms"] for r in triggered if r["llm_latency_ms"] > 0]
    avg_llm_ms = sum(llm_lat) / len(llm_lat) if llm_lat else 0
    # Effective platform impact = fallback_rate * avg_llm_latency (per query)
    eff_impact_ms = fallback_rate * avg_llm_ms

    # Language
    en = [r for r in rows if r["language"] == "en"]
    fr = [r for r in rows if r["language"] == "fr"]
    en_det = sum(1 for r in en if r["det_success"]) / len(en) if en else None
    en_hyb = sum(1 for r in en if r["hyb_success"]) / len(en) if en else None
    fr_det = sum(1 for r in fr if r["det_success"]) / len(fr) if fr else None
    fr_hyb = sum(1 for r in fr if r["hyb_success"]) / len(fr) if fr else None

    # Security retained
    security_ok = sum(1 for r in rows if r["security_correct"])
    security_total = sum(1 for r in rows if r["category"] in ("injection","sql_injection","unsupported"))

    print(f"\nDeterministic intent accuracy:  {det_acc:.2%}  ({sum(1 for r in rows if r['det_correct'])}/{total})")
    print(f"Hybrid intent accuracy:          {hyb_acc:.2%}  ({sum(1 for r in rows if r['hyb_correct'])}/{total})")
    print(f"Net intent accuracy gain:        {hyb_acc - det_acc:+.2%}")
    print(f"\nDeterministic SEMANTIC success:  {det_succ:.2%}  (correct intent OR correct clarification)")
    print(f"Hybrid SEMANTIC success:         {hyb_succ:.2%}")
    print(f"Net semantic success gain:       {hyb_succ - det_succ:+.2%}")
    print(f"\nDeterministic clarification ok:  {det_clar:.2%}")
    print(f"Hybrid clarification ok:         {hyb_clar:.2%}")
    print(f"\nErrors fixed by LLM:             {len(fixed)}")
    print(f"Correct broken by LLM:           {len(broken)}")
    print(f"Fallback triggered rate:         {fallback_rate:.2%}  ({len(triggered)}/{total})")
    print(f"Unnecessary LLM calls:           {sum(1 for r in triggered if r['det_success'])} (det was already right)")
    print(f"\nEN deterministic/hybrid:         {en_det:.2%} / {en_hyb:.2%}")
    print(f"FR deterministic/hybrid:         {fr_det:.2%} / {fr_hyb:.2%}")
    print(f"\nSecurity gated correctly:        {security_ok}/{security_total}")
    print(f"\nLLM fallback latency:            avg={avg_llm_ms:.0f}ms on {len(llm_lat)} calls")
    print(f"Effective added latency:         {eff_impact_ms:.0f}ms/query average")

    print(f"\n{'='*78}")
    print("PER-CASE")
    print("=" * 78)
    for r in rows:
        mark = ""
        if r["det_success"] and r["hyb_success"]:
            mark = "OK"
        elif not r["det_success"] and r["hyb_success"]:
            mark = "FIXED"
        elif r["det_success"] and not r["hyb_success"]:
            mark = "BROKEN"
        else:
            mark = "MISS"
        fb = "LLM" if r["fallback_triggered"] else "DET"
        agree = f"/{r['agreement']}" if r["agreement"] else ""
        clar = f" CLAR:{r.get('clar_reason')}" if r.get('clar_reason') else ""
        print(f"  {r['id']:4} [{mark:5}] [{fb}{agree:24}] det={r['det_intent']:22} hyb={r['hyb_intent']:22} "
              f"lat={r['llm_latency_ms']:.0f}ms{clar}")
        if mark == "BROKEN":
            print(f"        q: {r['query']}")

    # Save
    out = Path(__file__).parent / f"hybrid_results_{('quick' if quick else 'full')}.json"
    summary = {
        "model": model,
        "quick": quick,
        "total": total,
        "det_acc": round(det_acc, 4),
        "hyb_acc": round(hyb_acc, 4),
        "gain": round(hyb_acc - det_acc, 4),
        "det_success": round(det_succ, 4),
        "hyb_success": round(hyb_succ, 4),
        "success_gain": round(hyb_succ - det_succ, 4),
        "errors_fixed": len(fixed),
        "broken": len(broken),
        "fallback_rate": round(fallback_rate, 4),
        "avg_llm_ms": round(avg_llm_ms, 1),
        "effective_added_ms": round(eff_impact_ms, 1),
        "en_det": round(en_det, 4) if en_det else None,
        "en_hyb": round(en_hyb, 4) if en_hyb else None,
        "fr_det": round(fr_det, 4) if fr_det else None,
        "fr_hyb": round(fr_hyb, 4) if fr_hyb else None,
        "security_ok": security_ok,
        "security_total": security_total,
    }
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSaved summary to {out}")


if __name__ == "__main__":
    main()
