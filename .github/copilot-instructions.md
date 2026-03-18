# Copilot Instructions for Django Resolver

## Project Overview
**Django Resolver** is an enterprise-grade REST API for multi-tiered organizational maintenance ticket management with:
- **Organizational Hierarchy**: Organization → Campus → Department → Section hierarchy
- **Role-Based Access Control**: 6 roles (user, technician, section_head, hod, director, admin) with scope-based permissions
- **Escalation Workflows**: Automatic 2-level escalation (section_head → HOD) with customizable timing
- **Organizational Ticket Numbering**: CAMPUS-DEPT-XXXXX format (e.g., MAIN-IT-00001)
- **Token Authentication**: Password-based login + commented magic link support
- **Analytics & Reporting**: Organization-scoped analytics and PDF/CSV reports

Core app is `tickets/` with layered architecture: Models → Services (business logic) → Views (HTTP handling) → Serializers (data transformation).

## Authentication System
**Current**: Password-based authentication for all user roles
- All users authenticate with username/password via `/api/auth/login/`
- Token generated on login; used in `Authorization: Token {token}` header
- No email configuration required; works out of the box
- Test accounts with unique passwords in fixtures (e.g., `janedoe123`, `alexsmith123`, `adminuser123`)
- See `docs/DEFAULT_CREDENTIALS.md` for complete test account list (20+ test users)

**Magic Link (Future)**: Code preserved but commented out for future implementation
- Located in `tickets/api/simple_auth_views.py` (search for `MagicLink`)
- Enable later when email service configured
- See `docs/API_INTEGRATION_GUIDE.md` for authentication details

## Documentation Structure

**🎯 Master Guides (Start Here)**:
- **`docs/FIRST_TIME_SETUP.md`** - Complete setup guide for new developers
- **`docs/ARCHITECTURE_GUIDE.md`** - System architecture and design
- **`docs/API_INTEGRATION_GUIDE.md`** - API endpoints and integration

**Primary Documentation Location**: `docs/` directory with organized subsections:
- **Specifications**: `docs/specifications/WORKFLOW_SPEC.md` - Complete ticket workflow specification with organizational scope and architectural decisions
- **Compliance**: `docs/compliance/AUDIT_STATUS.md` - Consolidated compliance audit (96% compliance - all critical requirements met)
- **API**: `docs/API_INTEGRATION_GUIDE.md` - Complete API endpoints and integration; `docs/api/ANALYTICS.md` - Analytics specifications
- **Architecture**: `docs/ARCHITECTURE_GUIDE.md` - System design; `docs/architecture/LAYERS.md` - Layered architecture details; `docs/CODEBASE_ARCHITECTURE.md` - Complete technical reference
- **Testing**: `docs/testing/TESTING.md` - Test organization (157 tests); `docs/testing/SAMPLE_QUERIES.md` - Django ORM query examples
- **Navigation**: `docs/INDEX.md` - Master index for all documentation

**Key Documentation References**:
- Start with master guides above for your role/task
- See `docs/specifications/WORKFLOW_SPEC.md` for complete workflow requirements
- See `docs/compliance/AUDIT_STATUS.md` for compliance findings and implementation status
- See `docs/testing/TESTING.md` for comprehensive test coverage (157 tests)

## Architecture & Critical Patterns

### Organizational Models (`tickets/models.py`)
**Hierarchy (all in single file per Django best practice)**:
- `Organization`: Root entity (corporate, educational, government, healthcare)
- `Campus`: Geographic/operational divisions within org (e.g., MAIN, WEST, DOWNTOWN)
- `Department`: Functional divisions within campus (e.g., IT, FACILITIES, OPS) - has `head_of_department` FK
- `Section`: Specialized units within dept (e.g., ELECTRICAL, PLUMBING, NETWORK) - has `section_head` FK
- `Facility`: Physical/equipment assets linked to campus + department
- `CustomUser`: 6 roles (user, technician, section_head, hod, director, admin) with `primary_campus`, `primary_department`, sections M2M
- `Ticket`: Auto-generates `CAMPUS-DEPT-XXXXX` numbers, tracks escalation (level 0→1→2), status includes 'escalated'
- `TicketLog`: Immutable audit trail for all ticket changes

### Layered Architecture (Consolidated, Organization-First)
✅ **CONSOLIDATED STRUCTURE** - All functionality unified into organization-first design:

- **Models** (`tickets/models.py`): Data schema with organizational context
  - `CustomUser.organizational_scope` → returns access level (section/dept/org/system)
  - `Ticket.save()` → auto-generates CAMPUS-DEPT-XXXXX; schedules auto-escalation
  - Single model file: All models in `tickets/models.py` per Django best practice
  
- **Services** (`tickets/api/services/services.py`) - **UNIFIED SERVICE LAYER**
  - Single `TicketService` class with all business logic
  - Methods: `create_ticket()`, `assign_ticket()`, `escalate_ticket()`, `update_ticket_status()`, `close_ticket()`, `process_auto_escalations()`, `get_accessible_tickets()`
  - Validators: `validate_status_transition()`, `manual_escalation_allowed()`
  - Exceptions: `TicketServiceException`, `InsufficientScopeException`, `InvalidAssignmentException`, `InvalidEscalationException`
  - Helpers: Scope validation, notification, system user retrieval, auto-escalation logic
  - Import: `from tickets.api.services import TicketService`
  - Backwards compatibility: `OrganizationalTicketService = TicketService` alias
  
- **Views** (`tickets/api/views/views.py`) - **UNIFIED VIEW LAYER**
  - All 20+ endpoint classes consolidated in single file
  - Organization Hierarchy: `OrganizationListCreateView`, `CampusListCreateView`, `DepartmentListCreateView`, `SectionListCreateView`/`SectionDetailView`
  - Ticket Management: `TicketListCreateView`, `TicketDetailView`, `TicketEscalationView`, `OrganizationalTicketListView`, `EscalateTicketView`
  - Users: `UserListCreateView`, `UserDetailView`, `TechniciansBySectionView`, `AssignableUsersView`
  - Comments/Feedback: `CommentListCreateView`, `FeedbackListCreateView`
  - Bulk Operations: `BulkTicketStatusUpdateView`
  - Filtering: `?status=open&escalation_level=1&section=1&is_overdue=true`
  - All views use `IsWithinOrganizationalScope` permission + service layer delegation
  - Import via: `from tickets.api.views.index import <ViewName>`
  
- **Analytics** (`tickets/api/analytics/analytics.py`) - **UNIFIED ANALYTICS**
  - Single file with all analytics classes:
    - `TicketAnalytics`: Ticket counts, trends, distributions
    - `TechnicianAnalytics`: Performance metrics, workload analysis
    - `OrganizationalAnalytics`: Role-specific dashboards (Director, HOD, Section Head)
    - `AdminAnalytics`: System-wide monitoring
  - Role-specific dashboards: `director_dashboard()`, `hod_dashboard()`, `section_head_dashboard()`
  - SLA compliance tracking and escalation trend analysis
  - Import: `from tickets.api.analytics import OrganizationalAnalytics`
  
- **Reports** (`tickets/api/reports/`): PDF/CSV generation with org context

### Key Architectural Decisions
- **Unified service layer**: Single `TicketService` class - no legacy vs. organizational split
- **Unified views**: All endpoints consolidated in `views.py` with consistent organizational awareness
- **Unified analytics**: All analytics classes in one file (`analytics.py`)
- **Index files**: Use `index.py` in submodules for clean imports (see `tickets/api/views/index.py`, `tickets/api/analytics/index.py`)
- **Atomic operations**: Status/assignment changes use service methods to ensure DB updates + `TicketLog` creation
- **Pagination**: Custom classes in `tickets/api/pagination.py` add metadata (`total_pages`, `current_page`) to DRF responses
- **Single source of truth**: Each architectural layer has one primary consolidated file (services.py, views.py, analytics.py)

## Developer Workflows

### Setup
```bash
# Organizational tests (6 test classes, 75+ tests)
pytest tickets/tests/test_organizational.py -v

# Escalation workflow tests
pytest tickets/tests/test_organizational.py::EscalationWorkflowTestCase -v

# Specific test
pytest tickets/tests/test_apis.py::TicketAPITestCase::test_ticket_lifecycle_workflow -v
```
**Test organization** (`tickets/tests/`):
- `test_organizational.py` - 6 classes, 75+ tests: hierarchy, escalation, permissions, APIs, analytics
- `test_models.py`, `test_serializers.py`, `test_apis.py` (permissions, filters, lifecycle)
- `test_workflow.py` (status transitions), `test_analytics.py` (analytics endpoints)
python manage.py createsuperuser

# 4. Sample data (118 records: users, tickets, comments, feedback)
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
```

### Testing
```bash
# All tests
pytest tickets/tests/ -v

# Specific test file
pytest tickets/tests/test_apis.py -v

# Single test
pytest tickets/tests/test_apis.py::TicketAPITestCase::test_ticket_lifecycle_workflow -v
```
**Test organization** (`tickets/tests/`): `test_models.py`, `test_serializers.py`, `test_apis.py` (permissions, filters, lifecycle), `test_workflow.py` (status transitions), `test_analytics.py`

### Debugging Fixtures
```bash & Escalation
**Valid status flows** (enforced in services):
- `open` → `assigned` (auto-set when `assigned_to` assigned) → `in_progress` → `pending` ↔ `resolved` → `closed`
- `escalated`: Separate status indicating escalation in progress
- Status includes `escalated` option for parallel tracking

**Escalation workflow** (auto via `process_auto_escalations` command):
- **Level 0** (none): Initial state
- **Level 1** → Section Head escalation after `escalation_threshold_hours` (default: 48)
- **Level 2** → HOD escalation after another threshold (max level)
- **Manual escalation**: Any user can escalate with reason
- Closed tickets cannot escalate

### Role Permissions (Organizational Scope)
| Role | Organizational Scope | Permissions |
|------|-----|---|
| `user` | Section | Create tickets, comment on own, feedback |
| `technician` | Section | Update status, assign within section + user perms |
| `section_head` | Section | Escalation resolution, section oversight |
| `hod` (Head of Department) | Department | Final escalation point, dept-wide overview |
| `director` | Organization | Analytics only (no ticket management) |
| `admin` | System | Full access, close tickets, config |

### Assignment Rules (Organizational)
- Only technicians can be assigned
- Technician must have ticket's section in `user.sections.all()`
- TeOrganizational Hierarchy Endpoints
```
GET/POST     /api/organizations/
GET/PATCH    /api/organizations/{id}/
GET/POST     /api/campuses/
GET/PATCH    /api/campuses/{id}/
GET/POST     /api/departments/
GET/PATCH    /api/departments/{id}/
GET/POST     /api/sections/
GET/PATCH    /api/sections/{id}/
```

### Resource Endpoints
```
GET/POST     /api/tickets/               # Org-aware ticket CRUD
GET/PATCH    /api/tickets/{id}/          # Include escalation fields
POST         /api/tickets/{id}/escalate/ # Manual escalation endpoint
GET/POST     /api/facilities/
GET/POST     /api/comments/              # Sub-resource of tickets
GET/POST     /api/feedback/              # Sub-resource of tickets
GET/POST     /api/users/
```
- Use `StandardResultsSetPagination` (10/page) by default
- **Org-aware filtering**: `?status=open&section=1&campus=1&escalation_level=1&is_overdue=true`
- **Escalation filters**: `?escalation_level=1`, `?escalation_level=2`, `?next_escalation_due__lte={date}`

### Technician Assignment (Organization-scoped)
```
GET /api/technicians/?section_id={id}&campus_id={id}  # Technicians in section + campus
```
- Only returns technicians matching both section AND user's accessible campus
- Tickets include `available_technicians` field (org-filtered)
- Frontend uses this for assignment dropdowns

### Analytics Endpoints (Org-scoped)
```
GET /api/analytics/tickets/?timeframe=week&campus_id=1&section_id=1&days=30
GET /api/analytics/technicians/?technician_id=5&campus_id=1
GET /api/analytics/admin-dashboard/  # Director/Admin only
```
Query params: `timeframe` (day/week/month), `campus_id`, `section_id`, `facility_id`, `days`, `group_by`

### Escalation Management
```
GET  /api/tickets/?escalation_level=1  # Escalated to section_head
GET  /api/tickets/?escalation_level=2  # Escalated to HOD
POST /api/tickets/{id}/escalate/       # Manual escalation
```

### Reports
```
GET /api/reports/types/
GET /api/reports/generate/?report_type=tickets&format=pdf&campus=1&section=1ltsSetPagination` (10/page) by default
- Filtering: `?status=open&section=1&assigned_to__isnull=true&is_overdue=true`

### Technician Assignment
```6 indexes (including organizational):
  - `ticket_section_status_idx` - Composite on `(status, section, -updated_at)` (org filtering)
  - `ticket_assignment_idx` - Composite on `(assigned_to, status)`
  - `ticket_escalation_idx` - Composite on `(escalation_level, -escalated_at)` (escalation queries)
  - `ticket_auto_escalation_idx` - Composite on `(next_escalation_due, auto_escalation_enabled)` (scheduler)
  - `ticket_status_updated_idx` - Composite on `(status, -updated_at)`
  - Plus specialized org-hierarchy indexes on Campus, Department, Section
- Default ordering: `Ticket.Meta.ordering = ['-updated_at']`
- Performance impact: 66x improvement on org-filtered queries
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
``` & Patterns

### Code Style
- Follow PEP 8
- Use DRF generics for CRUD (`ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`)
- Custom views for analytics and escalation (inherit `APIView`)

### Organizational Access Control
- Always call `user.get_accessible_campuses()` before querying org resources
- Filter querysets by `campus__in=user.get_accessible_campuses()` in views
- Use `organizational_scope` property to determine access level
- Services should validate user has access to resource's org unit

### Escalation Management
- Call `process_auto_escalations()` via cron (hourly or every 30 min)
- Manual escalation: call `TicketService.escalate_ticket()` from `tickets/api/services/services.py`
- Check `next_escalation_due` before auto-escalating
- Update `escalation_reason` for audit trail

### Adding Features
1. **Model changes**: Add to `tickets/models.py` (keep all models in one file), then `python manage.py makemigrations`
2. **Business logic**: Add method to `TicketService` class in `tickets/api/services/services.py`, NOT views
3. **Escalation logic**: Add to TicketService escalation methods in consolidated `services.py`
4. **API endpoint**: Add view class to `tickets/api/views/views.py`, import in `index.py`, route in `urls.py`
5. **Analytics feature**: Add method to appropriate class in `tickets/api/analytics/analytics.py`
6. **Tests**: Add to `test_organizational.py` for org features, appropriate `test_*.py` file
7. **Management command**: Use `tickets/management/commands/` pattern for scheduled jobs

### Common Pitfalls
- ❌ Don't put business logic in views - put in TicketService (consolidated services.py)
- ❌ Don't skip org access validation (check `get_accessible_*()` methods)
- ❌ Don't modify closed/escalated tickets without explicit business rule
- ❌ Don't bypass `process_auto_escalations()` for escalation - always use it
- ❌ Don't split models across multiple files (Django best practice: keep in `models.py`)
- ❌ Don't import from old deprecated files (ticket_services, organizational_ticket_service, resource_views, organizational_views)
- ✅ Always use `TicketService` for business logic (consolidated single class)
- ✅ Always import from: `from tickets.api.services import TicketService` or `from tickets.api.views.index import ViewName`
- ✅ Filter by `campus__in=user.get_accessible_campuses()` when querying
- ✅ Use `TicketService` methods for escalation operations
- ✅ Add database indexes on frequently filtered fields (escalation_level, next_escalation_due)
- ✅ Log escalations and role-based access decisions in TicketLog
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
- Custom views for analytics and escalation (inherit `APIView`)

### Organizational Access Control
- Always call `user.get_accessible_campuses()` before querying org resources
- Filter querysets by `campus__in=user.get_accessible_campuses()`
- Use `organizational_scope` property to determine access level
- Services should validate user has access to resource's org unit via `TicketService` helpers

### Adding Features
1. **Model changes**: Add to `tickets/models.py`, then `python manage.py makemigrations`
2. **Business logic**: Add method to `TicketService` class in `tickets/api/services/services.py`, NOT views
3. **API endpoint**: Add view to `tickets/api/views/views.py`, import in `index.py`, add route to `urls.py`
4. **Tests**: Add to `test_organizational.py` for org features, appropriate `test_*.py` file
5. **Analytics**: Add method to class in `tickets/api/analytics/analytics.py`

### Common Pitfalls
- ❌ Don't put business logic in views - use TicketService
- ❌ Don't import from deprecated files (removed after consolidation)
- ❌ Don't split functionality across multiple files per layer
- ✅ Always use `from tickets.api.services import TicketService`
- ✅ Always use `from tickets.api.views.index import ViewName`
- ✅ Always use `from tickets.api.analytics import AnalyticsClass`
- ✅ Delegate to service layer from views via `TicketService` methods

## Key Files Reference
- `docs/API_INTEGRATION_GUIDE.md` - Complete API integration guide
- `docs/api/ANALYTICS.md` - Analytics query params and response schemas
- `docs/testing/SAMPLE_QUERIES.md` - 40+ ready-to-use Django ORM examples
- `docs/testing/TESTING.md` - Test organization and coverage (157 tests)
