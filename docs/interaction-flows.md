# Flux d'interaction — Banking Intelligence System

Trois flux représentatifs retenus pour la soutenance, traçables vers le code.

---

## Flux 1 — Question en langage naturel → SQL sécurisé → résultat (Assistant)

Ce flux illustre la frontière critique : **le LLM orchestre mais ne touche jamais la
base** ; le SQL est produit par un compilateur déterministe et exécuté en lecture seule.

```
[Utilisateur]  "Quel est le solde moyen par succursale ?"
      │  (Keycloak OIDC → JWT)
      ▼
[Frontend Assistant]  axios + Bearer token
      │  POST /api/…  (nginx → api-gateway:8000)
      ▼
[API Gateway]  validate JWT · rate-limit · journal d'audit
      ▼
[Orchestrateur (Mistral local)]   planifie la pipeline
      │  1. Intent Agent        → catégorie "aggregate", risque OK, gate passé
      │  2. Schema Agent        → tables/colonnes sémantiques (pgvector)
      │  3. Entity Resolution   → entités → colonnes réelles
      │  4. SQL Agent (déterministe) → SQL paramétré + LIMIT
      │  5. Validation Agent    → 5 vérifs anti-injection + signature HMAC
      │  6. Compliance Agent    → GDPR/PCI/SOX/AML/KYC (scope de données)
      ▼
[Execution Agent]   accès base en LECTURE SEULE
      │  access_controller : filtres lignes + colonnes visibles + masquage PII (rôle)
      │  query_executor : exécution bornée
      ▼
[Audit Agent]  journal immuable (audit_log)
      ▼
[Résultat]  tableau → Insights Agent (Mistral) résumé NL → frontend (WebSocket)
```

**Points de démonstration :**
- Aucune requête utilisateur n'atteint la base en texte brut : le SQL est **généré par
  code** (`sql_agent/sql_builder.py`), **vérifié** (`validation_agent/query_validator.py`),
  et **exécuté en lecture seule** avec RBAC ligne/colonne (`execution_agent/access_controller.py`).
- L'**orchestrateur** (LLM) ne reçoit que le plan structuré ; les résultats sont résumés
  par l'**Insights Agent** (LLM) sans accès direct.
- Preuves : `services/orchestrator/orchestrator_agent.py:1`, `services/sql_agent/main.py:137`,
  `services/execution_agent/access_controller.py:1`, `services/validation_agent/query_validator.py:1`.

---

## Flux 2 — Vue 360 Client (Customer 360)

Agrégat **lecture seule**, permissionné par sections, avec scope organisationnel.

```
[Utilisateur (risk_officer)]  GET /api/v1/customers/{id}/overview
      ▼
[API Gateway]  require_any_permission_audited(*customer:read_*)
      │         (« customer:read_risk », etc. — pas assez → 403/404)
      ▼
[Customer360Service]
      │  - scope org (branch/région)  → client hors scope → 404
      │  - gating par section (SECTION_PERMISSIONS) → sections non lues omises
      │  - masquage PII
      ▼
[Repos lecture seule]  banking_dev (autoritaire) + banking_integration (liens workbench)
      │  requêtes paramétrées, lectures bornées
      ▼
[Audit]  journal : endpoint, succès/échec/refus, request_id
      ▼
[Frontend Customer360]  overview + transactions + recherche clients (search)
```

**Points de démonstration :**
- La sécurité s'applique à l'**objet** (scope org) ET à la **section** (permissions fines),
  encodée dans `services/api_gateway/customer360/service.py` et `SECTION_PERMISSIONS`.
- Chaque accès est audité (`_customer_audit_entry`, `routes.py:2888`).
- Preuves : `services/api_gateway/routes.py:2863`, `:2919`, `:2987`, `services/api_gateway/customer360/service.py`.

---

## Flux 3 — Cas de conformité / enquête (Workbench)

Le workbench (service opérationnel séparé :8014) gère alertes, enquêtes, cas,
approbations, demandes d'information (IR), commentaires, notifications, outbox.

```
[Utilisateur]  Action opérationnelle (ex. créer/enquêter un cas de conformité)
      ▼
[Frontend (Alertes/Cases/Enquêtes/IR)]   modules UI dédiés
      │  POST /api/…  → nginx
      ▼
[API Gateway]  auth + proxy catch-all → workbench (injecte X-Test-User)
      │           routes.py:3040
      ▼
[Workbench (:8014)]
      │  repositories UoW (alerts, cases, investigations, approvals,
      │    information_requests, comments, notifications, timeline, outbox, directives)
      │  integration_app  (écriture d'essai interdite sur :5432 — refuse)
      │  EvidenceStorage  (preuves : 10 MB max, MIME allowlist)
      │  workers d'arrière-plan : expiration + outbox
      ▼
[Bases]  banking_integration (aire d'essai) · stockage preuves
      ▼
[Audit]  journal immuable · notifications (WebSocket)
```

**Points de démonstration :**
- Le **workbench** est bien un service à part entière (conteneur :8014), pas un
  microservice par module : on parle de « modules » du workbench, pas de microservices.
- La **séparation des environnements** : les écritures d'essai vont sur
  `banking_integration` et sont **refusées** si l'URL pointe vers :5432 en
  prod (`workbench/integration_app.py`).
- Preuves : `services/workbench/main.py`, `repos.py`, `storage.py`, `integration_app.py`.

---

## Récapitulatif des preuves transverses

| Élément transverse | Preuve |
|---|---|
| RBAC + scope + ownership | `services/shared/authorise.py` |
| Audit immuable | `init/postgres-audit-init.sql` |
| Keycloak realm + rôles | `keycloak/realm-banking-dev.json` |
| 4 bases + Redis + pgvector | `services/shared/config.py`, `init/*-init.sql` |
