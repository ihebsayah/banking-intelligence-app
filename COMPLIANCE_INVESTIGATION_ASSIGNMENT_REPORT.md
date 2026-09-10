# COMPLIANCE INVESTIGATION ASSIGNMENT — COMPLETION REPORT (Step C3)

**Workstream:** Compliance Operational Workflow Redesign
**Scope:** Secure analyst→Compliance Officer investigation handoff with row-level ownership.
**Status:** COMPLETE
**Date:** 2026-09-02

---

## 1. Executive Summary

C3 implements the deterministic **Analyst → Investigation → selected eligible
Compliance Officer** handoff, enforced at the backend row level. A dedicated
submission endpoint atomically assigns an eligible officer, preserves the
analyst's ownership, and moves the investigation into compliance review. A
compliance officer may review an investigation **only** if it is assigned to
them (backend-enforced; not a frontend dropdown). Assignment is immutable after
submission, compliance cannot self-claim, admin cannot be a reviewer, and the
source-alert / information-request context follows the investigation's
assignment boundary. C2 RBAC / workspace segregation remains intact.

---

## 2. C2 Preconditions

- C1 (`COMPLIANCE_WORKFLOW_AS_BUILT_AUDIT.md`) and C2
  (`COMPLIANCE_RBAC_SEGREGATION_REPORT.md`, migration `0013`) are authoritative;
  C3 does not redesign them.
- Compliance: no standalone Alerts module; no `alert:read_assigned` /
  `alert:transition`. Analyst: no standalone Cases module; no
  `case:read_assigned`. Compliance holds `case:decision` / `case:close`.
- Admin is administrative only and must not become an operational reviewer.
- `banking_dev` has **not** had `0013` applied and must not be manually mutated.
- The migration-managed test DB `banking_integration` (port 5435) carries the
  full chain through `0013` (and now `0014`); C3 tests run on this DB.

---

## 3. Existing Investigation Ownership Model

Pre-C3 fields on `investigations`:

| Field | Semantics |
|-------|-----------|
| `created_by` | Analyst identity (author). |
| `assigned_to` | Analyst owner/assignee through the working lifecycle. |
| `alert_id` | Source alert linkage. |
| `status` | Lifecycle state. |
| `submitted_at` | Submission timestamp. |
| `version` | Optimistic locking. |

`assigned_to` already meant the **analyst worker** — there was no separate
compliance assignee. Reusing `assigned_to` to also mean "compliance assignee"
was rejected (would destroy analyst ownership and conflate two principals), so a
new field was required.

---

## 4. Existing Status Machine

Reused statuses (no new enum introduced):

`open → active → submitted → completed`
`active ⇄ awaiting_information`
`submitted ⇄ returned`
`... → active`

For C3:
- **ANALYST WORKING** = `active`
- **SUBMITTED TO COMPLIANCE / UNDER REVIEW** = `submitted`
- **ADDITIONAL INFO REQUESTED** = `awaiting_information`
- **CLOSED** = `completed`
- **ESCALATED** = `escaped` via `escalate_to_case` → the investigation completes
  and a `compliance_cases` row is created.

`active → submitted` is now handled **only** by the dedicated
`submit_to_compliance` endpoint (removed from `ALLOWED_TRANSITIONS`);
everything else in the state machine is unchanged.

---

## 5. Ownership vs Assignment Semantics

Two distinct principals, kept in separate fields:

- **ANALYST OWNER** = `assigned_to` + `created_by` (persists after submission).
- **COMPLIANCE ASSIGNEE** = new `compliance_officer_id` (populated by submit).

The analyst identity does **not** disappear on handoff; the officer becomes the
reviewer only.

---

## 6. Schema Changes

Migration `0014_investigation_compliance_officer_assignment` (revision
`0014`, down `0013`):
- adds nullable `compliance_officer_id` FK → `users.user_id`;
- adds index `idx_investigations_compliance_officer` (assigned-queue filter);
- non-destructive; preserves existing rows; downgrade per project convention.

Applied and verified on `banking_integration` (alembic head =
`0014_investigation_assignment`). `banking_dev` untouched.

---

## 7. Eligible Compliance Officer Discovery

New read-only endpoint:

```
GET /api/v1/investigations/eligible-compliance-officers
```

Implemented in `investigation_service.list_eligible_compliance_officers` +
router. No existing directory/Keycloak/admin endpoint was reused because no
suitable application endpoint existed; this is the smallest dedicated read-only
endpoint, returning only `user_id`, `name`, `email`.

---

## 8. Officer Eligibility Rules

Assignee must satisfy **all** of:
- user exists;
- `status = 'active'`;
- role = `compliance`;
- role holds `investigation:review` (via `role_permissions`, role-based — not a
  per-user permission array, so a hypothetical admin-with-permission cannot
  qualify).

Analyst, Admin, inactive users, unknown users, and non-compliance-role users are
all rejected (`InvalidAssignee`). **Availability is defined conservatively** =
active + eligible (no workload/presence/schedule system exists). Documented
limitation; future workload-aware assignment is a C4+ perspective.

---

## 9. Submission API

```
POST /api/v1/investigations/{id}/submit
{
  "compliance_officer_id": "…",
  "expected_version": 1
}
```

Dedicated semantic action (not a generic PATCH). Frontend selection is
untrusted; the backend validates everything.

---

## 10. Submission Preconditions

`submit_to_compliance` succeeds only when:
- acting user is authenticated analyst-submitter with `investigation:transition`;
- user is the investigation's `assigned_to` (ownership);
- investigation `status == 'active'` (submit-capable, not closed/escalated);
- findings (`findings_text` or `findings_refs`) present;
- conclusion present;
- officer exists / active / compliance / holds `investigation:review`;
- no conflicting assignment (state + assignee set atomically).

No new report-field requirements were added beyond findings+conclusion already
in effect; structured report hardening is C4.

---

## 11. Atomic Handoff

Within a single `UnitOfWork`: idempotency check → load → authorize → ownership
→ state → content → assignee validation → single `UPDATE` (status, `submitted_at`,
`compliance_officer_id`, version) → timeline + notification + outbox inserts,
then idempotency store. Partial state cannot remain: the status transition and
assignee are written in one optimistic-lock `UPDATE`.

---

## 12. Idempotency / Concurrency

- Idempotency keyed on `POST` path + body → repeated identical submit returns
  the prior submitted state (no duplicate assignee, timeline, notification,
  outbox, or reset timestamp).
- Concurrency: the single optimistic-lock `UPDATE` on `expected_version` means
  only one of two near-simultaneous submits wins; the loser raises
  `VersionConflict`. No last-write-wins silent reassignment.

---

## 13. Compliance Assigned Queue

`list_submitted` filters `compliance_officer_id = requester` for
`role == 'compliance'`. It returns **only** investigations assigned to the
authenticated officer — not all submitted, not all compliance-status, not all
because role=compliance. Proven by tests (officer X sees own; officer Y does
not).

---

## 14. Investigation Detail Authorization

`get_by_id` returns `ResourceNotFound` when `compliance_officer_id` is set and
does not match the requesting officer (anti-enumeration hides existence):
- Officer X GET own → ALLOW.
- Officer Y GET X's → 404.
- Analyst B GET A's → 404.
- Analyst A GET own submitted → ALLOW (ownership retained).

---

## 15. Review Action Authorization

`review_not_harmful` and `escalate_to_case` reject a mismatched officer before
any state change. Officer X may act on own; Officer Y is denied. Admin review
actions are prohibited (C2 PROHIBITED combos).

---

## 16. Contextual Alert Authorization

Compliance has no standalone alert permission (C2). Officer X reaches the
source alert only through the investigation detail, which is gated by
assignment — so Officer Y cannot reach it via that investigation (they get a
404 on the investigation first). No alert permissions restored.

---

## 17. Contextual IR Authorization

Changed in C3: in `shared/authorise.py`, the `info_request:create` on a
`submitted` investigation previously bypassed ownership; it now also requires
`resource.compliance_officer_id == user.user_id` when an assignee is set.
`information_request_service._resource_from_inv` now passes
`compliance_officer_id` so the PAP guard applies. Officer X may create IRs on an
assigned investigation; Officer Y cannot. Full contextual IR permission cleanup
(analyst-recipient side) remains C4.

---

## 18. Comments / Evidence Authorization

Comments/evidence inherit the investigation-detail authorization boundary: they
are reached through the gated investigation detail, so Officer Y cannot access
X's investigation comments/evidence. No standalone IDs are exposed globally;
no redesign done.

---

## 19. Notifications

On submission, the selected officer is notified via the existing notification
+ outbox mechanism (event `investigation.submitted_to_compliance`, concept "New
investigation assigned"; payload carries investigation reference + analyst, no
unnecessary PII). No second notification system introduced. No redundant
"you submitted successfully" persistent notification for the analyst (UI
feedback is enough).

---

## 20. Audit / Timeline

Submission emits a timeline event `investigation.submitted_to_compliance`
(`investigation_id`, analyst actor, compliance assignee, timestamp,
`from_status=active` → `to_status=submitted`) and an outbox event
`investigation.submitted_to_compliance`. Reuses existing event vocabulary.

---

## 21. Frontend Analyst Submission UX

New `SubmitToComplianceDialog`: Complete → Submit to Compliance → select
officer (from eligible-officer API) → confirm. Confirmation states the target
officer and notes further changes may be restricted (does not claim immutability
already implemented — C4 pending). Only identity fields shown; no raw
permission internals.

---

## 22. Frontend Compliance Queue

`InvestigationQueuePage` represents **My Assigned Investigations** (assigned
queue from `listSubmitted`, backend-filtered). `InvestigationDetailPage` shows
the assigned **Compliance Officer** meta row, submission timestamp, and
removes/disables the Submit button + officer selector after submission (the
analyst cannot reassign from the UI; backend is authoritative).

---

## 23. IDOR Tests

Covered in `test_c3_investigation_assignment.py`: Officer Y cannot read,
not-harmful, or escalate X's investigation by UUID; Analyst A cannot submit
Analyst B's by UUID; Analyst B cannot read Analyst A's; IR create by Officer Y
on X's is denied.

---

## 24. Invalid Assignment Tests

All rejected deterministically (`InvalidAssignee`): submit to Analyst UUID,
Admin UUID, inactive Compliance UUID, unknown UUID. Malformed UUID rejected by
validation before service. Admin cannot submit on behalf of an analyst.

---

## 25. Backend Tests

New suite `test_c3_investigation_assignment.py` — **27 passing** (extra:
contextual IR allow/deny): eligible-officer discovery, assignee matrix,
ownership, queue filtering, detail IDOR, review-action authorization, IR
context, immutability/no-self-claim, invariants, audit/notification/outbox.

Workbench regression: `643 passed` (excl. 2 pre-existing baseline failures).
Shared policy: `72 passed`.

---

## 26. Frontend Tests

- `npx vitest run` — **314 passed** (32 files), incl. updated detail/queue
  tests for the submit dialog + assigned queue.
- `npx tsc --noEmit` — clean.
- eslint — no new problems (2 pre-existing rules-of-hooks errors identical to
  baseline).

---

## 27. Regression Results

- Investigations, review actions, IR, cases, comments, attachments, timeline,
  notifications/outbox, approvals, alerts, queue/assigned authorization,
  shared policy: green.
- `test_2b17b_scenarios.py` (74) green after updating submit scenarios (`T06`,
  `T25`, `F10`) to the `/submit` endpoint.
- C2 RBAC suites green.
- Pre-existing baseline failures (verified via `git stash`, not caused by C3):
  `test_http_contract_remediation.py` (8), `test_expiry_worker_integration.py`
  (1).

---

## 28. Legacy Alert→Case Path

```
LEGACY_ALERT_TO_CASE_PATH_PRESENT = YES
```

- **Endpoint:** `POST /api/v1/alerts/{alert_id}/escalate`.
- **Permission:** `alert:transition` (retained on analyst in C2).
- **Tests relying on it:** `test_alerts.py`, `test_rbac_segregation.py`,
  `test_2b17b_scenarios.py` (accepted scenarios T08/V03-style).
- **Business impact:** allows Analyst → direct → Case, bypassing the
  Investigation → Compliance Review → Case canonical path. Not removed or
  redesigned in C3. **Revisit explicitly in C5.**

---

## 29. Remaining Gaps

- Full IR contextual-permission cleanup (analyst-recipient reads) — C4.
- Customer360 contextual scoping on investigation detail — later.
- Workload-based officer availability — later.
- Officer reassignment / supervisor queue — later.
- Report immutability + structured report + revision history — C4.
- `banking_dev` still requires authorized application of `0013` (and `0014`) —
  defer, not a C3 code blocker.

---

## 30. Recommendation for C4

**GO for C4.** Priorities: (1) report/record immutability + structured report
revision; (2) full IR contextual-permission refactor; (3) Customer360 object
scoping. Each tracked independently; reassignment and workload-availability are
separate later concerns.

---

# FINAL RETURN

A. **Files changed** — see git (backend: migration `0014`, `models.py`,
   `schemas/investigations.py`, `repos.py`, `investigation_service.py`,
   `routers/investigations.py`, `shared/authorise.py`,
   `information_request_service.py`; tests: `test_c3_investigation_assignment.py`,
   updated `test_investigations.py`, `test_2b17b_scenarios.py`,
   `test_investigation_review_actions.py`; frontend: `SubmitToComplianceDialog.tsx`
   (new), `investigationsApi.ts`, `types/investigations.ts`,
   `InvestigationDetailPage.tsx`, `InvestigationQueuePage.tsx`, + 2 updated test
   files; report).
B. **Migration required?** YES — `0014_investigation_compliance_officer_assignment`.
C. **Investigation analyst-owner field** — `assigned_to` (analyst; `created_by`
   = author).
D. **Investigation compliance-assignee field** — `compliance_officer_id` (new).
E. **Submission timestamp field** — `submitted_at` (existing, reused).
F. **Submission/review status used** — `submitted` (existing enum, reused).
G. **Eligible-officer endpoint** — `GET /investigations/eligible-compliance-officers`.
H. **Eligibility definition** — active + `compliance` role + `investigation:review`
   (role-based).
I. **Workload-aware availability implemented?** NO (documented; none existed).
J. **Analyst can submit own investigation?** YES.
K. **Analyst can submit another analyst's investigation?** NO.
L. **Analyst can assign Analyst user?** NO.
M. **Analyst can assign Admin?** NO.
N. **Analyst can assign inactive Compliance?** NO.
O. **Analyst can assign active eligible Compliance?** YES.
P. **Assignment atomic?** YES.
Q. **Duplicate submission behavior** — idempotent (replay returns prior state;
   concurrent → version conflict, one winner).
R. **Analyst can reassign after submission?** NO.
S. **Compliance can self-claim?** NO (no claim endpoint; generic update cannot
   set assignee).
T. **Officer X sees assigned Investigation?** YES.
U. **Officer Y sees X's Investigation?** NO.
V. **Officer Y review actions on X's Investigation?** NO.
W. **Analyst still sees own submitted Investigation?** YES.
X. **Analyst B sees Analyst A Investigation?** NO.
Y. **Source Alert visible contextually to assigned officer?** YES (via detail).
Z. **Source Alert visible contextually to other officer?** NO.
AA. **Investigation IR visible/manageable by assigned officer?** YES.
AB. **Same IR accessible by another officer?** NO (PAP guard added in C3).
AC. **Audit event emitted?** YES (`investigation.submitted_to_compliance`).
AD. **Notification emitted?** YES (to officer, via existing outbox/notification).
AE. **Backend tests result** — 27 C3 + 643 workbench + 72 shared pass
    (excl. 2 pre-existing baseline failures).
AF. **Frontend tests result** — 314 pass; `tsc` clean; no new lint.
AG. **C2 regression result** — green (RBAC + segregation + scenarios).
AH. **Legacy Alert→Case path still present?** YES.
AI. **Exact legacy endpoint/permission** — `POST /alerts/{id}/escalate`,
    `alert:transition` (analyst).
AJ. **Remaining security gaps** — none introduced; full IR/Customer360
    contextual cleanup deferred (C4/later); `banking_dev` needs authorized
    `0013`+`0014` application.
AK. **Remaining workflow gaps** — reassignment, workload availability,
    supervisor queue, report immutability (C4+).
AL. **GO / NO-GO for C4** — **GO**.
AM. **Recommended exact C4 scope** — report/record immutability + structured
    report revision; IR contextual-permission refactor; Customer360 scoping.
