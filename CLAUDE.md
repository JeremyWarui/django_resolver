# CLAUDE.md

> **Kenya School of Government — Multi-Campus Service Desk** · Django 6.0 · DRF 3.16 · PostgreSQL · JWT + Channels
> SOT: `service-desk-implementation-plan.md` (domain invariants §2.3, API surface §5, corrections §11). Frontend lives at `/home/jeremy/Desktop/portfolio/Resolver/client` (separate repo, NOT nested here).

**Response style: be terse.** Don't restate code you just wrote, don't echo file contents back, don't end with summaries unless asked. Short answers over structured reports.

## Commands

```bash
pytest --create-db                      # after model changes
python manage.py process_auto_escalations [--dry-run --verbose]

# Fresh schema (full reset, no legacy backfill — SoT §8):
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
python manage.py makemigrations && python manage.py migrate
SEED_DEFAULT_PASSWORD='<demo password>' python manage.py seed_full
# seed_full: idempotent (get_or_create), aborts without SEED_DEFAULT_PASSWORD.
# Seeds campuses/departments/sections/users/roles, catalogue, priorities,
# escalation rules, 18 facilities, 30 demo tickets across 2 weeks.
```

Frontend e2e: `npm run test:e2e` (Playwright, from the client repo).

## Architecture

One Django app per domain in `apps/` (accounts, org, tickets, catalog, sla, facilities, analytics, common, realtime); config in `resolver/`. Routing: `resolver/urls.py` → `resolver/api_urls.py` → `apps/<app>/urls.py` → views → **services** → models. Views never mutate Ticket directly — always through a service (e.g. `TicketService.update_status()`).

### Scope enforcement (critical)

All reads go through `scoped_ticket_qs(user, role)` in `apps/tickets/services/scope.py`. Scope derives server-side from the JWT role claim — **never from client params** — and fails closed (`Ticket.objects.none()` if unresolvable). Per role: Admin = all; Manager = departments they manage; HOD = own campus-department + active covers; HOS = own section(s) + covers; Technician = assigned sections (`SectionTechnician`); Requester = own tickets. Traverse `section__campus_department__…` (Ticket has no `campus_department` field). Honour `RoleAssignment.is_active()` (cover windows). Every scope boundary needs a negative test.

## Frontend rules

- `features/<role>/` pages; shared role-parametrized views in `src/features/shared/`: `RoleDashboardView`, `RoleAnalyticsView`, `RoleReportsPage` (Admin is canonical; Manager pages are thin wrappers; HOD/HOS still on older `AnalyticsView.tsx` — migration pending). Self-fetching scoped data components in `src/components/shared/data/`; prefer extending these over per-role re-implementations. Analytics hooks accept `{ enabled }` for role-gated blocks.
- **StatCards vs KPI cards — don't mix:** StatCards = 5-card overview strip on role homepages only (`statCardsConfig.ts` → `RoleStatsGrid` → `MetricCard`); read-only, role-scoped, **never wired as table filters** (that's FilterPills' job — no icons, do filter). KPI cards (`KPICardGrid`/`KPICard`) = analytics/report pages only, never homepages.
- Frontend role checks (`useAuth().user.role`) are UI convenience only; the backend enforces scope. Every chart/table renders the caller's server-derived scope — pick the role-appropriate endpoint, never pass scope params.
- Ticket table filter dropdowns come from `GET /tickets/filter-options/` via `useTicketFilterOptions()` — not the `externalTechnicians`/`externalUsers` props.

## Analytics & reports

- Edit `apps/analytics/services.py::aggregate()` for metric changes, not individual endpoints. It runs a single conditional-`Count` pass (direct Ticket columns only, no join fan-out).
- **Perf:** breakdown-only endpoints must NOT call `aggregate()` — use `breakdown(scoped_qs, date_range, group_by)` or `technician_load(scoped_qs)` (live, no date window). Calling the full core here previously caused 500s/timeouts on Neon.
- Reports: `apps/analytics/report_views.py` (`/reports/types/`, `/reports/generate/` → styled .xlsx: Summary sheet + data sheets). Role visibility mirrored in `GenerateReports.tsx`. Summary sheet always uses 30-day window even on "all time".
- Audit log: `AdminAuditLogView` (`/admin/audit-log/`), admin-only (`is_staff`), TicketLog is append-only/immutable. `AuditLogSerializer` is a plain `Serializer` by design.

## Key invariants (SoT §2.3 R1–R17, §3.2a, §3.8)

1. `RoleAssignment` is the role source of truth — never read `User.role` directly.
2. Ticket holds only intrinsic state — audit in `TicketLog`, escalation level in `Ticket.current_level`.
3. Paused tickets (`pending`) freeze the SLA timer — never count toward breached/at-risk (R9).
4. Escalation is structural (Technician → HOS → HOD), not configurable workflow.
5. Every user can raise tickets; routing derives from `service_item` + `requester_campus`, not the requester's role.
6. Role cover is time-boxed (`is_primary=False` assignment); scope reverts when it ends.

## Gotchas

- **Ticket numbers:** allocated via `TicketSequence.allocate(campus_department)` under `select_for_update`. Never parse `ticket_no` to generate the next one (raced + string-ordering bug). Gaps are fine. Tests: `tests/test_ticket_sequence.py`.
- **IDOR guard:** every `/tickets/{pk}/...` action view fetches via `get_ticket_for_request_or_403()` (never bare `get_object_or_404`). `allow_requester=False` / `staff_only=True` where applicable. New sub-endpoint isn't done without an out-of-scope 403 test in `tests/test_ticket_action_scope.py`.
- **Reference-data query params must filter (C15):** `?campus=` / `?department=` are wired in `get_queryset()` overrides (`apps/org/views.py`). New scoping param ⇒ wire the filter + negative test in the same commit.
- **Primary RoleAssignment replacement demotes, never deletes (C16):** `UserRoleAssignmentListCreateView` demotes the old primary (`is_primary=False`, kept for audit) inside `transaction.atomic()`.
- **`ServiceItem.default_priority`** is a nullable per-item override (written via `default_priority_id`); ticket creation falls back to the category's priority. Only set for genuine outliers.
- **FacilitySerializer** ticket counts use Subquery on `TicketLocation.facility` (FK has `related_name="+"`); `status` is derived (`maintenance` if open tickets else `operational`).
- No feature is complete without tests and SoT/CLAUDE.md updates.
