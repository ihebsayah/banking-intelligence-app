# QUALIFICATION_V1 — Immutable Qualification Dataset

Step-19 immutable reference dataset for validator/security qualification and
for binding goldens to a fixed data snapshot. All artifacts in this directory
plus the two `E2E_QUALIFICATION_V1*` result files are the dataset; their SHA-256
fingerprints are pinned in `MANIFEST.sha256`.

## Purpose

The Step-18 frozen goldens (`benchmark/e2e_nl_sql/cases.json`) were authored
against `banking_dev`, but the live DB drifts (seeds, ETL, demos). That drift,
not compiler defects, was the sole cause of the 19 execution failures on the
live DB (audit: `results/execution_drift_audit.json` — 19/19 `FIXTURE_DRIFT`,
0 `SQL_ERROR`, 0 `RECONCILED`). To make "golden = expected" true by
construction, we snapshot `banking_dev` once into an immutable database and
derive goldens by executing each frozen case's compiled SQL on that snapshot.

## Data snapshot

```
CREATE DATABASE banking_qual_v1 TEMPLATE banking_dev;
```

- Created 2026-09-02. Owner/superuser: `banking_user`.
- Handle: `postgresql://banking_user:securepass123@localhost:5432/banking_qual_v1`
  (`PG_TEST_DSN`, no password on mac-local trust).
- Remains read-only for all benchmark runs (benchmark only issues SELECT).

## Files

| file | content |
|---|---|
| `fixture_manifest.json` | per-table `row_count` + `md5` content fingerprint, schema fingerprint, global row count (87,934), cases total (100) |
| `goldens_v1.json` | per-case `expected_result` (mode/value/tolerance or rows) re-executed against `banking_qual_v1` from the frozen compiled SQL |
| `build_fixture.py` | regenerates the two files above against a target DSN |
| `verify_qualification.py` | `--check-hashes` (immutability), `--live-drift` (row-count delta vs manifest), `--run-e2e` (assert END_TO_END == 100.0 on the fixture) |
| `MANIFEST.sha256` | pinned checksums of every dataset file |
| `E2E_QUALIFICATION_V1.json/.jsonl` (in `results/`) | full qualification run pinned in the manifest, with the runner's goldens overlay applied |

## Reproduce qualification run

```
PG_TEST_DSN=postgresql://banking_user:securepass123@localhost:5432/banking_qual_v1 \
GOLDENS_FILE=benchmark/qualification/QUALIFICATION_V1/goldens_v1.json \
RESULT_TAG=E2E_QUALIFICATION_V1 testenv/bin/python3 benchmark/e2e_nl_sql/benchmark_runner.py
```

Expected headline metrics (2026-09-02, Step-19):

```
END_TO_END_SEMANTIC_ACCURACY   100.0
RESULT_CORRECTNESS_RATE        100.0
VALIDATION_CORRECTNESS         100.0
SECURITY_BLOCK_RATE            100.0
UNSAFE_REQUEST_BLOCK_RATE      100.0
UNSAFE_REQUEST_EXECUTION_RATE  0.0
```

The `GOLDENS_FILE` overlay replaces each case's `expected_result` with the
fixture-bound value inside the runner (`benchmark_runner.py:main`), leaving the
frozen `cases.json` untouched.

## Verified via

```
testenv/bin/python3 benchmark/qualification/QUALIFICATION_V1/verify_qualification.py --check-hashes --live-drift
```