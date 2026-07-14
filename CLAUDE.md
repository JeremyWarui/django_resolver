# CLAUDE.md

Guide for Claude Code working with this repository.

> **Kenya School of Government — Multi-Campus Service Desk System**  
> Django 6.0 · DRF 3.16 · PostgreSQL · JWT + Channels

This is the **frontend contract** and **build companion** to `service-desk-implementation-plan.md` (the SOT). Read the plan first to understand domain invariants, the phased build, and acceptance criteria; use this file for commands, directory layout, request flow, and frontend guidance.

---

## Commands

```bash
# Backend dev server (http://localhost:8000/)
python manage.py runserver

# Run all tests (coverage included via pytest.ini)
pytest

# Run a single test file
pytest apps/tickets/tests/test_ticket_workflow.py -v

# Run a single test by name
pytest apps/tickets/tests/test_ticket_workflow.py::TestTicketLifecycle::test_create_and_resolve -v

# After model changes — rebuild the test DB
pytest --create-db

# Coverage report in HTML
pytest --cov-report=html

# Linting / formatting
flake8 apps/
black apps/

# Migrations
python manage.py makemigrations
python manage.py migrate

# Fresh schema (no legacy backfill — full reset per SoT §8)
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
python manage.py makemigrations
python manage.py migrate
python manage.py seed_full

# seed_full replaces the three old seeds (seed_reference, seed_org, seed_demo).
# It is idempotent (get_or_create throughout) and seeds:
#   - Priorities, EscalationRules, FacilityTypes, Facilities (18 buildings across 3 campuses)
#   - Campuses (NRB, MSA, KSM), Departments (ADM, HR, ICT), Sections, Users, RoleAssignments
#   - Service Catalogue (6 sections × categories + items)
#   - 30 demo tickets spread across current + previous calendar week

# Run auto-escalation sweep (normally cron; manual: every 5 min in production)
python manage.py process_auto_escalations
python manage.py process_auto_escalations --dry-run --verbose

# Check Django + app setup
python manage.py check
```

---

## Backend architecture

### Single-module structure (Phase 9 onwards)

All models, serializers, views, and services live in `apps/`:

```
resolver/              (Django project config)
├── settings.py
├── urls.py            (includes /api/ → apps.*.urls)
├── asgi.py
└── wsgi.py

apps/                  (all app logic)
├── accounts/          (User, UserProfile, auth, RoleAssignment)
├── org/               (Campus, Department, Section, SectionTechnician, etc.)
├── tickets/           (Ticket, TicketComment, TicketFeedback, TicketLog)
├── catalog/           (ServiceCategory, ServiceItem)
├── sla/               (Priority, EscalationRule, SLAHistory)
├── facilities/        (Facility, FacilityType, TicketLocation)
├── analytics/         (metrics core, role-scoped views, Report generators)
├── common/            (shared exceptions, validators, enums)
└── realtime/          (Channels consumers, WS events)
```

**URL routing:** `resolver/urls.py` includes `/api/` → `resolver/api_urls.py` → each app's `urls.py`.

### Request flow

```
HTTP Request (e.g., POST /api/v1/tickets/)
  ↓
resolver/urls.py       (/api/v1/ → resolver/api_urls.py)
  ↓
resolver/api_urls.py   (includes apps.*.urls)
  ↓
apps/tickets/urls.py   (path("tickets/", views.TicketListView.as_view()))
  ↓
apps/tickets/views/    (HTTP handling, permission checks, serialization)
  ↓
apps/tickets/services/ (business logic, scope validation, state changes)
  ↓
apps/tickets/models/   (ORM, invariant enforcement, state machine)
```

**Key rule:** Views never mutate Ticket directly. Always call a service (e.g., `TicketService.update_status()`).

### Scope enforcement

Every view, analytic, and report inherits scope from the JWT role claim via `scoped_ticket_qs(user, role)` in `apps/tickets/services/scope.py`. **Never filter scope from client params** — derive it server-side and fail closed (return empty queryset if scope can't be resolved).

Scope is **role-specific** (see SoT §1.3, §3.5):

- **Admin:** no filter
- **Manager:** `section__campus_department__department__manager_user == user`
- **HOD:** own campus department + active cover assignments
- **HOS:** own section(s) + active cover assignments
- **Technician:** assigned sections via `SectionTechnician`
- **Requester (any user):** own tickets only

---

## Frontend architecture

### File structure

```
Resolver/client/src/
├── features/
│   ├── admin/              (Admin role pages: AdminDashboard, SLARulesPage, etc.)
│   ├── manager/            (Manager role pages: ManagerDashboard, ManagerReportsPage)
│   ├── hod/                (HOD role pages: HODDashboard, HODReportsPage)
│   ├── hos/                (HOS role pages: HOSDashboard, HOSReportsPage)
│   ├── technician/         (Technician role pages: TechnicianDashboard, TechnicianReportsPage)
│   └── requester/          (Universal requester: MyRequests, TicketCreate)
├── components/
│   ├── ui/                 (shadcn/ui: Button, Card, Dialog, etc.)
│   ├── shared/             (MetricCard, DateRangeSelector, etc.)
│   └── layouts/            (MainLayout, SidebarNav, etc.)
├── hooks/
│   ├── useAuth.ts          (current user, role, permissions)
│   ├── useTicket.ts        (CRUD + list with pagination)
│   └── analytics/          (usePerformanceTechnicians, usePerformanceSections, etc.)
├── lib/
│   ├── api/                (apiClient, TicketAPI, ReportsAPI, etc.)
│   └── utils/              (formatters, validators)
├── types/
│   └── index.ts            (shared TypeScript types)
└── App.tsx
```

### Authentication & context

JWT access token stored in `localStorage` (or sessionStorage per `useAuth` config). `useAuth()` hook reads user context: `{ user: {id, email, username, role, campus_id}, token }`.

**Every API call includes:**
```typescript
headers: { Authorization: `Bearer ${token}` }
```

WS connection authenticated by the same JWT.

### Role-aware UI

Components check `useAuth().user.role` to show/hide features. **Critical:** the backend also enforces scope — frontend role checks are UI convenience, not a security boundary.

Example: `GenerateReports.tsx` shows different report types per role (technician sees "My Performance", admin sees all 5) and the descriptions reflect scope ("All tickets in your department" vs "Complete ticket audit trail").

### Layout & navigation

Each role has a `*Layout.tsx` (e.g., `AdminLayout`, `ManagerLayout`, `TechnicianLayout`) that:
1. Reads role from `useAuth()`
2. Renders a sidebar nav with role-specific menu items
3. Includes a header with user info and context switcher (role cover if active)
4. Wraps role-specific pages

**Context switch (§1.2 of SoT):**
- Staff users can toggle between their operational **Staff workspace** (their role's queues) and **My Requests** (requester view)
- This is not a permission change — both views pull from the same `useAuth()`, just different endpoints and components

### Card system — StatCards vs KPI cards

Two distinct card families. **Do not mix them up:**

- **StatCards → homepages (dashboards) only.** The 5-card overview strip at the top of every role homepage (Total / Open / Resolved / Pending / Escalated). Read-only overview, **role-scoped** (user → "my total tickets", admin → "total tickets in the system"). Stack: `statCardsConfig.ts` (`StatDefinition` catalog) → `StatCardsRenderer` → `RoleStatsGrid` → `MetricCard` (icon-in-circle + badge). All 6 roles use it. The shared `statusOverviewStats(idPrefix, totalDescription)` factory builds the Manager/HOD/HOS configs (one line each) from `live_status_distribution`.
- **KPI cards → analytics/report pages only.** `KPICardGrid` → `KPICard` (square icon + trend %). Used on the deep-dive analytics pages, never on homepages.

**StatCards are NOT table filters.** They are a read-only overview and must never be wired to filter ticket tables. Table filtering is done by the separate **FilterPills** (which share the StatCards color/font but carry no icons and *do* filter on click). Do not add `onCardClick`/filter wiring to StatCards.

### Shared role-scoped pages (Admin = canonical template)

The Admin Dashboard / Analytics / Reports are the canonical UI; the other roles **reuse the same components, scope-varied** (SoT §1.3). Three shared, `role`-parametrized views live in `src/features/shared/`:

- `RoleDashboardView` — the dashboard homepage (lifted from Admin `DashboardLayout`).
- `RoleAnalyticsView` — the deep analytics page (lifted from Admin `OrganisationAnalytics`).
- `RoleReportsPage` — the reports **landing** (tabs + Quick Access + Excel export; lifted from `ReportsPageEnhanced`). `GenerateReports` is already role-aware via `useAuth()`.

Each takes `role: 'admin' | 'manager' | 'hod' | 'hos'`; the role surface is only StatCards + titles + ticket-table role (+ a few role-gated blocks like Manager's Campus Performance). The Admin and Manager pages are **thin wrappers** (`<RoleXView role="…"/>`). HOD/HOS report/analytics still use the older `src/features/shared/AnalyticsView.tsx` (unified `/analytics/` envelope) — migrating them to the three shared views is the pending HOD/HOS pass.

**Reusable, self-fetching data components** (`src/components/shared/data/`), each scoped server-side by JWT: `DistributionCharts` (generic donut + volume bar — campus/section/…), `ServiceHealthCards` (Resolution/Response SLA + CSAT + Breached), `InsightsPanel` (unified-envelope `insights`), plus the StatCards stack. Prefer extending these over re-implementing per role. Analytics hooks (`useAnalytics`, `usePerformanceSections`, `usePerformanceCampusDepts`) accept an optional `{ enabled }` so role-gated blocks don't fire their query.

**Scope-by-role invariant (critical):** every chart, table, distribution, and KPI on dashboards / analytics / reports must render data for the **caller's scope** — campus / departmental / sectional / technician — derived server-side from the JWT. The same shared component therefore serves each role correctly: Admin = org-wide, Manager = department (across campuses), HOD = campus-department (its sections), HOS = section(s)/technicians, Technician = own. Never scope from client params; pick the role-appropriate endpoint/`group_by` and let the backend filter.

---

## Analytics & Reports

### Data flow

1. **Scope:** `scoped_ticket_qs(user, role)` returns a filtered Ticket queryset (read-only)
2. **Aggregate:** `aggregate(scoped_qs, date_range, group_by)` in `apps/analytics/services.py` computes all headline metrics (SLA %, CSAT, resolution p50/p90, net flow, etc.). It folds the headline scalars into a **single** conditional-`Count(filter=Q(...))` pass over the scoped queryset (direct `Ticket` columns only — no join fan-out), so the core is ~20 queries, not ~44.
3. **Role endpoints:** Each role-specific view (`OverviewView`, etc.) calls `aggregate()` once and slices the result to what that role should see
4. **Cheap breakdown-only paths (perf):** `aggregate()` is expensive against the remote Neon DB. Endpoints that need only a group-by must **not** call it:
   - `breakdown(scoped_qs, date_range, group_by)` — same `created_at` window, runs just the group-by (numbers match `aggregate()` exactly). Used by `PerformanceSectionsView`, `PerformanceCampusDepartmentsView`, `PerformanceTechniciansView`.
   - `technician_load(scoped_qs)` — live open-load per technician, **one query, no date window**. `aggregate()` reuses it for its headline `technician_load`.
   - Calling the full `aggregate()` core on these endpoints previously caused request timeouts (500s) under concurrent dashboard loads. `performance/{sections,campus-departments}` went 44→1 query; `performance/technicians` ~24→2.
5. **Frontend hooks:** Components use hooks (e.g., `usePerformanceTechnicians(params)`) that call `/api/v1/analytics/performance/technicians/` and return `{data, loading, error}`

### Reports (Phase 9+)

**Backend:** `apps/analytics/report_views.py` has two views:
- `GET /api/v1/reports/types/` → returns available report types + timeframe options
- `GET /api/v1/reports/generate/?report_type=...&timeframe=...&start_date=...&section_id=...` → streams an `.xlsx` file

**Excel format:**
- Sheet 1 (**Summary**): metrics that match the analytics overview (open backlog, SLA %, CSAT, p50/p90 resolution)
- Sheet 2+: data tables (Ticket Lifecycle, Technician Performance, Facility Health, Pending Analysis, or all 4 in Comprehensive)
- All sheets are styled and pivotable

**Scope enforcement:**
- Backend: `scoped_ticket_qs()` limits data to what the user can see
- Frontend: `GenerateReports.tsx` uses `useAuth()` to show only relevant report types per role, with descriptions that say "Your department" / "Your section" / "All technicians", etc.

**Available report types:**
| Type | Summary sheet | Data sheets | Who sees it |
|------|---------------|-------------|-----------|
| ticket-lifecycle | Yes | Ticket audit trail (all tickets with full lifecycle fields) | Admin, Manager, HOD, HOS |
| technician-performance | Yes | Technician metrics (load, resolved, CSAT, resolution time) | Admin, Manager, HOD, HOS; Tech sees self only |
| facility-health | Yes | Facility type breakdown (volume by category × facility) | Admin, Manager, HOD, HOS |
| pending-analysis | Yes | All pending tickets with pause durations | Admin, Manager, HOD, HOS |
| comprehensive | Yes (same) | All 4 sheets above | Admin, Manager, HOD, HOS |

**Timeframe options:** all time, last 24h, last 7d, last 30d, last 90d, last 1y, custom date range.

### Audit Log (Phase 10+)

**Backend:** `apps/tickets/views.py::AdminAuditLogView`
- `GET /api/v1/admin/audit-log/?page=1&page_size=20` → returns paginated system audit log (TicketLog entries)
- **Admin-only access** (checked via `user.is_staff`)
- **Fields returned:** `id`, `actor` (username), `action` (event_type), `target_type` ("ticket"), `ticket_no`, `detail`, `created_at`
- **Filtering:** `?actor=...&action=...&target_type=...&date_from=...&date_to=...`
- **Key invariant:** TicketLog records are append-only and immutable (cannot be edited/deleted)

**Frontend:** `AuditLogPage.tsx` in admin dashboard
- Displays system audit trail with ticket numbers and action badges
- Action badges use design system colors (from `index.css` CSS variables):
  - Green: Created/Resolved/Rated
  - Blue: Assigned/Reassigned/Comments
  - Orange: Status Changes/Reopened
  - Red: Escalated/SLA Breach
  - Gray: Closed
- Search by actor (technician name), date range filters
- Paginated table with proper spacing and layout

**Implementation detail:** `AuditLogSerializer` is a custom `Serializer` (not `ModelSerializer`) to avoid DRF auto-generating unwanted fields. Explicitly defines all output fields to fetch `ticket_no` from the related Ticket model.

---

## Key invariants

### From the SOT (SoT §1.3, §3.2, §3.8)

1. **`RoleAssignment` is the role source of truth** — a user's active assignment is their role; never read `User.role` directly.
2. **Scope resolves server-side** — never trust client `?scope=`, `?department_id=`, etc.
3. **Ticket holds only intrinsic state** — no denormalized fields like `campus_department`, `escalation_level`. Use `TicketLog` for audit, `Ticket.current_level` for escalation level.
4. **Paused tickets (status=`pending`)** don't breach SLA — the timer is frozen (R9).
5. **Escalation is structural, not workflow** — Technician → HOS → HOD is hard-wired; no configurable approval steps.
6. **Requester is universal** — every authenticated user can raise tickets; routing derives the target department from `service_item` + `requester_campus`, not the user's own role.
7. **Role cover is time-boxed and attributed** — a `RoleAssignment` with `is_primary=False` covers another role for a window; when cover ends, scope reverts to primary role.

### From Phase 6+ hardening (SoT §7, Phase 6)

- Traverse `section__campus_department__…` (no `Ticket.campus_department` field)
- Fail closed — if scope can't be resolved, return `Ticket.objects.none()`, never unfiltered
- JWT claim casing must be consistent (read directly from payload, don't rename)
- Honour `RoleAssignment.is_active()` (cover windows)
- Every scope boundary has a negative test (HOD A sees zero of HOD B's tickets; technician's individual metrics ⊂ sectional metrics)

---

## Common gotchas

**Scope bypass via `?technician_id=`:** A technician could request their own performance report with `technician_id=123` (someone else). The backend endpoint **always applies `scoped_ticket_qs()`** first, so it only sees their own tickets anyway. But the frontend `GenerateReports` auto-injects `technician_id=self` to make this explicit.

**Paused SLA:** When a ticket goes `pending`, the timer is frozen. Don't count paused tickets toward `breached` or `at_risk` metrics. (Handled by `aggregate()` in analytics/services.py.)

**Date-range filtering:** Analytics endpoints default to 30 days; reports respect the user's selected timeframe. But the **Summary sheet** always defaults to 30 days even if the user chose "all time" (to match the dashboard preset).

**Technician sectional vs individual:** A technician sees both their own performance (open, resolved, CSAT) AND section context (backlog, net flow, unassigned count). These are in separate response keys so the UI never shows section stats as the tech's personal metrics. Backend: `useTechnicianDashboard()` returns `{individual: {...}, sectional: {...}}`.

**Ticket table filter dropdowns (Sections / Technicians / Users):** These come from `GET /api/v1/tickets/filter-options/` (`TicketFilterOptionsView`), which returns only the values that appear in the caller's role-scoped ticket queryset. Section names include campus code prefix ("NRB - Networks") to disambiguate sections with the same type across campuses. Frontend: `useTicketFilterOptions()` hook, used by both `TicketsTable.tsx` (full tickets page) and `RecentTickets.tsx` (dashboard table). Do **not** use the `externalTechnicians`/`externalUsers` props on `useTicketTable` for these — they default to `[]`.

**FacilitySerializer enriched fields:** `FacilitySerializer` returns `type` (= `facility_type.code`, e.g. `"office_block"`), `campus_name`, `status` (derived from open ticket count — `"maintenance"` if > 0, else `"operational"`), and `openTickets` / `resolvedTickets` / `closedTickets` counts. Counts come from `TicketLocation.facility` FK via Subquery (not annotation) because `TicketLocation.facility` uses `related_name="+"`.

**Facility seeding:** `seed_full.py` seeds 18 `Facility` objects across 3 campuses (8 NRB, 5 MSA, 5 KSM) via `_seed_facilities()`. Re-running is safe (get_or_create keyed on `campus + code`). `FacilityType` reference data (5 types) is seeded by `_seed_facility_types()`.

**Reference-data query params must actually filter (C15):** `/departments/?campus=` and `/sections/?department=` are implemented via `get_queryset()` overrides on `DepartmentViewSet`/`SectionViewSet` (`apps/org/views.py`) — filtering `campus_departments__campus_id` / `campus_department__department_id`. If you add a new scoping query param to a reference-data endpoint, wire the filter in `get_queryset()` in the same commit; an accepted-but-ignored param is worse than none; add a negative test like `test_departments_filtered_by_campus` / `test_sections_filtered_by_department` in `tests/test_phase2.py`.

**Replacing a primary `RoleAssignment` demotes, never errors (C16):** `UserRoleAssignmentListCreateView` (`apps/accounts/views.py`) demotes the user's existing primary assignment (`is_primary=False`, kept for audit) before creating a new primary one, inside `transaction.atomic()`. Do not "fix" a `one_primary_role_per_user` `IntegrityError` here by deleting the old row — the old assignment must survive, just demoted.

**`ServiceItem.default_priority` is a nullable per-item override, not a required field:** `ServiceItemSerializer` writes it via `default_priority_id` (nullable — same pattern as `ServiceCategorySerializer`). `TicketCreateSerializer.validate()` resolves `item.default_priority or category.default_priority`, so leaving it unset (the common case) inherits the category's priority. Use this only for genuine outliers within a category (e.g. "Burst Pipe" inside "Plumbing Services") — retagging the whole category is the wrong tool when just one item is the exception.

---

## Development checklist

- [ ] Read `service-desk-implementation-plan.md` for domain & phased build
- [ ] Check `requirements.txt` for backend + frontend dependencies
- [ ] Run `pytest` to verify all tests pass
- [ ] Inspect `apps/*/models.py` to understand the domain
- [ ] Read `apps/tickets/services/scope.py` — scope is critical
- [ ] For analytics changes: edit `apps/analytics/services.py::aggregate()`, not individual endpoints
- [ ] For reports: the Excel structure and role visibility are in `apps/analytics/report_views.py` and `Resolver/client/src/features/admin/Reports/GenerateReports.tsx`
- [ ] When adding a role or org entity, update the scope table in SoT §3.5 and add a negative test
- [ ] No feature is complete until it has tests and the SoT/CLAUDE.md are updated
