# Diapositive de soutenance — « Architecture technique de la solution »

## Contraintes respectées
- **≤ 5 couches horizontales** + **1 élément transverse** (sécurité & audit).
- Couches imposées présentes : Frontend · API Gateway/IAM · Services métier ·
  Moteur multi-agents · Données & stockage.
- **3–4 couleurs max**.
- Script oral en français de 45–60 s.
- Message clé : **les données bancaires restent locales ; l'LLM n'a AUCUN accès
  direct à la base** (SQL déterministe + exécution en lecture seule).

---

## Disposition de la diapositive (16:9)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  Architecture technique de la solution                         [titre]     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐   Frontend — React · Keycloak OIDC · nginx (SPA+proxy)   │
│  │  FRONTEND    │──────────────────────────────────────────────┐           │
│  └──────────────┘  (JWT)                                        │           │
│  ┌──────────────┐                                               │           │
│  │ API GATEWAY/ │  FastAPI · JWT · RBAC · rate-limit · audit    │           │
│  │     IAM      │──────────────────────────────┐                │           │
│  └──────────────┘                              │                │           │
│  ┌──────────────┐   Services métier            ▼  ops           │           │
│  │   SERVICES   │  Workbench · Customer 360    │                │           │
│  │   MÉTIER     │──────────────────────────────┼──────────────┘             │
│  └──────────────┘                              ▼  requêtes                   │
│  ┌──────────────┐   Moteur IA multi-agents     │                             │
│  │ MOTEUR IA    │  Orchestrateur (LLM local) → intent → schema → entity →   │
│  │ MULTI-AGENTS │  SQL (déterministe) → validation → compliance → exécution │
│  └──────────────┘  → insights → audit         │                             │
│  ┌──────────────┐                              ▼                             │
│  │ DONNÉES &    │  Postgres main · integration · audit · embeddings(pgvector)│
│  │  STOCKAGE    │  · Redis · preuves (workbench)                            │
│  └──────────────┘                                                            │
│                                                                              │
│  ════════════ SÉCURITÉ & AUDIT  (transverse : Keycloak IAM · RBAC+scope ·   │
│              journal immuable · exécution lecture seule)  ════════════      │
└────────────────────────────────────────────────────────────────────────────┘

  Note visuelle (à placer à côté du moteur IA) :
  "LLM orchestre — n'ACCÈDE PAS à la base · SQL déterministe · exécution en
   lecture seule avec RBAC ligne/colonne"
```

### Choix de couleurs (3 max)
1. **Bleu nuit / indigo** — couches applicatives (frontend, gateway, services métier).
2. **Orange/ambre** — moteur IA multi-agents (mise en avant de la brique « intelligence »).
3. **Vert émeraude** — données & stockage.
4. Élément transverse (sécurité & audit) : **gris ardoise** ou bordure en pointillés —
   si 4 couleurs est un maximum, garder sécurité en **gris** (compté neutre) ou l'utiliser
   comme variante du bleu.

> Si l'outil autorise 4 : appliquer gris à la bannière transverse. Autrement, mettre la
> bannière en **bleu nuit en pointillés** pour rester à 3 couleurs.

---

## Script oral (45–60 s, français)

> « Cette solution s'articule en cinq couches. En haut, le **frontend React**
> s'authentifie en OIDC via **Keycloak** et converse avec une **API Gateway**
> qui centralise l'authentification, le contrôle d'accès par rôle et par
> périmètre organisationnel, et le journal d'audit. La couche **services métier**
> porte le workbench opérationnel — alertes, enquêtes, cas de conformité — ainsi
> que la vue **360 client**. Le cœur de la solution est un **moteur multi-agents** :
> un orchestrateur s'appuyant sur un modèle de langage local orchestre une chaîne
> intent-schéma-entités, mais le **SQL est généré de façon déterministe**, vérifié
> contre l'injection, contrôlé par la conformité, puis **exécuté en lecture seule**
> avec des droits au niveau ligne et colonne. Enfin, la couche **données** répartit
> les bases principales, d'intégration, d'audit et les embeddings vectoriels.
> Partout, la **sécurité et l'audit sont transverses** : l'essentiel est que le
> modèle de langage ne reçoit jamais d'accès direct à la base — les données
> bancaires restent locales et protégées à chaque étape. »

**Durée estimée** : ~50 s à un rythme soutenu.

---

## Table de validation (dispositif → preuve dans le dépôt)

| Dispositif affiché | Preuve dépôt |
|---|---|
| Frontend React · keycloak-js (OIDC PKCE) · nginx (SPA+proxy) | `frontend/package.json`, `frontend/src/auth/keycloak.ts`, `frontend/nginx.conf` |
| API Gateway : JWT + RBAC + rate-limit + audit | `services/api_gateway/main.py`, `routes.py` |
| Services métier : Workbench + Customer 360 | `services/workbench/main.py`, `services/api_gateway/customer360/service.py` |
| Moteur multi-agents : orchestrateur (Mistral local) | `services/orchestrator/orchestrator_agent.py:17` |
| SQL déterministe + validation + conformité | `services/sql_agent/sql_builder.py`, `validation_agent/query_validator.py`, `compliance_agent/compliance_checker.py` |
| Exécution lecture seule + RBAC ligne/colonne (frontière LLM) | `services/execution_agent/access_controller.py` |
| Données : main · integration · audit · embeddings (pgvector) · Redis | `services/shared/config.py`, `init/*-init.sql` |
| Sécurité transverse : Keycloak realm + rôles · audit immuable | `keycloak/realm-banking-dev.json`, `init/postgres-audit-init.sql` |

---

## Résumé visuel (texte à copier dans le bloc-note de l'outil de présentation)

```
Titre : Architecture technique de la solution
Frontend      | React · Keycloak OIDC · nginx
API Gateway   | JWT · RBAC · scope · audit · rate-limit
Services      | Workbench · Customer 360
Moteur IA     | Orchestrateur + agents · SQL déterministe · exécution lecture seule
Données       | Postgres main/integration/audit · pgvector · Redis · preuves
Transverse    | Sécurité & Audit — LLM sans accès direct à la base
```
