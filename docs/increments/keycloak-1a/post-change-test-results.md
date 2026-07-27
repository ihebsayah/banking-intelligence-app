# Post-Change Test Results — Increment 1A

**Date**: 2026-07-26
**After**: Keycloak authentication boundary implementation

## Focused Auth/Security Tests

| Suite | Collected | Passed | Failed | Errors | Duration |
|-------|-----------|--------|--------|--------|----------|
| test_security.py | 50 | 50 | 0 | 0 | 0.05s |
| test_portal_endpoints.py | 52 | 52 | 0 | 0 | 2.01s |
| test_user_management.py | 12 | 12 | 0 | 0 | 3.24s |
| test_keycloak_auth.py (NEW) | 24 | 24 | 0 | 0 | 1.35s |
| **Total** | **138** | **138** | **0** | **0** | **6.65s** |

## Comparison with Pre-Change Baseline

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total tests | 114 | 138 | +24 |
| Passed | 114 | 138 | +24 |
| Failed | 0 | 0 | 0 |
| Duration | 5.56s | 6.65s | +1.09s |

## New Test Coverage (test_keycloak_auth.py)

| Category | Tests | Status |
|----------|-------|--------|
| Valid RS256 token | 1 | PASS |
| Expired token | 1 | PASS |
| Invalid signature | 1 | PASS |
| Wrong issuer | 1 | PASS |
| Wrong audience | 1 | PASS |
| alg=none rejection | 1 | PASS |
| HS256 rejection | 1 | PASS |
| Malformed token | 1 | PASS |
| Unknown kid refresh | 1 | PASS |
| JWKS unavailable (warm cache) | 1 | PASS |
| JWKS unavailable (empty cache) | 1 | PASS |
| Role mapping (6 roles + edge cases) | 9 | PASS |
| Config defaults | 2 | PASS |
| User model fields | 2 | PASS |

## Regressions

**None.** All pre-existing tests continue to pass. The 24 new tests add Keycloak-specific coverage.

## Notes

- test_security.py has a known sys.modules pollution issue when run in the same process as other test files (pre-existing, not caused by this increment)
- All test suites pass when run individually or in the correct order
