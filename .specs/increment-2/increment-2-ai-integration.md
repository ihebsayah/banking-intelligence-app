# Increment 2 — AI Integration Architecture

## Principle
The existing AI agent pipeline runs **unchanged**. Inc 2 uses it via API, not by modifying agent internals. Agents stay focused on NL→SQL→Insights; operational workflow agents are added as new thin services.

## What Stays the Same
- `orchestrator` agent pipeline (intent→schema→entity→SQL→validation→execution→insights)
- All 8 existing agents — no refactoring
- AI Assistant chat interface — unchanged
- Audit logging — unchanged

## What Gets Added

### 1. Alert Engine (new `alert_engine` service, port 8020)
Not an AI agent — a rule-based trigger engine that:
- Polls KPI thresholds and risk flags on schedule
- Evaluates rules against new data
- Creates `Alert` records when conditions match
- Optionally calls compliance_agent for severity scoring

```
[alert_engine] Polls threshold/violation tables
    → Evaluates conditions
    → Creates Alert record
    → Optionally calls compliance_agent for LLM severity assessment
    → Triggers Notification
```

### 2. AI Suggestion Layer (thin extension to `insights_agent`)
When an investigation is being conducted, the insight agent can:
- Accept investigation context (findings, related data)
- Return suggested next steps, patterns, or risk indicators
- Called on-demand from the Analyst workbench, not auto-triggered

```
[Analyst] Requests AI suggestions from investigation page
    → POST /api/v1/ai/investigation-suggestions
    → sends investigation context + findings
    → insights_agent returns suggestions
```

### 3. Compliance Document Parser (extension to `compliance_agent`)
For evidence uploads:
- Accept document text (extracted by frontend)
- Classify document type
- Flag relevant regulatory frameworks
- Returns structured metadata for Evidence record

```
[User] Uploads evidence document
    → Frontend sends text to /api/v1/ai/classify-evidence
    → compliance_agent returns type, frameworks, summary
```

### 4. Watchlist Matching (lightweight service or util)
Rule-based fuzzy matching on watchlist items against customer/account data:
- Not AI — uses existing DB `similarity()` or pg_trgm
- Called during case review, not real-time
- Returns potential matches ranked by score

## Integration Points

| Existing Agent | Inc 2 Integration | Change Required |
|---------------|-------------------|-----------------|
| `orchestrator` | Analyst uses AI Assistant during investigation | None |
| `insights_agent` | New endpoint for investigation suggestions | Add 1 route |
| `compliance_agent` | Evidence classification | Add 1 route |
| `audit_agent` | All operational actions logged to audit_logs | Add entity_type/entity_id to log schema |
| `intent_agent` | Not needed — Inc 2 actions are explicit UI clicks | None |

## New API Routes (in api_gateway)

```
POST /api/v1/ai/investigation-suggestions
  Body: { investigation_id, context_summary, findings }
  Response: { suggestions: [{ type, description, confidence }] }

POST /api/v1/ai/classify-evidence
  Body: { text, filename }
  Response: { document_type, regulatory_frameworks, summary, confidence }
```

## No-Go Decisions
- **No new AI agents** for Inc 2 — operational workflows are deterministic state machines, not AI problems
- **No ML model training** — rule-based alert engine is sufficient
- **No real-time AI monitoring** — user-initiated AI calls only
- **No AI auto-assignment** — task assignment is role-based, not ML

## ponytail: Investigation suggestions use simple keyword/template matching initially, not LLM per request. Upgrade to LLM when users actually ask for "smarter suggestions."
