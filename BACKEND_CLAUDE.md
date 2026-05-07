# CLAUDE.md — Django Resolver Backend

> **Kenya School of Government — Multi-Campus Service Desk System**
> Django 6.0.3 · DRF 3.16.1 · PostgreSQL · Token Auth

---

## 1. Project Overview

Resolver is a multi-campus facilities and IT service-desk system. Staff raise tickets against service items; technicians are assigned within sections; supervisors manage at progressively broader scopes (section → campus → department-wide). The backend exposes a REST API consumed exclusively by the React frontend.

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
  ├── Campus 1 (NRB, MSA, MTG, NYR, ELD)
  │     └── Department (ICT, ADM, HR, FAC)
  │           └── Section (e.g. "Network", "Maintenance")
  │                 └── Facility (physical room/asset)
  │                       └── Ticket
  └── Campus 2+
        └── Department (same departments, different campus)
              └── Section (same structure)
```

**Key insight**: Departments span multiple campuses. A Manager/Director oversees a single Department across *all* campuses where that department exists.

---

## 5. Role System

### Current DB strings (models.py ROLE_CHOICES)

| DB value | Display | Scope |
|----------|---------|-------|
| `user` | User | Creates own tickets |
| `technician` | Technician | Works on assigned sections |
| `head_of_section` | Head of Section | Manages technicians + tickets in one section (one campus) |
| `hod` | Head of Department | Manages department + HoS in one campus |
| `manager` | Manager/Director | Views analytics across department (all campuses) |
| `admin` | System Administrator | System-wide access |

### Permission Scope per Role

| Role | Ticket List | Ticket Detail | Can Assign | Can Escalate | Analytics | Reports |
|------|------------|---------------|-----------|-------------|-----------|---------|
| user | Own only | Own only | ❌ | ❌ | ❌ | ❌ |
| technician | Own sections | Own sections | ❌ | ❌ | Own section | ❌ |
| head_of_section | Department tickets | Department tickets | ✓ (within section) | ✓ | Department | ✓ |
| hod | Campus dept tickets | Campus dept tickets | ✓ (campus scope) | ✓ | Campus dept | ✓ |
| manager | ❌ (analytics only) | ❌ (analytics only) | ❌ | ❌ | **Cross-campus dept** | ✓ |
| admin | All | All | ✓ | ✓ | System-wide | ✓ |

**Manager/Director exception**: No individual ticket view/list access. Sees only aggregated analytics and reports across their department's all-campus scope.

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

### Organization, Campus, Department, Section

Standard hierarchy. **Department spans multiple campuses** (e.g., "ICT Department" exists at NRB, MSA, MTG).

**Section FK**: `section.head_of_section` → CustomUser (head_of_section role, campus + department scope).

### Ticket (`tickets.models.Ticket`)

Key fields:

| Field | Type | Notes |
|-------|------|-------|
| `ticket_no` | CharField(20) | Auto `CAMPUS-DEPT-NNNNN` |
| `status` | CharField | See §8 |
| `priority` | CharField | See §9 |
| `section` | FK(Section) | Required |
| `facility` | FK(Facility) | Required — add `null=True` migration if needed |
| `service_item` | FK(ServiceItem) | Links to service catalogue (Phase 4+) |
| `raised_by` | FK(CustomUser) | Set on create |
| `assigned_to` | FK(CustomUser, null) | Technician or HoS |
| `assigned_at` | DateTimeField(null) | Set when assigned; escalation clock start |
| `escalation_level` | IntegerField(0) | 0/1/2 |
| `escalated_at` | DateTimeField(null) | Set on first escalation |
| `escalated_to` | FK(CustomUser, null) | Who escalation went to |
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

### ServiceCategory System (Phase 4)

**Models**:
```python
DepartmentType(name, code, description)
SectionType(department_type, name, code, staff_label, default_sla_hours)
ServiceCategory(section_type, name)  # e.g. "Electrical Services"
ServiceItem(category, name, description, sla_hours, requires_approval, form_schema)
```

**Purpose**: Identify work type without a `specialty` field on CustomUser. Ticket belongs to a ServiceItem → Category → SectionType, allowing semantic work-type display on frontend.

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

**staff_label**: Display-only. E.g., "Artisan" (Maintenance), "Technician" (ICT), "Officer" (Admin). Does not affect database role logic.

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
GET        /sections/<pk>/technicians/  # Available technicians in section
POST       /sections/<pk>/add-technician/  # Add technician to section
DELETE     /sections/<pk>/remove-technician/?user_id=<id>
```

### Analytics

```
GET  /analytics/tickets/
GET  /analytics/technicians/
GET  /analytics/admin-dashboard/
GET  /analytics/hod/          # HoD-scoped: their campus + department
GET  /analytics/section-head/ # Head-of-section scoped
GET  /analytics/manager/      # Manager-scoped: department across all campuses
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
| `TechnicianService.add_technician_to_section(user, technician, section)` | Add with scope validation |
| `TechnicianService.remove_technician_from_section(user, technician, section)` | Remove with scope validation |
| `TechnicianService.get_assignable_technicians(user, section)` | Return tech list per role scope |
| `validate_status_transition(current, new)` | Pure validator |
| `process_auto_escalations()` | Called by management command |

### Scope validation in TechnicianService

```python
def add_technician_to_section(user, technician, section):
    # Admin: any technician, any section
    # Manager: technician in same department, any campus
    # HoD: technician in same campus + same department
    # Head of Section: technician in same campus + same department
    # Permission denied: user, technician
```

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

### ServiceCategory serialization

```python
class ServiceCategorySerializer(serializers.ModelSerializer):
    section_type = NestedSectionTypeSerializer(read_only=True)
    service_items = ServiceItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = ServiceCategory
        fields = ["id", "name", "section_type", "service_items"]
```

---

## 13. Filtering & Pagination

**Filter class**: `tickets/api/filters.py` — uses `django-filter`.

Ticket filterable fields: `status`, `priority`, `section`, `assigned_to`, `raised_by`, `created_at` (date range), `service_item` (Phase 4+).

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

## 14. Permission Classes (`api/permissions.py`)

| Class | Used for | Behavior |
|-------|----------|----------|
| `IsWithinOrganizationalScope` | Object-level org scope gating | Enforces campus/dept/section visibility per role |
| `CanViewAndEditTickets` | Ticket list/detail | Permissive GET (role-aware results), restrictive PATCH |
| `CanAssignTickets` | Assignment endpoint | Must be HoS/HoD/Manager/Admin |
| `CanEscalateTickets` | Manual escalation | Must be HoS/HoD/Manager/Admin |
| `CanViewAnalytics` | Analytics endpoints | Role-scoped analytics (Manager sees cross-campus) |
| `CanManageSectionTechnicians` | Add/remove technicians | Scope-validated (campus + dept checks) |
| `IsAdminOrReadOnly` | Org structure CRUD | Admin-only write, read-only for others |

---

## 15. Admin Interface

Uses **Django Unfold** (`django-unfold`). Config in `resolver/settings.py` under `UNFOLD = { ... }`.

Site title: "Resolver". Header: "Maintenance Ticket Management".

Unfold must be listed **before** `django.contrib.admin` in `INSTALLED_APPS`. All admin classes inherit from `unfold.admin.ModelAdmin`.

---

## 16. Testing

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
| `test_organizational.py` | Scope rules per role (CORRECTED for manager) |
| `test_workflow.py` | Status transitions |
| `test_ticket_operations.py` | Assign, escalate, close |
| `test_analytics.py` | Analytics view responses (manager cross-campus) |
| `test_serializers.py` | Serializer field validation |
| `test_spec_compliance.py` | Contract tests |

Base class: `tickets/tests/base.py` → `BaseTicketTestCase` with `setUpTestData()`.

---

## 17. Fixture & Seed Data

**File**: `tickets/fixtures/tickets_initial_data.json`

Load order matters — use:

```bash
python manage.py loaddata tickets_initial_data --ignorenonexistent
```

`--ignorenonexistent` skips DepartmentType/SectionType/ServiceCategory/ServiceItem records until those models are migrated.

### Fixture structure

| Model | Count | Notes |
|-------|-------|-------|
| Organization | 1 | KSG |
| Campus | 5 | NRB, MSA, MTG, NYR, ELD |
| Department | 9 | ICT, Administration, HR, FAC, Finance, etc. |
| Section | 8 | Network, Maintenance, etc. |
| Facility | 11 | Buildings, rooms, equipment |
| CustomUser | 18 | Roles: user, tech, HoS, HoD, Manager, Admin |
| Ticket | 23+ | Mixed statuses, priorities, escalation states |
| Comment | ~20 | Related to tickets |
| Feedback | ~8 | On resolved/closed tickets |
| TicketLog | ~35+ | Status changes, assignments, escalations |
| DepartmentType | 4 | Skipped until Phase 4 |
| SectionType | 6 | Skipped until Phase 4 |
| ServiceCategory | 9+ | Skipped until Phase 4 |
| ServiceItem | 54+ | Skipped until Phase 4 |

### Seed users

| Username | Role | Campus | Department | Notes |
|----------|------|--------|-----------|-------|
| admin_user | admin | NRB | ICT | System admin |
| manager_ict | manager | — | ICT | Oversees ICT across all campuses |
| manager_adm | manager | — | Administration | Oversees Admin across all campuses |
| hod_ict_nrb | hod | NRB | ICT | ICT dept head at NRB |
| hod_adm_nrb | hod | NRB | Administration | Admin dept head at NRB |
| hod_ict_msa | hod | MSA | ICT | ICT dept head at MSA |
| hos_network_nrb | head_of_section | NRB | ICT | Network section head |
| hos_maint_nrb | head_of_section | NRB | Administration | Maintenance section head |
| tech_nrb_network | technician | NRB | ICT | Assigned to Network section |
| tech_nrb_maint_elec | technician | NRB | Administration | Assigned to Maintenance/Electrical |
| tech_nrb_maint_plumb | technician | NRB | Administration | Assigned to Maintenance/Plumbing |
| tech_msa | technician | MSA | ICT | MSA ICT technician |
| user_nrb | user | NRB | ICT | Regular user |
| user_msa | user | MSA | Administration | MSA user |
| user_mtg | user | MTG | — | MTG user |

All passwords: `TestPass123!`

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

**Manager scope**: No individual ticket list/detail access. Manager sees only analytics and reports. Verify endpoints return 403/empty for ticket CRUD.

**Technician management**: When HoD/HoS adds a technician to a section, validate both are in same campus + department. Manager cannot add technicians (only HoD/HoS/Admin can).

**ServiceCategory vs specialty**: Never add a `specialty` field to CustomUser. Work type is identified via Ticket → ServiceItem → ServiceCategory. This allows one technician to work across multiple service types.

**Escalation clock**: starts at `assigned_at`, not `created_at`. Unassigned tickets never escalate. Setting `next_escalation_due` on an unassigned ticket is a bug.

**pending status**: requires `assigned_to`, `pending_reason`, and `pending_comment`. Someone must be holding it.

**Ticket numbering**: uses `section.department.code`, not section code. All sections in the same department share one counter (`NRB-ADM-NNNNN`).

**Facility FK**: `on_delete=CASCADE`, no `null=True` on current model. If ServiceItem-based creation drops facility requirement, add a migration.

**`--ignorenonexistent`**: always use this flag with `loaddata` until Phase 4 models are migrated.

**Test DB**: `--reuse-db` in pytest.ini. After schema changes run `pytest --create-db` once to rebuild.

**M2M sections**: technician `sections` is a M2M through table. In fixtures this serializes as a list of PKs under `"sections": [1, 2]` on the `tickets.customuser` model record.
