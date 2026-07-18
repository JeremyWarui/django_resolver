# Service Desk — QA Findings & Fix Specification (User Testing, July 2026)

**Scope:** Backend = this repo (`django_resolver`). Frontend = `/home/jeremy/Desktop/portfolio/Resolver/client` (separate repo).
**Ground rules (from CLAUDE.md):** every fix that touches a scope boundary or ticket action needs a negative (403) test; views never mutate `Ticket` directly — go through services; no feature is complete without tests + SoT/CLAUDE.md updates.

**Reuse-first directive (strict):** before implementing anything in this spec, search the codebase (both repos) for an existing implementation of the same concern — services, serializers, shared components, hooks, WS invalidation, test fixtures — and extend it rather than building a parallel one. Only write something new when a deep search confirms nothing exists, or when what exists genuinely needs refactoring (say so in the commit). This applies even if it requires exhaustive searching — fan out subagents to sweep the codebase if needed. The "verified architecture facts" below are the product of exactly this kind of sweep; treat unverified assumptions the same way before coding against them.

**Verified architecture facts referenced below** (do not re-derive):

- Status transitions live in one place: `apps/tickets/services/lifecycle.py` `ALLOWED` map. Frontend mirror: `client/src/features/technician/StatusUpdateModal.tsx` (`NEXT_STATUSES` map, ~line 27).
- "Technicians" everywhere in the UI = `SectionTechnician` link rows, not a table of users with role technician. Technicians page reads `GET /technicians/` (`ScopedTechnicianRosterView`, `apps/org/views.py:178`); the Assign dialog reads `GET /sections/{pk}/assignable-technicians/` (`apps/org/views.py:247`).
- Realtime already exists end-to-end: backend emits (`apps/realtime/ws_utils.py`), frontend maps WS events → React Query invalidations in `client/src/lib/ws/wsClient.ts` (`handleWsEvent`). **Reuse this; do not add polling or a second mechanism.**
- Ticket list endpoint already supports `?assigned_to=` (`apps/tickets/views.py:329`).
- `GET /tickets/{pk}/comments/` + POST live in `TicketCommentListCreateView` (`apps/tickets/views.py:186`). There is currently **no** server-side gating on who may comment or in which status — scope check only.

---

## A. Admin

### A1. Newly created technician missing from Technicians page and Assign dialog

**Observed:** Technician created from Admin → Technicians appears in Users but not in the Technicians table, and therefore not in the Assign dialog.

**Expected:** a technician created from the Technicians page must reflect in **both** tables — Users (already works) **and** Technicians — immediately after creation, and consequently appear in the Assign dialog for tickets in their section(s).

**Actual mechanics (verified):** `TechnicianForm.tsx` does two sequential calls: `createUser` (creates a plain user with a `role='user'` primary assignment) then `createRoleAssignment(role='technician', is_primary=true, section_id=…)`. The backend role-assignment view syncs `SectionTechnician` via `_sync_org_scope` (`apps/accounts/views.py:139`). Both the Technicians page and the Assign dialog read `SectionTechnician`. So the symptom means the **second call failed or its side effect didn't land** — and `TechnicianForm.tsx` swallows that failure: it catches the role error, shows a toast, and still calls `onSuccess` and closes (lines ~239–246), leaving a role-less user that shows up only in Users.

**Fix spec:**
1. Reproduce: create a technician via the UI with devtools open; capture the response of `POST /users/{id}/role-assignments/`. Diagnose why it fails (payload sends `campus_id`/`department_id` alongside `section_id`; check serializer validation in `RoleAssignmentCreateSerializer`).
2. Whatever the cause: make the failure loud — on role-assignment failure the form must NOT report "Technician created" and must keep the dialog open with the error.
3. Prefer making creation atomic server-side: either a dedicated create-technician endpoint or accept that the two-step flow retries cleanly (user exists + role assignment retried from the same dialog).
4. Ensure the Technicians page refetches after successful create (check the page's query invalidation on dialog success).

**Acceptance:**
- [ ] Backend test: `POST /users/{id}/role-assignments/` with `role=technician, is_primary=true, section_id=S` ⇒ `SectionTechnician(user, S)` row exists (may already exist — verify/extend).
- [ ] UI: create technician → appears in Technicians table without manual refresh → appears in Assign dialog for a ticket in section S.
- [ ] Failure path: role-assignment error surfaces in the dialog; no false "created" toast.

---

## B. Ticket lifecycle & technician interface

### B1 + B2d. Comment gating (merged — one policy, enforced server-side)

**Observed:** (a) any technician in the section can comment on tickets not assigned to them; (b) the requester can comment while the ticket is still `open` (unassigned).

**Policy (decided — universal):** commenting is enabled **only after the ticket has been assigned** (`ticket.assigned_to` is set) and while **status ≠ `closed`**. This applies to **every role** — requester, technicians, and supervisors alike; there is no pre-assignment exemption. Among technicians, only the assigned one may comment; supervisors (hos/hod/manager/admin) in scope may comment once assigned.

**Fix spec:**
- **Backend (authoritative):** add the gate in `TicketCommentListCreateView.perform_create` (`apps/tickets/views.py:198`) — reject with 403 (wrong author) / 400 (bad status) before creating. Read access unchanged.
- **Frontend:** disable the comment input with an explanatory hint ("Comments open once a technician is assigned" / "Ticket is closed") in the shared ticket-detail comment component. Enable for the assigned technician and eligible roles only.

**Acceptance:**
- [ ] Negative tests (backend, in the ticket-action scope test module): unassigned same-section technician POST comment ⇒ 403; requester POST while `open` (unassigned) ⇒ 4xx; **supervisor (hos/hod/admin) POST while unassigned ⇒ 4xx**; requester POST once assigned ⇒ 201; assigned technician ⇒ 201; supervisor once assigned ⇒ 201; POST on `closed` ⇒ 4xx for all roles.
- [ ] UI: input disabled states for `open`, unassigned-tech, and `closed`; enabled after assignment.

### B1b. Status updates not gated on assignment (backend gap found during spec review)

**Observed (implied by the original 2a: assigned technician may "comment *and make updates*"):** `TicketStatusView` (`apps/tickets/views.py:119`) fetches via `get_ticket_for_request_or_403(request, pk)` with defaults — no `staff_only`, no assignment check. Any in-scope section technician, **and the requester**, can POST any legal transition; only the UI hides the button.

**Policy (verified against the model):** `Ticket.assigned_to` is a plain FK to the user model — there is no separate technician entity, "technician" is the JWT role claim + `SectionTechnician` membership. The gate is therefore two independent conditions on the caller:
- **Caller's role (from JWT via `get_request_role`) is `technician`:** allowed only if `ticket.assigned_to_id == request.user.id` (the ticket is assigned to *them*). Unassigned or otherwise-assigned section tickets ⇒ 403, view-only.
- **Caller is the requester (`raised_by`):** may only close (`resolved → closed`, the Rate & Close flow) and reopen (`resolved/closed → open` per B2f) their own ticket — no other transitions.
- **Supervisors (hos/hod/manager/admin) in scope:** unrestricted (existing behavior).

**Fix spec:** enforce in `TicketStatusView` (role + assignment + per-role allowed-transition check) before calling `transition_status`. Frontend needs no change (already hides the control for unassigned technicians).

**Acceptance:**
- [ ] Negative tests: same-section technician not assigned to the ticket POSTs a transition ⇒ 403; requester POSTs `in_progress` ⇒ 403; requester close-own and reopen-own ⇒ 200; assigned technician ⇒ 200.
- [ ] Claim (B2a) and assign flows unaffected (they set assignment before/with the transition).

### B2. "Assigned Tickets" page shows all section tickets

**Root cause (verified):** `TechTickets.tsx` calls `useTicketTable({ role:'technician', currentUserId, … })` but never pins the `assigned_to` filter, so it fetches the technician's full JWT scope (= section tickets — which is correct behavior for the *Section Tickets* page, wrong for this one).

**Fix spec:** pass `assigned_to: currentUserId` as a **fixed** (non-user-clearable) param for this page — backend already supports it (`apps/tickets/views.py:329`). Server scope still applies on top, so this is not a security change.
Also fix the stat strip in `TechTickets.tsx` (~line 48): `assigned` count currently includes `open` tickets, which can never be the technician's own.

**Acceptance:**
- [ ] Technician with 0 assigned tickets sees an empty state even when the section has open tickets.
- [ ] Section Tickets page behavior unchanged.

### B2a. New feature: Claim (self-assign) an unassigned section ticket

**Fix spec (backend first):**
- New endpoint `POST /tickets/{pk}/claim/` following the existing action-view pattern: fetch via `get_ticket_for_request_or_403()`, role must be `technician`, and the ticket's section must be one of the caller's `SectionTechnician` sections.
- Guard: ticket must be unassigned and status `open`. Race-safe: `select_for_update` (mirror `TicketSequence`/assign patterns) so two simultaneous claims can't both win.
- Effect: set `assigned_to = request.user`, then drive status `open → assigned → in_progress` **through `transition_status`** (two transitions inside one atomic block) or a dedicated service function that writes both `TicketLog` entries (`assigned` with actor = the technician, then `status_changed`) and emits the existing WS events. Do not mutate status directly in the view.
- **Frontend:** "Claim" button in the ticket-detail dialog, shown only when: viewer is a technician, ticket is in one of their sections, `assigned_to` is null, status is `open`. After success: detail + tables refresh (existing invalidation handles it), comment input becomes enabled per B1.

**Acceptance:**
- [ ] Out-of-scope 403 test in `tests/test_ticket_action_scope.py` (technician from another section claims ⇒ 403) — per CLAUDE.md this is required for any new `/tickets/{pk}/…` action.
- [ ] Claim on an already-assigned ticket ⇒ 4xx; concurrent double-claim ⇒ exactly one winner.
- [ ] After claim: `assigned_to` set, status `in_progress`, ticket appears in Assigned Tickets, timeline shows assigned + status events.

### B2b. Allow `pending → resolved`

**Root cause (verified):** `ALLOWED` map has `"pending": {"in_progress"}` (`lifecycle.py:10`); frontend mirror has the same (`StatusUpdateModal.tsx:30`). This is a **backend + frontend** change, not UI-only.

**Fix spec:** change to `"pending": {"in_progress", "resolved"}` and mirror in `NEXT_STATUSES`.
Dropped from the original ask: offering "Pending" while already pending — it's a no-op, requires a pause reason, and would corrupt SLA pause accounting. Offer exactly **In Progress** and **Resolved**.
Note: the SLA pause-resume block (`lifecycle.py:37-45`) already triggers on any transition out of `pending`, so `pending → resolved` settles `accumulated_pause` and sets `resolved_at` correctly — but add a test proving it (R9: paused time must not count against SLA).

**Acceptance:**
- [ ] Backend test: `pending → resolved` succeeds, pause is settled into `accumulated_pause`, due dates shifted, `resolved_at` set.
- [ ] Modal on a pending ticket offers In Progress + Resolved.

### B2c. Remove "Reopen" from the Rate & Close dialog

Frontend-only. Files: `client/src/features/user/RatingModal.tsx` and/or `client/src/components/shared/ticket/RatingWidget.tsx`. Dialog keeps: rating, rating comment, Close Ticket. The standalone Reopen button on ticket details stays.

**Acceptance:** [ ] no reopen control in the dialog; [ ] standalone Reopen still works.

### B2f. Reopen should restart the lifecycle at `open`

**Root cause (verified):** reopen is modeled as `resolved/closed → in_progress` in the `ALLOWED` map (`lifecycle.py:11-12`), with `event_type="reopened"` detection keyed to that pair (`lifecycle.py:72`).

**Fix spec (backend):**
- `ALLOWED`: `"resolved": {"closed", "open"}`, `"closed": {"open"}`. Update the reopened-event detection to `new_status == "open"`.
- **Clear `assigned_to` on reopen** (required for consistency: `open` is the "unassigned" state — the assign flow and the new Claim guard both assume `open` ⇒ unassigned). Log it in the same `TicketLog` flow.
- **SLA restarts (decided):** on reopen, recompute `response_due_at` / `resolution_due_at` from the reopen time using the same SLA computation used at ticket creation (`apps/sla`), and reset the pause state (`paused_at = None`, `accumulated_pause = 0`). Also clear `resolved_at` / `closed_at` — otherwise `is_breaching` and the analytics resolved-time metrics read a stale resolution on a live ticket. The original breach history stays in `TicketLog`.
- **Frontend:** requester Reopen button callers currently expect `in_progress`; update the ticket-detail reopen action and any status-badge logic.

**Acceptance:**
- [ ] Reopen from resolved and from closed ⇒ status `open`, `assigned_to` null, timeline shows `reopened`.
- [ ] Reopened ticket behaves like new: comments disabled until assigned (B1), claimable (B2a), assignable.
- [ ] Old `resolved → in_progress` direct transition is gone from both maps (or intentionally kept — decide and test either way).

### B2g. Tables and stat cards don't refresh on status change

**Root cause (verified):** the mechanism exists — `handleWsEvent` in `client/src/lib/ws/wsClient.ts` invalidates React Query keys per event — but two gaps:
1. `ticket_resolved` invalidates only `['ticket', id]`, never `['tickets']` ⇒ the requester's table goes stale exactly on the resolve transition (`wsClient.ts:174-179`).
2. Dashboards/stat cards use `['analytics', 'overview', <role>, …]` keys (`client/src/hooks/dashboard/*`), and **no ticket event invalidates `['analytics']`** (only `section_summary` does).

**Fix spec:** in `handleWsEvent`, add `invalidate(['tickets'])` to `ticket_resolved`, and `invalidate(['analytics'])` to `ticket_created`, `ticket_assigned`, `ticket_status_changed`, `ticket_resolved`. No new infra, no polling.
Verify the backend emits to the requester's `user_{id}` channel for every status change (check `emit_ticket_status_changed` / `emit_ticket_resolved` channel targets in `apps/realtime/ws_utils.py`) — if section-only, add the requester channel.

**Acceptance:**
- [ ] Technician resolves a ticket ⇒ requester's table row and stat cards update without refresh (two browsers).
- [ ] Scope preserved: only the requester's own data refetches (invalidation just refetches the caller's scoped endpoints — verify no cross-scope leakage in what's displayed).

### B2e. Comments don't show the author

**Root cause (verified):** `TicketCommentSerializer` returns `author` as a bare PK (`apps/tickets/serializers.py:287-291`) — the frontend has nothing to render. The timeline already renders actors, so a `_UserMinSerializer` exists in the same file.

**Fix spec:** nest `author = _UserMinSerializer(read_only=True)` (or add `author_name`) in the serializer; render header `[avatar/icon] [author name] … [relative time]` above the body in the comment component, matching the timeline's attribution style.

**Acceptance:** [ ] every comment shows author + timestamp; [ ] existing comments (author FK already stored) render correctly — no migration needed.

---

## C. HOD promoted user lands on the HOS interface

**Investigated — the obvious suspects are clean:** the route table (`App.tsx`: `hod → /hod`, `hos → /section-head`), `ProtectedRoute` (exact role match), `ROLE_LABELS` (no swap), the login role→route map, and `RoleAssignmentCreateSerializer` (hod requires campus+department, resolves the right `CampusDepartment`). The frontend role comes from the backend's `active_role` — so the bug is in **which assignment becomes active**, not in routing. Three concrete candidate causes, in likelihood order — reproduce each:

**C-1. Promotion performed via the wrong dialog (most likely).** The Users page has two flows: **Edit User** (creates `is_primary: true` — a real promotion) and the **Role Assignments modal**, which hardcodes `is_primary: false` and a required end date (`RoleAssignmentModal.tsx:65-72`) — it creates *covers only*. An admin "promoting" someone there leaves the HOS primary in place ⇒ user logs in as HOS. This exactly matches the field report.
- Fix: make the distinction impossible to miss — rename the modal's action ("Add temporary cover"), and/or add a "Set as primary role" path for admins in that modal. At minimum, after creating an assignment for a user whose primary differs, show a warning ("This user's primary role is still Head of Section").

**C-2. Demoted primary is still switchable (real authz gap — fix regardless).** C16 demotes the old primary (`is_primary=False`, kept for audit) **without** a `valid_until`. `SwitchRoleView` (`apps/accounts/views.py:108`) only checks `is_active()`, and a null window counts as a standing role ⇒ the demoted HOS assignment passes, and it's also listed in `available_roles` (`serialize_auth_user`) so the frontend role switcher offers it. A user promoted to HOD can therefore still enter — or be silently left in — their old HOS role, with `Section.hos` scope re-derived from the JWT claims.
- Fix: exclude demoted assignments (non-primary AND `valid_until IS NULL`) from `available_roles`, and reject them in `SwitchRoleView` (mirror the `resolve_active_assignment` rule at `jwt_utils.py:123`, which already requires covers to carry a `valid_until`). Negative test: switch-role into a demoted assignment ⇒ 400/403.

**C-3. Stale session — and the "immediate effect" requirement.** Promotion must take effect **immediately**, not just on next login: a user promoted from the default `user` role (or from HOS) to HOD/HOS should be moved to their new interface right away, with the full access of the new role. The mechanism already exists — **reuse it, don't build another**: a primary-role swap fires `emit_role_changed` on commit (`apps/accounts/views.py`, promotion view), the frontend WS handler reacts by forcing a clean re-login (`wsClient.ts` `role_changed` case), and the silent-refresh `roleChanged` flag is the fallback when the socket is down. What to verify/fix:
- The push actually reaches a plain-`user` session (they subscribe to `user_{id}` — should hold since DashboardShell wires the WS for all roles; test it).
- After the forced re-login, the role→route map sends them to the right home (`hod → /hod`, `hos → /section-head`).
- If the WS is disconnected, propagation waits on the next silent refresh — confirm the access-token lifetime keeps that window acceptably short, or tighten it.
If the wrong interface persists even after a **fresh login**, the cause is C-1/C-2, not this.

**Note on the report's framing (corrected):** technician assignment is legitimate for **both** HOS and HOD — only managers cannot assign. Seeing an assign action was therefore not itself evidence of the wrong interface; the defect is purely which role/interface was active. No capability changes to HOS or HOD. One constraint to verify while in here: when an HOD assigns, the candidate list must contain only technicians of the **ticket's section** — the Assign dialog reads `GET /sections/{pk}/assignable-technicians/` keyed by the ticket's section, so this should already hold; add a regression check rather than new logic.

**Acceptance:**
- [ ] Root cause documented after reproducing (which of C-1/C-2/C-3 — possibly more than one).
- [ ] Edit-User promotion HOS→HOD, fresh login ⇒ lands on `/hod`, sees HOD dashboard; `CampusDepartment.head_of_department` updated, old `Section.hos` cleared (verify `_sync_org_scope` did both).
- [ ] **Immediate effect:** promote a logged-in default `user` to HOD (and separately to HOS) ⇒ their active session is interrupted within seconds (WS push) and, after re-login, they land on `/hod` / `/section-head` with full new-role access — no manual logout needed. Repeat with the WS blocked to confirm the silent-refresh fallback propagates within the access-token lifetime.
- [ ] Switch-role into a demoted assignment ⇒ rejected; demoted assignment absent from the role switcher.
- [ ] Regression: active time-boxed covers still switchable within their window; HOS promotion still routes to `/section-head`.
- [ ] HOD assign dialog on a ticket lists only that ticket's section technicians (existing behavior — regression check).

---

## D. Surface captured-but-hidden dialog data (pending reason, resolution note, rating)

All three are already **captured and stored** — none are displayed. Verified storage:
- Pending reason and resolution note both travel as `reason` on `POST /tickets/{pk}/status/` and land in **`TicketLog.reason`** (`transition_status`). The status dialog already *requires* them (`StatusUpdateModal.tsx`: note min 3 chars on every transition; structured reason + optional comment for pending). No capture changes needed.
- Rating + rating comment land in **`TicketFeedback`** (one-to-one with Ticket). But it is **write-only** today: `TicketFeedbackView` is POST-only and `TicketReadSerializer` doesn't include feedback.
- The timeline API already returns `reason` per event (`TicketLogSerializer`, `apps/tickets/views.py:86`), but `TicketTimeline.tsx` never renders it.

### D1. Show pending reason
- **Frontend:** render `reason` under `status_changed` entries in `TicketTimeline.tsx`. While a ticket is `pending`, show an "On hold: <reason>" callout in the ticket detail — derive it from the latest pending transition in the timeline data the dialog already fetches (no new endpoint).

### D2. Show resolution note
- **Frontend:** same timeline rendering covers it (the `resolved` event's `reason`). Additionally show a "Resolution" block in ticket detail when status is `resolved`/`closed` — this is what the requester reads before rating in the Rate & Close dialog (B2c), so include it there too.

### D3. Show rating + rating comment
- **Backend:** expose feedback on reads — nest a read-only `feedback` (`TicketFeedbackSerializer`) in the ticket **detail** serializer (null until submitted). Visibility follows ticket scope; no extra gating needed.
- **Frontend:** on resolved/closed tickets with feedback, show rating stars + comment in the ticket detail (requester and staff views). Extend the shared `RatingWidget`/detail components rather than per-role re-implementations.

**Acceptance:**
- [ ] Pending ticket shows its on-hold reason in detail + timeline.
- [ ] Resolved ticket shows the resolution note in detail, timeline, and the Rate & Close dialog.
- [ ] Submitted rating + comment visible on the ticket detail to requester and staff in scope; absent (not erroring) before submission.
- [ ] Backend test: ticket detail includes `feedback` after submission; list endpoint payload size unchanged (detail-only nesting).

---

## Suggested implementation order

1. **C-2** (authz gap — smallest fix, closes a live privilege-retention hole) and **B1 + B1b** (server-side comment and status-update gating — same authz theme, same test module).
2. **B2f, B2b** — both edit the same `ALLOWED` map + frontend mirror; do together with one test pass over transitions.
3. **B2a** (claim — depends on B2f's `open ⇒ unassigned` invariant), then **B2** (assigned-tickets filter, trivial).
4. **A1** (technician creation) — independent; needs a live reproduction first.
5. **B2g, B2e, B2c** — realtime invalidation + display polish.
6. **D1–D3** — display of captured data (D2 pairs naturally with B2c since both touch the Rate & Close dialog; D3 needs the small serializer change first).
7. **C-1/C-3** — UX hardening of the promotion flow after root cause is confirmed in testing.

Corrections to the draft's ordering rationale: A1 does **not** block the B items (Assign dialog and Claim read `SectionTechnician`, which existing technicians already have); and C is not "isolated routing" — it's active-role resolution, partially fixed by C-2 which should go first, not last.

---

## Resolution log (implementation, July 2026)

All items above are implemented across both repos. Notes on what was actually found:

- **C root cause (documented per acceptance):** the backend accepts the promotion payload and
  `_sync_org_scope` works, and the route table + role→route login map are correct (verified
  `hod → /hod`, `hos → /section-head`). The live defects were **C-1 + C-2 in combination**: an
  admin "promoting" via the Role Assignments modal creates a time-boxed cover (`is_primary=false`),
  leaving the HOS primary active — and even after a real Edit-User promotion, the demoted HOS row
  (non-primary, `valid_until IS NULL`) remained switchable via `POST /auth/switch-role/` and was
  offered in `available_roles`. C-2 is closed server-side (rejected + hidden; negative tests in
  `tests/test_phase6_auth.py`); C-1 mitigated with a post-create warning toast in
  `RoleAssignmentModal` when the cover role differs from the primary. The C-3 immediate-effect
  mechanism (`emit_role_changed` → WS `role_changed` → forced re-login, `jwt_refresh.roleChanged`
  fallback) was verified intact — but a third gap was found on user follow-up: **page reload never
  re-validated the role.** The auth store rehydrates `user` + a still-valid access token from
  localStorage, `useUserData` returned the cached user without any server call, and the
  `roleChanged` refresh check only runs when a request 401s (token expiry, 15 min) — so a promoted
  user who pressed F5 kept the old `user` interface, and with no channel layer (dev without Redis,
  where `emit_ws_event` silently no-ops) the WS push never arrived either. Fixed: `useUserData`
  (mounted by `DashboardShell` for every role) now calls `GET /auth/me/` on dashboard mount and
  forces the role-changed re-login when the server-derived active role differs from the cached one.
  `getProfile()` in `lib/api/auth.ts` was dead code that mis-parsed the `/auth/me/` shape (expected
  a `user` wrapper that endpoint never sends) — rewritten to the real top-level shape.
- **A1:** the backend accepts TechnicianForm's exact payload (regression test
  `test_primary_technician_assignment_syncs_section_technician`) and the Technicians page already
  refetches on success. The real defect was the swallowed role-assignment failure: the form now
  keeps the dialog open on that error, shows it, and remembers the created user id so resubmit
  retries only the role step (no duplicate account).
- **B1/B1b:** enforced in `TicketCommentListCreateView.perform_create` and `TicketStatusView`;
  negative + positive tests in `tests/test_ticket_action_scope.py` (`TestCommentGating`,
  `TestStatusUpdateGating`). CommentThread mirrors the gate with explanatory disabled states.
- **B2a:** `POST /tickets/{pk}/claim/` (`TicketClaimView` + `claim_ticket` service in
  `lifecycle.py`, `select_for_update`); Claim button in `TicketDetailPage`; tests in
  `TestClaimEndpoint` (out-of-section 403, non-technician 403, double-claim 409, log/actor
  assertions). The concurrency guard is the post-lock re-check; a threaded race test was skipped
  because the local suite runs on SQLite where `SELECT … FOR UPDATE` is a no-op.
- **B2b/B2f:** `ALLOWED` map updated; reopen = `resolved/closed → open`, clears `assigned_to`,
  restarts SLA via the new shared `apps/sla/services/due_dates.compute_due_dates()` (also now used
  at ticket creation), clears pause state and `resolved_at`/`closed_at`. `resolved→in_progress`
  removed (tested). Frontend `VALID_NEXT` mirrored; the modal's illegal `assigned→open` option
  (always 400'd server-side) was dropped at the same time. `reopenTicket()` now posts `open`.
- **B2:** `useTicketTable` gained `fixedParams`; TechTickets pins `assigned_to` and the stat strip
  no longer counts `open` tickets as assigned.
- **B2c:** RatingWidget/RatingModal are close-only; the standalone Reopen button remains.
- **B2e:** `TicketCommentSerializer` nests `author` (`_UserMinSerializer`) — CommentThread already
  rendered `author.full_name`, so no frontend change was needed beyond types.
- **B2g:** `handleWsEvent` now invalidates `['tickets']` on `ticket_resolved` and `['analytics']`
  on created/assigned/status_changed/resolved. Backend emit targets verified: both
  `emit_ticket_status_changed` and `emit_ticket_resolved` already include `user_{raised_by}`.
- **D1–D3:** timeline renders `TicketLog.reason` under status events (`note` mapping fixed to stop
  leaking raw `to_value`); ticket detail derives the On-Hold reason and Resolution note from the
  already-fetched timeline (no new endpoint); Rate & Close shows the resolution note; detail API
  nests read-only `feedback` (detail serializer only — list payload unchanged, tested) rendered
  via the shared `RatingStars`.

SoT updated: §4.1 (machine + per-role gate + claim), §4.2 unchanged, §5.1 (switch-role demoted
rule), §5.3 (claim row, comment gate, feedback nesting). CLAUDE.md gotchas updated.
