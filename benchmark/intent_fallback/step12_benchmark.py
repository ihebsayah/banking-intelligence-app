"""
Step 12: Post-hardening conditional semantic fallback benchmark.

Compares THREE systems on the frozen 83-case set:
  A. Step-10 deterministic baseline (frozen JSON, pre-hardening)
  B. Step-11 deterministic hardened (frozen JSON, just re-run)
  C. Step-12 hybrid = Step-11 deterministic + conditional semantic fallback (live)

Also runs the 20-case quick screen (Step 12 §13).

Usage:
    python benchmark/intent_fallback/step12_benchmark.py --quick
    python benchmark/intent_fallback/step12_benchmark.py --full
    python benchmark/intent_fallback/step12_benchmark.py --full --no-llm  # dry-run trigger analysis only
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "intent_agent"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ.setdefault("SEMANTIC_LAYER_ENABLED", "false")

from intent_agent.intent_recognizer import IntentRecognizer
from intent_benchmark import CASES, IntentCase
from post_hardening_eligibility import (
    EligibilityClass,
    make_fallback_decision_step12,
)
from post_hardening_hybrid import step12_hybrid_resolve
from quick_screen_cases import QUICK_CASES
from semantic_resolver import SemanticResolver

_HERE = Path(__file__).resolve().parent

SECURITY_CATEGORIES = ("injection", "sql_injection", "unsupported")
SECURITY_EXPECTED_INTENTS = {
    "K01": "risk_analysis", "K02": "customer_analysis",
    "J01": "risk_analysis", "J02": "customer_analysis",
}


def _classify_eligibility(intent_output: dict, query: str):
    intent_output["_query"] = query
    return make_fallback_decision_step12(intent_output)


# ── Correctness evaluators ─────────────────────────────────────────────────

def evaluate_case(output: dict, case: IntentCase) -> dict:
    """Correctness per spec correctness model (semantic_success mirrors it)."""
    intent_correct = output["primary_category"] == case.expected_intent
    clarification_correct = output["requires_clarification"] == case.requires_clarification

    is_security = case.category in SECURITY_CATEGORIES
    if is_security:
        blocked = not output.get("supported_capability", True) or \
                  output.get("risk_level", "safe") in ("adversarial", "suspicious")
        semantic_success = blocked
    elif case.requires_clarification:
        semantic_success = clarification_correct
    else:
        semantic_success = intent_correct

    return {
        "intent_correct": intent_correct,
        "clarification_correct": clarification_correct,
        "semantic_success": semantic_success,
    }


# ── Per-case transition labelling (spec §18) ───────────────────────────────

def label_transition(det_ev: dict, hyb_ev: dict, triggered: bool, base_ev: dict,
                     case: IntentCase) -> str:
    """Classify a triggered case into one of the spec §18 transition classes."""
    if not triggered:
        return "NOT_TRIGGERED"
    is_security = case.category in SECURITY_CATEGORIES
    if is_security:
        sec_ok = hyb_ev["semantic_success"]
        return "SECURITY_PRESERVED" if sec_ok else "SECURITY_GATE_BROKEN"
    # LLM-invalid outputs surface via provider/format — the hybrid keeps
    # deterministic behavior then, so we can't tell from ev alone. Tracked separately.
    if det_ev["semantic_success"] and hyb_ev["semantic_success"]:
        return "CORRECT_PRESERVED"
    if not det_ev["semantic_success"] and hyb_ev["semantic_success"]:
        return "FIXED_BY_LLM"
    if det_ev["semantic_success"] and not hyb_ev["semantic_success"]:
        # deterministic had it right, LLM broke it
        if det_ev["intent_correct"] and not hyb_ev["intent_correct"]:
            return "CORRECT_DETERMINISTIC_BROKEN"
        return "CORRECT_CLARIFICATION_BROKEN"
    return "UNCHANGED_WRONG"


# ── Run single-system evaluation ───────────────────────────────────────────

def run_deterministic(recognizer, cases):
    rows, lat = [], []
    for case in cases:
        t0 = time.perf_counter()
        out = recognizer.recognize_sync(case.query)
        lat.append((time.perf_counter() - t0) * 1000)
        rows.append({"case": case, "det_out": out, "eval": evaluate_case(out, case)})
    return rows, lat


def run_hybrid(recognizer, resolver, cases):
    rows, llm_lat = [], []
    for case in cases:
        det_out = recognizer.recognize_sync(case.query)
        decision = _classify_eligibility(det_out, case.query)
        hybrid = step12_hybrid_resolve(case.query, det_out, resolver)
        # LLM latency captured by hybrid when it actually called resolver
        if hybrid.get("_fallback_triggered"):
            llm_lat.append(hybrid.get("_llm_latency_ms", 0))
        rows.append({
            "case": case,
            "det_out": det_out,
            "hyb_out": hybrid,
            "decision": decision,
            "eval": evaluate_case(hybrid, case),
            "det_eval": evaluate_case(det_out, case),
        })
    return rows, llm_lat


def _agg(rows, ev_key):
    return sum(1 for r in rows if r[ev_key]["semantic_success"])


def summarize(rows, cases, llm_lat_ms=None, show_rows=False, label=""):

    total = len(cases)
    intent = sum(1 for r in rows if r["eval"]["intent_correct"])
    clar = sum(1 for r in rows if r["eval"]["clarification_correct"])
    sem = sum(1 for r in rows if r["eval"]["semantic_success"])

    fr = [r for r in rows if r["case"].language == "fr"]
    en = [r for r in rows if r["case"].language == "en"]
    fr_intent = sum(1 for r in fr if r["eval"]["intent_correct"])
    en_intent = sum(1 for r in en if r["eval"]["intent_correct"])

    constraint_cases = [r for r in rows if r["case"].expected_constraints]
    constraints_ok = sum(
        1 for r in constraint_cases
        if all(r["hyb_out"]["explicit_constraints"].get(k) == v
               for k, v in r["case"].expected_constraints.items())
    )

    sec_cases = [r for r in rows if r["case"].category in SECURITY_CATEGORIES]
    sec_ok = sum(1 for r in sec_cases if r["eval"]["semantic_success"])

    out = {
        "label": label,
        "total": total,
        "intent_accuracy": round(intent / total, 4) if total else None,
        "clarification_accuracy": round(clar / total, 4) if total else None,
        "semantic_success": round(sem / total, 4) if total else None,
        "fr_accuracy": round(fr_intent / len(fr), 4) if fr else None,
        "fr_total": len(fr),
        "en_accuracy": round(en_intent / len(en), 4) if en else None,
        "en_total": len(en),
        "constraints_accuracy": round(constraints_ok / len(constraint_cases), 4) if constraint_cases else None,
        "injection_blocked": sum(1 for r in sec_cases if r["case"].category != "unsupported" and r["eval"]["semantic_success"]),
        "injection_total": sum(1 for r in rows if r["case"].category in ("injection", "sql_injection")),
        "unsupported_blocked": sum(1 for r in sec_cases if r["case"].category == "unsupported" and r["eval"]["semantic_success"]),
        "unsupported_total": sum(1 for r in rows if r["case"].category == "unsupported"),
        "security_ok": sec_ok,
        "security_total": len(sec_cases),
    }
    return out


# ── Helpers ────────────────────────────────────────────────────────────────

def pct(n, d):
    return round(n / d, 4) if d else None


def trigger_metrics(rows):
    """spec §14: fallback precision/recall/unnecessary-call-rate."""
    calls = [r for r in rows if r["hyb_out"].get("_fallback_triggered")]
    n_calls = len(calls)

    # 'Genuinely resolvable' ground truth per decision class
    true_resolvable = sum(
        1 for r in rows
        if r["decision"].eligibility_class == EligibilityClass.SEMANTICALLY_RESOLVABLE
    )
    true_non_resolvable = [
        r for r in rows
        if r["decision"].eligibility_class != EligibilityClass.SEMANTICALLY_RESOLVABLE
    ]
    unnecessary = [
        r for r in calls
        if r["decision"].eligibility_class != EligibilityClass.SEMANTICALLY_RESOLVABLE
    ]

    # Of all resolvable deterministic-failures, how many reached LLM
    resolvable_failures = [
        r for r in rows
        if r["decision"].eligibility_class == EligibilityClass.SEMANTICALLY_RESOLVABLE
        and not r["det_eval"]["semantic_success"]
    ]
    resolvable_failures_called = [
        r for r in resolvable_failures if r["hyb_out"].get("_fallback_triggered")
    ]

    precision = pct(
        sum(1 for r in calls if r["decision"].eligibility_class == EligibilityClass.SEMANTICALLY_RESOLVABLE),
        n_calls,
    )
    recall = pct(len(resolvable_failures_called), len(resolvable_failures))
    unnecessary_rate = pct(len(unnecessary), n_calls)

    # Degenerate-case defaults: with no calls there is nothing missed, nothing
    # unnecessary; with no resolvable failures recall is vacuously perfect.
    if n_calls == 0:
        precision, unnecessary_rate = 1.0, 0.0
    if len(resolvable_failures) == 0:
        recall = 1.0

    return {
        "llm_calls": n_calls,
        "fallback_rate": pct(n_calls, len(rows)),
        "fallback_precision": precision,
        "fallback_recall": recall,
        "unnecessary_llm_call_rate": unnecessary_rate,
        "true_resolvable_eligible": true_resolvable,
        "resolvable_failures": len(resolvable_failures),
        "resolvable_failures_called": len(resolvable_failures_called),
        "unnecessary_calls_by_class": {
            k.value: sum(1 for r in unnecessary
                         if r["decision"].eligibility_class == k)
            for k in EligibilityClass
        },
    }


def error_transitions(rows):
    counts = {}
    for r in rows:
        t = label_transition(
            r["det_eval"], r["eval"], r["hyb_out"].get("_fallback_triggered"),
            None, r["case"],
        )
        agg = counts.setdefault(t, {"count": 0, "cases": []})
        agg["count"] += 1
        agg["cases"].append(r["case"].id)
    return counts


def latency_stats(llm_lat_ms):
    if not llm_lat_ms:
        return None
    s = sorted(llm_lat_ms)
    return {
        "calls": len(s),
        "p50": round(statistics.median(s), 2),
        "p90": round(s[int(len(s) * 0.90)], 2),
        "p95": round(s[int(len(s) * 0.95)], 2),
        "max": round(max(s), 2),
        "mean": round(statistics.mean(s), 2),
    }


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    quick = "--quick" in sys.argv[1:]
    no_llm = "--no-llm" in sys.argv[1:]
    model = "qwen2.5:3b"
    for i, a in enumerate(sys.argv):
        if a == "--model" and i + 1 < len(sys.argv):
            model = sys.argv[i + 1]

    resolver = SemanticResolver(model=model, enabled=not no_llm)
    recognizer = IntentRecognizer(semantic_layer_enabled=False)

    if quick:
        cases = [c for c in QUICK_CASES if hasattr(c, "expected_use_llm")]
        # quick cases are QuickCase not IntentCase; build IntentsCase on the fly
        from intent_benchmark import IntentCase as IC
        cases = [
            IC(id=c.id, query=c.query, language=c.language, category="quick",
               expected_intent=c.expected_intent or "unknown",
               requires_clarification=c.expected_clarification)
            for c in QUICK_CASES
        ]
    else:
        cases = CASES

    print("=" * 78)
    print(f"STEP 12: POST-HARDENING CONDITIONAL SEMANTIC FALLBACK ({model} llm={not no_llm})")
    print(f"Cases: {len(cases)}  {'QUICK SCREEN' if quick else 'FULL 83-CASE'}")
    print("=" * 78)

    rows, llm_lat = run_hybrid(recognizer, resolver, cases)
    tm = trigger_metrics(rows)

    print(f"\n── TRIGGER (spec §6/§7/§13/§14) ──────────────────────────────")
    print(f"LLM calls:                        {tm['llm_calls']}/{len(cases)} ({tm['fallback_rate']:.1%} fallback rate)")
    print(f"FALLBACK_PRECISION:               {tm['fallback_precision']:.1%}")
    print(f"FALLBACK_RECALL:                  {tm['fallback_recall']:.1%}")
    print(f"UNNECESSARY_LLM_CALL_RATE:        {tm['unnecessary_llm_call_rate']:.1%}  {tm['unnecessary_calls_by_class']}")
    print(f"Truly resolvable eligible:        {tm['true_resolvable_eligible']}")
    print(f"Resolvable failures sent to LLM:  {tm['resolvable_failures_called']}/{tm['resolvable_failures']}")

    print(f"\n── PER-CASE TRIGGER/LLM RESULT ───────────────────────────────")
    for r in rows:
        c = r["case"]
        det = r["det_out"]
        hyb = r["hyb_out"]
        fb = "LLM" if hyb.get("_fallback_triggered") else "DET"
        elig = r["decision"].eligibility_class.value[:22]
        agree = hyb.get("_agreement") or "-"
        mark = "OK" if r["eval"]["semantic_success"] else "  "
        print(f"  {c.id:4} [{mark}] [{fb}] [{elig:22}] [{agree:38}] det={det.get('primary_category','')[:16]:16} hyb={hyb.get('primary_category','')[:16]:16} lat={hyb.get('_llm_latency_ms',0):.0f}ms")

    # Borrow the standard hybrid metrics (intent/semantic/clarification)
    det_acc = sum(1 for r in rows if r["det_eval"]["intent_correct"]) / len(rows)
    hyb_acc = sum(1 for r in rows if r["eval"]["intent_correct"]) / len(rows)
    det_clar = sum(1 for r in rows if r["det_eval"]["clarification_correct"]) / len(rows)
    hyb_clar = sum(1 for r in rows if r["eval"]["clarification_correct"]) / len(rows)
    det_sem = sum(1 for r in rows if r["det_eval"]["semantic_success"]) / len(rows)
    hyb_sem = sum(1 for r in rows if r["eval"]["semantic_success"]) / len(rows)
    fixed = [r for r in rows if not r["det_eval"]["semantic_success"] and r["eval"]["semantic_success"]]
    broken = [r for r in rows if r["det_eval"]["semantic_success"] and not r["eval"]["semantic_success"]]

    # EN/FR intent
    fr_rows = [r for r in rows if r["case"].language == "fr"]
    en_rows = [r for r in rows if r["case"].language == "en"]
    fr_det = sum(1 for r in fr_rows if r["det_eval"]["intent_correct"]) / len(fr_rows) if fr_rows else 0
    fr_hyb = sum(1 for r in fr_rows if r["eval"]["intent_correct"]) / len(fr_rows) if fr_rows else 0
    en_det = sum(1 for r in en_rows if r["det_eval"]["intent_correct"]) / len(en_rows) if en_rows else 0
    en_hyb = sum(1 for r in en_rows if r["eval"]["intent_correct"]) / len(en_rows) if en_rows else 0

    # Security
    sec_ok = sum(1 for r in rows if r["case"].category in SECURITY_CATEGORIES and r["eval"]["semantic_success"])
    sec_tot = sum(1 for r in rows if r["case"].category in SECURITY_CATEGORIES)

    # Invented constraints (spec §22)
    invented = 0
    for r in rows:
        hyb_constraints = r["hyb_out"].get("constraints_from_llm")
        if hyb_constraints:
            # compare to explicitly-stated constraint values
            q = r["case"].query.lower()
            for k, v in hyb_constraints.items():
                if str(v) not in q:
                    invented += 1
    invented_rate = pct(invented, len(rows))

    ls = latency_stats(llm_lat)
    fb_rate = tm["fallback_rate"]
    eff_added = (fb_rate * ls["mean"]) if ls else 0

    n_calls = tm["llm_calls"]

    print(f"\n── HEADLINE METRICS ──────────────────────────────────────────")
    print(f"Deterministic intent accuracy:  {det_acc:.2%}  ({sum(1 for r in rows if r['det_eval']['intent_correct'])}/{len(rows)})")
    print(f"Hybrid intent accuracy:          {hyb_acc:.2%}  ({sum(1 for r in rows if r['eval']['intent_correct'])}/{len(rows)})")
    print(f"Net intent accuracy gain:        {hyb_acc - det_acc:+.2%}")
    print(f"Deterministic SEMANTIC success:  {det_sem:.2%}")
    print(f"Hybrid SEMANTIC success:         {hyb_sem:.2%}")
    print(f"Net semantic success gain:       {hyb_sem - det_sem:+.2%}")
    print(f"Deterministic clarification ok:  {det_clar:.2%}")
    print(f"Hybrid clarification ok:         {hyb_clar:.2%}")
    print(f"Errors fixed by LLM:             {len(fixed)}")
    print(f"Correct broken by LLM:           {len(broken)}")

    print(f"\n── LANGUAGE ──────────────────────────────────────────────────")
    print(f"FR deterministic/hybrid intent:  {fr_det:.2%} / {fr_hyb:.2%}")
    print(f"EN deterministic/hybrid intent:  {en_det:.2%} / {en_hyb:.2%}")
    fr_fixed = [r for r in fr_rows if not r["det_eval"]["semantic_success"] and r["eval"]["semantic_success"]]
    fr_broken = [r for r in fr_rows if r["det_eval"]["semantic_success"] and not r["eval"]["semantic_success"]]
    en_fixed = [r for r in en_rows if not r["det_eval"]["semantic_success"] and r["eval"]["semantic_success"]]
    en_broken = [r for r in en_rows if r["det_eval"]["semantic_success"] and not r["eval"]["semantic_success"]]
    print(f"FR fixed: {[r['case'].id for r in fr_fixed]}  broken: {[r['case'].id for r in fr_broken]}  calls: {sum(1 for r in fr_rows if r['hyb_out'].get('_fallback_triggered'))}")
    print(f"EN fixed: {[r['case'].id for r in en_fixed]}  broken: {[r['case'].id for r in en_broken]}  calls: {sum(1 for r in en_rows if r['hyb_out'].get('_fallback_triggered'))}")

    print(f"\n── SECURITY ──────────────────────────────────────────────────")
    print(f"Security gated correctly:        {sec_ok}/{sec_tot}")

    print(f"\n── CONSTRAINT SAFETY (spec §22) ──────────────────────────────")
    print(f"INVENTED_CONSTRAINT_RATE:        {invented_rate:.1%} (target 0%)")

    print(f"\n── LATENCY (spec §23) ────────────────────────────────────────")
    if ls:
        print(f"LLM p50/p90/p95/max:              {ls['p50']}/{ls['p90']}/{ls['p95']}/{ls['max']} ms")
        print(f"Tools mean:                      {ls['mean']} ms over {ls['calls']} calls")
    else:
        print("No LLM calls.")
    print(f"Fallback rate:                   {tm['fallback_rate']:.1%}")
    print(f"Effective added latency:         {eff_added:.0f} ms/query average")

    print(f"\n── ERROR TRANSITIONS (spec §18/§19) ──────────────────────────")
    trans = error_transitions(rows)
    for t, agg in sorted(trans.items()):
        print(f"  {t:32} {agg['count']:3}  {','.join(agg['cases'])}")

    # Net value (spec §19)
    br = trans.get("CORRECT_DETERMINISTIC_BROKEN", {}).get("count", 0)
    cb = trans.get("CORRECT_CLARIFICATION_BROKEN", {}).get("count", 0)
    fixed_n = len(fixed)
    net_fixes = fixed_n - br - cb
    net_sem_gain = hyb_sem - det_sem
    gain_per_call = pct(net_fixes, n_calls)
    print(f"\n── NET VALUE (spec §19) ──────────────────────────────────────")
    print(f"FIXED_BY_LLM:                    {fixed_n}")
    print(f"CORRECT_DETERMINISTIC_BROKEN:    {br}")
    print(f"CORRECT_CLARIFICATION_BROKEN:    {cb}")
    print(f"NET_FIXES:                       {net_fixes}")
    print(f"NET_SEMANTIC_GAIN:               {net_sem_gain:+.2%}")
    print(f"GAIN_PER_LLM_CALL:               {gain_per_call}")

    # Save
    out = _HERE / ("step12_quick_results.json" if quick else "step12_full_results.json")
    save = {
        "model": model,
        "quick": quick,
        "mode": "dry-run-no-llm" if no_llm else "live",
        "trigger": tm,
        "headlines": {
            "det_intent": round(det_acc, 4),
            "hyb_intent": round(hyb_acc, 4),
            "det_semantic": round(det_sem, 4),
            "hyb_semantic": round(hyb_sem, 4),
            "det_clar": round(det_clar, 4),
            "hyb_clar": round(hyb_clar, 4),
            "fr_det": round(fr_det, 4), "fr_hyb": round(fr_hyb, 4),
            "en_det": round(en_det, 4), "en_hyb": round(en_hyb, 4),
            "security_ok": sec_ok, "security_total": sec_tot,
            "fixed": len(fixed), "broken": len(broken),
            "net_fixes": net_fixes, "gain_per_call": gain_per_call,
            "invented_constraints": invented, "invented_rate": round(invented_rate, 4),
        },
        "latency": ls,
        "effective_added_latency_ms": round(eff_added, 1),
        "transitions": {k: v["count"] for k, v in sorted(trans.items())},
        "cases": [
            {
                "id": r["case"].id,
                "query": r["case"].query,
                "category": r["case"].category,
                "language": r["case"].language,
                "expected_intent": r["case"].expected_intent,
                "expected_clarification": r["case"].requires_clarification,
                "det_intent": r["det_out"]["primary_category"],
                "det_correct": r["det_eval"]["intent_correct"],
                "det_semantic_ok": r["det_eval"]["semantic_success"],
                "hyb_intent": r["hyb_out"]["primary_category"],
                "hyb_correct": r["eval"]["intent_correct"],
                "hyb_semantic_ok": r["eval"]["semantic_success"],
                "eligibility": r["decision"].eligibility_class.value,
                "triggered": r["hyb_out"].get("_fallback_triggered", False),
                "agreement": r["hyb_out"].get("_agreement"),
                "llm_latency_ms": r["hyb_out"].get("_llm_latency_ms", 0),
                "ambiguity_codes": r["det_out"].get("ambiguity_codes") or [],
            }
            for r in rows
        ],
    }
    out.write_text(json.dumps(save, indent=2, ensure_ascii=False))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()