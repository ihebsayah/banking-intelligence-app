# Architecture Diagrams

**Date:** 2026-07-26
**Purpose:** Visual architecture documentation using Mermaid diagrams.
**Note:** Render these with any Mermaid-compatible viewer (GitHub, VS Code, mermaid.live).

---

## 1. High-Level System Architecture

```mermaid
graph TB
    Client[Client Application]

    subgraph "API Layer"
        GW[API Gateway<br/>:8000<br/>JWT Auth + Rate Limit]
    end

    subgraph "Pipeline Orchestration"
        ORCH[Orchestrator<br/>:8001]
    end

    subgraph "NL Understanding"
        INTENT[Intent Agent<br/>:8002<br/>spaCy NLP]
        SCHEMA[Schema Agent<br/>:8003<br/>Domain Mapping]
        ENTITY[Entity Resolution<br/>:8004<br/>Join Construction]
    end

    subgraph "SQL Pipeline"
        SQL[SQL Agent<br/>:8005<br/>Template Generation]
        VALID[Validation Agent<br/>:8006<br/>5-Check + HMAC]
        COMPLY[Compliance Agent<br/>:8011<br/>GDPR/PCI/SOX]
    end

    subgraph "Execution"
        EXEC[Execution Agent<br/>:8007<br/>Query + PII Mask + RBAC]
    end

    subgraph "Post-Processing"
        INSIGHTS[Insights Agent<br/>:8013<br/>Stats + NL Summary]
        AUDIT[Audit Agent<br/>:8008<br/>WORM Log]
    end

    subgraph "Supporting Services"
        EMBED[Embedding Service<br/>:8009<br/>pgvector]
        SECRETS[Secrets Manager<br/>:8010<br/>STUB]
        AUDIT_ENH[Audit Enhancement<br/>:8012<br/>Analytics]
    end

    subgraph "Data Stores"
        PG[(PostgreSQL<br/>banking_dev<br/>:5432)]
        AUDIT_DB[(PostgreSQL<br/>audit_logs<br/>:5433)]
        EMB_DB[(PostgreSQL<br/>embeddings<br/>:5434)]
        REDIS[(Redis<br/>:6379)]
    end

    subgraph "External"
        OLLAMA[Ollama<br/>mistral + tinyllama]
    end

    Client --> GW
    GW --> ORCH
    ORCH --> INTENT --> SCHEMA --> ENTITY --> SQL --> VALID --> COMPLY --> EXEC
    EXEC --> INSIGHTS
    INSIGHTS --> AUDIT
    EXEC --> PG
    AUDIT --> AUDIT_DB
    EMBED --> EMB_DB
    INSIGHTS --> OLLAMA
    SCHEMA --> REDIS
    ENTITY --> REDIS
    EXEC --> REDIS
    INSIGHTS --> REDIS
    EMBED --> PG
```

---

## 2. Request Pipeline (8-Step Sequential Flow)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant GW as API Gateway<br/>:8000
    participant O as Orchestrator<br/>:8001
    participant I as Intent Agent<br/>:8002
    participant S as Schema Agent<br/>:8003
    participant E as Entity Resolution<br/>:8004
    participant Q as SQL Agent<br/>:8005
    participant V as Validation Agent<br/>:8006
    participant CP as Compliance Agent<br/>:8011
    participant X as Execution Agent<br/>:8007
    participant N as Insights Agent<br/>:8013
    participant A as Audit Agent<br/>:8008

    C->>GW: POST /query (JWT + NL query)
    GW->>GW: JWT verify + RBAC extraction
    GW->>O: Forward request

    rect rgb(240, 248, 255)
        Note over O,A: Core Pipeline (8 sequential steps)
        O->>I: Step 1: Classify intent
        I-->>O: {category, confidence, structured_intent}
        Note right of I: Gate: supported_capability?<br/>risk_level?<br/>requires_clarification?

        O->>S: Step 2: Map to schema
        S-->>O: {tables, columns, joins}

        O->>E: Step 3: Resolve entities
        E-->>O: {join_structure, keys}

        O->>Q: Step 4: Generate SQL
        Q-->>O: {sql, parameters}

        O->>V: Step 5: Validate + HMAC sign
        V-->>O: {signed_query, checks_passed}
        Note right of V: Gate: all 5 checks pass?

        O->>CP: Step 6: Compliance check
        CP-->>O: {compliant: true/false}
        Note right of CP: Gate: compliant?

        O->>X: Step 7: Execute query
        X->>X: Verify HMAC → Cache check → Execute
        X->>X: RBAC filter → PII mask → Format
        X-->>O: {data, metadata}

        O->>N: Step 8: Generate insights
        N-->>O: {statistics, trends, summary}

        O->>A: Fire-and-forget audit log
    end

    O-->>C: JSON response
```

---

## 3. Security Defense Layers

```mermaid
graph LR
    subgraph "Layer 1: Authentication"
        JWT[JWT Token<br/>HS256]
    end

    subgraph "Layer 2: Intent Gate"
        ADVERSARIAL{Adversarial?<br/>Unsupported?<br/>Ambiguous?}
    end

    subgraph "Layer 3: SQL Validation"
        CHECK1[Syntax Check]
        CHECK2[SELECT-only]
        CHECK3[Keyword Blacklist]
        CHECK4[LIMIT Enforced]
        CHECK5[Pattern Detection<br/>22 regex]
    end

    subgraph "Layer 4: HMAC Signing"
        HMAC[SHA-256 HMAC<br/>Query Tamper Proof]
    end

    subgraph "Layer 5: RBAC"
        RBAC[Role-based<br/>Row + Column<br/>Filtering]
    end

    subgraph "Layer 6: PII Masking"
        PII[7 Column Types<br/>4 Roles]
    end

    subgraph "Layer 7: Compliance"
        COMPLIANCE[GDPR / PCI-DSS<br/>SOX / AML / KYC]
    end

    JWT --> ADVERSARIAL
    ADVERSARIAL -->|pass| CHECK1
    CHECK1 --> CHECK2 --> CHECK3 --> CHECK4 --> CHECK5
    CHECK5 -->|pass| HMAC
    HMAC --> RBAC --> PII --> COMPLIANCE

    style ADVERSARIAL fill:#ff6b6b,color:#fff
    style CHECK5 fill:#ffa500,color:#fff
    style HMAC fill:#4ecdc4,color:#fff
    style RBAC fill:#45b7d1,color:#fff
    style PII fill:#96ceb4,color:#fff
    style COMPLIANCE fill:#a8e6cf,color:#000
```

---

## 4. Intent Pipeline (Dual-Signal Merge)

```mermaid
graph TD
    NL[Natural Language Query]

    subgraph "Signal 1: Keyword Recognizer"
        SPACY[spaCy Tokenize + Lemmatize]
        KEYWORDS[8 Banking Keyword Categories]
        DENSITY[Confidence = Token Match Density]
        RC1[requires_clarification =<br/>confidence < 0.85 OR<br/>ambiguities > 0]
    end

    subgraph "Signal 2: Structured Intent"
        RULES[Rule-based Domain Detection]
        TASK[Task Extraction<br/>aggregation/comparison/listing]
        METRICS[Metric Detection]
        FILTERS[Filter Extraction]
        TIME[Time Range Extraction]
        RC2[requires_clarification =<br/>ambiguities > 0 AND<br/>NOT has_explicit_intent]
    end

    subgraph "Merge Logic"
        MERGE[OR-merge for booleans<br/>Structured overrides Keyword]
        OVERRIDE[known issue:<br/>requires_clarification<br/>always overridden to False]
    end

    NL --> SPACY --> KEYWORDS --> DENSITY --> RC1
    NL --> RULES --> TASK --> METRICS --> FILTERS --> TIME --> RC2
    RC1 --> MERGE
    RC2 --> MERGE
    MERGE --> OVERRIDE

    style OVERRIDE fill:#ff6b6b,color:#fff
```

---

## 5. Database Architecture

```mermaid
erDiagram
    CUSTOMERS ||--o{ ACCOUNTS : has
    ACCOUNTS ||--o{ TRANSACTIONS : contains
    ACCOUNTS ||--o{ LOANS : has
    CUSTOMERS ||--o{ KYC_STATUS : verified_by
    CUSTOMERS ||--o{ BENEFICIARIES : has
    CUSTOMERS ||--o{ CARDS : owns

    BRANCHES ||--o{ EMPLOYEES : employs
    BRANCHES ||--o{ BRANCH_LOCATIONS : located_at
    BRANCHES ||--o{ ACCOUNTS : services

    PRODUCTS ||--o{ ACCOUNTS : offered_as
    PRODUCTS ||--o{ CARDS : offered_as

    TRANSACTIONS ||--o{ TRANSACTION_DETAILS : has

    CUSTOMERS ||--o{ RISK_FLAGS : flagged
    CUSTOMERS ||--o{ AML_FLAGS : monitored
    CUSTOMERS ||--o{ FRAUD_DETECTION : watched
    CUSTOMERS ||--o{ CREDIT_RISK_SCORES : scored
    CUSTOMERS ||--o{ COMPLIANCE_VIOLATIONS : violated

    ACCOUNTS ||--o{ FEES : charged
    ACCOUNTS ||--o{ COMMISSIONS : earns
    ACCOUNTS ||--o{ INTEREST_INCOME : generates

    REGIONS ||--o{ BRANCHES : contains

    CUSTOMERS {
        uuid id PK
        varchar name
        varchar email
        varchar phone
        varchar address
        date created_at
    }

    ACCOUNTS {
        uuid id PK
        uuid customer_id FK
        uuid branch_id FK
        uuid product_id FK
        varchar account_type
        decimal balance
        varchar status
    }

    TRANSACTIONS {
        uuid id PK
        uuid account_id FK
        decimal amount
        varchar type
        timestamp transaction_date
    }

    RISK_FLAGS {
        uuid id PK
        uuid customer_id FK
        varchar flag_type
        varchar severity
        timestamp flagged_at
    }

    SEMANTIC_LAYER {
        business_glossary synonym_to_canonical
        metric_registry kpi_definitions
        table_metadata table_descriptions
        column_metadata column_descriptions
        join_registry valid_join_paths
    }
```

---

## 6. Service Communication Map

```mermaid
graph TD
    GW[API Gateway<br/>:8000] -->|HTTP| ORCH[Orchestrator<br/>:8001]

    ORCH -->|HTTP| INTENT[Intent Agent<br/>:8002]
    ORCH -->|HTTP| SCHEMA[Schema Agent<br/>:8003]
    ORCH -->|HTTP| ENTITY[Entity Resolution<br/>:8004]
    ORCH -->|HTTP| SQL[SQL Agent<br/>:8005]
    ORCH -->|HTTP| VALID[Validation Agent<br/>:8006]
    ORCH -->|HTTP| EXEC[Execution Agent<br/>:8007]
    ORCH -->|HTTP| AUDIT[Audit Agent<br/>:8008]
    ORCH -->|HTTP| COMPLY[Compliance Agent<br/>:8011]
    ORCH -->|HTTP| INSIGHTS[Insights Agent<br/>:8013]

    SCHEMA -->|Redis| REDIS[(Redis<br/>:6379)]
    ENTITY -->|Redis| REDIS
    EXEC -->|Redis| REDIS
    INSIGHTS -->|Redis| REDIS

    EXEC -->|asyncpg| PG[(PostgreSQL<br/>banking_dev<br/>:5432)]
    AUDIT -->|asyncpg| ADB[(PostgreSQL<br/>audit_logs<br/>:5433)]
    EMBED[Embedding Service<br/>:8009] -->|asyncpg| EDB[(PostgreSQL<br/>embeddings<br/>:5434)]

    INSIGHTS -->|HTTP| OLLAMA[Ollama<br/>mistral + tinyllama]

    INTENT -->|pgvector| EDB
    SCHEMA -->|pgvector| EDB

    subgraph "All services read from"
        CONFIG[config.py<br/>Settings singleton]
    end
```

---

## 7. Deployment Architecture

```mermaid
graph TB
    subgraph "Docker Host"
        subgraph "Application Containers"
            GW[api-gateway<br/>:8000]
            ORCH[orchestrator<br/>:8001]
            INTENT[intent-agent<br/>:8002]
            SCHEMA[schema-agent<br/>:8003]
            ENTITY[entity-resolution<br/>:8004]
            SQL[sql-agent<br/>:8005]
            VALID[validation-agent<br/>:8006]
            EXEC[execution-agent<br/>:8007]
            AUDIT[audit-agent<br/>:8008]
            EMBED[embedding-service<br/>:8009]
            COMPLY[compliance-agent<br/>:8011]
            AUDIT_ENH[audit-enhancement<br/>:8012]
            INSIGHTS[insights-agent<br/>:8013]
        end

        subgraph "Data Containers"
            PG[(postgres:16<br/>banking_dev<br/>:5432)]
            ADB[(postgres:16<br/>audit_logs<br/>:5433)]
            EDB[(postgres:16<br/>pgvector<br/>:5434)]
            REDIS[(redis:7<br/>:6379)]
        end

        subgraph "External"
            OLLAMA[(ollama<br/>mistral + tinyllama<br/>:11434)]
        end
    end

    subgraph "Health Checks"
        HC[All services: HTTP /health<br/>Docker HEALTHCHECK every 30s<br/>Timeout: 10s<br/>Retries: 3]
    end
```

---

## 8. Data Flow for a Single Query

```mermaid
flowchart TD
    START([User asks: "Show me top 10 customers by balance"]) --> GW[API Gateway<br/>JWT verify]
    GW --> ORCH[Orchestrator<br/>initialize pipeline]
    ORCH --> INTENT[Intent Agent<br/>classify: customer_analysis<br/>task: ranking<br/>metric: balance<br/>limit: 10]
    INTENT --> GATE{Gate Check}

    GATE -->|supported + no risk| SCHEMA[Schema Agent<br/>tables: customers, accounts<br/>domain: customers]
    GATE -->|unsupported| REJECT1[REJECT: unsupported]

    SCHEMA --> ENTITY[Entity Resolution<br/>join: customers.id = accounts.customer_id<br/>keys: customer_id]
    ENTITY --> SQL[SQL Agent<br/>SELECT c.name, SUM(a.balance)<br/>FROM customers c<br/>JOIN accounts a ON c.id = a.customer_id<br/>GROUP BY c.name<br/>ORDER BY SUM(a.balance) DESC<br/>LIMIT $1<br/>PARAMS: [10]]

    SQL --> VALID[Validation Agent<br/>✓ syntax OK<br/>✓ SELECT-only<br/>✓ no dangerous keywords<br/>✓ LIMIT present<br/>✓ no injection patterns<br/>HMAC signed]

    VALID --> COMPLY[Compliance Agent<br/>✓ GDPR: no PII in SELECT<br/>✓ PCI: no card data<br/>✓ SOX: audit trail OK]
    COMPLY --> EXEC[Execution Agent<br/>verify HMAC ✓<br/>cache miss<br/>execute query<br/>RBAC filter<br/>PII mask<br/>format JSON]

    EXEC --> INSIGHTS[Insights Agent<br/>statistics: count, avg, min, max<br/>context: above/below average<br/>trend: N/A (single period)<br/>summary: template]

    INSIGHTS --> AUDIT[Audit Agent<br/>fire-and-forget log]
    AUDIT --> RESPONSE([Response:<br/>{data: [...], insights: {...},<br/>metadata: {pipeline_steps: [...],<br/>confidence: 0.85}}])

    style REJECT1 fill:#ff6b6b,color:#fff
    style GATE fill:#ffa500,color:#fff
```

---

## 9. AI Reasoning Maturity Map

```mermaid
graph TD
    subgraph "DETERMINISTIC (No AI)"
        style DETERM fill:#90EE90
        A1[Schema Agent<br/>static dict mapping]
        A2[Entity Resolution<br/>static join keys]
        A3[SQL Agent<br/>template + parameterization]
        A4[Validation Agent<br/>regex + sqlparse]
        A5[Execution Agent<br/>query execution]
        A6[Access Controller<br/>role-based filtering]
        A7[PII Masking<br/>regex patterns]
        A8[Compliance Agent<br/>rule-based checks]
    end

    subgraph "ML (Not LLM)"
        style ML fill:#87CEEB
        B1[Intent Agent<br/>spaCy NLP<br/>keyword scoring<br/>heuristic confidence]
    end

    subgraph "LLM (Template Fallback)"
        style LLM fill:#FFB6C1
        C1[Insights Agent<br/>Ollama tinyllama<br/>for NL summaries]
    end

    subgraph "DEAD CODE"
        style DEAD fill:#ff6b6b,color:#fff
        D1[Confidence Gate<br/>requires_clarification<br/>always overridden to False]
    end

    D1 -.->|unreachable| B1
```
