# Architecture technique — Banking Intelligence System

> Document traçable vers le code et la configuration du dépôt.
> Tout composant ci-dessous est attesté par une référence `chemin:ligne`.
> Les points non confirmés sont explicitement marqués **[à vérifier]**.
> « Module » ≠ « microservice » : les « services » sont des conteneurs séparés
> (vus dans `docker-compose.yml`) ; les modules *au sein* d'un service ne sont pas
> déployés de façon indépendante.

---

## 1. Vue d'ensemble des couches

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 1. FRONTEND         React 18 + TS + Vite · Keycloak-js (OIDC PKCE)       │
│                     nginx (serviteur SPA + reverse-proxy /api → gateway) │
├──────────────────────────────────────────────────────────────────────────┤
│ 2. API GATEWAY /    FastAPI (:8000) · JWT/Keycloak · RBAC · scope ·      │
│    IAM              rate-limit · journal d'audit · proxy workbench       │
├──────────────────────────────────────────────────────────────────────────┤
│ 3. SERVICES         workbench (:8014) · customer360 (dans gateway)       │
│    MÉTIER           = alertes/cas/enquêtes/approbations/IR/outbox        │
├──────────────────────────────────────────────────────────────────────────┤
│ 4. MOTEUR IA        orchestrateur (Mistral local) → pipeline d'agents    │
│    MULTI-AGENTS     intent→schema→entity→sql→validation→compliance→      │
│                     exécution→insights→audit                             │
├──────────────────────────────────────────────────────────────────────────┤
│ 5. DONNÉES &       postgres-main · postgres-integration · postgres-audit │
│    STOCKAGE        postgres-embeddings (pgvector) · Redis · stockage     │
│                    de preuves (travail d'enquête)                         │
└──────────────────────────────────────────────────────────────────────────┘
        ════════════ TRANSVERSE : Sécurité & Audit (Keycloak/JWT,          ════════
                    journal d'audit immuable, RBAC+scope+ownership)
```

---

## 2. Couche 1 — Frontend

| Élément | Preuve |
|---|---|
| Stack React 18 + TS + Vite | `frontend/package.json` |
| Auth OIDC via keycloak-js, PKCE S256, `login-required` | `frontend/src/auth/keycloak.ts`, `frontend/src/auth/AuthProvider.tsx` |
| Intercepteur axios : rafraîchit le token (`updateToken`) et l'attache en Bearer | `frontend/src/api/client.ts:22` |
| Routes protégées (`ProtectedRoute` + permissions) | `frontend/src/App.tsx:67` et suiv. |
| Pages métier 18+ (BankingDashboard, Assistant, Risk, Compliance, KPI, Customers, Alerts, Investigations, Cases, Approvals, IR, Outbox…) | `frontend/src/App.tsx` (imports pages) |
| WebSocket (socket.io-client) pour logs d'agents / notifications | `frontend/src/hooks/useWebSocket.ts` |
| serviteur SPA + reverse-proxy `/api/ → api-gateway:8000` (nginx) | `frontend/nginx.conf` |
| Modules API client (24 modules, dont `customer360Api`, `attachmentsApi` pour le streaming de preuves) | `frontend/src/api/*` |

---

## 3. Couche 2 — API Gateway / IAM

Service **`api_gateway`** (FastAPI, port 8000).

| Capacité | Preuve |
|---|---|
| Auth JWT (bcrypt users) + validation Keycloak RS256/JWKS | `services/api_gateway/auth.py`, `keycloak_auth.py` |
| Rate limiting (slowapi, 100/min) | `services/api_gateway/main.py` |
| Middleware d'audit (chaque requête journalisée) | `services/api_gateway/main.py` |
| CORS | `services/api_gateway/main.py` |
| Moteur de politique (RBAC + scope org + ownership) | `services/shared/authorise.py` (`PermissionDeniedError`, `ScopeDeniedError` → 404, `OwnershipDeniedError`, `ProhibitedComboError`) |
| Routes Customer 360 (overview / transactions / search) avec permission-gate + journal d'audit | `services/api_gateway/routes.py:2863`, `:2919`, `:2987` |
| Proxy catch-all vers workbench (injecte `X-Test-User`, réécrit les chemins) — **enregistré en dernier** pour ne pas masquer les routes concrètes | `services/api_gateway/routes.py:3040` |

> Distinction importante : **reverse proxy** (nginx, couche 1) ≠ **API Gateway / IAM** (ce service, couche 2) ≠ **services métier** (couche 3). Aucun « microservice » front-end ne s'appelle directement la base.

---

## 4. Couche 3 — Services métier

### 4.1 Workbench (`:8014`)
Conteneur séparé (opérationnel : alertes, enquêtes, cas, approbations).
- Application d'intégration montée (via `.mount`), rejette toute URL pointant vers :5432 (`services/workbench/integration_app.py`) — l'écriture d'essai utilise la base d'intégration.
- `repos.py` : repositories UoW (alerts, cases, investigations, approvals, information requests, comments, notifications, timeline, outbox, directives).
- `storage.py` : `EvidenceStorage`, `EVIDENCE_STORAGE_ROOT`, limite 10 MB, types MIME en liste blanche.
- Routers : `routers/` (12 fichiers, dont `admin_orphans`, `admin_outbox`).
- Workers d'arrière-plan : expiration + outbox (lancement via background tasks, `services/workbench/main.py`).

### 4.2 Customer 360 (dans l'API Gateway, pas conteneur séparé)
- Agrégat **lecture seule** sur `banking_dev` (autoritaire) + `banking_integration` (liens workbench / scopes org) : `services/api_gateway/customer360/service.py`.
- Gating par section via `SECTION_PERMISSIONS`, scope org branch/région, masquage PII : `services/api_gateway/customer360/service.py`.
- Repos lecture seule, paramétrés, lectures bornées : `services/api_gateway/customer360/repos.py`.

> Les modules d'alertes/enquêtes/cas ne sont **pas** des microservices : c'est le workbench (un conteneur) qui les héberge. Les agents (`compliance_agent`, `execution_agent`,…) sont bien des conteneurs séparés — ce sont eux les microservices/agents.

---

## 5. Couche 4 — Moteur IA multi-agents

Pile confirmée : `Intent → Schema → Entity Resolution → SQL → Validation → Compliance → Execution → (Insights, Audit)`.

| Agent | Port | Implémentation / rôle | LLM ? | Preuve |
|---|---|---|---|---|
| **Orchestrateur** | (orchestrator) | Pilote la pipeline, appelle chaque agent par URL, **Mistral local** (`MISTRAL_API_URL`, défaut `http://localhost:11434`), diff usage websocket | ✅ | `services/orchestrator/orchestrator_agent.py:1`, `:17` |
| **Intent Agent** | 8001 | Reconnaissance d'intention + gate (rejette adversarial/suspicious, clarification si confiance < seuil) | déterministe | `services/intent_agent/intent_recognizer.py` |
| **Schema Agent** | — | Carte sémantique (domaines, colonnes) via pgvector | déterministe | `services/schema_agent/` |
| **Entity Resolution** | — | Résout entités/id sémantiques → colonnes | déterministe | `services/entity_resolution_agent/` |
| **SQL Agent** | 8005 | `SQLBuilder` : SQL paramétré, jamais de concaténation utilisateur, LIMIT garanti **déterministe** | ❌ | `services/sql_agent/main.py:137`, `sql_builder.py`, `deterministic_compiler.py` |
| **Validation Agent** | — | 5 vérifs anti-injection (syntax, SELECT only, keywords, LIMIT, patterns) + signature HMAC | déterministe | `services/validation_agent/query_validator.py:1` |
| **Compliance Agent** | 8011 | Vérifs GDPR / PCI-DSS / SOX / AML / KYC (masquage, colonnes cartes, tables SOX) | déterministe | `services/compliance_agent/compliance_checker.py:11` |
| **Execution Agent** | 8007 | Exécution isolée, **base en lecture seule**, `access_controller` (filtres lignes + colonnes + PII par rôle), `query_executor`, `result_verifier`, `plan_refiner`, `pg_repair_engine` | déterministe | `services/execution_agent/main.py`, `access_controller.py:1` |
| **Insights Agent** | 8013 | Statistiques + résumé NL via Mistral | ✅ | `services/insights_agent/` (`statistical_analyzer`, `mistral_integrator`) |
| **Audit Agent** | 8008 | Journal d'audit | déterministe | `services/audit_agent/` |
| **Embedding Service** | — | Calcule embeddings (all-MiniLM-L6-v2, 384 dim) pour schéma/entités | déterministe (modèle) | `services/embedding_service/` |

### Point clé — frontière LLM / données
- Le **LLM** (orchestrateur, insights) reçoit uniquement le **plan structuré** et les **résumés** ; il ne reçoit **jamais d'accès direct à la base**.
- Le SQL final est produit par un **compilateur déterministe** (`sql_agent/SQLBuilder`) et exécuté par l'**execution agent en lecture seule** avec RBAC au niveau ligne/colonne (`execution_agent/access_controller.py`).
- ⇒ **Les données bancaires restent locales ; l'accès à la base est borné et jamais « brut » pour l'LLM.**

---

## 6. Couche 5 — Données & stockage

| Composant | Rôle | Preuve |
|---|---|---|
| `postgres-main` (banking_dev :5432) | Données autoritaires (customers, accounts…), lectures du gateway | `init/postgres-main-init.sql`, `shared/config.py` |
| `postgres-integration` (banking_integration :5435) | Aire d'écriture d'essai du workbench (tests) | `init/*`, `workbench/integration_app.py` |
| `postgres-audit` (audit_logs :5433) | `audit_log` **immutable** write-once | `init/postgres-audit-init.sql` |
| `postgres-embeddings` (pgvector :5434) | `schema_embeddings`, `domain_categories`, `semantic_id_mappings` (384d, index IVFFlat) | `init/postgres-embeddings-init.sql` |
| Redis | Cache / file d'attente | `shared/config.py`, `shared/redis_client.py` **[à vérifier : usage exact]** |
| `EvidenceStorage` | Stockage local de preuves (10 MB, MIME allowlist) | `workbench/storage.py`, `EVIDENCE_STORAGE_ROOT` |

---

## 7. Sécurité & audit (transverse)

| Mécanisme | Preuve |
|---|---|
| OIDC Keycloak (realm `banking-intelligence`, rôles : banking_analyst, executive_manager, risk_officer, compliance_officer, internal_auditor ; protection force brute ; token 600 s) | `keycloak/realm-banking-dev.json` |
| RBAC + scope org + ownership (policy engine partagé) | `shared/authorise.py` |
| Journal d'audit immuable (écriture unique) | `init/postgres-audit-init.sql` |
| RBAC ligne/colonne + masquage PII à l'exécution SQL | `execution_agent/access_controller.py` |

---

## 8. Table de validation (preuve → affirmation)

| # | Affirmation | Preuve | Statut |
|---|---|---|---|
| 1 | Frontend React + TS + Vite | `frontend/package.json` | ✅ confirmé |
| 2 | Auth OIDC keycloak-js PKCE | `frontend/src/auth/keycloak.ts` | ✅ confirmé |
| 3 | nginx SPA + proxy `/api` → gateway | `frontend/nginx.conf` | ✅ confirmé |
| 4 | API Gateway : JWT + rate-limit + audit + CORS | `api_gateway/main.py` | ✅ confirmé |
| 5 | RBAC + scope + ownership | `shared/authorise.py` | ✅ confirmé |
| 6 | Customer 360 (gateway) lecture seule, sections par permission | `api_gateway/routes.py:2863`, `customer360/service.py` | ✅ confirmé |
| 7 | Workbench service opérationnel séparé | `workbench/main.py`, `integration_app.py`, `storage.py` | ✅ confirmé |
| 8 | Pipeline agents Intent→…→Audit | `orchestrator/orchestrator_agent.py:1` | ✅ confirmé |
| 9 | Orchestrateur + Insights utilisent Mistral local | `orchestrator_agent.py:17`, `insights_agent/mistral_integrator` | ✅ confirmé |
| 10 | SQL déterministe paramétré (pas d'LLM) | `sql_agent/main.py:137`, `sql_builder.py` | ✅ confirmé |
| 11 | Exécution lecture seule + RBAC ligne/colonne | `execution_agent/access_controller.py` | ✅ confirmé |
| 12 | Compliance déterministe GDPR/PCI/SOX/AML/KYC | `compliance_agent/compliance_checker.py` | ✅ confirmé |
| 13 | 4 bases + Redis : main, integration, audit, embeddings(pgvector) | `shared/config.py`, `init/*-init.sql` | ✅ confirmé |
| 14 | Audit immuable | `init/postgres-audit-init.sql` | ✅ confirmé |
| 15 | Keycloak realm + rôles | `keycloak/realm-banking-dev.json` | ✅ confirmé |
| 16 | Usage Redis exact (cache vs file) | `shared/redis_client.py` | ⚠️ à vérifier |
| 17 | Migrations Alembic présentes | `alembic.ini`, `migrations/` | ⚠️ à vérifier |
| 18 | .env secrets/services | `.env`, `.env.example` | ⚠️ à lire (pas de secrets dans ce doc) |

> Note : les éléments ⚠️ à vérifier ne bloquent pas la conclusion ci-dessus ; ils sont marqués pour éviter toute affirmation non vérifiée.
