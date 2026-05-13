# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **Kenya School of Government — Multi-Campus Service Desk System**
> Django 6.0.3 · DRF 3.16.1 · PostgreSQL · Token Auth

---

## Commands

```bash
# Dev server
python manage.py runserver

# Run all tests (coverage included via pytest.ini)
pytest

# Run a single test file
pytest tickets/tests/test_views_permissions.py -v

# Run a single test by name
pytest tickets/tests/test_ticket_workflow_e2e.py::TestCompleteTicketLifecycle::test_full_workflow_open_to_closed -v

# After schema changes — rebuild the test DB
pytest --create-db

# Coverage report in HTML
pytest --cov-report=html

# Linting / formatting
flake8 tickets/
black tickets/

# Migrations
python manage.py makemigrations
python manage.py migrate

# Load fixture
python manage.py loaddata tickets_initial_data

# Flush and reload
python manage.py flush --no-input && python manage.py loaddata tickets_initial_data

# Run auto-escalation sweep (normally scheduled via cron)
python manage.py process_auto_escalations
python manage.py process_auto_escalations --dry-run --verbose
```

---

## Architecture

### Single-App Structure

One Django app (`tickets/`) contains all models, serializers, and API logic. The `resolver/` package is just Django project config (settings, root urls, wsgi/asgi).

All URL patterns live in `tickets/api/urls.py` and are included under `/api/` in `resolver/urls.py`.

### Request Flow

```
HTTP Request
  → resolver/urls.py             (/api/ → tickets/api/urls.py)
  → tickets/api/views/           (HTTP handling, permission checks)
  → tickets/api/services/        (business logic, org-scope validation)
  → tickets/models/              (ORM, state machine methods)
  → tickets/email_service.py     (side effects)
```

Views **never** mutate tickets directly via ORM — they always call `TicketService`.

### Directory Map

```
tickets/
├── models/
│   ├── __init__.py         — Re-exports all model classes
│   ├── organisation.py     — Campus, Department, CampusDepartment
│   ├── sections.py         — SectionType, Section, TechnicianSection
│   ├── catalogue.py        — ServiceCategory, ServiceItem
│   ├── facilities.py       — Facility
│   ├── tickets.py          — Ticket, TicketLog, Comment, Feedback
│   └── users.py            — CustomUser
├── serializers/
│   ├── __init__.py         — Re-exports all serializer classes
│   ├── org.py              — Campus, Department, CampusDepartment serializers
│   ├── sections.py         — SectionType, Section, TechnicianSection serializers
│   ├── catalogue.py        — ServiceCategory, ServiceItem serializers
│   ├── facilities.py       — Facility serializers
│   ├── tickets.py          — Ticket serializers (Create, List, Detail)
│   ├── users.py            — UserSerializer
│   └── common.py           — Shared helpers
├── admin.py                — Unfold admin registrations
├── pagination.py           — TicketPagination (page_size=20, max=100)
├── email_service.py        — TicketEmailService (lifecycle notifications)
├── fixtures/
│   └── tickets_initial_data.json  — Seed data
├── management/commands/
│   └── process_auto_escalations.py
└── api/
    ├── urls.py             — All URL patterns
    ├── permissions/
    │   ├── __init__.py     — Re-exports all permission classes
    │   ├── base.py         — IsAdminOrReadOnly
    │   ├── org.py          — IsWithinOrganizationalScope, CanManageSectionTechnicians
    │   ├── tickets.py      — CanViewTicket, CanEditTicket, CanAssignTickets, etc.
    │   └── users.py        — CanManageUsers, IsTechnicianOrAdmin
    ├── filters.py          — DjangoFilterBackend filter classes
    ├── simple_auth_views.py — Login / logout / register / profile
    ├── views/
    │   ├── index.py        — Re-exports all view classes
    │   ├── ticket_views.py — TicketListCreateView, TicketCreateView, TicketDetailView, BulkStatusUpdateView
    │   ├── org_views.py    — Campus, Department, CampusDepartment, Section CRUD + HOD/HOS assignment
    │   ├── technician_views.py — TechnicianSection assignment views
    │   ├── catalogue_views.py  — ServiceCategory, ServiceItem views
    │   └── user_views.py   — UserListCreateView, TechniciansBySectionView
    ├── services/
    │   ├── __init__.py     — Public API (re-exports)
    │   ├── ticket_service.py      — TicketService (create, assign, escalate, close)
    │   ├── technician_service.py  — TechnicianService (section membership)
    │   ├── validators.py   — validate_status_transition, validate_pending_transition
    │   └── exceptions.py   — TicketServiceException, InsufficientScopeException, etc.
    ├── analytics/
    │   ├── index.py        — Re-exports analytics views
    │   ├── views.py        — All analytics API views
    │   ├── base_analytics.py
    │   ├── admin_analytics.py
    │   ├── manager_analytics.py
    │   ├── hod_analytics.py
    │   ├── section_head_analytics.py
    │   ├── ticket_analytics.py
    │   ├── technician_analytics.py
    │   └── user_analytics.py
    └── reports/
        ├── report_generator.py
        └── views.py
```

---

## Organisational Hierarchy

As defined in BACKEND_PLAN.md:

```
Campus  (physical location/branch — root entity)
  └── CampusDepartment  (Campus + Department join, owned by HOD)
        └── Section  (campus-specific instance of SectionType, owned by HOS)
              ├── TechnicianSection  (Technician → Section M2M assignment)
              ├── Facility  (physical room/asset on that campus)
              └── Ticket
```

```
Department  (global — e.g., "ICT", "Administration")
  └── SectionType  (type definition — e.g., "Software Support", "Procurement")
        └── ServiceCategory  (e.g., "Hardware", "Networking")
              └── ServiceItem  (e.g., "Laptop Repair", "Wi-Fi Issue")
```

Ticket number auto-generated as `CAMPUS-DEPT-NNNNN` (e.g. `NRB-ICT-00001`). All sections in the same department share one counter.

---

## Ticket Creation Flow

Auto-resolution order per BACKEND_PLAN.md §5:

1. User selects `department_id` + `service_item_id` via `POST /api/tickets/create/`
2. System resolves `CampusDepartment` ← `user.primary_campus` + `department`
3. System resolves `SectionType` ← `service_item → category → section_type`
4. System resolves `Section` ← `CampusDepartment` + `SectionType`
5. Returns ticket + eligible technicians (filtered by section, campus, active status)

Endpoint: `POST /api/tickets/create/` → `TicketCreateView` (not `ticket-list`)

---

## Role System

| DB value | Scope |
|----------|-------|
| `user` | Own tickets only |
| `technician` | Tickets in assigned sections |
| `head_of_section` | Own section; can assign tickets and manage section technicians |
| `hod` | Own campus + department |
| `manager` | Own department across all campuses |
| `admin` | Full system access |

`CustomUser.sections` is a M2M to `Section` via `TechnicianSection` — this is how technicians are scoped.

`manager` ticket scope: `section__campus_department__department == user.primary_department` across all campuses.

---

## Ticket Status Machine

```
open ──────────────────────────────────→ assigned → in_progress ⇄ pending → resolved → closed
pending_approval → (approve) → open
pending_approval → (reject)  → rejected
```

- Use `TicketService.update_ticket_status()`, never set `status` directly.
- `pending` requires `assigned_to`, `pending_reason`, and `pending_comment`.
- Priority overridden on every `save()` by escalation level (0→low, 1→medium, ≥2→high). `priority="critical"` bypasses this.
- Escalation clock starts at `assigned_at`, not `created_at`. Unassigned tickets never escalate.

---

## Serializers

Three main ticket serializers:

| Class | Used for |
|-------|---------|
| `TicketCreateSerializer` | `POST /tickets/create/` — org-resolution, service catalogue |
| `TicketListSerializer` | `GET /tickets/` — flat, lightweight |
| `TicketSerializer` | `GET /tickets/<pk>/` — full nested detail |

Read/write split pattern used throughout:
```python
section = NestedSectionSerializer(read_only=True)
section_id = PrimaryKeyRelatedField(queryset=Section.objects.all(), source='section', write_only=True)
```

Several serializers have `get_fields()` overrides that strip fields based on `request.user.role`.

---

## Authentication

DRF Token Auth. Header: `Authorization: Token <40-char-hex>`.

| Method | URL | Notes |
|--------|-----|-------|
| POST | `/api/auth/login/` | Returns `{ token, user }` |
| POST | `/api/auth/logout/` | Invalidates token |
| GET | `/api/auth/profile/` | Authenticated user profile |
| POST | `/api/auth/register/` | Self-registration, role defaults to `user` |
| GET | `/api/auth/check-method/` | Returns `{ method: "password" }` |

---

## Fixture & Seed Data

```bash
python manage.py loaddata tickets_initial_data
```

All fixture users share the password: **`adminuser123`**

Key seed users:

| Username | Role | Campus | Notes |
|----------|------|--------|-------|
| `admin_user` | admin | NRB | Full access |
| `manager_ict` | manager | NRB | ICT dept |
| `hod_ict_nrb` | hod | NRB | ICT dept |
| `hos_ict_nrb` | head_of_section | NRB | ICT section 1 |
| `tech_alex` | technician | NRB | ICT section 1 |
| `user_sarah` | user | NRB | ADM dept |
| `user_msa` | user | MSA | |

---

## Testing

Tests use `pytest-django` with `--reuse-db` (drop with `--create-db` after migrations change).

### Test files

| File | Tests | Purpose |
|------|-------|---------|
| `test_views_permissions.py` | 55 | CRUD operations and role-based permission checks |
| `test_apis.py` | 23 | Multi-step workflow and integration scenarios |
| `test_ticket_workflow_e2e.py` | 26 | End-to-end ticket lifecycle (6 stages) |
| `test_analytics_permissions.py` | 77 | Access control for all 11 analytics endpoints |
| `test_analytics_aggregation.py` | 45 | Data correctness and metric calculations |
| `test_analytics_scoping.py` | 32 | Organisational boundary enforcement |

### Key fixtures (`conftest.py`)

```
campus → campus_department (+ department, hod) → section (+ section_type, hos)
                                                        └── service_category → service_item
```

- User factories: `user_factory`, `admin_user_factory`, `technician_factory`, `section_head_factory`, `hod_factory`, `manager_factory`
- `ticket_factory`, `comment_factory`, `feedback_factory`
- `service_category`, `service_item`, `service_item_requires_approval`
- `api_client`, `authenticated_client`, `authenticated_admin_client`, `authenticated_technician_client`

See `docs/testing/TESTING.md` for full fixture reference.

---

## Key Pitfalls

- **Ticket creation endpoint**: Use `POST /api/tickets/create/` (`ticket-create`) not `POST /api/tickets/` (`ticket-list`). The create endpoint runs org-structure resolution; the list endpoint does not.
- **`TicketCreateSerializer` field names**: `department_id`, `service_item_id`, `facility_id` (not `department`, `service_item`, `facility`).
- **`manager` ticket scope**: scoped to `section__campus_department__department == user.primary_department` — not campus-scoped.
- **Escalation clock**: starts at `assigned_at`. Setting `next_escalation_due` on an unassigned ticket is a bug.
- **`pending` fields**: transition to `pending` requires both `pending_reason` and `pending_comment` or raises `ValidationError`.
- **`CampusDepartment` required on `Ticket`**: the FK is non-nullable. Always set `campus_department=section.campus_department` when creating tickets directly (e.g. in tests using `ticket_factory`).
- **Test DB sequence**: after fixture loads, call `pytest --create-db` if ticket IDs need to be predictable.
- **HOD analytics strict assignment**: HOD can only access a `CampusDepartment`'s analytics if `campus_department.head_of_department == user` — same-campus HODs who aren't explicitly assigned are blocked.

---

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | SQLite (dev) | PostgreSQL DSN in prod |
| `SECRET_KEY` | hardcoded dev key | Must override in prod |
| `DEBUG` | `True` | |
| `CORS_ALLOWED_ORIGINS` | `localhost:5173` | Add prod frontend URL |
| `REDIS_URL` | — | Required for caching in prod |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | For lifecycle email notifications |

`.env` file at `django_resolver/.env`, loaded via `python-dotenv`.

---

## Deployment (Render)

`render.yaml` at repo root. Build command: `./build.sh` (pip install → collectstatic → migrate → loaddata).

Live backend: `https://django-resolver.onrender.com/api`

---

## Service Catalogue

`ServiceItem.requires_approval = True` → ticket starts as `pending_approval` instead of `open`.

The `Ticket` model has `service_item` FK, `form_data` JSONField, and `due_date` DateTimeField. `save()` sets `due_date` from the SLA cascade: `service_item.sla_hours` → `section_type.default_sla_hours` → 24h fallback.

---

## Future Phases

### Phase 4 — SLA Tracking & Email Notifications

**Backend**

1. Fix `is_overdue` on `Ticket` model (`models/tickets.py`) — replace hardcoded 7-day window with `due_date`-based check.
2. Add `time_remaining` property to `Ticket` model.
3. Add `check_sla_breaches` management command (cron-only, no Celery).
4. Implement missing email methods in `email_service.py`: `send_ticket_created`, `send_ticket_status_updated`, `send_ticket_approved`, `send_sla_breach_alert`.

### Phase 5 — Attachments

Add `Attachment` model with file upload to `tickets/attachments/%Y/%m/%d/`, max 10 MB, max 5 per ticket. Endpoints: `POST/GET /api/tickets/{id}/attachments/` and `DELETE /api/attachments/{id}/`.
