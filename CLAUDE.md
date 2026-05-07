# CLAUDE.md — Django Resolver Backend

> **Kenya School of Government — Multi-Campus Service Desk System**
> Django 6.0.3 · DRF 3.16.1 · PostgreSQL · Token Auth

---

## 1. Project Overview

Resolver is a multi-campus facilities and IT service-desk system. Staff raise tickets against service items; technicians are assigned within sections; heads of section, HoDs, and managers supervise at progressively broader scopes. The backend exposes a REST API consumed exclusively by the React frontend.

**Live backend**: `https://django-resolver.onrender.com/api`
**Local**: `http://localhost:8000/api`

---

## 2. Tech Stack

| Layer | Package | Version |
|-------|---------|---------|
| Framework | Django | 6.0.3 |
| REST | djangorestframework | 3.16.1 |
| Auth tokens | rest_framework.authtoken | built-in |
| CORS | django-cors-headers | 4.9.0 |
| Filters | django-filter | 25.2 |
| Admin UI | django-unfold | 0.85.0 |
| DB driver | psycopg2-binary | 2.9.11 |
| DB URL parser | dj-database-url | 3.1.2 |
| Cache | django-redis / redis | 6.0.0 / 7.3.0 |
| Static files | whitenoise | 6.12.0 |
| Spreadsheet | openpyxl | 3.1.5 |
| Tests | pytest-django / pytest-cov | 4.12.0 / 7.0.0 |

Python: **3.13+** (no walrus-operator workarounds needed).

---

## 3. Directory Layout

```
django_resolver/
├── manage.py
├── pytest.ini
├── requirements.txt
├── resolver/                   # Django project package
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
└── tickets/                    # Single Django app
    ├── models.py               # All models
    ├── serializers.py          # All DRF serializers
    ├── admin.py                # Unfold admin registrations
    ├── pagination.py           # TicketPagination
    ├── urls.py                 # (empty — routing in api/urls.py)
    ├── email_service.py
    ├── fixtures/
    │   └── tickets_initial_data.json
    ├── management/commands/
    │   └── process_auto_escalations.py
    ├── migrations/
    └── api/
        ├── urls.py             # All URL patterns
        ├── permissions.py      # Permission classes
        ├── filters.py          # DjangoFilterBackend filter classes
        ├── simple_auth_views.py
        ├── views/
        │   ├── index.py        # Re-exports all view classes
        │   └── views.py        # All view implementations
        ├── services/
        │   ├── __init__.py     # Re-exports
        │   └── services.py     # Business logic (TicketService + validators)
        ├── analytics/
        │   ├── index.py
        │   ├── analytics.py    # TicketAnalytics, OrganizationalAnalytics
        │   └── views.py        # Analytics API views
        └── reports/
            ├── report_generator.py
            └── views.py
```

URL prefix: all API routes live under `/api/` (set in `resolver/urls.py`).

---

## 4. Organizational Hierarchy

```
Organization
  └── Campus (code e.g. "NRB", "MSA", "MTG")
        └── Department (code e.g. "ICT", "ADM", "HR")
              └── Section (e.g. "Software", "Procurement")
                    └── Facility (physical room/asset)
                          └── Ticket
```

**Definition models (Phase 4 — not yet migrated):**

```
DepartmentType  ─── blueprints applied to any campus
SectionType     ─── includes staff_label, default_sla_hours
ServiceCategory
ServiceItem     ─── form_schema JSON, sla_hours, requires_approval
```

These exist in the fixture with `--ignorenonexistent` support; they are loaded but silently skipped until migrations create the tables.

---

## 5. Role System

### Current DB strings (models.py ROLE_CHOICES)

| DB value | Display |
|----------|---------|
| `user` | User |
| `technician` | Technician |
| `section_head` | Section Head |
| `hod` | Head of Department |
| `director` | Director |
| `admin` | System Administrator |

### **Target strings (fixture + Phase implementation)**

> **CRITICAL**: The fixture and implementation plan use the **new** strings below. Before writing new code, rename in `ROLE_CHOICES` and update every reference.

| Old (DB) | New (target) | Notes |
|----------|-------------|-------|
| `section_head` | `head_of_section` | max_length already 15, fits |
| `director` | `manager` | Cross-campus, own-department scope |

`head_of_section` inherits all `technician` permissions plus assign/reassign within their section. `manager` scope: cross-campus but restricted to own department (NOT org-wide).

### Permission classes (`api/permissions.py`)

| Class | Used for |
|-------|----------|
| `IsWithinOrganizationalScope` | Object-level org scope gating |
| `CanViewAndEditTickets` | Ticket list/detail (permissive GET, restrictive PATCH) |
| `CanAssignTickets` | Assignment endpoint |
| `CanEscalateTickets` | Manual escalation |
| `CanViewAnalytics` | Analytics endpoints |
| `IsAdminOrReadOnly` | Org structure CRUD |
| `IsOwnerOrTechnicianOrAdmin` | Legacy — being phased out |

**Note**: `permissions.py` still references old strings `section_head`/`director`. Update when renaming roles.

---

## 6. Authentication

**Mechanism**: DRF Token authentication.
**Header**: `Authorization: Token <40-char-hex>`

```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
    ],
    ...
}
```

### Auth endpoints

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/auth/login/` | Password login → returns `{ token, user }` |
| POST | `/api/auth/logout/` | Invalidates token |
| GET | `/api/auth/profile/` | Current user profile |
| POST | `/api/auth/register/` | Self-registration (role=user) |
| GET | `/api/auth/check-method/` | Returns `{ method: "password" }` |

Magic-link endpoints exist in code but are commented out (`simple_auth_views.py`). Enable by uncommenting and configuring `EMAIL_HOST_*`.

### Session seed password

All fixture users share the same password hash:

```
pbkdf2_sha256$1200000$vreSnIHT54LLxvqshySYIJ$g1yrN+g/MSh1EaK22L2H3+z+8ucW+MBv+6OSwjIVnUk=
```

Plain-text: `TestPass123!` — change in any real deployment.

---

## 7. Models Reference

### CustomUser (`tickets.models.CustomUser`)

Extends `AbstractUser`. Key custom fields:

| Field | Type | Notes |
|-------|------|-------|
| `role` | CharField(15) | See §5 |
| `primary_campus` | FK(Campus) | nullable |
| `primary_department` | FK(Department) | nullable |
| `sections` | M2M(Section) | Technician section assignments |
| `phone_number` | CharField(15) | |
| `can_assign_tickets` | BooleanField | Capability flag |
| `can_escalate_tickets` | BooleanField | Capability flag |
| `can_view_analytics` | BooleanField | Capability flag |

### Ticket (`tickets.models.Ticket`)

Key fields:

| Field | Type | Notes |
|-------|------|-------|
| `ticket_no` | CharField(20) | Auto `CAMPUS-DEPT-NNNNN` |
| `status` | CharField | See §8 |
| `priority` | CharField | See §9 |
| `section` | FK(Section) | Required |
| `facility` | FK(Facility) | Required — add `null=True` migration if needed |
| `raised_by` | FK(CustomUser) | Set on create |
| `assigned_to` | FK(CustomUser, null) | Technician or HoS |
| `assigned_at` | DateTimeField(null) | Set when assigned; escalation clock start |
| `escalation_level` | IntegerField(0) | 0/1/2 |
| `escalated_at` | DateTimeField(null) | Set on first escalation |
| `next_escalation_due` | DateTimeField(null) | Recomputed by `_schedule_next_escalation()` |
| `resolved_at` | DateTimeField(null) | Set on resolve |
| `closed_at` | DateTimeField(null) | Set on close |
| `pending_reason` | CharField(null) | Required when `status=pending` |
| `pending_comment` | TextField(null) | Required when `status=pending` |
| `location_details` | CharField(200) | |
| `form_data` | JSONField(null) | ServiceItem form submission |

**Ticket number generation** (in `Ticket.save()`):

```python
campus_code = section.department.campus.code   # e.g. "NRB"
dept_code   = section.department.code           # e.g. "ICT"
# → "NRB-ICT-00001"
```

All sections in the same department share the same counter. Two sections in `NRB-ADM` both produce `NRB-ADM-NNNNN` numbers.

### Section

| Field | Notes |
|-------|-------|
| `sla_hours` | Overrides SectionType default; overridden by ServiceItem.sla_hours |
| `section_head` | FK(CustomUser, null) — the assigned head_of_section |

---

## 8. Ticket Status Machine

Valid statuses: `open → assigned → in_progress → pending → resolved → closed`
Rejectable at: `pending_approval → rejected`

### Status consistency rules

| Status | `assigned_to` | `resolved_at` | `pending_reason` |
|--------|---------------|---------------|-----------------|
| `open` | **null** | null | null |
| `pending_approval` | **null** | null | null |
| `rejected` | optional null | null | null |
| `assigned` | **set** | null | null |
| `in_progress` | **set** | null | null |
| `pending` | **set** | null | **set** |
| `resolved` | **set** | **set** | null |
| `closed` | **set** | **set** | null |

`Ticket.change_status()` enforces transitions and logs them. Do not set `status` directly; call this method.

### Approval workflow

If `ServiceItem.requires_approval = True`, ticket is created with `status = pending_approval`. A manager or admin approves/rejects before work begins.

---

## 9. Priority & Escalation

### Priority override in `Ticket.save()`

```python
if self.priority != "critical":
    if self.escalation_level == 0: self.priority = "low"
    elif self.escalation_level == 1: self.priority = "medium"
    elif self.escalation_level >= 2: self.priority = "high"
```

Set `priority = "critical"` manually (e.g. overdue check) — it is never downgraded.

### Overdue rule

`check_and_mark_critical()`: ticket is overdue if active and `created_at < now - 168h` (7 days). Sets `priority = "critical"`.

### Escalation timeline (`_schedule_next_escalation()`)

| Condition | `next_escalation_due` |
|-----------|----------------------|
| `assigned_to is None` | **None** |
| `status` in resolved/closed/rejected/pending_approval | **None** |
| `escalation_level >= 2` | **None** |
| `escalation_level == 0` | `assigned_at + 48h` |
| `escalation_level == 1` | `escalated_at + 24h` |

### Management command

```bash
python manage.py process_auto_escalations
```

Runs the escalation sweep. Schedule via cron or Celery beat in production.

---

## 10. API Endpoints Summary

All under `/api/`. Auth required unless noted.

### Organization Hierarchy

```
GET/POST   /organizations/
GET/PUT/DELETE /organizations/<pk>/
GET/POST   /campuses/
GET/PUT/DELETE /campuses/<pk>/
GET/POST   /departments/
GET/PUT/DELETE /departments/<pk>/
GET/POST   /sections/
GET/PUT/DELETE /sections/<pk>/
GET/POST   /facilities/
GET/PUT/DELETE /facilities/<pk>/
```

### Tickets

```
GET/POST   /tickets/
GET/PATCH/DELETE /tickets/<pk>/
POST       /tickets/<ticket_id>/escalate/
POST       /tickets/<ticket_id>/close/
POST       /tickets/<ticket_id>/escalate-manual/
POST       /tickets/bulk-status-update/
GET        /tickets/organizational/list/
```

### Comments & Feedback

```
GET/POST   /comments/
GET/POST   /feedback/
GET/POST   /tickets/<ticket_id>/comments/
GET/POST   /tickets/<ticket_id>/feedback/
```

### Users & Technicians

```
GET/POST   /users/
GET/PATCH/DELETE /users/<pk>/
GET        /users/me/
GET        /technicians/          ?section_id=<id>
GET        /assignable-users/
```

### Analytics

```
GET  /analytics/tickets/
GET  /analytics/technicians/
GET  /analytics/admin-dashboard/
GET  /analytics/director/
GET  /analytics/hod/
GET  /analytics/section-head/
GET  /analytics/organizational/
```

### Reports

```
POST  /reports/generate/        body: { report_type, filters }
GET   /reports/types/
```

---

## 11. Services Layer (`api/services/services.py`)

All business logic lives here. Views call service methods; views never touch ORM directly for ticket mutations.

### Key public functions

| Function | Purpose |
|----------|---------|
| `TicketService.create_ticket(user, data)` | Create with org validation |
| `TicketService.assign_ticket(user, ticket, assignee)` | Assign with scope check |
| `TicketService.escalate_ticket(user, ticket, reason)` | Manual escalation |
| `TicketService.close_ticket(user, ticket)` | Close with auth check |
| `TicketService.get_accessible_tickets(user, filters)` | Scope-aware queryset |
| `validate_status_transition(current, new)` | Pure validator |
| `process_auto_escalations()` | Called by management command |

### Custom exceptions

```python
TicketServiceException        # Base
InsufficientScopeException    # Wrong org scope
InvalidAssignmentException    # Technician not in section
InvalidEscalationException    # Already at max level, etc.
```

---

## 12. Serializers (`tickets/serializers.py`)

Two ticket serializers:

| Class | Usage |
|-------|-------|
| `TicketListSerializer` | `GET /tickets/` — flat, lightweight |
| `TicketSerializer` | `GET /tickets/<pk>/` — full nested detail |

Nested read/write pattern: read fields return nested objects; write fields use `_id` suffix with `PrimaryKeyRelatedField`.

```python
# Example pattern
section = NestedSectionSerializer(read_only=True)
section_id = PrimaryKeyRelatedField(queryset=Section.objects.all(), source='section', write_only=True)
```

---

## 13. Filtering & Pagination

**Filter class**: `tickets/api/filters.py` — uses `django-filter`.

Ticket filterable fields: `status`, `priority`, `section`, `assigned_to`, `raised_by`, `created_at` (date range).

**Pagination**: `TicketPagination` in `tickets/pagination.py`.

```python
class TicketPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
```

Response envelope:
```json
{ "count": 42, "next": "...", "previous": null, "results": [...] }
```

---

## 14. Admin Interface

Uses **Django Unfold** (`django-unfold`). Config in `resolver/settings.py` under `UNFOLD = { ... }`.

Site title: "Resolver". Header: "Maintenance Ticket Management".

Unfold must be listed **before** `django.contrib.admin` in `INSTALLED_APPS`. All admin classes inherit from `unfold.admin.ModelAdmin`.

---

## 15. Testing

```bash
# Run all tests
cd django_resolver
pytest

# With coverage
pytest --cov=tickets --cov-report=html

# Single file
pytest tickets/tests/test_models.py -v
```

Config in `pytest.ini`: `DJANGO_SETTINGS_MODULE = resolver.settings`. `--reuse-db` keeps the test DB between runs (drop with `--create-db` when migrations change).

### Test files

| File | Covers |
|------|--------|
| `test_models.py` | Model methods, escalation logic |
| `test_apis.py` | Endpoint smoke tests |
| `test_auth_comprehensive.py` | Login/logout/register flows |
| `test_organizational.py` | Scope rules per role |
| `test_workflow.py` | Status transitions |
| `test_ticket_operations.py` | Assign, escalate, close |
| `test_analytics.py` | Analytics view responses |
| `test_serializers.py` | Serializer field validation |
| `test_spec_compliance.py` | Contract tests |

Base class: `tickets/tests/base.py` → `BaseTicketTestCase` with `setUpTestData()`.

---

## 16. Fixture & Seed Data

**File**: `tickets/fixtures/tickets_initial_data.json`

Load order matters — use:

```bash
python manage.py loaddata tickets_initial_data --ignorenonexistent
```

`--ignorenonexistent` skips DepartmentType/SectionType/ServiceCategory/ServiceItem records until those models are migrated.

### Fixture contents

| Model | Count | Notes |
|-------|-------|-------|
| Organization | 1 | KSG |
| Campus | 5 | NRB, MSA, MTG, NYR, ELD |
| Department | 9 | |
| Section | 8 | |
| Facility | 11 | |
| CustomUser | 18 | roles across all 6 |
| Ticket | 23 | see distribution below |
| Comment | ~20 | |
| Feedback | ~8 | resolved/closed tickets |
| TicketLog | ~35 | |
| DepartmentType | 4 | skipped until migrated |
| SectionType | 6 | skipped until migrated |
| ServiceCategory | 9 | skipped until migrated |
| ServiceItem | 54 | with form_schema; skipped until migrated |

### Ticket status distribution

| Status | Count |
|--------|-------|
| open | 3 |
| assigned | 3 |
| in_progress | 3 |
| pending | 3 |
| pending_approval | 5 |
| resolved | 3 |
| closed | 2 |
| rejected | 1 |

Overdue tickets (created >7 days before 2026-05-07): PKs 1, 2, 12, 13, 14 — all `priority=critical`.

### Seed users

| Username | Role | Campus | Dept |
|----------|------|--------|------|
| admin_user | admin | NRB | ICT |
| manager_jane | manager | NRB | — |
| hod_alex | hod | NRB | ADM |
| hod_maria | hod | MSA | — |
| hod_kevin | hod | NRB | ICT |
| hos_ben | head_of_section | NRB | ICT |
| hos_mike | head_of_section | NRB | ADM |
| hos_linda | head_of_section | NRB | ADM |
| hos_david | head_of_section | NRB | ADM |
| tech_alex | technician | NRB | ICT (section 1) |
| tech_john | technician | NRB | ADM (section 2) |
| tech_carol | technician | NRB | ADM (section 3) |
| tech_robert | technician | NRB | ADM (section 4) |
| tech_msa | technician | MSA | (section 5) |
| tech_mtg | technician | MTG | (section 6) |
| user_sarah | user | NRB | ADM |
| user_msa | user | MSA | — |
| user_mtg | user | MTG | — |

All passwords: `TestPass123!`

---

## 17. Future Models (Phase 4–6)

These are already in the fixture. Implement in order:

### Phase 4 — Service Catalogue

```python
class DepartmentType(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

class SectionType(models.Model):
    department_type = models.ForeignKey(DepartmentType, ...)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    staff_label = models.CharField(max_length=50)   # e.g. "Carpenter", "Electrician"
    default_sla_hours = models.IntegerField(default=72)

class ServiceCategory(models.Model):
    section_type = models.ForeignKey(SectionType, ...)
    name = models.CharField(max_length=100)

class ServiceItem(models.Model):
    category = models.ForeignKey(ServiceCategory, ...)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sla_hours = models.IntegerField(null=True)      # Overrides SectionType default
    requires_approval = models.BooleanField(default=False)
    form_schema = models.JSONField(default=list)    # Array of field defs
```

**form_schema field def shape:**

```json
{
  "name": "field_key",
  "label": "Display Label",
  "type": "text|textarea|select|multiselect|number|date",
  "required": true,
  "options": ["A", "B"],   // select/multiselect only
  "min": 1,                // number only
  "max": 100               // number only
}
```

### Phase 5 — ERP Integration

Add `erp_ticket_id`, `erp_synced_at` fields to Ticket. Sync via outbound webhook.

### Phase 6 — Multi-org

Add `Organization.parent` self-FK. Manager scope becomes configurable.

---

## 18. Settings & Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | SQLite (dev) | PostgreSQL DSN for prod |
| `SECRET_KEY` | hardcoded dev key | Must set in prod |
| `DEBUG` | `True` | Set `False` in prod |
| `ALLOWED_HOSTS` | `*` | Restrict in prod |
| `CORS_ALLOWED_ORIGINS` | localhost:5173 | Add prod frontend URL |
| `EMAIL_BACKEND` | console | Set SMTP for magic links |
| `EMAIL_HOST` | smtp.gmail.com | |
| `EMAIL_PORT` | 587 | |
| `EMAIL_HOST_USER` | — | |
| `EMAIL_HOST_PASSWORD` | — | |
| `REDIS_URL` | — | Required for caching in prod |

`.env` file at `django_resolver/.env` — loaded via `python-dotenv` in settings.

---

## 19. Deployment (Render)

Config: `render.yaml` at repo root.

Build command: `./build.sh` (runs `pip install`, `collectstatic`, `migrate`).

```bash
# build.sh essentials
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
python manage.py loaddata tickets_initial_data --ignorenonexistent
```

Static files served by Whitenoise. No separate static file server needed.

---

## 20. Common Pitfalls

**Role string migration**: `models.py` and `permissions.py` still use `section_head`/`director`. The fixture uses `head_of_section`/`manager`. Before implementing Phase 3+ features, write a data migration and update all string references.

**Ticket numbering**: uses `section.department.code`, not section code. All sections in the same department share one counter (`NRB-ADM-NNNNN`).

**Escalation clock**: starts at `assigned_at`, not `created_at`. Unassigned tickets never escalate. Setting `next_escalation_due` on an unassigned ticket is a bug.

**pending status**: requires `assigned_to`, `pending_reason`, and `pending_comment`. Someone must be holding it.

**Facility FK**: `on_delete=CASCADE`, no `null=True` on current model. If ServiceItem-based creation drops facility requirement, add a migration.

**`--ignorenonexistent`**: always use this flag with `loaddata` until Phase 4 models are migrated.

**Analytics URL stale strings**: `analytics/views.py` imports `DirectorDashboardView` and `SectionHeadDashboardView`. When roles rename, update the view names too.

**Test DB**: `--reuse-db` in pytest.ini. After schema changes run `pytest --create-db` once to rebuild.

**M2M sections**: technician `sections` is a M2M through table. In fixtures this serializes as a list of PKs under `"sections": [1, 2]` on the `tickets.customuser` model record.
