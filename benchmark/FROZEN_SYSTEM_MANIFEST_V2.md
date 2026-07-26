# Frozen System Manifest V2

**Created:** 2026-07-24T03:18:13Z  
**Frozen at:** 2026-07-24T03:18:13Z  
**Description:** Frozen system manifest for blind benchmark V2. This manifest captures the exact system state before the new blind benchmark is created and executed.

## Methodology

> The new blind benchmark was NOT used to configure or tune this frozen system. The system was frozen based on the post-remediation state of the original 160-question holdout.

## Git State

| Field | Value |
|-------|-------|
| Commit | `55930e4b743e6b7e7a41e4ee68c0bb373c0e502d` |
| Branch | `main` |
| Tag | `blind-v2-freeze` |
| Status | modified files present - code changes from remediation are uncommitted |

**Previous frozen manifest:** `benchmark/FROZEN_SYSTEM_MANIFEST.json`  
**Previous freeze commit:** `d03cb280cd37ff701fe5752c99ddfc90332062ed`

## Code Checksums (SHA-256)

| File | SHA-256 |
|------|---------|
| `services/intent_agent/structured_intent.py` | `38ce2b3c...d25a` |
| `services/intent_agent/intent_recognizer.py` | `840fcb5a...420eb` |
| `services/intent_agent/models.py` | `dfdbe901...ad8ae` |
| `services/orchestrator/orchestrator_agent.py` | `9b4087a3...9b20` |
| `services/api_gateway/routes.py` | `bf7698d4...13aff5` |
| `services/sql_agent/sql_builder.py` | `a15b22ec...e4f9` |
| `services/schema_agent/schema_matcher.py` | `a6737de6...924b` |
| `services/shared/config.py` | `0bd284b4...2440` |
| `services/entity_resolution_agent/entity_resolver.py` | `1230de91...157be` |

## Benchmark Checksums (SHA-256)

| File | SHA-256 |
|------|---------|
| `benchmark/holdout/holdout_questions.json` | `db2d62ea...08e` |
| `benchmark/holdout/run_holdout.py` | `12d034c5...1f39` |
| `benchmark/run_development.py` | `0219a806...cf90` |
| `benchmark/run_smoke.py` | `8e2aafee...84c7` |

## Configuration

| Setting | Value |
|---------|-------|
| `INTENT_CONFIDENCE_THRESHOLD` | `0.31` |
| `SEMANTIC_LAYER_ENABLED` | `false` |
| `DEV_MODE` | `true` |
| `BENCHMARK_MODE` | `false` |

## Services

| Service | Port | Purpose |
|---------|------|---------|
| api_gateway | 8000 | REST API entry point, request routing, validation |
| intent_agent | 8002 | Intent classification and parameter extraction |
| orchestrator_agent | 8003 | Pipeline orchestration and agent coordination |
| sql_agent | 8004 | SQL generation and execution |
| schema_agent | 8005 | Database schema matching and context |
| entity_resolution_agent | 8006 | Entity resolution and aliasing |
| postgres | 5432 | Primary database with pgvector extension |
| redis | 6379 | Caching and session management |
| ollama | 11434 | Local LLM inference |

## Docker

| Field | Value |
|-------|-------|
| Compose checksum | `cb2dd1d7...945b` |

### Image IDs

| Image | ID |
|-------|----|
| banking-intelligence-system-api-gateway:latest | `d2d756fa74b7` |
| banking-intelligence-system-frontend:latest | `9b7feac5bc00` |
| python:3.11-slim | `a3ab0b966bc4` |
| postgres:16-alpine | `16bc17c64a57` |
| redis:7-alpine | `6ab0b6e73817` |
| ollama/ollama:latest | `0ff452f6a4c3` |
| pgvector/pgvector:pg16 | `7d400e340efb` |

## Dependencies

| Type | Checksum |
|------|----------|
| Python lock | `572cf7a8...94132` |
| Node lock | N/A |

## Database

| Field | Value |
|-------|-------|
| Name | `banking_dev` |
| Snapshot | `banking_dev_benchmark.dump` |

## Model

| Field | Value |
|-------|-------|
| Name | `mistral` |
| Provider | `ollama` |
| Version | `mistral:latest (6577803aa9a0)` |

## Integrity Guarantees

| Guarantee | Value |
|-----------|-------|
| New benchmark used for tuning | **false** |
| New benchmark exposed to implementation | **false** |
| Code changes after freeze | **none permitted** |
