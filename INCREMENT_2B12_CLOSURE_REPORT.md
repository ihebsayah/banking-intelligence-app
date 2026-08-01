# Increment 2B.12 — Frontend: Investigation Queue + Detail — Closure Report

Status: CLOSED. All verification green. No backend files modified.

---

## 1. Executive Summary

Implemented the workbench Investigation surfaces — `/workbench/investigations` (Investigation Queue) and `/workbench/investigations/:investigationId` (Investigation Detail) — with the full canonical state-machine (start / submit / complete / mark-revision-started / approve / return / cancel), the structured findings notebook (findings text, `[{type,id,description}]` references, conclusion), optimistic-lock conflict UX, comments + timeline tabs, unsaved-changes guard, typed API client, error handling, and accessibility. Consumed the implemented backend exactly as built; zero backend changes. Backend regression reconfirmed at **429 passed, 4 skipped**.

## 2. Task Definition & Scope

Frontend-only increment per `increment-2B-implementation-sequence.md` (frozen, authoritative over prompt wording):
- Canonical routes `/workbench/investigations` and `/workbench/investigations/:investigationId`.
- Queue (assigned, status/priority filters, pagination) + detail workspace.
- Findings editor with structured `findings_refs` (`[{ type, id, description }]` — no raw JSON), explicit Save (no server auto-save), local debounced draft persistence.
- Canonical transition labels (frozen contract, not prompt wording): "Start Investigation", "Submit for Review", "Complete", "Mark Revision Started", compliance "Approve & Complete"→"Approve", "Return for Revision", admin "Cancel Investigation".
- Comments + Timeline tabs (included in 2B.12 scope per frontend-workflows §1.4, verified).
- No new state-management/UI library; follow the 2B.11 pattern (useState/useEffect + typed object-literal API modules).
- Out of scope (confirmed): `awaiting_information` transitions (transition-blocked at the authorise layer — no `investigation:transition` for that state, so no UI buttons; rendered read-only, deferred to the IR Inbox increment), evidence file upload (Phase 2D), backend/contract/RBAC changes.

## 3. Route Integration

Added under the business layout in `frontend/src/App.tsx`:
- `/workbench/investigations` → `<InvestigationQueuePage />`
- `/workbench/investigations/:investigationId` → `<InvestigationDetailPage />`

Both wrapped in `ProtectedRoute requiredRole={['analyst','compliance','admin']} requiredPermission="investigation:read_own"` (server remains the enforcer).

## 4. Permission Gating

- Routes gated with `investigation:read_own` via `ProtectedRoute`.
- Per-button gating in the detail action bar uses `useAuth().hasPermission` + `hasRole` (frontend gates prevent unnecessary round-trips; the backend authorise layer is authoritative):
  - Start / Submit / Complete / Mark Revision Started → `investigation:transition` + status-appropriate + assignee
  - Approve / Return for Revision → `investigation:review` + status `submitted`
  - Cancel Investigation → `investigation:assign` + admin role + status NOT IN (completed, cancelled)
  - Findings editing → `investigation:modify_findings` + assignee + status IN (active, returned)
- `awaiting_information` renders read-only with a "resumes from the Information Request workflow (Phase 2D)" guidance note — no transition button, matching the backend state machine.
- Sidebar: added "Investigations" (`FileSearch`) nav item immediately after Alert Queue, role-filtered via the existing `NAV_ITEMS` mechanism.

## 5. Typed API Client — `frontend/src/api/investigationsApi.ts`

Object-literal module mirroring the established `alertsApi` pattern:
- `listAssigned({ status?, priority?, page?, perPage? })` → `GET /investigations/assigned`
- `get(id)` → `GET /investigations/{id}`
- `update(id, { findings_text?, findings_refs?, conclusion?, expected_version })` → `PATCH /investigations/{id}`
- `transition(id, { target_status, return_reason?, expected_version })` → `PATCH /investigations/{id}/transition`
- `cancel(id, { cancel_reason, expected_version })` → `POST /investigations/{id}/cancel`
- `listComments(id, page?, perPage?)` → `GET /investigations/{id}/comments`
- `createComment(id, content, isInternal)` → `POST /investigations/{id}/comments`
- `listTimeline(id, page?, perPage?)` → `GET /investigations/{id}/timeline`

All mutations send `X-Request-ID`; duplicate-sensitive mutations (transition, cancel, createComment) send `X-Idempotency-Key` (crypto.randomUUID with a fallback). No `X-Version` header (the alerts impl sends none and the backend does not require it).

## 6. Type Definitions — `frontend/src/types/investigations.ts`

Wire shapes mirror `services/workbench/schemas/investigations.py`, `comments.py`, `timeline.py` exactly: `Investigation` (incl. `findings_text`, `findings_refs: FindingRef[]`, `conclusion`, `return_reason`, version + timestamps), `InvestigationStatus` (7 canonical states), `InvestigationPriority`, `FindingRef` (`{ type, id, description }`), list/mutation responses (mutations return `{ success, investigation, version }`), `Comment`/`CommentListResponse` (incl. `is_redacted` — internal comments may omit `content`), `TimelineEntry`/`TimelineListResponse` (`old_value`/`new_value`/`metadata` blobs, `occurred_at`).

## 7. Investigation Queue Page — `frontend/src/components/investigations/InvestigationQueuePage.tsx`

Table of assigned investigations: title + linked-alert tag (`alert #xxxxxxxx` or `no linked alert`) + `v{version}`, priority badge, status badge, started/submitted/updated timestamps. Row click (and Enter/Space keyboard) navigates to the detail route.

## 8. Queue Filters

Status + priority selects (`aria-label`-ed), each resetting to page 1, passed to `listAssigned` as `status`/`priority`.

## 9. Queue Pagination

Per-page 50 with prev/next. Following the A1 convention (and the frozen backend shape), "Next" enables when the page is full (`items.length === per_page`); `total` is informational.

## 10. Queue States

- Loading: skeleton rows.
- Empty: "No investigations assigned to you" with a context-aware hint when filters are active.
- Error: structured error panel with Retry (reuses the workbench error parser).

## 11. Investigation Detail Page — `frontend/src/components/investigations/InvestigationDetailPage.tsx`

Header (title, `Investigation · created`), status + priority badges, `v{version}` chip, assignee chip, returned-reason banner (prominent, when `returned`), workflow-guidance strip, description panel, linked-alert panel (navigates to `/workbench/alerts/:alertId`), meta grid (status, priority, assigned to, created by, scope, started/submitted/completed/created/updated), tab bar, action bar, and dialogs.

## 12. Detail Header, Badges & Meta

Uses `BankingHeader` with a Queue back-action. Meta grid renders every field the single investigation shape provides (unlike alerts, investigations have no admin metadata-only DTO). Loading and not-found states render dedicated skeletons/panels with a back-to-queue action.

## 13. Status/State-Sensitive Rendering

Explicit next-action guidance per status (`workflowGuidance`): open → "Start the investigation to begin work on it."; active → "Record findings and a conclusion, then submit for review."; submitted → "Submitted for compliance review."; returned → "Rework the findings and resume the investigation."; completed/cancelled → read-only notes; awaiting_information → Phase 2D note. Submit/Complete buttons additionally require findings/conclusion presence client-side (backend preconditions remain authoritative).

## 14. Action Bar & Per-Action Gating

Conditional rendering per §4. Submit/Complete gate on `hasFindings` / `hasConclusion`; Approve/Return appear only for reviewers on `submitted`; Cancel only for admins with `investigation:assign`. The bar renders nothing when no action applies (terminal states).

## 15. Analyst Transition Actions

- **Start Investigation** (`open` → `active`): inline button, optimistic-lock safe, disable-while-acting.
- **Submit for Review** (`active` → `submitted`): confirmation dialog that explicitly states the findings become review-oriented and that this is a submission for review, not a final compliance approval (matches the frozen submission semantics).
- **Complete** (`active` → `completed`): confirmation dialog; requires findings + conclusion.
- **Mark Revision Started** (`returned` → `active`): inline button; resumes and clears the return reason on the server.

## 16. Compliance Review Actions

- **Approve** (`submitted` → `completed`): confirmation dialog; the reviewer's final approval closes the investigation.
- **Return for Revision** (`submitted` → `returned`): dialog requiring a return reason, which is surfaced prominently to the analyst on return.

## 17. Admin Cancellation

Admin-only (`investigation:assign` + admin role) `POST /investigations/{id}/cancel` dialog requiring a cancellation reason, with an audited/irreversible notice (not deleted; moves to `cancelled`; linked alert unaffected). Terminal statuses hide the action.

## 18. Optimistic-Lock Conflict UX (409)

Any 409 (`VERSION_CONFLICT` / `INVALID_TRANSITION` / `IDEMPOTENCY_MISMATCH` / `APPROVAL_EXECUTED`) surfaces the amber banner "Investigation was updated by someone else. Your unsaved changes are preserved — review and re-save." with a Refresh button. The dialog closes, a background refetch pulls fresh server state, and the banner persists until the user explicitly clicks Refresh. Critically, the FindingsEditor does **not** clobber unsaved local edits on refetch (dirty detection is computed against the latest server shape; the draft is only reset after a successful Save). 409s are also handled inside the editor directly (Save → conflict → parent banner).

## 19. Findings Editor — `frontend/src/components/investigations/FindingsEditor.tsx`

Notebook panel: findings textarea, structured references list (type / id / description inputs with add/remove), conclusion textarea. Save button is the single write path (no server auto-save) and posts `findings_text` + `findings_refs` + `conclusion` + `expected_version`; disabled when not dirty or not editable. Dirty detection compares the draft against the latest server shape (field-wise + reference-wise). Read-only view (disabled fields + "Read-only view" note) for non-editors (e.g. compliance reviewers, non-assignees, terminal statuses). A success status message ("Findings saved.") appears after save.

## 20. Unsaved-Changes Guard

The app uses a non-data `BrowserRouter`, so `useBlocker` is unavailable (verified: it requires a data-router context and throws otherwise). Guard implemented as: a `beforeunload` listener warns on tab close when dirty, and the page's own navigation actions (Queue back-action, linked-alert panel) confirm via `window.confirm` before leaving. This covers the page's explicit escape routes without a shell/router redesign.

## 21. Comments Tab — `frontend/src/components/investigations/CommentsTab.tsx`

Post form (comment textarea; "Internal comment (visible to compliance only)" checkbox gated on `comment:view_internal_content`; otherwise a visibility note) → `POST /comments` (idempotency-keyed), then refetches page 1. List renders author id, timestamp, Internal/Redacted chips, and `content ?? 'Internal comment — content restricted in this view.'` (CommentMetadataView shape). Paginated 50/page with prev/next.

## 22. Timeline Tab — `frontend/src/components/investigations/TimelineTab.tsx`

`GET /timeline` (`occurred_at` ascending, 50/page). Renders `investigation.*` event types humanised (e.g. "status changed"), a delta summary when `old_value`/`new_value` contain status changes ("status active → submitted"), and the actor + timestamp. Empty and loading states included.

## 23. Error Handling

Central `parseInvestigationError` (`frontend/src/components/investigations/investigationErrors.ts`) maps status + `error` code to kinds: conflict, forbidden, not_found, validation, service_unavailable, unknown — each with an actionable message (e.g. `DB_UNAVAILABLE`/503 → "Service temporarily unavailable"). 401 is handled by the existing `apiClient` interceptor. 403/404 render a not-found panel with a back-to-queue action. 422 surfaces the validation message in the relevant dialog/editor.

## 24. Idempotency & Trace Headers

`X-Request-ID` on every mutation (update, transition, cancel, createComment); `X-Idempotency-Key` on transition, cancel, and createComment (dedupe-safe against double-submit / network retry, matching the backend idempotency store).

## 25. Accessibility & Responsive

- Tabs use `role="tablist"/"tab"`/`aria-selected`/`aria-controls` and labelled tab panels; keyboard focusable via native buttons.
- Modal shell reused: `role="dialog"`, `aria-modal`, `aria-labelledby`, Esc-to-close, overlay-click close, scroll-lock.
- Form fields have explicit `<label>`s; queue selects, pagination buttons, and ref remove buttons have `aria-label`s; error/success regions use `role="alert"` / `role="status"`.
- Responsive: queue table scrolls horizontally on small screens; filter bar and action bar wrap; meta grid collapses 3→2→1 columns; badges/actions wrap.

## 26. Frontend Tests + Production Build

- Baseline: **34 passed (6 files)**; production build **passed**.
- After 2B.12: **66 passed (9 files)**, +32 new tests:
  - `investigationsApi.test.ts` — 10 tests (query params + defaults, get, update payload with structured refs, transition with/without return_reason, cancel, comments list/create, timeline list, header presence).
  - `InvestigationQueuePage.test.tsx` — 5 tests (render + badges + linked-alert tag, empty state, filter→refetch, error + retry, row navigation).
  - `InvestigationDetailPage.test.tsx` — 17 tests (render fields/badges/version/linked alert, not-found + back-to-queue, start, submit dialog with review-orientation copy, complete with conclusion, hidden actions without findings, reviewer approve, reviewer return with reason, no review actions without `investigation:review`, returned banner + resume, admin cancel with reason, non-admin cannot cancel, findings edit + save payload, read-only findings for reviewer, 409 conflict banner + refetch, comments tab, timeline tab).
- Production build: **passes** (tsc + vite build). The only build output warnings are the pre-existing chunk-size advisory.
- `npm run lint`: no errors or warnings introduced by this increment's files (3 pre-existing errors remain in unrelated `DebugDashboard.tsx`).

## 27. Backend Regression

Backend untouched (`git status` shows frontend-only files). Core regression reconfirmed at the same command as the 2B.11 baseline:
- `cd services && python3 -m pytest shared/tests workbench/tests -q` → **429 passed, 4 skipped** (identical to baseline).
- Investigation/comment/timeline/information-request backend suites all green; no contract drift.

## 28. Out of Scope & Next Steps

- Out of scope: `awaiting_information` transition UI (backend has no `investigation:transition` for that state — read-only render + Phase 2D note), evidence file upload (Phase 2D), notifications surface, WS live push, approval queue, any backend/contract/RBAC change.
- Next canonical task: the Information Request (IR) Inbox increment (unlocks `awaiting_information` lifecycle UI), then the Case Workbench and comments/timeline enhancements for cases.
- Documented, decision-bound points (frozen backend, no changes): `awaiting_information` is terminal for the analyst until the IR increment (§4/§13); `useBlocker` unavailable under the non-data `BrowserRouter`, so the unsaved guard is `beforeunload` + explicit-action confirm (§20); findings preconditions (findings/conclusion) are gated client-side for UX with the backend remaining authoritative (§13/§15).
