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
pytest tickets/tests/test_models.py -v

# Run a single test by name
pytest tickets/tests/test_workflow.py::TestStatusTransitions::test_open_to_assigned -v

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

# Load fixture (always use --ignorenonexistent until Phase 4 models exist)
python manage.py loaddata tickets_initial_data --ignorenonexistent

# Flush and reload
python manage.py flush --no-input && python manage.py loaddata tickets_initial_data --ignorenonexistent

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
  → resolver/urls.py  (/api/ → tickets/api/urls.py)
  → tickets/api/views/views.py   (HTTP handling, permission checks)
  → tickets/api/services/        (business logic, org-scope validation)
  → tickets/models.py            (ORM, state machine methods)
  → tickets/email_service.py     (side effects)
```

Views **never** mutate tickets directly via ORM — they always call `TicketService`.

### Directory Map

```
tickets/
├── models.py               — All models (see §Models)
├── serializers.py          — All DRF serializers
├── admin.py                — Unfold admin registrations
├── pagination.py           — TicketPagination (page_size=20, max=100)
├── email_service.py        — EmailService (magic link + ticket notifications)
├── fixtures/
│   └── tickets_initial_data.json  — Seed data (use this one)
├── management/commands/
│   └── process_auto_escalations.py
└── api/
    ├── urls.py             — All URL patterns
    ├── permissions.py      — Permission classes
    ├── filters.py          — DjangoFilterBackend filter classes
    ├── simple_auth_views.py — Login / logout / register / profile
    ├── views/
    │   ├── index.py        — Re-exports all view classes
    │   └── views.py        — All view implementations
    ├── services/
    │   ├── __init__.py     — Public API (re-exports below)
    │   ├── ticket_service.py      — TicketService (create, assign, escalate, close)
    │   ├── technician_service.py  — TechnicianService (section membership)
    │   ├── validators.py   — validate_status_transition, validate_pending_transition
    │   └── exceptions.py   — TicketServiceException, InsufficientScopeException, etc.
    ├── analytics/
    │   ├── index.py        — Re-exports analytics views
    │   ├── views.py        — Analytics API views
    │   ├── base_analytics.py
    │   ├── admin_analytics.py
    │   ├── manager_analytics.py
    │   ├── hod_analytics.py
    │   ├── section_head_analytics.py
    │   ├── ticket_analytics.py
    │   └── technician_analytics.py
    └── reports/
        ├── report_generator.py
        └── views.py
```

---

## Organizational Hierarchy

```
Organization
  └── Campus  (code e.g. "NRB", "MSA")
        └── Department  (code e.g. "ICT", "ADM")
              └── Section  (e.g. "Software", "Procurement")
                    ├── Facility  (physical room/asset)
                    └── Ticket
```

Ticket number auto-generated as `CAMPUS-DEPT-NNNNN` (e.g. `NRB-ICT-00001`). All sections in the same department share one counter.

---

## Role System

| DB value | Scope |
|----------|-------|
| `user` | Own tickets only |
| `technician` | Tickets in assigned sections |
| `head_of_section` | Own section; inherits technician perms + can assign |
| `hod` | Own department on own campus |
| `manager` | Own department across all campuses in the org; can list/view/approve tickets |
| `admin` | Full system access |

`CustomUser.sections` is a M2M to `Section` — this is how technicians are scoped.

`manager` ticket scope: `section__department__code == user.primary_department.code` across all campuses in the org.

---

## Ticket Status Machine

```
open ──────────────────────────────────→ assigned → in_progress ⇄ pending → resolved → closed
pending_approval → (approve) → open
pending_approval → (reject)  → rejected
```

- Use `Ticket.change_status()`, never set `status` directly.
- `pending` requires `assigned_to`, `pending_reason`, and `pending_comment`.
- Priority is overridden on every `save()` by escalation level (0→low, 1→medium, ≥2→high). Setting `priority="critical"` bypasses this.
- Escalation clock starts at `assigned_at`, not `created_at`. Unassigned tickets never escalate.

---

## Serializers

Two ticket serializers:

| Class | Used for |
|-------|---------|
| `TicketListSerializer` | `GET /tickets/` — flat, lightweight |
| `TicketSerializer` | `GET /tickets/<pk>/` — full nested detail |

Read/write split pattern used throughout:
```python
section = NestedSectionSerializer(read_only=True)
section_id = PrimaryKeyRelatedField(queryset=Section.objects.all(), source='section', write_only=True)
```

Several serializers have `get_fields()` overrides that strip fields based on `request.user.role`:
- `FacilitySerializer`: strips `purchase_date`, `warranty_expiry`, `asset_value` below `hod`
- `SectionSerializer`: strips `technicians` below `head_of_section`
- `TicketSerializer`: strips escalation detail from `user`; strips `available_technicians` and `organizational_path` below `head_of_section`

---

## Authentication

DRF Token Auth. Header: `Authorization: Token <40-char-hex>`.

| Method | URL | Notes |
|--------|-----|-------|
| POST | `/api/auth/login/` | Returns `{ token, user }` |
| POST | `/api/auth/logout/` | Invalidates token |
| GET | `/api/auth/profile/` | Same as `/api/users/me/` |
| POST | `/api/auth/register/` | Self-registration, role defaults to `user` |
| GET | `/api/auth/check-method/` | Returns `{ method: "password" }` |

Magic-link endpoints exist in `simple_auth_views.py` but are commented out. Enable by configuring `EMAIL_HOST_*` settings.

---

## Fixture & Seed Data

```bash
python manage.py loaddata tickets_initial_data --ignorenonexistent
```

`--ignorenonexistent` skips Phase 4 models (DepartmentType, SectionType, ServiceCategory, ServiceItem) until their migrations exist.

All fixture users share the password: **`adminuser123`**

Key seed users:

| Username | Role | Campus | Notes |
|----------|------|--------|-------|
| `admin_user` | admin | NRB | |
| `manager_ict` | manager | NRB | ICT dept |
| `hod_ict_nrb` | hod | NRB | ICT dept |
| `hos_ict_nrb` | head_of_section | NRB | ICT section 1 |
| `tech_alex` | technician | NRB | ICT section 1 |
| `user_sarah` | user | NRB | ADM dept |
| `user_msa` | user | MSA | |

---

## Testing

Tests use `pytest-django` with `--reuse-db` (drop with `--create-db` after migrations change).

Base classes in `tickets/tests/base.py`:

- `BaseTicketTestCase` — `setUpTestData()` creates full org hierarchy + sample ticket. Use `self.user`, `self.admin`, `self.technician`, `self.section`, `self.facility`, `self.ticket`. Has `create_ticket()`, `create_comment()`, `create_feedback()` helpers.
- `BaseAPITestCase(BaseTicketTestCase)` — adds `self.api_client` (authenticated as `self.user`). Use `self.authenticate_as(user)` to switch roles mid-test.

---

## Key Pitfalls

- **`manager` ticket scope**: managers can list and view tickets scoped to their department code across all campuses in the org. `_manager_in_scope()` in `permissions.py` enforces object-level access for PATCH/PUT/DELETE. `get_accessible_tickets()` in `ticket_service.py` scopes the list queryset.
- **Escalation clock**: starts at `assigned_at`. Setting `next_escalation_due` on an unassigned ticket is a bug.
- **`pending` fields**: status transition to `pending` requires both `pending_reason` and `pending_comment` or it raises `ValidationError`.
- **Facility FK**: `on_delete=CASCADE`, no `null=True`. If ticket creation ever drops the facility requirement, add a migration first.
- **Ticket numbering** uses `section.department.code`, not section code. Two sections in the same department share a counter.
- **Test DB sequence**: call `self.reset_ticket_sequence()` in `setUp()` if a test needs predictable ticket IDs.

---

## Environment Variables

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | SQLite (dev) | PostgreSQL DSN in prod |
| `SECRET_KEY` | hardcoded dev key | Must override in prod |
| `DEBUG` | `True` | |
| `CORS_ALLOWED_ORIGINS` | `localhost:5173` | Add prod frontend URL |
| `REDIS_URL` | — | Required for caching in prod |
| `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | — | For magic-link auth |

`.env` file at `django_resolver/.env`, loaded via `python-dotenv`.

---

## Deployment (Render)

`render.yaml` at repo root. Build command: `./build.sh` (pip install → collectstatic → migrate → loaddata).

Live backend: `https://django-resolver.onrender.com/api`

---

## Service Catalogue (Partially Implemented)

Models `DepartmentType`, `SectionType`, `ServiceCategory`, `ServiceItem` exist in `models.py` and in fixtures but **tables are not yet migrated**. The fixture records are silently skipped by `--ignorenonexistent`.

Once migrated, the ticket creation flow will support `service_item_id`. If `ServiceItem.requires_approval = True`, the ticket starts as `pending_approval` instead of `open`.

The `Ticket` model already has `service_item` FK, `request_data` JSONField, and `due_date` DateTimeField. The `save()` method already sets `due_date` from the SLA cascade: `service_item.sla_hours` → `section.effective_sla_hours`.

---

## Future Phases

### Phase 4 — SLA Tracking & Email Notifications

Everything needed to surface SLA deadlines and send lifecycle emails. Do not start until the service catalogue models are migrated and all existing tests pass.

#### Backend

**1. Fix `is_overdue` on `Ticket` model (`models.py:730`)**

The current implementation uses a hardcoded 7-day window from `created_at`. Replace it with a `due_date`-based check:

```python
@property
def is_overdue(self) -> bool:
    if not self.due_date:
        return False
    if self.status in ('resolved', 'closed', 'rejected'):
        return False
    return timezone.now() > self.due_date
```

**2. Add `time_remaining` property to `Ticket` model**

```python
@property
def time_remaining(self):
    if self.due_date and not self.is_overdue:
        return self.due_date - timezone.now()
    return None
```

Expose both `is_overdue` and `time_remaining` in `TicketSerializer` as `SerializerMethodField` (read-only). `time_remaining` should serialize as total seconds (integer) or null.

**3. Add `check_sla_breaches` management command**

Create `tickets/management/commands/check_sla_breaches.py`:
- Queries tickets where `due_date < now()` and status not in `('resolved', 'closed', 'rejected')`
- For each: sends breach alert to `assigned_to` and `section.head_of_section`
- Uses a `TicketLog` entry (action `"sla_breach_alert"`) to track when the alert was sent — skip if a log entry exists within the last 24h to prevent duplicate emails
- Add a cron comment at the top: `# 0 * * * * python manage.py check_sla_breaches`
- Do not add Celery — use cron only

**4. Implement missing email notifications in `email_service.py`**

Currently implemented: `send_ticket_assigned` (event 2), `send_ticket_pending_approval` (event 4), `send_ticket_rejected` (event 6), `send_ticket_resolved` (event 7).

Add the four missing methods to `TicketEmailService`:

| Method | Trigger | Recipients |
|--------|---------|------------|
| `send_ticket_created(ticket)` | Ticket created | HOD + `section.head_of_section` |
| `send_ticket_status_updated(ticket, old_status)` | Any status change | `ticket.raised_by` |
| `send_ticket_approved(ticket)` | Approved | `ticket.raised_by` + `section.head_of_section` |
| `send_sla_breach_alert(ticket)` | Called by `check_sla_breaches` command | `ticket.assigned_to` + `section.head_of_section` |

Each method must have a `.txt` and `.html` template pair under `tickets/templates/emails/`. Use `EmailMultiAlternatives`. All methods silently return `False` (never raise) if email is not configured.

Wire `send_ticket_created` into `TicketService.create_ticket()` and `send_ticket_status_updated` into `TicketService` wherever status transitions happen.

**5. Tests to add**

- `is_overdue` returns `False` when `due_date` is null
- `is_overdue` returns `False` for terminal statuses even when overdue
- `is_overdue` returns `True` when `due_date` has passed and status is open/active
- `check_sla_breaches` command finds the correct tickets
- `check_sla_breaches` does not send duplicate alerts within 24h (check `TicketLog`)
- Each new email method sends to the correct recipients (use `django.test.utils.override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')`)

---

### Phase 5 — Attachments

Organisation analytics is already complete (`OrganizationalAnalyticsView` in `analytics/views.py`, wired at `/api/analytics/organizational/`). Only the attachments feature remains.

Do not start until Phase 4 is complete and all tests pass.

#### Backend

**1. Add `Attachment` model to `models.py`**

```python
class Attachment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE,
                               related_name='attachments')
    file = models.FileField(upload_to='tickets/attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()   # bytes
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
```

**2. Server-side validation (enforce in the serializer or view)**
- Max file size: 10 MB
- Allowed content types: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Max 5 attachments per ticket — check `ticket.attachments.count()` before saving

**3. API endpoints**

```
POST   /api/tickets/{id}/attachments/     — upload; permission: anyone who can view the ticket
GET    /api/tickets/{id}/attachments/     — list attachments on a ticket
DELETE /api/attachments/{id}/             — delete; permission: uploader or admin only
```

Add to `tickets/api/urls.py`. Register in `views/index.py`.

**4. File storage**

In `settings.py`, set `MEDIA_ROOT` and `MEDIA_URL`. In dev, Django serves media via `django.views.static.serve` (add to `resolver/urls.py` under `settings.DEBUG`). In prod (Render), configure an external storage backend (e.g. Cloudinary or S3 via `django-storages`) — document the required env vars in this file when that decision is made.

**5. Expose attachments in `TicketSerializer`**

Add a nested `AttachmentSerializer` (read-only) to `TicketSerializer.attachments`. Do not include in `TicketListSerializer` — keep the list endpoint lightweight.
