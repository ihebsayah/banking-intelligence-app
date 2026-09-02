"""benchmark/qualification/QUALIFICATION_V1/verify_qualification.py

Immutability + drift verification for the QUALIFICATION_V1 dataset:

  --check-hashes : recompute SHA-256 of every dataset file and compare against
                   MANIFEST.sha256 (detects any tampering / post-hoc edits).
  --live-drift   : compare current live banking_dev row counts against the
                   fixture_manifest row counts (detects fixture drift since the
                   snapshot was taken).
  --run-e2e      : re-run the full E2E suite against the immutable fixture with
                   the bound goldens and assert END_TO_END == 100.0.

Exit code 0 = all checks pass.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
QUALS = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, "benchmark", "e2e_nl_sql", "results")
LIVE_DSN = "postgresql://banking_user:securepass123@localhost:5432/banking_dev"
QUAL_DSN = "postgresql://banking_user:securepass123@localhost:5432/banking_qual_v1"
PY = os.path.join(ROOT, "testenv", "bin", "python3")


def _files() -> list:
    return sorted(
        glob.glob(os.path.join(QUALS, "*"))
        + [os.path.join(RESULTS, "E2E_QUALIFICATION_V1.json"),
           os.path.join(RESULTS, "E2E_QUALIFICATION_V1_traces.jsonl")]
    )


def check_hashes() -> bool:
    manifest_path = os.path.join(QUALS, "MANIFEST.sha256")
    if not os.path.exists(manifest_path):
        print("MISSING MANIFEST.sha256")
        return False
    manifest = {}
    for line in open(manifest_path, encoding="utf-8"):
        if "  " in line:
            h, p = line.strip().split("  ", 1)
            manifest[os.path.basename(p)] = h
    ok = True
    for f in _files():
        rel = os.path.basename(f)
        if rel == "MANIFEST.sha256":
            continue
        h = hashlib.sha256(open(f, "rb").read()).hexdigest()
        expected = manifest.get(rel)
        status = "OK" if h == expected else "TAMPERED/MISSING"
        if h != expected:
            ok = False
        print(f"  {status:15s} {rel}")
    print(f"[hashes] {'PASS' if ok else 'FAIL'}")
    return ok


def live_drift() -> bool:
    import psycopg2
    manifest = json.load(open(os.path.join(QUALS, "fixture_manifest.json"), encoding="utf-8"))
    expected = {t["table"]: t["row_count"] for t in manifest["tables"]}
    con = psycopg2.connect(LIVE_DSN)
    cur = con.cursor()
    ok = True
    for table, want in expected.items():
        try:
            cur.execute(f'select count(*) from public."{table}"')
            got = cur.fetchone()[0]
        except Exception:
            got = "ERR"
        if got != want:
            ok = False
            print(f"  DRIFT  {table:28s} fixture={want:8d} live={got}")
    con.close()
    print(f"[live-drift] {'PASS (no drift)' if ok else 'DRIFT DETECTED'}")
    return ok


def run_e2e() -> bool:
    env = dict(os.environ,
               PG_TEST_DSN=QUAL_DSN,
               GOLDENS_FILE=os.path.join("benchmark", "qualification", "QUALIFICATION_V1", "goldens_v1.json"),
               RESULT_TAG="E2E_QUALIFICATION_V1")
    subprocess.run([PY, os.path.join(ROOT, "benchmark", "e2e_nl_sql", "benchmark_runner.py")],
                   cwd=ROOT, env=env, check=True)
    data = json.load(open(os.path.join(RESULTS, "E2E_QUALIFICATION_V1.json"), encoding="utf-8"))
    m = data["metrics"]
    e2e = m["END_TO_END_SEMANTIC_ACCURACY"]
    print(f"[run-e2e] END_TO_END_SEMANTIC_ACCURACY={e2e} (target 100.0)")
    return e2e == 100.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-hashes", action="store_true")
    ap.add_argument("--live-drift", action="store_true")
    ap.add_argument("--run-e2e", action="store_true")
    args = ap.parse_args()
    if not any((args.check_hashes, args.live_drift, args.run_e2e)):
        ap.error("choose at least one check")

    results = []
    if args.check_hashes:
        results.append(check_hashes())
    if args.live_drift:
        results.append(live_drift())
    if args.run_e2e:
        results.append(run_e2e())

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()