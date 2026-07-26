# Test Inventory

Authoritative inventory of the test suite. Generated from actual `pytest --co` output.

## Test Configuration

| Setting | Value |
|---------|-------|
| Framework | pytest |
| Config file | `pytest.ini` |
| asyncio_mode | auto |
| import-mode | importlib |
| Python | 3.13 |
| Total collected | 623 |
| Collection errors | 1 (`test_schema_agent.py`) |

## Collection Error

```
tests/test_schema_agent.py — AttributeError: module 'models' has no attribute 'JoinPath'
Source: services/schema_agent/schema_matcher.py:19
```

## Test Files (30 files in `tests/`)

### Unit Tests

| File | Tests | Description |
|------|------:|-------------|
| `test_audit_enhancement.py` | 14 | Audit enhancement data lineage, compliance reports |
| `test_caching.py` | 5 | Caching layer behavior |
| `test_preset_queries_unit.py` | 1 | Preset query unit validation |
| `test_vagueness_logic.py` | 11 | Vagueness detection logic |

### Agent Tests

| File | Tests | Description |
|------|------:|-------------|
| `test_compliance_agent.py` | 16 | Compliance agent rules and reporting |
| `test_entity_resolution_agent.py` | 10 | Entity resolution and deduplication |
| `test_execution_agent.py` | 10 | Execution agent task handling |
| `test_insights_agent.py` | 12 | Insights generation agent |
| `test_intent_agent.py` | 17 | Intent classification agent |
| `test_schema_agent.py` | 18 | Schema matching agent (collection error) |
| `test_sql_agent.py` | 12 | SQL generation agent |
| `test_validation_agent.py` | 10 | Validation agent checks |

### Integration Tests

| File | Tests | Description |
|------|------:|-------------|
| `test_integration.py` | 15 | General integration flows |
| `test_live_pg_integration.py` | 37 | Live PostgreSQL integration |

### Benchmark / Performance

| File | Tests | Description |
|------|------:|-------------|
| `test_benchmark_gate.py` | 84 | SQL benchmark gate tests (NPL, LDR, currencies, replanning) |
| `test_performance.py` | 7 | Performance benchmarks |

### Security

| File | Tests | Description |
|------|------:|-------------|
| `test_security.py` | 50 | Security rules, auth, injection prevention |

### E2E / Portal

| File | Tests | Description |
|------|------:|-------------|
| `test_increment2_compile.py` | 71 | Increment 2 full compile flow |
| `test_increment3_execution.py` | 70 | Increment 3 full execution flow |
| `test_portal_endpoints.py` | 52 | Portal API endpoints |

### Feature-Specific

| File | Tests | Description |
|------|------:|-------------|
| `test_kpi_governance.py` | 15 | KPI governance and validation |
| `test_phase6b1_semantic_activation.py` | 12 | Phase 6b1 semantic layer activation |
| `test_phase6b_fixes.py` | 17 | Phase 6b semantic layer fixes |
| `test_preset_queries.py` | 17 | Preset query execution |
| `test_query_signing.py` | 10 | Query signing and verification |
| `test_request_gating.py` | 17 | Request gating and rate limiting |
| `test_user_management.py` | 12 | User management CRUD |

### Local / Utility

| File | Tests | Description |
|------|------:|-------------|
| `run_activation_test.py` | 0 | Activation test runner (no test functions) |
| `week3_local_test.py` | 0 | Week 3 local test (no test functions) |
| `week4_local_test.py` | 19 | Week 4 local tests (format, cache, orchestrator) |

## Summary by Category

| Category | Files | Tests |
|----------|------:|------:|
| Unit | 4 | 31 |
| Agent | 8 | 105 |
| Integration | 2 | 52 |
| Benchmark / Performance | 2 | 91 |
| Security | 1 | 50 |
| E2E / Portal | 3 | 193 |
| Feature-Specific | 7 | 100 |
| Local / Utility | 3 | 19 |
| **Total** | **30** | **641** |

> Note: 623 collected by pytest; 18 additional in `test_schema_agent.py` fail at collection time due to `JoinPath` import error.

## Last Verified Execution

- **Command:** `python3 -m pytest tests/ --co -q`
- **Status:** 623 collected, 1 collection error
- **Date:** 2026-07-26
- **Platform:** macOS (darwin), Python 3.13

## Keycloak Migration Impact

- **Auth tests:** Need Keycloak mock/stub replacing current auth fixtures
- **Integration tests:** Need Keycloak test realm for `test_live_pg_integration.py`
- **Security tests:** 50 tests in `test_security.py` — auth-related assertions need Keycloak token validation
- **Benchmark baselines:** `test_benchmark_gate.py` (84 tests) baselines need re-establishment post-migration
