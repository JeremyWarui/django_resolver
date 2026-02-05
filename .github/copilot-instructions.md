# Copilot Instructions for Django Resolver

## Project Overview
**Django Resolver** is a Django REST API for maintenance ticket management with token-based authentication, role-based access, analytics, and reporting. Core app is `tickets/` with a layered architecture separating concerns across models, serializers, views, services, and analytics.

## Authentication System
**Current**: Password-based authentication for all user roles
- All users authenticate with username/password
- Simple and reliable, no email configuration required
- Test accounts have unique passwords defined in fixtures (e.g., `janedoe123`, `alexsmith123`, `adminuser123`)
- See `docs/DEFAULT_CREDENTIALS.md` for complete test account list

**Magic Link (Future)**: Code is preserved but commented out
- Located in `tickets/api/simple_auth_views.py`
- Can be enabled later when email service is configured
- See `docs/AUTHENTICATION.md` for enable instructions

## Architecture & Critical Patterns

### Layered Architecture
- **Models** (`tickets/models.py`): Data schema with custom behaviors
  - `CustomUser`: Extends AbstractUser with role field (user/admin/technician/manager) and M2M to sections
  - `Ticket`: Auto-generates `TKT-XXXXXX` numbers via `save()`, tracks lifecycle with `resolved_at`, uses helper methods `change_status()` and `change_assignment()` for atomic updates + logging
  - Status flow: open → assigned → in_progress → pending ⇄ resolved → closed
- **Services** (`tickets/api/services/`): Business logic layer - **NEVER put business logic in views**
  - `ticket_services.py`: Validates status transitions, enforces role permissions, handles assignment rules (technician must belong to ticket's section)
  - Use `validate_status_transition(old_status, new_status, user_role)` before status changes
- **Views** (`tickets/api/views/`): Request/response handling only
  - `resource_views.py`: DRF generics for CRUD, delegates to services via `perform_create()`/`perform_update()`
  - Custom filters: `?assigned_to__isnull=true`, `?is_overdue=true` (>7 days old in open/assigned/in_progress)
- **Analytics** (`tickets/api/analytics/`): Separate module with `analytics.py` (logic) and `views.py` (endpoints)
- **Reports** (`tickets/api/reports/`): PDF/CSV generation with `report_generator.py`

### Key Architectural Decisions
- **Index files**: Use `index.py` in submodules for clean imports (see `tickets/api/views/index.py`, `tickets/api/analytics/index.py`)
- **Atomic operations**: Status/assignment changes use model helper methods (`ticket.change_status(new_status, performed_by=user)`) to ensure atomic DB updates + `TicketLog` creation
- **Pagination**: Custom classes in `tickets/api/pagination.py` add metadata (`total_pages`, `current_page`) to DRF responses

## Developer Workflows

### Setup
```bash
# 1. Environment
cp .env.example .env  # Configure SECRET_KEY, DEBUG, ALLOWED_HOSTS, DATABASE_URL

# 2. Dependencies
pip install -r requirements.txt

# 3. Database
python manage.py migrate
python manage.py createsuperuser

# 4. Sample data (118 records: users, tickets, comments, feedback)
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### Testing
```bash
# All tests
python manage.py test tickets

# Specific test file
python manage.py test tickets.tests.test_apis

# Single test
python manage.py test tickets.tests.test_apis.TicketAPITestCase.test_ticket_lifecycle_workflow
```
**Test organization** (`tickets/tests/`): `test_models.py`, `test_serializers.py`, `test_apis.py` (permissions, filters, lifecycle), `test_workflow.py` (status transitions), `test_analytics.py`

### Debugging Fixtures
```bash
python manage.py shell
from tickets.models import *
# Example: See SAMPLE_QUERIES.md for 20+ pre-built queries
Ticket.objects.filter(status='pending').values('ticket_no', 'pending_reason')
```

## Critical Business Rules

### Ticket Status Transitions
**Valid flows** (enforced in `validate_status_transition()`):
- `open` → `assigned` (auto-set when `assigned_to` is set)
- `assigned` → `in_progress` OR `pending`
- `in_progress` → `pending` OR `resolved`
- `pending` → `in_progress` OR `resolved`
- `resolved` → `closed` (admin/manager only)
- `closed`: No further transitions allowed

**Role permissions**:
- `user`: Can create tickets, add comments (if related), submit feedback
- `technician`: Can update status (except `closed`), must belong to ticket's section
- `admin`/`manager`: Full access including closing tickets

### Assignment Rules
- Only technicians can be assigned (`user.role == 'technician'`)
- Technician must have ticket's section in `user.sections.all()`
- Cannot reassign resolved/closed tickets

### Auto-behaviors
- Ticket numbers: Generated in `Ticket.save()` as `TKT-{id:06d}`
- Username generation: `UserSerializer.create()` uses `{first_name}.{last_name}`, appends `-{counter}` if taken
- `resolved_at`: Auto-set when status → `resolved` or `closed`

## API Patterns

### Resource Endpoints
```
/api/sections/, /api/facilities/, /api/tickets/, /api/comments/, /api/feedback/, /api/users/
```
- Use `StandardResultsSetPagination` (10/page) by default
- Filtering: `?status=open&section=1&assigned_to__isnull=true&is_overdue=true`

### Technician Assignment
```
/api/technicians/?section_id={id}  # Get technicians filtered by section for assignment
```
- Tickets include `available_technicians` field showing who can be assigned
- Only technicians belonging to ticket's section can be assigned
- Frontend should use this endpoint to populate assignment dropdowns

### Analytics Endpoints
```
/api/analytics/tickets/?timeframe=week&facility_id=1&group_by=day&days=30
/api/analytics/technicians/?technician_id=5
/api/analytics/admin-dashboard/
```
Query params: `timeframe` (day/week/month), `facility_id`, `section_id`, `technician_id`, `group_by`, `days`

### Reports
```
/api/reports/generate/?report_type=tickets&format=pdf&status=open
/api/reports/types/
```

## Frontend Integration

### CORS Configuration
- Configured in `resolver/settings.py` using `django-cors-headers`
- Allowed origins from env var `ALLOWED_ORIGINS` (comma-separated): `http://localhost:5173,http://127.0.0.1:5173`
- `CORS_ALLOW_CREDENTIALS = True` enables cookies/auth headers
- CORS middleware positioned before `CommonMiddleware` in middleware stack

### API Response Format
All paginated endpoints return:
```json
{
  "count": 100,
  "next": "http://api.example.org/accounts/?page=3",
  "previous": "http://api.example.org/accounts/?page=1",
  "total_pages": 10,
  "current_page": 2,
  "results": [...]
}
```

## Performance Optimizations

### Database Indexes
- `Ticket` model has 4 indexes for optimal query performance:
  - `ticket_updated_at_idx` - Single field index on `-updated_at` (default ordering)
  - `ticket_status_idx` - Single field index on `status` (frequently filtered)
  - `ticket_assigned_to_idx` - Single field index on `assigned_to` (assignment queries)
  - `ticket_status_updated_idx` - Composite index on `(status, -updated_at)` (common filter combo)
- Default ordering: `Ticket.Meta.ordering = ['-updated_at']` (most recent updates first)
- Performance impact: 66x faster (4.7s → 0.07s for 100 tickets)

### Conditional Serialization
- **List views** use simplified serialization for performance:
  - Skip `comments`, `feedback`, `available_technicians` (expensive nested queries)
  - Use `assigned_to_name` (simple string) instead of full `assigned_to` object
  - Context flag: `skip_available_technicians=True` in `get_serializer_context()`
- **Detail views** include full nested objects and relationships
- Controlled via `get_fields()` override in `TicketSerializer`

### Query Optimization
- Use `select_related()` for foreign keys: `section`, `facility`, `raised_by`, `assigned_to`
- Only use `prefetch_related()` in detail views (comments, feedback)
- OrderingFilter enabled with fields: `created_at`, `updated_at`, `status`

## Conventions

### Code Style
- Follow PEP 8
- Use DRF generics for CRUD (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`)
- Custom views for analytics (inherit `APIView`)

### Adding Features
1. **Model changes**: Add to `tickets/models.py`, then `python manage.py makemigrations`
2. **Business logic**: Add to relevant service file, NOT views
3. **API endpoint**: Add view to `tickets/api/views/`, import in `index.py`, add route to `tickets/api/urls.py`
4. **Tests**: Add to appropriate `tickets/tests/test_*.py` file

### Common Pitfalls
- ❌ Don't modify closed tickets (enforced in `update_ticket()`)
- ❌ Don't bypass services - always call service functions from views
- ❌ Don't create `TicketLog` manually - use `ticket.change_status()` or `ticket.change_assignment()`
- ❌ Don't remove database indexes without profiling performance impact first
- ✅ Use `performed_by` parameter in model helpers for audit trail
- ✅ Add database indexes on frequently filtered/ordered fields

## Key Files Reference
- `tickets/api/README.md`: API architecture deep-dive
- `docs/api/ANALYTICS.md`: Analytics query params, response schemas
- `tickets/fixtures/SAMPLE_QUERIES.md`: 20+ ready-to-use Django ORM examples
- `tickets/tests/README.md`: Test coverage map (40+ test cases)
