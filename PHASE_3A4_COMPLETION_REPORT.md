# Phase 3A.4 — Customer Context Embedded into the Operational Workbench — Completion Report

Status: **COMPLETE.** Frontend **261/261 tests pass** (27 files), `tsc --noEmit` clean, eslint clean for all new/changed files; backend Customer 360 suite **20/20 pass** (untouched). Phase 3A.4 embedded authorized, read-only Customer 360 context into the analyst's operational workbench (Alert → Investigation → Case detail pages) with no new backend surface.

---

## 1. Task Definition & Scope

Phase 3A.3 delivered the standalone Customer 360 page (`/workbench/customers/:customerId`) and the Workbench route split. Phase 3A.4 closes the loop for the analyst's operational flow: while working an alert / investigation / case, the analyst sees the customer's authorized context inline, without leaving the workbench.

Delivered:

1. A shared, read-only `CustomerContextPanel` consumed by the three workbench detail pages.
2. Shared pure formatters (`customer360Format.ts`) reused by both the Customer 360 page and the panel (no duplicated formatting logic).
3. Embedded context in `AlertDetailPage` (alert's own `related_entity_*`), `InvestigationDetailPage` (linked alert → customer), and `CaseDetailPage` (alert, or investigation → alert → customer).
4. Safe degradation for forbidden / not-found / unavailable / network / malformed outcomes — the panel never fabricates data.
5. Focused tests for the panel and each embedding path; full frontend + backend regression.

Out of scope (unchanged): backend, authorization model, workflow/mutations, linkage remediation (3A.5), IR/approval rendering.

## 2. Authoritative Documents Followed

- `PHASE_3A_CUSTOMER_360_DISCOVERY_REPORT.md`, `PHASE_3A2_COMPLETION_REPORT.md`, `PHASE_3A2A_COMPLETION_REPORT.md` — Customer 360 read bridge design + frozen access matrix
- `init/11-phase3a2-customer-permission-seeds.sql` — permission matrix the panel inherits server-side
- `services/api_gateway/customer360/{service,repos,models}.py` + `services/api_gateway/routes.py` — the server-side enforcer (unchanged)

## 3. Design Decision

**Frontend-only slice; the gateway stays the single authorization enforcer.**

- The panel calls the existing, server-authorized `GET /api/v1/customers/{id}/overview` via `customer360Api.getOverview`. No new endpoint, no duplicate Customer 360, no direct DB access, no LLM/external changes.
- Authorization, org-scope (404 out-of-scope), section gating, PII masking, and audit all remain unchanged server-side. The client renders only what the response grants and cannot elevate.
- Resolution reads are themselves server-gated: the investigation page reads the linked alert via `alertsApi.get` (an `alert:read_assigned`-gated read), the case page reads `casesApi.get` then `alertsApi.get` (or `investigationsApi.get` → `alertsApi.get`). Any denial / failure yields an absent panel — no leak, no crash.
- The Customer 360 page remains the only detailed viewer; the panel is presentation-only.

## 4. Implementation

### 4.1 `frontend/src/components/customers/customer360Format.ts` (new)

Pure formatters extracted from `Customer360Page.tsx` and shared with the panel: `money`, `isMasked`, `dateOnly`, `severityVariant`, `statusVariant`, `riskClassification`. The page now imports these (mechanical refactor, no behavior change — its 18 tests still pass).

### 4.2 `frontend/src/components/customers/CustomerContextPanel.tsx` (new)

Props: `{ customerId: string }`. Fetches the overview on mount; renders:

- **Granted identity** — name (fallback: `customer_id`), mono id, customer_type/segment badges, `Masked` badge when the delivered identity contains masked tokens.
- **Assessment chips** (non-admin) — Risk class (from `admin_metadata.risk_classification` or `riskClassification(risk.risk_score)`), KYC status, PEP status, sanctions status, active-flag count. Only rendered when the corresponding section is present.
- **KPI strip** — accounts, deposits (`total_balance_by_currency`), loans outstanding (`total_outstanding_loans_by_currency`), 30d transactions (`transaction_summary.d30_total_count`).
- **Metadata-only (admin) view** — `admin_metadata` counts + risk classification only; monetary/KYC/PEP content structurally absent.
- **Relationship line** — primary branch · region · RM names.
- **Generated timestamp** and an **Open Customer 360** link.

Outcomes: loading skeleton; error states per `Customer360ApiError.kind` (`forbidden` / `not_found` / `unavailable` / `network` / `malformed` / `unknown`) with retry only where meaningful; masked tokens are never unmasked client-side.

### 4.3 Embedding

- `AlertDetailPage.tsx` — when `related_entity_type === 'customer' && related_entity_id` (non-admin view), the panel renders under the "Related" box.
- `InvestigationDetailPage.tsx` — a resolver effect fetches the linked alert (`investigation.alert_id`); if its related entity is a customer, the panel renders in the overview tab.
- `CaseDetailPage.tsx` — a resolver effect prefers `case.alert_id`; falls back to `case.investigation_id` → `investigationsApi.get` → its `alert_id` → alert. If the resolved alert relates to a customer, the panel renders in the overview tab.

Absent customer references (the known G1 phantom-link population) and denied reads resolve to no panel.

## 5. Authorization / Privacy Behavior

- No new endpoint → no new attack surface; the gateway remains the single gate (permission + org scope + PII masking + audit).
- Panel renders exactly the granted sections; masked tokens stay masked; no client-side elevation; compliance history stays hidden from analysts (server denies `customer:read_compliance_history` regardless of the panel).
- Workbench resolution reads are permission-gated; denial → panel absent (no leak).
- Panel is read-only — no new escalate/approve/reopen/submit powers.

## 6. Tests Added/Updated

Frontend (`frontend/src/components/...`):

- New `customers/__tests__/CustomerContextPanel.test.tsx` (7 tests): granted identity/assessment/KPI rendering; masked tokens + `Masked` badge; metadata-only (admin) view without fabricated detail; link to the full page (incl. URL-encoded id); forbidden / not-found / unavailable-with-retry states never rendering customer data.
- `alerts/__tests__/AlertDetailPage.test.tsx` (+1, 1 updated): customer alert renders the panel with both "Open Customer 360" links correct; non-customer related entity shows no panel.
- `investigations/__tests__/InvestigationDetailPage.test.tsx` (+3): linked customer alert → panel; non-customer alert → absent; alert read failure → absent, page unaffected.
- `cases/__tests__/CaseDetailPage.test.tsx` (+4): direct alert → panel; investigation-only resolution → panel; non-customer alert → absent; no alert/investigation → absent with no resolution fetches.
- `customers/__tests__/Customer360Page.test.tsx` (1 updated): alert→Customer 360 navigation now expects both links.

Result: **261 passed** (27 files), up from **246**.

Regression: backend Customer 360 suite **20 passed** (`PYTHONPATH=services/api_gateway:services ./testenv/bin/python3 -m pytest services/api_gateway/customer360/tests -q`). `tsc --noEmit` clean; eslint reports no issues in any new/changed file (the pre-existing conditional-`useEffect` error in `auth/ProtectedRoute.tsx:68` and 98 pre-existing warnings are untouched).

## 7. Known Gaps + Readiness Verdict

Known gaps (unchanged, out of scope): G1 phantom workbench customer-links (724/727 alerts carry no resolved entity — the panel handles this by rendering nothing), G2–G9 from the discovery report, and 3A.5 (linkage validation) / 3A.6 (gap remediation).

**READY.** The operational workbench now surfaces authorized Customer 360 context inline at the alert → investigation → case levels, reusing the server-enforced read bridge with no backend changes, no duplicated Customer 360 logic, and no data fabrication on denied/unavailable/absent paths. 261 frontend tests + 20 backend tests pass; lint/typecheck clean for the change set.

## Files Reference

- `frontend/src/components/customers/customer360Format.ts` — new shared formatters
- `frontend/src/components/customers/CustomerContextPanel.tsx` — new read-only panel
- `frontend/src/components/alerts/AlertDetailPage.tsx` — panel embed (customer related entity)
- `frontend/src/components/investigations/InvestigationDetailPage.tsx` — linked-alert resolver + panel embed
- `frontend/src/components/cases/CaseDetailPage.tsx` — alert / investigation→alert resolver + panel embed
- `frontend/src/components/customers/Customer360Page.tsx` — imports shared formatters (no behavior change)
- Test files: `CustomerContextPanel.test.tsx` (new), `AlertDetailPage.test.tsx`, `InvestigationDetailPage.test.tsx`, `CaseDetailPage.test.tsx`, `Customer360Page.test.tsx` (updated)
