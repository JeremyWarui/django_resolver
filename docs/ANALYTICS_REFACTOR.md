# Analytics & Reporting Refactor — Working Doc / Handoff

> **Purpose:** persistent progress tracker so this multi-phase refactor can resume across
> sessions. Full approved plan also lives at `~/.claude/plans/tidy-leaping-pudding.md`.
> Update the **Progress** checklist as work lands.

## Goal (one line)
Kill duplication in analytics/reporting on both backend and frontend by treating **KPIs as
scope-invariant** (one metric engine over `scoped_ticket_qs(role)`) and each **role view as a
config** (scope + default group_by + visible KPI set), then add an **insights layer** and reuse
the **Admin Dashboard UI** as the canonical template across roles.

## Two governing principles
1. **KPIs are scope-invariant** — defined once, computed over `scoped_ticket_qs(user, role)`.
   Only the input queryset, the `group_by` dimension, and the visible KPI set change by role.
2. **A role view = (scope filter) + (default group_by) + (visible KPI set)** — a small config
   object, not a bespoke page.

## Key decisions (locked)
- **Range:** user-selectable, **defaults to 30 days**, selection flows end-to-end identically
  (dashboard, series, breakdown, AND report Summary sheet). Remove the hidden 30d override on the
  Summary sheet — 30d is a default only.
- **Insights** live in a **separate** `apps/analytics/insights.py` (not folded into `aggregate()`).
- **Scope of v1:** everything incl. insights (recurrence/root-cause, bottleneck, sla-leak,
  capacity, csat-driver).
- **Admin Dashboard is the canonical UI template** (layout/spacing/charts/tables/ticket cards);
  reused across roles, data varies by scope.
- **Manager** report = + insights + facilities. **HOD/HOS** = + facilities + total ticket-flow
  (stacked bar by status). **Technician** = dedicated own-performance report (NOT the org
  template). **StatCards** keep the existing `StatCardsRenderer`/`statCardsConfig` design system.
- **Stacked ticket-flow chart does not exist yet** — add stacked support to `AppBarChart`.
- **Typosquat dep:** remove `django-restframework==0.0.1` from `requirements.txt`.

## Per-role lens
| Role | scope | default group_by | comparison | extra report sections |
|---|---|---|---|---|
| admin | all | department | yes | full template (reference) |
| manager | own dept (all campuses) | campus_department | yes | insights + facilities |
| hod | own campus_department | section | yes | facilities + ticket-flow (stacked) |
| hos | own section(s) | technician | yes | facilities + ticket-flow (stacked) |
| technician | assigned sections | time (trend) | no | own-performance only |
| user | own tickets | status | no | personal status view |

## Environment / how to run
- Python venv: **`.venv/`** in this repo. Use `.venv/bin/python`, `.venv/bin/pytest`, `.venv/bin/pip`.
- Tests: `.venv/bin/pytest -q` (in-memory SQLite). Prod/Neon = PostgreSQL.
- **Portability:** keep analytics DB-agnostic (no `percentile_cont`, no `distinct(*fields)`, no raw
  JSON ops); reduce `accumulated_pause` DurationField math in Python; validate new analytics on a
  real Postgres once before shipping.
- Frontend: `/home/jeremy/Desktop/portfolio/Resolver/client/` — `npm run build` (tsc) must be clean.

## Progress (update as you go)
- [x] **Baseline (2026-06-04):** `319 passed, 1 failed, 1 xfailed`. The 1 failure is
      **pre-existing & unrelated**: `tests/test_phase2.py::test_create_service_category`
      (`IntegrityError: NOT NULL constraint failed: catalog_servicecategory.default_priority_id`
      — test creates a ServiceCategory without its required `default_priority`). Treat as known
      baseline, NOT a regression. xfail = `test_phase10::test_cover_user_can_switch_role`.
- [x] **Phase 1 — shared helpers (no behaviour change)** ✅ DONE (138 targeted tests pass)
  - [x] `apps/common/time_windows.py` :: `active_window_q(now)` + `is_window_active()` — replaced
        `scope.py::_active_q` + `escalation.py::_build_active_q`; `RoleAssignment.is_active()` reuses it.
  - [x] `apps/common/roles.py` :: `resolve_role(request)` (with DB fallback) — `get_request_role`,
        `BaseAnalyticsView.get_role`, `GenerateReportView._get_role` all delegate to it.
  - [x] `apps/analytics/role_config.py` :: `ROLE_VIEWS` + `get_role_config` + `resolve_group_by`.
  - [x] `manage.py check` clean; targeted pytest green.
- [x] **Phase 2 — extend `aggregate()`** ✅ DONE (`apps/analytics/services.py`; 30 analytics tests pass)
  - [x] New metrics: unassigned, aging_buckets, pause_total/avg_seconds, ever_paused/currently_paused,
        ticket_flow (status variants), csat_satisfied_pct, rating_histogram.
  - [x] New group_bys via one generic `_group_by_generic` + `_GENERIC_GROUP_BY` map: department,
        section_type, service_category, service_item, priority, facility_type, facility, status; plus 'time'.
  - [x] Unit tests: `tests/test_phase7.py::TestExtendedMetrics` (6).
- [x] **Phase 3 — `apps/analytics/insights.py`** ✅ DONE :: `compute_insights(qs, date_range, enabled)`
  - [x] recurring_fault, bottleneck, sla_leak, capacity, csat_driver. Tests: `TestInsights` (5).
- [x] **Phase 4 — collapse endpoints + fix reports** ✅ DONE (39 analytics tests pass)
  - [x] `AnalyticsView` → `{scope,range,headline,series,breakdown,ticket_flow,demand,insights}`;
        added `GET /api/v1/analytics/` (name="analytics"); old 9 routes kept as shims.
  - [x] `report_views.py`: `_report_date_range` helper; Summary uses same window as data sheets
        (no 30d force); Summary p50/p90 from `aggregate()`; technician sheet N+1 killed (one
        grouped query) + uses `ACTIVE_STATUSES`.
  - [x] Tests: `test_resolve_group_by_fails_closed`, `TestUnifiedAnalytics`, `TestReportRange`.
- [~] **Phase 5 — frontend unification** (tsc clean, exit 0)
  - [x] `AnalyticsEnvelope` + helper types in `types/analytics.types.ts`; `getAnalytics()` fetcher;
        `useAnalytics()` hook.
  - [x] Stacked support in `components/shared/data/AppBarChart.tsx` (`stacked` prop, recharts stackId).
  - [x] `features/shared/AnalyticsView.tsx` (admin template: stat cards → charts → stacked ticket-flow
        → breakdown table → facilities → insights; sections toggled by `config/analyticsRoles.ts`).
  - [x] HOD/HOS/Manager ReportsPage → thin wrappers over `<AnalyticsView role=.. />` (forks deleted);
        Technician keeps its perf report.
  - [x] `npm run build` (tsc + vite) clean — app builds end-to-end.
  - [x] **Phase 5 polish (2026-06-04, signed off):**
        - Migrated live bespoke `ManagerStatsCards` + `TechnicianStatsCards` onto `StatCardsRenderer`.
          The dead configs `MANAGER_ORGANIZATION_STATS` / `TECHNICIAN_PERSONAL_STATS` (nothing read
          them; they targeted a STALE `data.department.*` / `data.personal.*_count` shape) were
          REPURPOSED to the actual live shapes: Manager now reads `live_status_distribution ||
          status_distribution` (Total/Open/Resolved/Pending/Escalated, Admin-style); Technician reads
          the flat `counts` prop (New Work/Active Jobs/On Hold/Finished). No visual change.
        - Deleted dead `HODStatsCards` + `SectionHeadStatsCards` components + barrel exports (were
          barrel-only refs). Their configs remain (still referenced by STAT_VIEWS/STAT_DEFINITIONS maps).
        - **Decoupled technician stat cards from table filtering** (per user): removed `onCardClick`
          from `TechTickets` → `TechnicianStatsCards`; stat cards are now read-only overview only.
          FilterPills remain the sole ticket-table filter. (StatCards = overview; FilterPills = table.)
        - `config/roleNav.ts` + generic `RoleDashboardLayout` were ALREADY in place (HOD/HOS/Manager
          layouts already consume them); fixed a latent `defaultRole: string` → `UserRole` type error
          that incremental tsc had been masking.
        - `npm run build` (tsc -b + vite) clean.
  - [x] **StatCards system unification (2026-06-05, signed off):** rule = **homepages → StatCards
        (role-scoped), Analytics pages → KPI cards**.
        - Extracted a shared `statusOverviewStats(idPrefix, totalDescription)` factory in
          `statCardsConfig.ts` (canonical Total/Open/Resolved/Pending/Escalated from
          `live_status_distribution`, hoisted `liveCount`). `MANAGER_ORGANIZATION_STATS`,
          `HOD_DEPARTMENT_STATS`, `SECTION_HEAD_PERSONAL_STATS` are now one-line factory calls —
          killed ~250 lines of stale per-role card defs (the old HOD/SH/Manager configs read
          `data.department.*`/`data.personal.*` shapes nothing populated).
        - Recreated `HODStatsCards` + `SectionHeadStatsCards` as thin `StatCardsRenderer` wrappers
          (prop-driven: take the role-scoped `/analytics/overview/` payload). Re-added barrel exports.
        - **Gap A** — `HODDashboard` + `HOSDashboard` now render the StatCards row at the **top**
          (role-scoped via `useHODDashboard`/`useSectionHeadDashboard`); removed the redundant
          "Workload" `KPICardGrid`. Kept the "Health Overview" KPI strip below (SLA/CSAT/NetFlow/
          Reopen — has trend %, no StatCard equivalent) — FLAGGED for user: move to analytics if a
          pure StatCards-only homepage is wanted.
        - **Gap B** — `HODAnalyticsPage` + `HOSAnalyticsPage` gained the same StatCards summary at
          top (admin/manager analytics already had one) so all four analytics pages match.
        - `KPICardGrid` now used only on Analytics/Report pages (correct). `npm run build` clean.
        - RUNTIME TODO: confirm backend `/analytics/overview/` populates `live_status_distribution`
          for HOD/HOS scope (Admin/Manager already proven).
  - [x] **500 on `performance/sections` fixed (2026-06-05):** root cause = `PerformanceSectionsView`
        (and `PerformanceCampusDepartmentsView`) called the full `aggregate()` (**44 SQL queries,
        ~13–15s against remote Neon**) just to return a 1-query breakdown; 3 concurrent fires blew
        past a timeout → 500 (~18–20s in the browser console). Added `services.breakdown(scoped_qs,
        date_range, group_by)` — builds the same created_at window and dispatches to the group-by
        helper only. Both views now use it: **44→1 query, ~13s→0.25s**, output byte-identical
        (verified). 40 analytics tests pass.
        **Update (2026-06-05):** `PerformanceTechniciansView` also fixed — extracted
        `services.technician_load(scoped_qs)` (live open-load, 1 query; `aggregate()` reuses it) and
        the view now uses `technician_load()` + `breakdown(..., "technician")`: ~24→**2 analytics
        queries**, output verified identical. All three Performance endpoints are now lightweight.
  - [x] **`aggregate()` query batching (2026-06-05):** cut **44 → 23 SQL queries** (~48% fewer
        round-trips — the win that matters on remote Neon). Folded ~19 independent scalar `.count()`
        calls (open_backlog, created/prior_created, resolved/prior_resolved, resolution-SLA total/met
        ×2, at_risk, breached, escalated window+live, unassigned, currently_paused, 4 aging buckets)
        into ONE conditional-`Count('id', filter=Q(...))` pass over `scoped_qs` — safe because every
        predicate is a direct Ticket column (no join fan-out). Also folded response-SLA 4→2 (FILTER
        over the Subquery-annotated `first_response_at`, validated to match) and CSAT `satisfied`
        into `csat_agg`. Output value-identical (verified). Full suite: **335 passed, 1 xfailed, 1
        pre-existing catalog failure** = baseline, zero regressions. Speeds up EVERY `aggregate()`
        caller: all dashboards, `/analytics/overview/` (incl. new HOD/HOS StatCards), report Summary.
        Remaining ~23 are inherently-separate GROUP BYs (distributions ×5, demand ×4), percentile
        row-fetches ×3, reassignment/reopen Exists-counts, technician_load, csat/prior — left as-is.
  - [ ] **STILL DEFERRED (needs sign-off — riskier, touches working typing):**
        - Remove legacy `as any` (`ReportsPageEnhanced.tsx:43`) / `as unknown as` api aliases
          (`lib/api/analytics.ts:84-93`, `HODDashboard.tsx:76`, `HOSDashboard.tsx:66`) —
          these are legacy admin/dashboard paths, not the new envelope code.
- [x] **Phase 6 — breach logging + dep cleanup** ✅ DONE
  - [x] Rewrote `check_sla.py` against `resolution_due_at` (pause-aware, excludes paused) →
        idempotent `TicketLog(event_type="sla_breach")` + WS emit. Test: `TestSLABreachCommand`.
  - [x] Removed `django-restframework==0.0.1`; uninstalled from `.venv`; `rest_framework` imports
        fine; `manage.py check` clean.

## Verification status (2026-06-04)
- **Backend:** `335 passed, 1 failed (pre-existing catalog test), 1 xfailed` — +16 new tests vs the
  319 baseline, no regressions. `manage.py check` clean.
- **Frontend:** `npm run build` (tsc -b + vite) clean, exit 0.
- **New frontend files:** `src/hooks/analytics/useAnalytics.ts`, `src/lib/api/analytics.ts::getAnalytics`,
  `src/config/analyticsRoles.ts`, `src/features/shared/AnalyticsView.tsx`, `AnalyticsEnvelope` types.
  HOD/HOS/Manager `*ReportsPage.tsx` are now thin wrappers; `AppBarChart` gained `stacked`.

## Key file references (current state)
- `apps/analytics/services.py:190` `aggregate(scoped_qs, date_range, group_by=None)`; return dict
  `:512-561`; group_by helpers `:86-186`; `_percentile` `:64`; `ACTIVE_STATUSES` `:20`;
  `resolve_date_range` `:27`.
- `apps/analytics/views.py` — 9 views; `BaseAnalyticsView.get_role` `:28`; OverviewView `:88`
  (technician dual-scope `:96`).
- `apps/analytics/report_views.py` — `_sheet_summary` `:112` (30d force `:120-121`);
  `_sheet_technician_performance` `:246-307` (N+1); `_get_role` `:450`; `_base_qs` `:76`.
- `apps/analytics/urls.py` — 9 analytics routes + 2 report routes.
- Active-window dupes: `apps/tickets/services/scope.py:80`, `apps/sla/services/escalation.py:52`,
  `apps/accounts/models.py:141`.
- Role-extraction dupes: `apps/common/permissions.py:4` (canonical, has DB fallback).
- Frontend forks: `src/features/{hod,hos,manager,technician}/*ReportsPage.tsx`.
- Frontend template refs: `src/features/admin/Dashboard/DashboardLayout.tsx`,
  `src/features/admin/OrganisationAnalytics.tsx`, `src/features/admin/Reports/ReportsPageEnhanced.tsx`.
- Shared UI primitives: `src/components/shared/data/` (ChartCard, AppBarChart, AppPieChart,
  TicketVolumeChart, DataTable, StatCards/StatCardsRenderer, KPICardGrid, MetricCard) +
  `src/features/admin/Dashboard/FacilityChart.tsx`.
- StatCards config: `src/constants/statCardsConfig.ts` (STAT_VIEWS `:792`, STAT_DEFINITIONS).

## Out of scope (deferred per user)
CI/CD, observability/Sentry, Redis cache, Celery, Docker, security headers. Escalation-command
consolidation flagged for later.
