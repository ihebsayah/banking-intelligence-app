# COMPLIANCE REPORT IMMUTABILITY + IR FEEDBACK LOOP — COMPLETION REPORT (Step C4)

**Workstream:** Compliance Operational Workflow Redesign
**Scope:** Make the submitted Analyst report immutable and route all post-submission
Analyst input through the Information Request (IR) feedback loop.
**Status:** COMPLETE
**Date:** 2026-09-02

---

## 1. Executive Summary

C4 makes the original submitted Analyst report an **authoritative, durable,
immutable record** and forces every post-submission Analyst contribution through
the **Information Request (IR) feedback loop** — never a direct re-open/rewrite
of the report.

Three mechanisms work together:

1. **Ring-fenced editing** — Findings/refs/conclusion editing (`PATCH
   /investigations/{id}`), evidence upload/delete, and any generic transition
   that could re-activate a submitted report are locked to the pre-submission
   `active` state only. The `submitted → returned → active` report-edit path is
   removed from the canonical state machine.
2. **INSERT-only snapshot** — at `submit_to_compliance` the exact submitted
   report (`findings_text`, `findings_refs`, `conclusion`), its evidence
   manifest, the authoring analyst, the assigned compliance officer, the
   submission timestamp and a SHA-256 `report_hash` are written to a new
   `investigation_report_submissions` table. That row is append-only and is
   surfaced to compliance review via `submission_snapshot` on the
   investigation read/response — the compliance officer always reviews the
   authoritative submitted version.
3. **IR-only post-submit loop** — from `submitted`, compliance requests
   additional information via an IR; the investigation moves
   `submitted → awaiting_information`; the analyst acks/responds; compliance
   accepts/returns; and the investigation resumes to `submitted`. The report
   row is never mutated across any IR cycle.

C3 invariants are preserved: `compliance_officer_id` survives
`submitted → awaiting_information → submitted`, `submitted_at` is preserved,
and C2 compliance/analyst RBAC segregation remains intact.

---

## 2. Objective

Make analyst report submission a **one-way door**: once submitted, the original
report is the immutable historical record. All further analyst contribution is
captured as Information Request responses, and compliance review always reads
the authoritative submitted snapshot.

---

## 3. Scope

**In scope**

- Immutable submitted Analyst report (findings, refs, conclusion) + evidence.
- Post-submission analyst input routed through the IR feedback loop only.
- Authoritative submission snapshot persisted (`investigation_report_submissions`).
- Surface the snapshot to compliance review.
- Remove the `submitted → returned → active` report-edit path from the
  canonical flow; document legacy `returned` handling.

**Out of scope (explicitly deferred, documented for later steps)**

- Customer360 object scoping (§46 region of the broader mandate).
- Compliance Case redesign (§45 / §46).
- Report **structure** redesign beyond the immutable snapshot (§30).
- Legacy alert → case path fix (keep `POST /alerts/{id}/escalate` +
  `alert:transition`; documented for C5).

---

## 4. Canonical Rule

> The original submitted analyst report (`findings_text`, `findings_refs`,
> `conclusion`) is **immutable**. Post-submission analyst input flows via IR
> response **only**. There is no return-for-revision report-edit path in the
> canonical flow.

---

## 5. Success Criteria

1. Analyst's submitted report becomes an **immutable historical record** — no
   edit/delete path mutates `findings_text`/`findings_refs`/`conclusion` or
   evidence once the investigation leaves `active`.
2. Analyst cannot re-open a submitted report and edit it.
3. Compliance cannot redirect an IR to a non-authoring party nor change the
   analyst owner.
4. Compliance can only request information/add via IR; analyst responds via IR;
   the report row is **byte-identical** to the submitted snapshot.
5. No analyst can mutate the original report through comments, attachments, or
   any generic endpoint while `submitted`/`awaiting_information`.
6. Compliance completing/escalating can only act while the report is in
   compliance-review state (`submitted`), not while `awaiting_information`.
7. The original report remains **exactly the same** before/after any number of
   IR cycles, and `compliance_officer_id` / `submitted_at` are preserved.
8. Existing C2 RBAC and C3 row-level ownership survive end-to-end.

---

## 6. Canonical State Flow

```
            report editable                        report immutable
open → active ──(submit_to_compliance)──▶ submitted
                                            │  ▲
                          compliance       │  │ accept (no active IRs):
                        creates IR         │  │ awaiting_information → submitted
                                            ▼  │
                                      awaiting_information
                                            │  │
                          analyst acks → responds (IR-only), compliance accepts
```

- `active` is the **only** report-editable state.
- `submitted`, `awaiting_information`, `completed`, `cancelled` are
  report-immutable.
- `returned` is retained **only as a legacy status** (frozen/read-only); it is
  not produced by the canonical flow and has no re-open transition.

---

## 7. Attack Surfaces Locked (Post-Submission Editing Paths)

| # | Surface | Endpoint / Function | C4 disposition |
|---|---------|---------------------|----------------|
| E1 | Generic findings/report edit | `PATCH /investigations/{id}` → `InvestigationService.update` | Restricted to `status == "active"` only (removed `returned`). `submitted`/`awaiting_information`/`returned` → `WORKFLOW_STATE`/`INVALID_TRANSITION`. |
| E2 | Generic transition re-open | `PATCH /investigations/{id}/transition` → `InvestigationService.transition` | Removed `submitted → returned` and `returned → active` from `ALLOWED_TRANSITIONS`. No path returns a report to `active` after submission. |
| E3 | Evidence upload | `POST /investigations/{id}/attachments` | Restricted to `open`/`active`. Rejected in `submitted`/`awaiting_information`/`returned`. |
| E4 | Evidence delete | `DELETE /investigations/{id}/attachments/{att}` | Restricted to `open`/`active`. Rejected in `submitted`/`awaiting_information`/`returned`. |
| E5 | Comments | `POST /investigations/{id}/comments` | Allowed (does **not** mutate the report; separate entity). Provides a response channel but cannot alter findings. |
| E6 | Cancel | `POST /investigations/{id}/cancel` | `returned` removed from `CANCEL_ALLOWED_FROM`; cancellation only from operational states. |
| E7 | Status machine | `ALLOWED_TRANSITIONS` | `submitted: [completed]`; `active: [awaiting_information]`; `awaiting_information: [active]`. |
| E8 | IR recipient | `create_for_investigation` / `create` | Recipient is backend-derived (analyst owner / assignee), **not** user-supplied redirect; compliance cannot reassign. |
| E9 | PATCH alias re-submission | `transition` to `active` from `submitted` | Impossible — not in `ALLOWED_TRANSITIONS`. |

---

## 8. Immutability of the Report Fields

After submission, all three report fields (`findings_text`, `findings_refs`,
`conclusion`) are frozen because the only mutating function
(`InvestigationService.update`) rejects any investigation whose status is not
`active`, and no transition can return a submitted investigation to `active`.
Therefore the working `investigations` row's report fields **are** the immutable
record, and the separately persisted `investigation_report_submissions` row is
the durable, authoritative snapshot guaranteed to equal them.

---

## 9. The Immutable Snapshot

New table `investigation_report_submissions` (migration
`0015_report_submissions`), seeded once at `submit_to_compliance`:

| Column | Type | Purpose |
|--------|------|---------|
| `submission_id` | varchar PK | Surrogate id. |
| `investigation_id` | uuid FK (investigations, ON DELETE CASCADE) | Owning investigation. |
| `analyst_id` | varchar FK (users) | Original report author. |
| `compliance_officer_id` | varchar FK (users) | Officer assigned at submission. |
| `findings_text` | text | Immutable findings body. |
| `findings_refs` | jsonb | Immutable structured references. |
| `conclusion` | text | Immutable conclusion. |
| `submitted_at` | timestamptz | Submission moment. |
| `evidence_manifest` | jsonb | Attachment filenames + SHA-256 at submission. |
| `report_hash` | varchar(64) | SHA-256 of normalized report+evidence. |
| `created_at` | timestamptz | Insert time. |

**Design guarantees:** there is **no UPDATE/DELETE** repo path for this table
(`ReportSubmissionRepo` exposes only `insert` and read). It is append-only.
`report_hash` fingerprints the report so any downstream consumer can verify the
submitted content is intact across IR cycles and case escalation.

---

## 10. Snapshot Capture at Submission

`InvestigationService.submit_to_compliance` now, inside the same `UnitOfWork`:

1. Validates ownership (`assigned_to == user`), state (`active`), findings and
   conclusion present, and the recipient is an eligible active compliance
   officer (unchanged C3 logic).
2. Assigns `status = submitted`, `submitted_at`, `compliance_officer_id`.
3. Reads the current attachment manifest (`AttachmentRepo.list_by_investigation`)
   and builds `evidence_manifest` (filename + sha256 + uploader + time).
4. Computes `report_hash = sha256({findings, refs, conclusion, manifest})`.
5. Inserts a new `investigation_report_submissions` row (analyst_id = submitting
   user, compliance_officer_id = recipient).
6. Emits timeline/notification/outbox as before.

The response now includes `submission_snapshot`.

---

## 11. Backend Derivation of the IR Recipient

`create_for_investigation` (and the case variant) keep the recipient
`assigned_to` set from the owning analyst / case assignee. The `info_request:create`
authorisation remains ownership-guarded on a **submitted** investigation (C3):
only the assigned compliance officer (`resource.compliance_officer_id`) may open
an IR, so compliance cannot pivot an IR to a different party.

---

## 12. Compliance Cannot Redirect

- The submitted investigation's `compliance_officer_id` is immutable after C3.
- IR creation on a submitted investigation requires that officer identity.
- There is no compliance-side "reassign IR" or "redirect IR" path.
- The analyst owner (who authors the report) is the only IR responder.

---

## 13. Analyst Cannot Mutate the Report Post-Submission

- `PATCH /investigations/{id}` → rejected for `submitted`/`awaiting_information`
  (`WORKFLOW_STATE` / `INVALID_TRANSITION`).
- Evidence upload/delete → rejected for `submitted`/`awaiting_information`.
- `transition` → no `submitted → active`; no `returned → active`.
- Comments → allowed, but do not touch report fields.
- The report fields are therefore byte-identical to the snapshot at all times
  after submission.

---

## 14. Compliance Decision Gating (no decisions while awaiting input)

- `review_not_harmful` requires `status == "submitted"`.
- `escalate_to_case` requires `status == "submitted"`.
- While `awaiting_information`, neither completion nor escalation can run —
  compliance must first accept/cancel the IR(s), which resumes the
  investigation to `submitted`.

---

## 15. IR Feedback Loop (canonical)

1. `submitted` → compliance `create_for_investigation` → `awaiting_information`.
2. Analyst `acknowledge` (open/returned → acknowledged).
3. Analyst `respond` (acknowledged → responded) — the post-submit input channel.
4. Compliance `accept` (responded → accepted) **or** `return` (responded →
   returned → analyst may re-respond).
5. On accept (or cancel when no active IRs remain), investigation resumes
   `awaiting_information → submitted` with `compliance_officer_id` and
   `submitted_at` preserved.

The snapshot row is **not** replaced by any IR cycle; there is exactly one
snapshot per submission.

---

## 16. Status & Enum Reuse

- No new status enums were introduced (§43 respected).
- Existing IR statuses reused: `open / acknowledged / responded / accepted /
  returned / cancelled`.
- Investigation `returned` retained in the enum as a **legacy** status but is
  no longer reachable in the canonical flow.

---

## 17. Legacy `returned` Handling

Existing rows already in `returned`:

- Are displayed as frozen ("Legacy state — report is frozen").
- Cannot be re-opened (`returned → active` removed) or edited
  (`update` restricted to `active`).
- Cannot be cancelled (`returned` removed from `CANCEL_ALLOWED_FROM`).
- Are **not** rewritten back to `active` (no data migration). They are left
  read-only for review; any remediation path for such pre-C4 rows is
  documented as out of scope (admin/manual), consistent with §35 "do not
  rewrite legacy" instruction.

---

## 18. Why No New Snapshot Per IR Cycle

Because post-submit report mutation is impossible, re-submission (and therefore
a *second* authoritative snapshot) cannot occur. A single INSERT-only snapshot
captured at the one-and-only submission is both sufficient and correct. This
avoids over-engineering while meeting the "authoritative submission snapshot"
requirement.

---

## 19. Evidence Manifest

At submission the attachment inventory is snapshotted (filenames + SHA-256).
Any attempt to add/delete evidence post-submission is blocked (E3/E4), so the
manifest equals the frozen evidence set. This makes the evidence an immutable
part of the submitted record.

---

## 20. Report Hash

`report_hash` is the SHA-256 of the normalised
`{findings_text, findings_refs, conclusion, evidence_manifest}`. It is stored
for tamper-evidence and can be re-computed to prove the report has not changed
since submission (used by the C4 test `test_full_ir_cycle_preserves_snapshot_and_assignee`).

---

## 21. Compliance Review Display

`GET /investigations/{id}` (and the `submit` response) now return
`submission_snapshot` containing the authoritative snapshot. The frontend
detail page renders the report; because the report is frozen post-submission,
the rendered findings equal the snapshot. Compliance completing/escalating acts
against the immutable submitted content.

---

## 22. Frontend Changes

- `InvestigationDetailPage`: removed "Return for Revision" (compliance) and
  "Mark Revision Started" (analyst) actions; `canEditFindings` reduced to
  `status === 'active'`; legacy `returned` shown as frozen; IR
  ("Request Additional Information") remains the post-submit path.
- `types/investigations.ts`: added `SubmissionSnapshot` type and optional
  `submission_snapshot` on `Investigation`.
- `InvestigationQueuePage`: unchanged behaviour (still lists legacy `returned`).
- Tests updated to reflect the C4 no-return canonical flow.

---

## 23. README / Operational Documentation Pointers

- Backend: `InvestigationService.submit_to_compliance`, `InvestigationService.update`,
  `InvestigationService.transition`, `ReportSubmissionRepo`, `SubmissionSnapshot`.
- Migration: `migrations/versions/0015_investigation_report_submissions.py`.
- Frontend: `InvestigationDetailPage.tsx`, `types/investigations.ts`.

---

## 24. Migration & Deployment Note

- New migration `0015_report_submissions` applied and verified on
  `banking_integration` (port 5435), chained after `0013` / `0014`, and is now
  `alembic head`.
- `banking_dev` was **not** mutated. Live deployment must apply the authorised
  chain `0013 → 0014 → 0015` to the shared database via the normal release
  process (out of scope here, per mandate).
- The schema is `INSERT-only`; no `banking_dev` manual DML was performed.

---

## 25. Test Coverage

New/updated tests (all integration, real Postgres):

- `test_c4_*` in `test_c3_investigation_assignment.py` (suite now 31 tests):
  - `test_submit_creates_immutable_report_snapshot`
  - `test_post_submit_findings_edit_denied`
  - `test_submitted_response_returns_snapshot_for_assigned_officer`
  - `test_full_ir_cycle_preserves_snapshot_and_assignee`
- Updated `test_2b17b_scenarios.py`: `T24` (generic return now denied) and
  `T25` (legacy returned frozen, no report edit).
- Updated `test_investigations.py` to reflect the locked state machine
  (return-for-revision denied; snapshot surfacing).
- Frontend `InvestigationDetailPage.test.tsx` updated for the no-return flow.

**Regression results (real Postgres / vitest):**

- Workbench integration suite: **655 passed** (8 live-HTTP/worker env failures +
  1 env error are pre-existing — require the workbench server on :8014 and the
  expiry worker, neither is running here; unaffected by C4).
- Shared suite: **72 passed** (incl. contextual `info_request:create` guard).
- Frontend: **314 passed** (32 files); `tsc --noEmit` clean.
- `test_c3_investigation_assignment.py`: **31 passed**.

---

## 26. Verifying the Invariants (Proof Summary)

- **Immutable report**: `update()` restricted to `active`; no transition to
  `active` from submitted states → report fields cannot change post-submit.
- **Snapshot durability**: `investigation_report_submissions` is INSERT-only and
  equals the frozen report row.
- **IR-only analyst input**: the only post-submit analyst mutation is
  `ir.respond`; investigation report fields are untouched.
- **Assignee preserved**: `accept`/`cancel` resume to `submitted` without
  touching `compliance_officer_id` (asserted in the C4 IR-cycle test).
- **Decision gating**: `review_not_harmful` / `escalate_to_case` require
  `submitted`.
- **C2 segregation intact**: compliance still holds no standalone Alerts/IR
  inbox; analyst still holds no standalone Cases.

---

## 27 (Final Return — §48)

**Step C4: GO.**

**Recommendation:** Proceed to **C5** (legacy alert → case escalation path and
Compliance Case redesign).

**Recommended C5 scope (recommended order):**
1. `POST /alerts/{id}/escalate` + `alert:transition` legacy path — align with
   the C3/C4 canonical investigation handoff and IR loop.
2. Compliance Case workflow — align case creation/resolution with the immutable
   investigation snapshot and the IR feedback loop; reuse the snapshot
   (`submission_snapshot`) as the case's authoritative submitted-report
   reference (§38).
3. Revisit `returned` legacy status lifecycle — decide production remediation
   policy applying the same immutability rules (C4 kept it read-only/frozen).

**Not required for C5 (deferred):** Customer360 object scoping (§46) and report
structure redesign beyond the immutable snapshot (§30).

**Deliverables this step:** `COMPLIANCE_REPORT_IMMUTABILITY_IR_REPORT.md`,
migration `0015_report_submissions`, immutable-snapshot + IR-loop backend and
frontend changes, and the C4 test additions. Stopping after this report per
step mandate.
