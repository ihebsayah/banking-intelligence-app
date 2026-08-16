# Phase 3A.6 — Test Data Isolation and Data Hygiene Report

**Status: PHASE 3A.6 COMPLETE.**
**Produced: 2026-08-16**

---

## 1. Executive Summary

Phase 3A.6 successfully established complete test data isolation for the operational Workbench environment (`banking_integration`). Automated integration test suites and smoke scripts can now run repeatedly without leaving persistent test artifacts in the operational database.

Key achievements:
- **Root Cause Identified**: Integration tests (`test_2b17b_scenarios.py`, `conftest.py`) and smoke scripts (`staging_smoke_test.sh`) were seeding workflow entities with random UUIDs directly into `banking_integration` without teardown fixtures.
- **Deterministic Isolation Implemented**: Added an `autouse=True` fixture (`isolate_test_data`) in `services/workbench/tests/conftest.py` that differential-snapshots database IDs before each test and deletes only test-created records upon teardown. Added an exit trap (`cleanup_smoke_data`) in `scripts/staging_smoke_test.sh`.
- **Primary Acceptance Criterion Verified**:
  $$\text{Baseline} \equiv \text{After Run \#1} \equiv \text{After Run \#2}$$
  Running the 74-test scenario suite twice resulted in zero net change to persistent operational data.
- **Phase 3A.5 Preserved**: All 21/21 Customer 360 backend tests pass, and canonical entity resolutions (`CUST_00921`, `ACC_00412` $\rightarrow$ `CUST_00141`, `CUST_00077`, `CUST_00001`) remain intact.
- **Zero Pollution**: The 724 historical test artifacts remain untouched and their count did not increase.

---

## 2. Root Cause Analysis

Before Phase 3A.6:
1. `services/workbench/tests/test_2b17b_scenarios.py` defined seed helpers (`_seed_alert`, `_seed_investigation`, `_seed_case`, `_seed_ir`, `_seed_comment`, `_seed_approval`) that inserted rows into PostgreSQL via `asyncpg` but provided no teardown logic.
2. `services/workbench/tests/conftest.py` defined `seed_workflow_objects` fixture which inserted rows without `yield` / cleanup statements.
3. `scripts/staging_smoke_test.sh` created temporary `Smoke Alert`, `Dismiss Test`, `Smoke Investigation`, `Smoke Case`, and `IR Smoke Case` rows using `psycopg2` without an `EXIT` trap cleanup handler.

---

## 3. Isolation Strategy Selected

**Selected Approach: Deterministic Differential Teardown (Strategy B)**.

- **Mechanism**:
  - Before each test, the fixture snapshots the exact set of pre-existing primary keys across all operational tables (`alerts`, `investigations`, `compliance_cases`, `information_requests`, `comments`, `approval_requests`, `decisions`).
  - During test execution, tests run normally and insert whatever data they require.
  - On test teardown, the fixture calculates the set difference ($\text{post\_keys} \setminus \text{pre\_keys}$) and executes parameterized `DELETE FROM <table> WHERE id = ANY($1)` targeting **only** newly inserted test primary keys.
- **Why Not Transaction Rollback?**: Tests issue independent HTTP requests to running services and manage separate database connections/transactions. Rollback on a single test connection cannot isolate writes performed across separate service connections.
- **Why Not TRUNCATE/DELETE ALL?**: Broad cleanup is prohibited as it would destroy canonical business demo data and historical audit records.

---

## 4. Files Changed

| File | Type | Changes Made |
|---|---|---|
| [`services/workbench/tests/conftest.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/tests/conftest.py#L140-L200) | Test Fixtures | Added `isolate_test_data` autouse fixture and teardown for `seed_workflow_objects`. |
| [`services/workbench/tests/test_audit_mock.py`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/services/workbench/tests/test_audit_mock.py#L52-L63) | Test Mock | Added `allow_reuse_address = True` to HTTPServer to avoid port 18008 socket bind failures between test runs. |
| [`scripts/staging_smoke_test.sh`](file:///Users/ihebsayah/Documents/Reporting-app/banking-intelligence-system/scripts/staging_smoke_test.sh#L15-L35) | Shell Script | Added `trap cleanup_smoke_data EXIT` to clean up temporary smoke alerts, cases, and requests upon script termination. |

---

## 5. Verification & Data Fingerprint Comparison

### 5.1 Dataset Fingerprint Across Test Runs

| Metric / Table | Baseline (Step A) | After Run #1 (Step B) | After Run #2 (Step C) | Status |
|---|---|---|---|---|
| `alerts` | **728** | **728** | **728** | **UNCHANGED** |
| `investigations` | **717** | **717** | **717** | **UNCHANGED** |
| `compliance_cases` | **1486** | **1486** | **1486** | **UNCHANGED** |
| `information_requests` | **251** | **251** | **251** | **UNCHANGED** |
| `approval_requests` | **225** | **225** | **225** | **UNCHANGED** |
| `comments` | **212** | **212** | **212** | **UNCHANGED** |
| `unlinked_alerts` (historical artifacts) | **724** | **724** | **724** | **UNCHANGED** |

$$\text{Baseline} \equiv \text{After Run \#1} \equiv \text{After Run \#2}$$

### 5.2 Scenario Test Results
- **Run #1**: `pytest services/workbench/tests/test_2b17b_scenarios.py` $\rightarrow$ **74 / 74 PASSED** (38.64s).
- **Run #2**: `pytest services/workbench/tests/test_2b17b_scenarios.py` $\rightarrow$ **74 / 74 PASSED** (37.04s).

### 5.3 Customer 360 / Phase 3A.5 Regression Verification
- **Customer 360 Test Suite**: **21 / 21 PASSED** (`pytest services/api_gateway/customer360/tests`).
- **Canonical Entity Resolution**:
  - `CUST_00921` $\rightarrow$ `CUST_00921`
  - `ACC_00412` $\rightarrow$ `CUST_00141`
  - `CUST_00077` $\rightarrow$ `CUST_00077`
  - `CUST_00001` $\rightarrow$ `CUST_00001`

---

## 6. Historical Artifact Classification & Cleanup Recommendation

### 6.1 Classification of 724 Unlinked Artifacts

Analysis of the 724 historical unlinked alerts in `banking_integration`:

1. **672 Alerts (`"Seed Alert"`)**:
   - Created by pre-Phase 3A.6 runs of `test_2b17b_scenarios.py`.
   - Characteristics: `title = 'Seed Alert'`, `related_entity_type IS NULL`.
2. **30 Alerts (`"Test Alert"`, `"Smoke Alert"`, `"Dismiss Test"`)**:
   - Created by pre-Phase 3A.6 runs of `test_infrastructure_smoke.py` and `staging_smoke_test.sh`.
3. **22 Alerts (Ad-hoc benchmark artifacts)**:
   - Created during early development iterations prior to Phase 3A.4.

### 6.2 Remediation Recommendation (NOT EXECUTED)

To clean up historical artifacts without risking canonical data or active workflows, the following targeted query can be authorized in a future phase:

```sql
-- PROPOSED CLEANUP (AWAITING SEPARATE AUTHORIZATION - NOT EXECUTED)
BEGIN;

DELETE FROM alerts 
WHERE related_entity_type IS NULL 
  AND related_entity_id IS NULL 
  AND title IN ('Seed Alert', 'Test Alert', 'Smoke Alert', 'Dismiss Test');

COMMIT;
```

> **Status**: The 724 historical artifacts have **NOT** been deleted and remain intact.

---

## 7. Remaining Risks & Safeguards

- **Risk**: A developer writing a new test file outside `services/workbench/tests/` without using `conftest.py`.
  - *Safeguard*: `conftest.py` is loaded for all tests under `services/workbench/tests/`. Any new test placed in this directory automatically inherits `isolate_test_data`.
- **Risk**: Test process being forcefully terminated (`SIGKILL` / `kill -9`) before pytest teardown runs.
  - *Safeguard*: Standard pytest test runs (`pytest`) execute teardown handlers gracefully. In CI/CD pipelines, container teardown handles test environment reset if the container is destroyed.

---

## 8. Final Verdict

**PHASE 3A.6 COMPLETE.**
