# Django Resolver — Multi-Campus Service Desk API

Backend for the Kenya School of Government service desk system. A multi-campus ticket lifecycle API with role-scoped analytics, Excel report generation, and real-time event streaming.

**Stack:** Django 6.0 · DRF 3.16 · PostgreSQL (Neon) · JWT · Django Channels · pytest (343 tests, 1 xfail)

---

## Quick Start

```bash
git clone https://github.com/JeremyWarui/django_resolver && cd django_resolver
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/django_resolver
SECRET_KEY=your-secret-key
DEBUG=True
```

```bash
python manage.py migrate
python manage.py seed_full          # seeds campuses, departments, sections, users, facilities, demo tickets
python manage.py runserver          # http://localhost:8000
```

**Admin panel:** http://localhost:8000/admin

---

## Seed Accounts

`seed_full` creates demo users across all roles, all sharing the `DEFAULT_PASSWORD` constant defined in `apps/common/management/commands/seed_full.py` (not reproduced here — read it from the source file).

| Role | Username example |
|------|-----------------|
| Admin | admin |
| Manager | admin_mgr |
| HOD | nrb_admin_hod |
| HOS | nrb_networks_hos |
| Technician | nrb_networks_tech1 |
| Requester | any user with no `RoleAssignment` |

---

## Architecture

### App layout

```
apps/
├── accounts/     — User, UserProfile, JWT auth, RoleAssignment
├── org/          — Campus, Department, Section, SectionTechnician
├── tickets/      — Ticket, TicketComment, TicketFeedback, TicketLog
├── catalog/      — ServiceCategory, ServiceItem
├── sla/          — Priority, EscalationRule, SLAHistory
├── facilities/   — Facility, FacilityType, TicketLocation
├── analytics/    — aggregate/breakdown services, role-scoped views, report generation
├── common/       — shared exceptions, validators, enums, management commands
└── realtime/     — Django Channels consumers, WS event dispatch
```

### Request flow

```
HTTP → resolver/urls.py → resolver/api_urls.py → apps/*/urls.py → views/ → services/ → models/
```

Views never mutate Ticket directly — always call a service (e.g. `TicketService.update_status()`).

### Scope enforcement

Every view derives scope from the JWT role claim via `scoped_ticket_qs(user, role)` in `apps/tickets/services/scope.py`. Scope is never read from client query params — it is resolved server-side and fails closed (empty queryset on error).

---

## Roles

| Role | Scope |
|------|-------|
| Admin | Organisation-wide |
| Manager | Own department across all campuses |
| HOD | Own campus-department (all its sections) |
| HOS | Own section(s) |
| Technician | Sections assigned via `SectionTechnician` |
| Requester | Own tickets only (every authenticated user) |

---

## Key Endpoints

All under `/api/v1/`:

```
Auth:           POST  /auth/login/           POST /auth/refresh/
Tickets:        GET   /tickets/              GET/PATCH /tickets/{id}/
                POST  /tickets/create/       POST /tickets/{id}/assign/
                POST  /tickets/{id}/comments/ POST /tickets/{id}/feedback/
Filter options: GET   /tickets/filter-options/
Analytics:      GET   /analytics/overview/   GET /analytics/performance/technicians/
                GET   /analytics/performance/sections/
Reports:        GET   /reports/types/        GET /reports/generate/?report_type=...&timeframe=...
Audit log:      GET   /admin/audit-log/      (admin only)
Org:            GET   /campuses/  /departments/?campus=  /sections/?department=  /technicians/
Facilities:     GET   /facilities/
Catalogue:      GET   /catalogue/categories/  /catalogue/items/
```

---

## Analytics & Reports

`aggregate(scoped_qs, date_range, group_by)` in `apps/analytics/services.py` is the single metrics core — one conditional-Count pass over the scoped queryset. Role endpoints call it once and slice the result.

For breakdown-only paths (`performance/sections`, `performance/technicians`), `breakdown()` is used instead of `aggregate()` to avoid the full ~44-query pass (reduced to 1–2 queries).

Reports stream `.xlsx` files with a Summary sheet + data sheets (Ticket Lifecycle, Technician Performance, Facility Health, Pending Analysis). Available types: `ticket-lifecycle`, `technician-performance`, `facility-health`, `pending-analysis`, `comprehensive`.

---

## Testing

```bash
pytest                                      # all tests (343 passed, 1 xfail)
pytest apps/tickets/tests/ -v              # specific app
pytest --create-db                         # rebuild test DB after model changes
pytest --cov-report=html                   # HTML coverage report
```

---

## Management Commands

```bash
python manage.py seed_full                          # idempotent full seed
python manage.py process_auto_escalations           # run escalation sweep
python manage.py process_auto_escalations --dry-run --verbose
```

---

## Org Hierarchy

```
Campus
  └── CampusDepartment  (Campus + Department + HOD)
        └── Section  (CampusDepartment + SectionType + HOS)
              ├── SectionTechnician  (Technician ↔ Section)
              └── Ticket
```

**Ticket numbering:** `CAMPUS-DEPT-NNNNN` (e.g. `NRB-ICT-00001`)

**Status workflow:** `open → assigned → in_progress ⇄ pending → resolved → closed`

**Escalation:** Technician → HOS → HOD — structural, time-based, cron-driven.

**Priority resolution:** `ServiceItem.default_priority` (optional per-item override) → falls back to `ServiceCategory.default_priority`. Lets one urgent item (e.g. "Burst Pipe") outrank its otherwise-routine category (e.g. "Plumbing Services") without moving it or changing the category for everyone else.

---

## License

MIT
