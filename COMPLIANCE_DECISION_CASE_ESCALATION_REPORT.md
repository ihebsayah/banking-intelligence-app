# COMPLIANCE DECISION + CASE ESCALATION — COMPLETION REPORT (Step C5)

**Workstream:** Compliance Operational Workflow Redesign
**Scope:** Finalize the compliance decision layer so the only formal case-creation
path is Investigation → assigned Compliance Officer → Create Case; remove the
legacy direct Alert→Case escalation path; persist structured immutable decision
statements; preserve provenance to Alert / Investigation / immutable report
snapshot.
**Status:** COMPLETE
**Date:** 2026-09-03

---

## 1. Executive Summary

C5 closes the last remaining bypass in the compliance workflow: the legacy
analyst-facing **direct Alert → ComplianceCase** escalation
(`POST /alerts/{id}/escalate`, gated only on `alert:transition` + alert
`under_investigation`). That path is **removed**. From now on the **only**
formal case-creation path is:

> ALERT → Analyst Investigation → Immutable Report (`submitted`) → Assigned
> Compliance Officer → Compliance Review → **Create Compliance Case**
> (`POST /investigations/{id}/review/escalate`), or **Not Harmful** /
> **Request Additional Information**.

The investigation-level compliance decision is now persisted as a **structured,
INSERT-only, immutable** record (a new `investigation_review_decisions` table),
replacing the previous practice of storing the decision as a comment-prefix
(`[Not Harmful]` / `[Escalated to Case]`). Every final decision carries a
mandatory rationale, the deciding officer, and (for escalations) the resulting
case id, and preserves provenance to the Alert, the Investigation, and the
immutable C4 submission snapshot (via `investigation_id` — no new FK on
`compliance_cases`).

---

## 2. Objective

Make **case creation a one-way, officer-gated decision** with a durable,
immutable audit record:

1. The analyst can **never** create a Compliance Case directly from an Alert.
2. Only an **assigned Compliance Officer**, acting on a `submitted`
   investigation whose immutable report snapshot exists, may create a case.
3. The decision itself (NOT_HARMFUL or ESCALATE_TO_CASE) is stored
   **structurally** and is **INSERT-only** (never updated/deleted).
4. Provenance is preserved: case → investigation → alert, with the immutable
   C4 snapshot as the authoritative report reference.

---

## 3. Scope

**In scope**

- Remove legacy `POST /alerts/{id}/escalate` + `alert:transition` analyst grant.
- Persist structured immutable decisions (`investigation_review_decisions`).
- Officer continuity: case `assigned_to` = escalating compliance officer.
- Source Alert finalized to `resolved` at the investigation's final outcome.
- Notify the report analyst of the final outcome.
- Snapshot-gated escalation (`NO_SUBMISSION_SNAPSHOT` when missing).

**Out of scope (explicitly deferred)**

- **Customer360** object scoping (§50 → planned **C6**).
- Workload-based officer availability / reassignment / supervisor queue.
- Report structure redesign.
- New LLM logic.
- Forced migrations of historical cases/alerts (historical truth preserved).

---

## 4. Canonical Rule

> The only formal compliance-case creation path is
> **Investigation (submitted) → assigned Compliance Officer → `review/escalate`**.
> `review/escalate` requires `investigation:review` **and** `case:create`, an
> assigned officer, a `submitted` investigation, and an existing immutable
> report snapshot. An analyst may never create a case directly from an Alert.
> Every review decision (not-harmful or escalation) is an **immutable,
> INSERT-only** record.

---

## 5. Success Criteria

1. Analyst cannot create a case directly from an Alert (`POST /alerts/{id}/escalate`
   returns 404; route removed).
2. Only an assigned Compliance Officer (`investigation:review` + `case:create`)
   can produce a final compliance decision on a `submitted` investigation.
3. Admin cannot final-decision (no seeded `case:create`; `investigation:review`
   is PROHIBITED for admin in `authorise.py`).
4. Escalation requires the C4 immutable report snapshot (else 409
   `NO_SUBMISSION_SNAPSHOT`).
5. No duplicate active case per investigation (409 `DUPLICATE_ESCALATION`);
   escalation is idempotent-safe.
6. Created case `assigned_to` = the escalating compliance officer (no unassigned
   pool).
7. Decision is persisted structurally and **immutably** (INSERT-only table).
8. Source Alert resolves to `resolved` at final outcome (workflow event
   `alert.resolved_from_investigation` + timeline + outbox).
9. Report analyst is notified of the final outcome.
10. Provenance: case → investigation → alert, with immutable snapshot reference.
11. Full backend + frontend regression green.

---

## 6. Canonical State Flow

```
ALERT ──(analyst Start Investigation)──▶ INVESTIGATION active
        ──(analyst submit_to_compliance)──▶ submitted   (C4 immutable snapshot)
                                                 │
                    assigned Compliance Officer ──┤
                                                 ▼
        ┌───────────────┬────────────────────────┴─────────────────┐
        │ Review        │ Review                                   │
        ▼               ▼                                          ▼
  Request Info     Not Harmful                               Create Case
  (IR loop)        ──▶ completed  (decision NOT_HARMFUL)    ──▶ COMPLIANCE CASE
                                                    (decision ESCALATE_TO_CASE)
```

- `submitted` is the **only** state in which compliance may final-decision.
- Escalation and Not-Harmful both require the **assigned** officer.
- After a final outcome, the investigation becomes `completed` and the source
  Alert is finalized to `resolved`.

---

## 7. Attack Surfaces Locked (Direct Case Creation Paths)

Audit confirmed exactly **two** historical case-creation entry points. C5
dispositions:

| # | Surface | Endpoint | C5 disposition |
|---|---------|----------|----------------|
| A1 | Analyst direct alert escalation | `POST /alerts/{id}/escalate` (`alert:transition`, alert `under_investigation`) | **Removed** (route, service method, schema, frontend UI/API, `alert:transition` analyst grant, `ALERT_TRANSITIONS` map entry). Returns 404. |
| A2 | Assigned officer investigation escalation | `POST /investigations/{id}/review/escalate` (`investigation:review` + `case:create`, `submitted`) | Retained — this is the **canonical** path. |

No third path exists (verified by audit of all `compliance_cases` INSERT sites).

---

## 8. Removal of the Legacy Alert→Case Path

Backend removals:

- `AlertService.escalate` method removed (`services/workbench/services/alert_service.py`).
- `POST /alerts/{alert_id}/escalate` route removed (`routers/alerts.py`).
- `EscalateAlertRequest` / `EscalateResponse` schemas removed (`schemas/alerts.py`).
- `alert:transition` removed from the analyst role (migration `0016` + `init/10-phase2b-permission-seeds.sql`) and from
  `ALERT_TRANSITIONS["under_investigation"]` in `services/shared/authorise.py`.
- `alert:transition` **retained** in `ALL_PERMISSION_CODES` so the shared
  authorisation test (`test_authorise_collections.py`) still expects an
  empty-status mutation to raise `WorkflowStateError` (backward compatibility).

Analyst **retains** `alert:read_assigned`, `alert:acknowledge`, `alert:dismiss`,
`alert:investigate` — the Start-Investigation path is untouched.

---

## 9. Structured Immutable Decision Record

New INSERT-only table `investigation_review_decisions` (migration `0016`):

| Column | Type | Purpose |
|--------|------|---------|
| `review_decision_id` | varchar PK | Surrogate id. |
| `investigation_id` | uuid FK (investigations, ON DELETE CASCADE) | Owning investigation. |
| `compliance_officer_id` | varchar FK (users) | Deciding officer. |
| `decision_type` | varchar(32) | `NOT_HARMFUL` or `ESCALATE_TO_CASE`. |
| `rationale` | text | Mandatory decision rationale. |
| `resulting_case_id` | uuid FK (compliance_cases) nullable | Set only for escalation. |
| `decided_at` | timestamptz | Decision moment. |
| `created_at` | timestamptz | Insert time. |

**Design guarantees:** `ReviewDecisionRepo` exposes only `insert` (INSERT-only)
and a read-only `fetch_for_investigation`. There is **no** UPDATE/DELETE path.
Corrections are new audit events, never rewrites.

---

## 10. Rationale Is Now Structural, Not a Comment Prefix

Previously the decision was recorded only as an internal comment whose content
began with `[Not Harmful]` / `[Escalated to Case]`. C5 replaces that with a
typed `decision_type` column plus a mandatory, free-text `rationale`. This makes
decisions queryable, typed, and audit-immutable.

---

## 11. Officer Continuity (Case Ownership)

The created `ComplianceCase` sets `assigned_to = user.user_id` (the escalating
compliance officer). There is **no** unassigned case pool — the officer who made
the decision owns and carries the case forward. The `case:create` permission
seed still requires the officer to hold it.

---

## 12. Escalation Requires the Immutable Report Snapshot

`escalate_to_case` checks `ReportSubmissionRepo.fetch_for_investigation(...)`
inside the same `UnitOfWork`. If the C4 immutable submission snapshot is absent,
it raises `WorkbenchError("NO_SUBMISSION_SNAPSHOT", ..., 409)`. This guarantees
the resulting case always has an authoritative immutable report reference.

---

## 13. Provenance to the Immutable Report

The case's report provenance is resolved through `investigation_id` (present on
the created case). No new FK was added to `compliance_cases`; the immutable
C4 snapshot is located by `investigation_id`, and the source Alert is located by
the case's `alert_id` (which equals the investigation's linked `alert_id`).

---

## 14. Duplicate Escalation Guard

`escalate_to_case` checks `CaseRepo.fetch_active_for_investigation(...)`. If an
active case already exists for the investigation, it raises
`WorkbenchError("DUPLICATE_ESCALATION", ..., 409)`. Combined with the
`X-Idempotency-Key` idempotency layer, a replayed/retried escalation cannot
produce a second case.

---

## 15. Source Alert Finalization

At the investigation's final outcome (Not Harmful or Escalated), the source
Alert is finalized via `_finalize_source_alert`:

- If the linked Alert is already `dismissed`/`resolved`, no-op.
- Otherwise it is set to `resolved` (`resolved_at`/`resolved_by`, version bump,
  optimistic `AlertRepo.update`), with timeline + outbox event
  `alert.resolved_from_investigation`.

This closes the alert lifecycle cleanly when an investigation reaches a final
compliance outcome.

---

## 16. Analyst Final-Outcome Notification

`_notify_report_analyst` sends a notification to `inv.assigned_to or
inv.created_by` (the report analyst):
- `investigation_reviewed` on Not Harmful.
- `investigation_escalated` on escalation.

The two notification types were added to the DB `notifications.notification_type`
CHECK constraint via migration `0017` (the C5 types were not in the `0010`
approved set).

---

## 17. Permission Model

- Analyst: no `alert:transition`; retains alert operations + Start Investigation.
- Compliance officer: `investigation:review` + `case:create` → can final-decision.
- Admin: **cannot** final-decision — admin lacks seeded `case:create`, and
  `investigation:review` is PROHIBITED for the admin role in `authorise.py`.

`ALL_PERMISSION_CODES` still contains `alert:transition` (legacy-code
compatibility for the shared empty-status test), but no role is granted it and
no transition map references it.

---

## 18. Escalation Path Detail

`InvestigationService.escalate_to_case` (same `UnitOfWork`):

1. `authorise(investigation:review)` then `authorise(case:create)`.
2. Ownership: `inv.compliance_officer_id == user.user_id` (else
   `AuthOwnershipDenied`).
3. State: `inv.status == "submitted"` (else `InvalidTransition`).
4. Snapshot exists (else 409 `NO_SUBMISSION_SNAPSHOT`).
5. No active case (else 409 `DUPLICATE_ESCALATION`).
6. `ComplianceCase.create(assigned_to=officer)`.
7. `ReviewDecisionRepo.insert(ESCALATE_TO_CASE, resulting_case_id=case.id)`.
8. Finalize investigation (`completed`), `_finalize_source_alert`, notify
   analyst, timeline + outbox (`investigation.escalated_to_case`, `case.created`).

---

## 19. Not-Harmful Path Detail

`InvestigationService.review_not_harmful`:

1. `authorise(investigation:review)`.
2. Ownership + `submitted` state.
3. `ReviewDecisionRepo.insert(NOT_HARMFUL, resulting_case_id=None)`.
4. Finalize investigation (`completed`), `_finalize_source_alert`, notify
   analyst, timeline + outbox (`investigation.review_not_harmful`) with
   `decision_id` and `resolved_alert_id`.

No compliance case is created on the Not-Harmful path (asserted by test).

---

## 20. Frontend Changes

- Removed `EscalateAlertDialog`, the analyst "Escalate" button,
  `alertsApi.escalate`, the `EscalateAlertPayload`/`EscalateResponse` types, and
  the `PERMISSIONS.ALERT_TRANSITION` gate from `AlertDetailPage.tsx`.
- `PERMISSIONS.ALERT_TRANSITION` (`alert:transition`) removed from
  `frontend/src/lib/permissions.ts`.
- The compliance review area (`InvestigationDetailPage.tsx`) already exposes
  exactly three actions — `showNotHarmful`, `showEscalateCase`,
  `showRequestInfo` — correctly gated; `MarkNotHarmfulDialog` and
  `EscalateToCaseDialog` (rationale required) already exist and are retained.
- Frontend tests updated to remove the escalate interaction.
- `tsc --noEmit` clean; vitest green.

---

## 21. Home / Handler / Routing Pointers

- `services/workbench/services/investigation_service.py`
  (`review_not_harmful`, `escalate_to_case`, `_finalize_source_alert`,
  `_notify_report_analyst`, `ReviewDecisionRepo`).
- `services/workbench/repos.py` — `ReviewDecisionRepo` (INSERT-only).
- `services/workbench/models.py` — `InvestigationReviewDecision`.
- `services/workbench/routers/investigations.py` — `POST /{id}/review/escalate`.
- Migrations: `0016_review_decisions`, `0017_c5_notification_types`.
- Frontend: `InvestigationDetailPage.tsx`, `MarkNotHarmfulDialog.tsx`,
  `EscalateToCaseDialog.tsx`, `alertsApi.ts`, `permissions.ts`.

---

## 22. Status & Enum Reuse

- No new investigation/case status enums were introduced.
- Reused existing states (`submitted`, `completed`) and the C4 state machine
  (`active → submitted ⇄ awaiting_information → submitted → completed`).
- `decision_type` is a new controlled varchar (`NOT_HARMFUL` /
  `ESCALATE_TO_CASE`).

---

## 23. Legacy Handling

- Legacy alert escalation is fully removed; historical rows/truth are untouched.
- `returned` remains a frozen/legacy investigation state with no transitions
  (unchanged from C4).
- No forced migration of historical cases/alerts — historical truth preserved.

---

## 24. Migration & Deployment Note

- `0016_review_decisions`: `investigation_review_decisions` table + index,
  removes analyst `alert:transition` seed.
- `0017_c5_notification_types`: extends the `notifications.notification_type`
  CHECK to add `investigation_reviewed` / `investigation_escalated`.
- Applied and verified on `banking_integration`. `alembic heads` =
  `0017_c5_notification_types`; `alembic current` = `0017_c5_notification_types`.
- `banking_dev` was **not** mutated. `alert:transition` verified **absent** from
  `role_permissions` on `banking_integration`.
- The decision table is INSERT-only; no manual DML was performed.

---

## 25. Test Coverage

Backend (real Postgres where integration):

- `test_investigation_review_actions.py` (24 passed) — rewired to patch the
  concrete repos (`ReviewDecisionRepo.insert`, `AlertRepo`, `ReportSubmissionRepo`,
  `CaseRepo`, `NotificationRepo`, etc.), asserting immutable decision rows, officer
  continuity, no-case-on-Not-Harmful, snapshot gating, duplicate-escalation guard.
- `test_c3_investigation_assignment.py` (31 passed) — officer review/not-harmful/
  escalate/denials; cleanup updated for the new decision FK.
- `test_alerts.py` (25 passed) — `TestEscalate` removed.
- `test_2b17b_scenarios.py` (74 passed) — `T08` now asserts 404 on the removed
  alert-escalate endpoint; `V03` rewritten.
- `test_c2_rbac_segregation_integration.py` (9 passed), `test_rbac_segregation.py`
  (22 passed).
- Shared suite (`services/shared/tests`) — **72 passed** (incl.
  `test_authorise_collections.py` empty-status `alert:transition` behaviour).

**Regression results:**

- Workbench integration suite: **719 passed** (excluding 2 pre-existing
  env-failures that require a live workbench server on `:8014` and the expiry
  worker — unaffected by C5).
- Shared suite: **72 passed**.
- Frontend: **312 passed (32 files)**; `tsc --noEmit` clean.

---

## 26. Verifying the Invariants (Proof Summary)

- **Analyst cannot create a case from an Alert**: route + method + schema +
  frontend removed; `T08` asserts 404.
- **Officer-only final decision**: `escalate_to_case` requires
  `investigation:review` + `case:create` + ownership; Not Harmful requires
  `investigation:review` + ownership; admin denied (no `case:create`,
  `investigation:review` PROHIBITED).
- **Immutable decisions**: `investigation_review_decisions` is INSERT-only.
- **Snapshot gating**: escalation 409s without the C4 immutable snapshot.
- **No duplicate case**: `DUPLICATE_ESCALATION` guard + idempotency key.
- **Provenance**: case → investigation → alert → immutable snapshot; case
  `alert_id` = investigation `alert_id`.
- **Alert closed at final outcome**: resolved + `alert.resolved_from_investigation`.
- **C2/C3 segregation intact**; `submitted`-state decision gating preserved.

---

## 27 (Final Return — §52)

**Step C5: GO.**

**Recommendation:** Proceed to **C6** with a scoped objective.

**Recommended C6 scope:** **Customer360** object scoping and customer-linkage
surfacing on Alerts / Investigations / Compliance Cases (§50), as the remaining
operational-workflow gap. Reuse the C4 immutable snapshot and C5 decision record
as authoritative references. Recommended optional hardening (separately tracked,
not blocking C6): workload-based officer availability and a supervisor queue.

**Not required for C6 (deferred per mandate):** report structure redesign,
reassignment workflow, new LLM logic, forced migration of historical rows.

**Deliverables this step:** `COMPLIANCE_DECISION_CASE_ESCALATION_REPORT.md`,
migrations `0016_review_decisions` + `0017_c5_notification_types`, structured
immutable decision layer, legacy alert-escalation removal (backend + frontend),
officer-continuity case ownership, alert finalization, analyst notification, and
updated backend + frontend test coverage. Stopping after this report per step
mandate.

---

## Appendix — §52 Final Return (A → AJ)

| # | Question | C5 answer |
|---|----------|-----------|
| A | Is the analyst able to create a Compliance Case directly from an Alert (legacy path)? | **NO** — `POST /alerts/{id}/escalate` removed (404); no other analyst case-creation path exists. |
| B | Is the legacy alert→case path still operational anywhere? | **NO** (route absent; no role retains `alert:transition`; no transition map references it). |
| C | Are final compliance decisions persisted structurally & immutably? | **YES** — `investigation_review_decisions`, INSERT-only, typed `decision_type` + mandatory rationale. |
| D | Do Not-Harmful decisions create a case? | **NO** — `resulting_case_id = NULL`; asserted by test. |
| E | Is case creation exclusively via assigned officer on a `submitted` investigation? | **YES** — `investigation:review` + `case:create` + ownership + `submitted`. |
| F | Can an unassigned or non-owning officer create a case? | **NO** — `AuthOwnershipDenied` when officer mismatch. |
| G | Can the admin final-decision? | **NO** — no `case:create`; `investigation:review` PROHIBITED for admin. |
| H | Does escalation require the immutable C4 report snapshot? | **YES** — 409 `NO_SUBMISSION_SNAPSHOT` when missing. |
| I | Is a duplicate/retried escalation prevented? | **YES** — `DUPLICATE_ESCALATION` guard + idempotency key. |
| J | Is the created case assigned to the escalating officer (no unassigned pool)? | **YES** — `assigned_to = officer.user_id`. |
| K | Is provenance preserved (case → investigation → alert → immutable snapshot)? | **YES** — via `investigation_id` + `alert_id`; no new FK on `compliance_cases`. |
| L | Is the source Alert finalized at final outcome? | **YES** — resolved + `alert.resolved_from_investigation` (timeline + outbox). |
| M | Is the report analyst notified of the final outcome? | **YES** — `investigation_reviewed` / `investigation_escalated`. |
| N | Is the Start-Investigation (analyst) path intact? | **YES** — analyst retains `alert:investigate` & alert operations. |
| O | Does the C4 state machine remain authoritative? | **YES** — `submitted`-only final-decision; `completed` on outcome. |
| P | Are all runtime env-dependent tests excluded from the C5 green regression? | **YES** — only `:8014` HTTP / expiry-worker env tests excluded (pre-existing). |
| Q | Frontend: is analyst alert escalation UI/API fully removed? | **YES** — dialog, button, API, permission gate all removed. |
| R | Frontend: does the compliance 3-action review remain and stay gated? | **YES** — Not Harmful / Escalate Case / Request Info, role-gated. |
| S | Frontend typecheck + tests green? | **YES** — 312 passed (32 files), `tsc --noEmit` clean. |
| T | Backend suite green? | **YES** — 719 workbench + 72 shared + targeted C5 suites green. |
| U | Migration head applied on `banking_integration`? | **YES** — `0017_c5_notification_types`. |
| V | Is `alert:transition` retained in `ALL_PERMISSION_CODES` (back-compat)? | **YES** — but granted to no role; shared empty-status test still passes. |
| W | Historical rows/truth untouched? | **YES** — no forced migration of cases/alerts. |
| X | Immutability of decision rows enforced? | **YES** — INSERT-only repo; no UPDATE/DELETE path. |
| Y | No new enums introduced? | **YES** (reused existing status model; a controlled `decision_type` varchar). |
| Z | Case-owned report reference is authoritative/immutable? | **YES** — resolved to the C4 INSERT-only snapshot. |
| AA | Not-Harmful leaves the submitted queue & does not create a case? | **YES** — `completed`; no case (test-asserted). |
| AB | Escalation leaves the submitted queue & creates exactly one case? | **YES** — `completed`; single case (idempotency + guard). |
| AC | Notifications schema permits C5 types? | **YES** — migration `0017` extends the CHECK. |
| AD | No production code modified beyond authorized C5 changes? | **YES** — migrations + service/schema/repo + frontend as designed; tests updated. |
| AE | Are post-outcome findings edits still denied (C4 preserved)? | **YES** — C4 immutability intact. |
| AF | Is workload-based officer availability required for C6? | **NO** (deferred; optional). |
| AG | Is supervisor queue required for C6? | **NO** (deferred; optional). |
| AH | Is Customer360 in scope for C6? | **YES** — recommended C6 scope. |
| AI | Does the report mislead on any go/no-go delta? | **NO** — all listed answers reflect verified behaviour. |
| AJ | Overall go/no-go for C5 → C6? | **GO** — proceed to C6 (Customer360 scoping). |
