# Pre-Change Test Results — Increment 1A

**Date**: 2026-07-26
**Commit**: 78840c6
**Branch**: main
**Working tree**: Clean (before changes)

## Focused Auth/Security Tests

| Suite | Collected | Passed | Failed | Errors | Duration |
|-------|-----------|--------|--------|--------|----------|
| test_security.py | 50 | 50 | 0 | 0 | 0.05s |
| test_portal_endpoints.py | 52 | 52 | 0 | 0 | 2.23s |
| test_user_management.py | 12 | 12 | 0 | 0 | 3.28s |
| **Total** | **114** | **114** | **0** | **0** | **5.56s** |

## Notes

- All 114 focused tests pass on the baseline.
- 623 total tests in the suite; 38 pre-existing failures and 104 collection errors (unrelated to auth).
- These pre-existing failures must NOT be attributed to the Keycloak migration.
