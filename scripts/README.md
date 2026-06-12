# scripts/

One-off debug, fix, and scratch scripts from early development.

**Do not run these in production** — they were used to patch issues during the initial build phases.

| Script | Purpose |
|---|---|
| `fix_cors.py` | Patch CORS headers on api-gateway |
| `fix_date_type.py` | Fix date column type mismatch |
| `fix_executor_date.py` | Fix date handling in execution_agent |
| `fix_fallback.py` | Fix orchestrator LLM fallback logic |
| `fix_init_vars.py` | Fix uninitialized variables |
| `fix_join_key.py` | Fix SQL join key bug |
| `fix_orch2.py` | Orchestrator pipeline patch v2 |
| `fix_orchestrator.py` | Orchestrator pipeline patch v1 |
| `fix_products.py` | Fix product table query |
| `fix_re.py` | Fix regex pattern in intent_agent |
| `fix_risk_flags.py` | Fix risk_flags schema |
| `fix_unit_test_risk_flags.py` | Fix unit test for risk_flags |
| `debug.py` | Ad-hoc debug script |
| `db_test.py` | Quick DB connectivity test |
| `print_payload.py` | Print raw pipeline payload |
| `test_local.py` | Local manual test runner |
| `test_mistral.py` | Mistral/Ollama smoke test |
| `test_mistral_output.py` | Mistral output format test |
| `test_orch.py` | Orchestrator manual test |
