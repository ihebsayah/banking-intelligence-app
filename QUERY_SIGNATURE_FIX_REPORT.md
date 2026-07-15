# Query Signature Fix Report — Resolve SIGNATURE_INVALID End-to-End

This report details the root cause of the `SIGNATURE_INVALID` error and the implementation of the new, shared canonical signing contract.

## Root Cause Analysis

Before this fix, query signature verification failed due to two main issues:
1. **Signing Key Parity**: The `validation-agent` container did not have the `QUERY_SIGNING_KEY` environment variable set in `docker-compose.yml`, causing it to fall back to a hardcoded default key (`DEMO_KEY_CHANGE_IN_PRODUCTION_DO_NOT_USE_IN_PROD`). In contrast, the `execution-agent` did have the variable set and fell back to `CHANGE_IN_PRODUCTION`.
2. **Lack of a Unified Serialization Standard**: There was no unified serializer contract. SQL whitespace variations (e.g. carriage returns or multiline formatting introduced by the SQL agent) and parameter order changes could result in different byte streams between the signer and verifier.

---

## Services & Architecture Involved

- **API Gateway**: Entry point that authenticity-tokens requests and forwards query inputs to the Orchestrator.
- **Orchestrator Agent**: Manages the pipeline. Generates standard `request_id` and `nonce` parameters and passes them downstream.
- **Validation Agent**: Validates queries against security policies, normalizes the SQL and parameters, signs the safe request using the new canonical contract, and attaches the signature.
- **Execution Agent**: Verifies the signature from the Validation Agent against the raw execution parameters. It parses metadata (timestamp, nonce, and request_id) directly from the signature token to perform validation.

---

## Technical Details

### Old Signature Format
The old signature was formatted as:
```text
sha256:{hex_sig}:{timestamp}
```
And was signed over a simple concatenated string:
```python
message = sql + "|" + str(sorted(str(p) for p in parameters))
```

### New Canonical Signature Format
The new signature payload includes `request_id`, `sql`, `parameters`, `timestamp`, and `nonce`.
The signature string carries this metadata inline:
```text
sha256:{hex_sig}:{timestamp}:{nonce}:{request_id}
```
The payload is serialized using deterministic JSON formatting:
```python
json.dumps(
    payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
```

The normalization rules guarantee that:
- SQL consecutive whitespace runs (including carriage returns and newlines) are collapsed to a single space.
- Parameters (dictionaries, lists, dates, and datetimes) are recursively sorted and formatted.
- Unicode characters are normalized to standard NFC format.
- Clock skew tolerance check is enforced (within 60 seconds of skew/age).

---

## Environment & Infrastructure Changes

1. **`docker-compose.yml`**:
   - Passed `QUERY_SIGNING_KEY` and `QUERY_SIGNATURE_MAX_AGE_SECONDS` to the `validation-agent` container.
   - Added `QUERY_SIGNATURE_MAX_AGE_SECONDS` to the `execution-agent` and `orchestrator-agent` containers.
2. **`.env` & `.env.example`**:
   - Added template values:
     ```text
     QUERY_SIGNING_KEY=replace-with-a-long-random-secret
     QUERY_SIGNATURE_MAX_AGE_SECONDS=60
     ```

---

## Tests Executed

1. **Unit Tests (`tests/test_query_signing.py`)**:
   - Passed 10 scenario tests covering: valid signature acceptance, wrong keys, modified SQL/parameters/request_ids, expired timestamps, clock skew tolerance, dictionary sorting parity, whitespace normalization, and Unicode French characters.
2. **Execution Agent Test Suite (`POST http://localhost:8007/test_execution`)**:
   - Verified all 15 test cases (PII masking, RBAC column masking, CSV/Table formats, Redis caching, signature tamper detection) passed successfully.
3. **Validation Agent Test Suites (`POST http://localhost:8006/test_good_queries` & `/test_injections`)**:
   - Validated standard query approvals and verified that all 22 injection vectors (DML, DDL, SQL comments, blind injections) are correctly rejected.

---

## Live Verification Results

We successfully ran the queries through the API Gateway, and both processed without signature errors:

### 1. English Query
- **Query**: `Show customer names and their account balances`
- **Status**: `success`
- **Row Count**: **100 rows**
- **Data Freshness**: `real-time` (Direct DB hit)
- **Sample Result**:
  ```json
  {
    "id": "3532c5ee-00c2-42b6-9c40-477caad52726",
    "account_id": "ACC_00001",
    "customer_id": "CUST_00001",
    "account_type": "checking",
    "status": "active",
    "balance": "1774.52",
    "available_balance": "1774.52",
    "currency": "TND",
    "branch_id": "BR_021",
    "created_at": "2025-11-12T17:43:34"
  }
  ```

### 2. French Query
- **Query**: `Quel est le montant total des dépôts par segment client ?`
- **Status**: `success`
- **Row Count**: **100 rows**
- **Data Freshness**: `real-time` (Direct DB hit after cache eviction)
- **Sample Result**:
  ```json
  {
    "id": "3532c5ee-00c2-42b6-9c40-477caad52726",
    "account_id": "ACC_00001",
    "customer_id": "CUST_00001",
    "account_type": "checking",
    "status": "active",
    "balance": "1774.52",
    "available_balance": "1774.52",
    "currency": "TND",
    "branch_id": "BR_021",
    "created_at": "2025-11-12T17:43:34"
  }
  ```

---

## Remaining Limitations
- Clock skew validation relies on the verifier machine's clock matching the signer machine's clock (tolerance parameter `QUERY_SIGNATURE_MAX_AGE_SECONDS` is set to 60 seconds to support normal server lag).
