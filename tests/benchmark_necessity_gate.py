"""Offline benchmark for the Insights Necessity Gate (STEP 3).

Runs a representative set of query TYPES through the gate (no DB, no LLM)
and reports routing distribution and unnecessary-LLM-call rate.

Usage:  python3 -m tests.benchmark_necessity_gate
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "insights_agent"))

from necessity_gate import NecessityGate
from models import (
    AnalyticalFactPackage, DatasetProfile, AnomalyFact, CorrelationFact,
    TemporalComparison, Provenance,
)


def _profile(row_count, numeric, categorical, nulls=None):
    cols = list(numeric) + list(categorical)
    return DatasetProfile(
        row_count=row_count, columns=cols,
        numeric_columns=list(numeric), categorical_columns=list(categorical),
        null_counts={c: 0 for c in cols} if nulls is None else nulls,
    )


def _pkg(profile, anomalies=(), corr=(), temporal=(), recs=0, eq=0.9):
    pkg = AnalyticalFactPackage(
        query_intent="x", query_text="", dataset_profile=profile,
        anomalies=list(anomalies), correlations=list(corr),
        temporal_comparisons=list(temporal),
        recommendation_candidates=[object()] * recs,
    )
    pkg.evidence_quality.score = eq
    return pkg


_A = lambda: AnomalyFact(column="balance", observed_value=9999.0, mean=100.0,
                         std_dev=10.0, deviation=900.0, severity="extreme",
                         provenance=Provenance(source="deterministic_calculation", column="balance", method="z"))
_C = lambda: CorrelationFact(column_a="a", column_b="b", coefficient=0.9, sample_size=100,
                             provenance=Provenance(source="deterministic_calculation", method="pearson"))
_T = lambda: TemporalComparison(column="balance", earliest_period="2024-01", latest_period="2024-02",
                                previous_value=100.0, current_value=130.0, absolute_change=30.0,
                                percentage_change=30.0,
                                provenance=Provenance(source="deterministic_calculation", method="po"))

# (label, intent, text, pkg, expected_route)
BENCH = [
    ("direct_lookup", "retrieve", "Balance of customer CUST_00141",
     _pkg(_profile(1, ("balance",), ())), "DETERMINISTIC"),
    ("count", "customer_analysis", "How many customers are in branch X?",
     _pkg(_profile(42, (), ("region",))), "DETERMINISTIC"),
    ("avg_agg", "product_analysis", "Average loan amount",
     _pkg(_profile(50, ("amount",), ())), "DETERMINISTIC"),
    ("top_n", "customer_analysis", "Top 5 branches by deposits",
     _pkg(_profile(20, ("balance",), ("branch",))), "DETERMINISTIC"),
    ("concentration", "geographic_analysis", "Analyze deposit concentration by region",
     _pkg(_profile(100, ("balance",), ("region",))), "LLM_USEFUL"),
    ("trend_valid", "transaction_analysis", "Explain the trend in loan exposure",
     _pkg(_profile(100, ("balance",), ()), temporal=(_T(),)), "LLM_USEFUL"),
    ("anomaly_valid", "risk_analysis", "Identify unusual transaction activity",
     _pkg(_profile(100, ("balance",), ()), anomalies=(_A(),)), "LLM_USEFUL"),
    ("compare_explain", "geographic_analysis", "Compare branches and explain what stands out",
     _pkg(_profile(100, ("balance",), ("region",))), "LLM_USEFUL"),
    ("override_explain", "retrieve", "Balance of CUST_00141 explain the reason",
     _pkg(_profile(1, ("balance",), ())), "LLM_USEFUL"),
    ("trend_no_evidence", "transaction_analysis", "Explain the trend in loan exposure",
     _pkg(_profile(100, ("balance",), ())), "DETERMINISTIC"),
    ("anomaly_none", "risk_analysis", "Identify unusual transaction activity",
     _pkg(_profile(100, ("balance",), ())), "DETERMINISTIC"),
    ("fr_analytical", "geographic_analysis", "Analyser la concentration des dépôts par région",
     _pkg(_profile(100, ("balance",), ("region",))), "LLM_USEFUL"),
    ("fr_direct", "retrieve", "Solde de CUST_00141",
     _pkg(_profile(1, ("balance",), ())), "DETERMINISTIC"),
]


def main():
    gate = NecessityGate()
    tp = fp = tn = fn = 0
    print(f"{'query':28} {'expected':12} {'got':12} {'use_llm'}")
    print("-" * 70)
    for label, intent, text, pkg, expected in BENCH:
        d = gate.evaluate(intent, text, pkg)
        got = "LLM_USEFUL" if d.use_llm else "DETERMINISTIC"
        ok = got == expected
        if ok:
            if got == "LLM_USEFUL":
                tp += 1
            else:
                tn += 1
        else:
            if got == "LLM_USEFUL":
                fp += 1
            else:
                fn += 1
        print(f"{label:28} {expected:12} {got:12} {'Y' if d.use_llm else 'N'} {'OK' if ok else 'MISMATCH'}")
    print("-" * 70)
    n = tp + tn + fp + fn
    llm_calls = tp + fp
    unnecessary_llm = fp
    rate = unnecessary_llm / llm_calls if llm_calls else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print(f"Cases: {n}")
    print(f"  UNNECESSARY LLM CALL RATE : {rate:.0%}  ({fp} false positives / {llm_calls} LLM-route)")
    print(f"  LLM routing precision      : {precision:.0%}")
    print(f"  LLM routing recall         : {recall:.0%}")
    print(f"  False negatives            : {fn} (LLM-needed routed to deterministic)")
    print(f"  Deterministic%             : {sum(1 for *_, e in BENCH if e=='DETERMINISTIC')/n:.0%} of benchmark routed away")


if __name__ == "__main__":
    main()
