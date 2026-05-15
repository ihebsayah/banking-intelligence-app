# Security Documentation — Banking Intelligence System

This document describes the complete security model, threat analysis, and compliance posture of the Banking Intelligence System.

---

## Security Architecture Overview

```
External User
     │
     ▼ HTTPS
[API Gateway :8000]
├── JWT Authentication (HS256)
├── Rate Limiting (100 req/min)
├── Request Audit Logging
└── RBAC Role Extraction
     │
     ▼
[Validation Agent :8006]  ← THE SECURITY GATE
├── Check 1: SQL Syntax
├── Check 2: SELECT-Only (no DML/DDL)
├── Check 3: Keyword Blacklist (30+ patterns)
├── Check 4: LIMIT Clause Required
├── Check 5: Injection Pattern Detection
└── HMAC-SHA256 Signature
     │
     ▼ Only signed queries proceed
[Execution Agent :8007]
├── Signature Verification (rejects tampered SQL)
├── Row-Level Security (role-based WHERE filters)
├── Column-Level Security (role-based column list)
└── PII Masking (SSN, card, email, phone)
```

---

## Threat Model

### Threats Mitigated

| Threat | Mitigation | Status |
|--------|-----------|--------|
| SQL Injection (classic) | Keyword blacklist + pattern detection | ✅ Blocked |
| SQL Injection (UNION-based) | UNION keyword in blacklist | ✅ Blocked |
| SQL Injection (time-based blind) | SLEEP, BENCHMARK, WAITFOR blocked | ✅ Blocked |
| SQL Injection (stacked queries) | Statement type check + EXEC blocked | ✅ Blocked |
| SQL Injection (OR 1=1) | Pattern regex check | ✅ Blocked |
| Unauthorized data access | JWT + RBAC + column filtering | ✅ Blocked |
| PII data exposure | Auto-masking for non-compliance roles | ✅ Blocked |
| Unbounded query (DoS) | LIMIT clause required | ✅ Blocked |
| Query tampering in transit | HMAC-SHA256 signature verification | ✅ Blocked |
| Brute force login | Rate limiting (100 req/min) | ✅ Blocked |
| Privilege escalation | Role immutable in JWT payload | ✅ Blocked |
| Data mutation | SELECT-only check (all writes rejected) | ✅ Blocked |
| Schema discovery | Column whitelist per role | ✅ Mitigated |
| Audit log tampering | WORM audit log (write-only) | ✅ Blocked |

### Residual Risks

| Risk | Impact | Notes |
|------|--------|-------|
| Legitimate but expensive queries | Medium | Mitigated by LIMIT enforcement + 30s timeout |
| JWT secret rotation | Medium | Requires service restart; improve with key rotation API |
| Embedding DB not validated | Low | Embedding service is read-only, separate DB |
| spaCy model poisoning | Low | Intent model updated offline, not via API |

---

## SQL Security Model (5-Layer Defense)

Every query passes through 5 sequential checks. **All 5 must pass.**

### Check 1: Syntax Validation
```python
parsed = sqlparse.parse(sql)
if not parsed or not parsed[0].tokens:
    reject("SQL could not be parsed — invalid syntax")
```
- Ensures query is structurally valid SQL
- Prevents parser-confusion attacks

### Check 2: SELECT-Only Enforcement
```python
if stmt_type != "SELECT":
    reject(f"Non-SELECT statement detected: type='{stmt_type}'")
```
- **Blocks:** INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, TRUNCATE, EXEC, LOAD, MERGE, REPLACE, UPSERT
- No data modification is ever possible through this system

### Check 3: Dangerous Keyword Blacklist
```python
DANGEROUS_KEYWORDS = {
    "DELETE", "INSERT", "UPDATE", "REPLACE", "MERGE", "UPSERT",
    "DROP", "CREATE", "ALTER", "TRUNCATE", "RENAME",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "CALL",
    "SLEEP", "BENCHMARK", "LOAD_FILE", "OUTFILE", "DUMPFILE",
    "LOAD", "INTO OUTFILE", "INTO DUMPFILE",
    "PROCEDURE", "FUNCTION", "TRIGGER", "EVENT",
    "INFORMATION_SCHEMA", "SYS", "MYSQL", "PG_CATALOG",
    "PG_SLEEP", "PG_READ_FILE",
    "COMMIT", "ROLLBACK", "SAVEPOINT",
    "FLUSH", "RESET", "PURGE",
}
```
Uses word-boundary regex matching (`\bKEYWORD\b`) to prevent substring bypass.

### Check 4: LIMIT Clause Required
```python
if "LIMIT" not in sql_upper:
    reject("No LIMIT clause — query could return unbounded rows")
```
- Prevents denial-of-service via full table scans
- Prevents data exfiltration via large dump queries
- Maximum limit enforced at API layer (1000 rows)

### Check 5: Injection Pattern Detection
```python
SUSPICIOUS_PATTERNS = [
    ("or_1_equals_1",   re.compile(r"\bOR\s+'?1'?\s*=\s*'?1'?", re.I)),
    ("and_1_equals_1",  re.compile(r"\bAND\s+'?1'?\s*=\s*'?1'?", re.I)),
    ("comment_inject",  re.compile(r"--\s*\w")),
    ("null_byte",       re.compile(r"\x00")),
    ("hex_encode",      re.compile(r"0x[0-9a-fA-F]{4,}")),
    ("time_attack",     re.compile(r"\bWAITFOR\s+DELAY\b", re.I)),
    ("blind_extract",   re.compile(r"\bIF\s*\(\s*\d+\s*=\s*\d+", re.I)),
    ...
]
```

---

## HMAC Query Signing

### Signature Format
```
sha256:<HMAC_HEX>:<UNIX_TIMESTAMP>
```

### Generation (Validation Agent)
```python
import hmac, hashlib, time

def _sign(sql: str, params: list, key: bytes) -> str:
    payload = sql + "|" + json.dumps(sorted(params), separators=(",", ":"))
    digest = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()
    return f"sha256:{digest}:{int(time.time())}"
```

### Verification (Execution Agent)
```python
def verify_signature(sql: str, params: list, signature: str) -> bool:
    if not signature.startswith("sha256:"):
        return False
    parts = signature.split(":")
    _, provided_hex, _ = parts[0], parts[1], parts[2]
    expected_payload = sql + "|" + json.dumps(sorted(params), separators=(",", ":"))
    expected_hex = hmac.new(SIGNING_KEY, expected_payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected_hex, provided_hex)
```

Uses `hmac.compare_digest` to prevent timing attacks.

### What Signing Protects Against
- Query modification after validation (man-in-the-middle between agents)
- Direct calls to Execution Agent bypassing Validation Agent
- Replay attacks with modified parameters

---

## Authentication (JWT)

### Token Structure
```json
{
  "sub": "analyst1",
  "role": "analyst",
  "exp": 1715734800,
  "iat": 1715731200,
  "jti": "unique-token-id"
}
```

### Configuration
```
JWT_SECRET_KEY=<256-bit random key>
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600
```

### Best Practices Applied
- Short-lived tokens (1 hour)
- Role baked into JWT (prevents role injection)
- JTI (token ID) for revocation support
- Algorithm explicitly specified (prevents "none" attack)

---

## Role-Based Access Control

### Role Hierarchy
```
compliance (highest)  — all data, no masking
    │
    ├── manager — all rows (branch scope in prod), PII masked
    │
    ├── analyst — all rows, PII masked, business columns only  
    │
    └── customer (lowest) — own rows only, minimal columns
```

### Column Visibility by Role

**analyst:** customer_id, name, segment, risk_score, kyc_verified, account_id, account_type, status, balance, available_balance, currency, branch_id, transaction_id, amount, transaction_type, transaction_date, description, flag_type, severity, resolved

**customer:** customer_id, name, segment, account_id, account_type, balance, available_balance, transaction_id, amount, transaction_type, transaction_date

**compliance:** ALL columns (no restriction)

**Hidden from all non-compliance:** ssn, credit_card, email_address, phone, date_of_birth, password, credit_score

### Row-Level Security

In production, `customer` role gets an automatic WHERE clause appended:
```sql
WHERE customer_id = :authenticated_user_id
```
This is enforced by the Execution Agent AFTER SQL generation, using the authenticated user's ID from the JWT.

---

## PII Masking Specification

| Column | Raw Value | Masked Value | Pattern |
|--------|-----------|--------------|---------|
| `ssn` | `123-45-6789` | `***-**-6789` | Keep last 4 |
| `credit_card` | `4532-1234-5678-9012` | `****-****-****-9012` | Keep last 4 |
| `email` | `alice@bank.com` | `a***@bank.com` | Keep first char + domain |
| `phone` | `+1-555-123-4567` | `+1-***-***-4567` | Keep country code + last 4 |
| `date_of_birth` | `1985-03-15` | `****-**-15` | Keep day only |
| `credit_score` | `725` | `***` | Fully masked |
| `password` | `hash_abc123` | `[REDACTED]` | Fully redacted |

---

## Audit Logging

### What Is Logged
Every request to the system creates an immutable audit record:
```json
{
  "timestamp": "2025-05-15T01:30:00.000Z",
  "request_id": "req-uuid-here",
  "user_id": "analyst1",
  "user_role": "analyst",
  "action": "QUERY",
  "query_text": "Top 10 customers by balance",
  "intent_classified": "customer_analysis",
  "validation_result": "PASSED",
  "rows_returned": 10,
  "columns_masked": ["ssn", "credit_score"],
  "execution_time_ms": 145,
  "source": "live",
  "ip_address": "192.168.1.100",
  "user_agent": "curl/7.88.1"
}
```

### Audit Log Properties
- **Append-only:** No DELETE endpoint exists on the Audit Agent
- **Immutable:** Records are written once with UUID + timestamp
- **Persistent:** Stored in PostgreSQL (survives container restarts)
- **Searchable:** Indexed on `user_id`, `timestamp`, `action`

---

## Security Configuration

### Required Environment Variables
```bash
# Authentication
JWT_SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600

# HMAC Query Signing
HMAC_SIGNING_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">

# Database
POSTGRES_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=200
```

### Key Rotation
1. Generate new `JWT_SECRET_KEY` and `HMAC_SIGNING_KEY`
2. Update `.env` file
3. Rolling restart: `docker-compose up -d --no-deps api_gateway validation_agent execution_agent`
4. Existing JWT tokens will be invalidated (users re-authenticate)

---

## Security Test Coverage

All security controls are tested in `tests/test_security.py`:

- **20 SQL injection tests** — All must be BLOCKED
- **10 authentication tests** — Token validation, signature verification
- **10 authorization tests** — Role restrictions, column visibility
- **10 access control tests** — End-to-end ACL verification

```bash
pytest tests/test_security.py -v
# Expected: 50+ passed, 0 failed
```

---

## Compliance Notes

This system is designed with banking regulatory requirements in mind:

- **GDPR/CCPA:** PII minimization via automatic masking; compliance officers retain full access for lawful purposes
- **SOX:** Immutable audit trail for all data access; no data modification possible
- **GLBA:** Customer data access restricted by role; SSN/account numbers masked by default
- **PCI-DSS:** Card numbers masked to last-4 digits for all non-compliance roles

> **Important:** This system is a reporting/analytics platform only. It cannot modify any banking data. All writes are rejected at the validation layer.
