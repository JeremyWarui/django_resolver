# Django Resolver - Codebase Architecture & Data Flow

## 📋 Table of Contents
1. [Project Overview](#project-overview)
2. [Directory Structure & File Roles](#directory-structure--file-roles)
3. [Core Data Models](#core-data-models)
4. [Authentication Data Flow](#authentication-data-flow)
5. [API Request/Response Flow](#api-requestresponse-flow)
6. [Ticket Lifecycle Flow](#ticket-lifecycle-flow)
7. [Analytics Data Flow](#analytics-data-flow)
8. [Module Dependencies](#module-dependencies)
9. [Adding New Features](#adding-new-features)

---

## Project Overview

**Django Resolver** is a REST API for maintenance ticket management system with:
- **Token-based Authentication** with password-based login for all user roles
- **Role-based Access Control** (user, technician, manager, admin)
- **Ticket Lifecycle Management** with status transitions and assignment rules
- **Analytics & Reporting** with temporal aggregation (day/week/month)
- **Comprehensive Audit Trail** via TicketLog model

**Tech Stack**: Django 5.2.7 + Django REST Framework 3.16.1 + PostgreSQL

---

## Directory Structure & File Roles

### Root Level Files

| File/Directory | Purpose | Details |
|---|---|---|
| `manage.py` | Django CLI | Run migrations, shell, management commands |
| `requirements.txt` | Dependencies | All Python packages (Django, DRF, etc.) |
| `pytest.ini` | Test Config | Pytest configuration for test discovery |
| `build.sh` | Deploy Script | Build script for production deployment |
| `render.yaml` | Cloud Config | Render.com deployment configuration |
| `.env` | Environment Vars | SECRET_KEY, DEBUG, DATABASE_URL (not in git) |
| `.gitignore` | Git Config | Excludes .env, fixtures, sensitive docs |

### `resolver/` - Django Project Configuration

Core Django project setup - **no business logic here**:

| File | Purpose |
|---|---|
| `settings.py` | Project settings: installed apps, middleware, CORS, database, auth |
| `urls.py` | Root URL routing: mounts `tickets/` app URLs |
| `asgi.py` | ASGI server entrypoint (for deployment) |
| `wsgi.py` | WSGI server entrypoint (for production) |

**Key Settings**:
- `CORS_ALLOWED_ORIGINS`: Frontend origin (http://localhost:5173)
- `INSTALLED_APPS`: tickets, rest_framework, corsheaders
- `REST_FRAMEWORK`: Token auth, pagination, permissions
- `DEFAULT_PAGINATION_CLASS`: StandardResultsSetPagination (10 items/page)

### `tickets/` - Main Application Root

**Role**: Contains all business logic, models, serializers, and API endpoints.

#### Core Files

| File | Purpose | Key Classes/Functions |
|---|---|---|
| `models.py` | Database schema | `CustomUser`, `Ticket`, `Facility`, `Section`, `Comment`, `Feedback`, `TicketLog` |
| `serializers.py` | Data serialization | `TicketSerializer`, `UserSerializer`, `CommentSerializer`, `FeedbackSerializer` |
| `auth_models.py` | Auth models | `LoginSession`, `MagicLink` (commented out) |
| `permissions.py` | Access control | `IsAuthenticated`, `IsTechnicianOrAdmin`, `IsAdminOrManager` |
| `admin.py` | Django admin | Admin interface configuration |
| `urls.py` | App-level routing | Includes API routes and auth routes |
| `pagination.py` | Pagination logic | `StandardResultsSetPagination` with metadata |
| `email_service.py` | Email utilities | Magic link email templates (future) |

### `tickets/api/` - API Implementation Layer

**Role**: Complete REST API implementation with separation of concerns.

```
tickets/api/
├── __init__.py
├── urls.py                    # Main API routing
├── simple_auth_views.py       # Authentication endpoints
├── permissions.py             # Custom permission classes
├── filters.py                 # DRF filter backends
│
├── views/                     # Presentation layer (UNIFIED)
│   ├── index.py              # Clean exports
│   └── views.py              # All 20+ endpoint classes (CONSOLIDATED)
│
├── services/                  # Business logic layer (UNIFIED)
│   ├── __init__.py
│   └── services.py           # TicketService class (ALL operations)
│
├── analytics/                 # Analytics module (UNIFIED)
│   ├── analytics.py          # All 4 analytics classes (CONSOLIDATED)
│   └── index.py              # Clean exports
│
└── reports/                   # Report generation
    ├── report_generator.py   # PDF/CSV logic
    └── views.py              # Report endpoints
```

#### API Layer Breakdown — CONSOLIDATED ARCHITECTURE

**`views/views.py`** - REST Endpoints (UNIFIED, 20+ classes)
**Organization Hierarchy**:
- `OrganizationListCreateView`, `CampusListCreateView`, `DepartmentListCreateView`
- `SectionListCreateView`, `SectionDetailView`

**Ticket Management**:
- `TicketListCreateView`, `TicketDetailView` - Ticket CRUD
- `TicketEscalationView`, `EscalateTicketView` - Escalation endpoints (2-level workflow)
- `OrganizationalTicketListView` - Org-scoped ticket queries

**Users & Assignment**:
- `UserListCreateView`, `UserDetailView` - User CRUD
- `TechniciansBySectionView` - Section-filtered technicians
- `AssignableUsersView` - Available technicians for assignment dropdown

**Comments & Feedback**:
- `CommentListCreateView`, `FeedbackListCreateView` - Sub-resources

**Bulk Operations**:
- `BulkTicketStatusUpdateView` - Atomic multi-ticket status updates

**Analytics**:
- `OrganizationalAnalyticsView`, `AnalyticsTicketsView`, `AnalyticsTechniciansView`

All views:
- Use `IsWithinOrganizationalScope` permission
- Delegate to `TicketService` for business logic
- Filter by user's organizational access (campus, department, section)
- Include org-aware pagination and filtering

**`services/services.py`** - Business Logic Layer (UNIFIED)
**Single TicketService class** with comprehensive methods:
- `create_ticket(user, section, facility, title, description, priority)` - Create with org context
- `assign_ticket(ticket, technician, performed_by)` - Validate technician can be assigned
- `escalate_ticket(ticket, reason, performed_by)` - 2-level escalation (section_head → HOD)
- `update_ticket_status(ticket, new_status, performed_by, reason)` - Validate status transitions
- `close_ticket(ticket, performed_by)` - Final status with audit
- `process_auto_escalations()` - Cron job for auto-escalation (runs hourly)
- `get_accessible_tickets(user)` - Org-filtered ticket queries

**Validators**:
- `validate_status_transition(old_status, new_status, user_role)` - Enforces workflow rules
- `manual_escalation_allowed(ticket, user)` - Check escalation permissions

**Exception classes**:
- `TicketServiceException`, `InsufficientScopeException`, `InvalidAssignmentException`, `InvalidEscalationException`

Import: `from tickets.api.services import TicketService`

**`simple_auth_views.py`** - Authentication
- `check_auth_method()` - Returns current auth strategy
- `simple_auth_login()` - Password-based login → Token generation
- `simple_logout()` - Invalidates token, logs session
- `user_profile()` - Returns current user data
- `register_user()` - Create new user account
- *Commented*: Magic link functions for future implementation

**`analytics/analytics.py`** - Analytics Logic (UNIFIED, 4 classes)
- `TicketAnalytics` - Ticket counts, trends, distributions by facility, section, status
- `TechnicianAnalytics` - Technician performance, workload, completion metrics
- `OrganizationalAnalytics` - Role-specific: `director_dashboard()`, `hod_dashboard()`, `section_head_dashboard()`
- `AdminAnalytics` - System-wide monitoring, overdue tickets, SLA compliance

All classes support:
- Temporal aggregation: day/week/month grouping
- Date range filtering: past N days
- Org-scoped queries: filtered by user's organizational access

Import: `from tickets.api.analytics import AnalyticsClass`

**`reports/report_generator.py`** - Report Generation
- PDF generation from ticket data
- CSV export functionality
- Filtering by status, facility, date range, org hierarchy

### `tickets/migrations/` - Database Schema Evolution

| File | Change |
|---|---|
| `0001_initial.py` | Creates all core tables (CustomUser, Ticket, etc.) |
| `0002_alter_facility_options...` | Metadata updates (ordering, permissions) |
| `0003_alter_ticket_options...` | Adds database indexes for performance |

**Indexes created**:
- `ticket_updated_at_idx` - Query ordering by updated_at
- `ticket_status_idx` - Filter by status
- `ticket_assigned_to_idx` - Filter by assignment
- `ticket_status_updated_idx` - Composite filter

### `tickets/fixtures/` - Test Data

**`tickets_initial_data.json`** (118 records)
- 12 CustomUser records (4 roles × 3 users each)
- 3 Facility records
- 4 Section records
- 98 Ticket records (mixed statuses)
- Comments and feedback for sample tickets
- **Passwords**: All hashed using Django's PBKDF2 algorithm

Load fixture: `python manage.py loaddata tickets/fixtures/tickets_initial_data.json`

### `tickets/tests/` - Test Suite (40+ tests)

| File | Coverage |
|---|---|
| `test_models.py` | Model methods, custom behaviors, validations |
| `test_serializers.py` | Serializer output, nested relationships |
| `test_apis.py` | REST endpoints, permissions, filtering |
| `test_ticket_operations.py` | Ticket create/update/delete workflows |
| `test_workflow.py` | Status transitions, assignment rules, role permissions |
| `test_analytics.py` | Analytics aggregation, temporal grouping |
| `base.py` | `BaseTicketTestCase` - Shared setup for all tests |

Run tests: `python manage.py test tickets`

### `docs/` - Documentation Hub

| Directory | Contents |
|---|---|
| `INDEX.md` | Navigation hub for all documentation |
| `PROJECT_STRUCTURE.md` | Directory tree and module purposes |
| `CODEBASE_ARCHITECTURE.md` | This file - architecture and data flows |
| `AUTHENTICATION.md` | Auth system details and endpoints |
| `DEFAULT_CREDENTIALS.md` | Test user accounts (in .gitignore for security) |
| `api/GUIDE.md` | Complete API reference for frontend |
| `api/ANALYTICS.md` | Analytics endpoints and query params |
| `architecture/LAYERS.md` | API layered architecture |
| `testing/TESTING.md` | Test organization and running tests |
| `testing/SAMPLE_QUERIES.md` | 20+ Django ORM query examples |

---

## Core Data Models

### Model Relationships Diagram

```
CustomUser (extends AbstractUser)
├── role: user | technician | manager | admin
├── sections: M2M to Section
├── owned_token: 1-1 with Token
└── login_sessions: 1-M with LoginSession

Ticket
├── ticket_no: auto-generated (TKT-XXXXXX)
├── status: open → assigned → in_progress ⇄ pending → resolved → closed
├── section: FK to Section
├── facility: FK to Facility
├── raised_by: FK to CustomUser
├── assigned_to: FK to CustomUser (technician only)
├── created_at, updated_at, resolved_at: timestamps
├── comments: 1-M with Comment
├── feedback: 1-M with Feedback
└── logs: 1-M with TicketLog

Section
├── name: string
└── tickets: 1-M with Ticket

Facility
├── name: string
└── tickets: 1-M with Ticket

Comment
├── ticket: FK to Ticket
├── author: FK to CustomUser
└── content: text

Feedback
├── ticket: FK to Ticket
├── rating: 1-5
└── comments: text

TicketLog
├── ticket: FK to Ticket
├── old_status, new_status: for tracking
├── changed_by: FK to CustomUser
└── timestamp: when change occurred

LoginSession
├── user: FK to CustomUser
├── token: 1-1 with Token
├── login_method: 'password' | 'magic_link'
├── remember_me: boolean
├── expires_at: datetime
├── ip_address, user_agent: session info
```

### Key Model Methods

**`CustomUser`**:
- `is_technician()` - Check if user is technician
- `can_manage_sections()` - Check if user can manage assigned sections
- `get_available_tickets()` - Get tickets user can access by role

**`Ticket`**:
- `change_status(new_status, performed_by=user)` - Atomic status change + log creation
- `change_assignment(assigned_to, performed_by=user)` - Atomic assignment + log creation
- `save()` - Auto-generates ticket_no if not set
- `is_overdue()` - Returns True if open/assigned/in_progress for >7 days

---

## Authentication Data Flow

### Password-Based Login Flow

```
1. Frontend POST /api/auth/login/
   └─ Payload: {"username": "tech_maria", "password": "mariagarcia"}

2. simple_auth_login() in simple_auth_views.py
   ├─ Authenticate user with Django's authenticate()
   │  └─ Django hashes password and compares with DB
   ├─ Check login_method parameter (password/magic_link)
   ├─ Create or update LoginSession record
   │  ├─ login_method: 'password'
   │  ├─ expires_at: now + 30 days
   │  └─ ip_address, user_agent: captured from request
   └─ Return Response:
      {
        "token": "abc123xyz789",
        "user_id": 4,
        "username": "tech_maria",
        "role": "technician",
        "email": "maria.garcia@company.com",
        "session_id": "uuid-here",
        "expires_at": "2025-02-15T10:30:00Z"
      }

3. Frontend stores token in localStorage/sessionStorage
   └─ Includes in all subsequent requests as: Authorization: Token abc123xyz789

4. REST Framework TokenAuthentication middleware
   ├─ Extracts token from Authorization header
   ├─ Looks up Token record in database
   ├─ Sets request.user to associated CustomUser
   └─ Proceeds with request handling

5. After logout POST /api/auth/logout/
   ├─ Delete LoginSession record
   ├─ Delete Token record
   └─ Response: {"detail": "Successfully logged out"}
```

### Session Management

**LoginSession Model Fields**:
- `user` - FK to CustomUser
- `token` - 1-1 with Token
- `login_method` - 'password' or 'magic_link'
- `remember_me` - Boolean for persistent sessions
- `expires_at` - Session expiration datetime
- `ip_address` - Source IP for security
- `user_agent` - Browser/client info
- `created_at` - Session creation timestamp

**Cleanup**: 
- Use `python manage.py clear_sessions --force` to remove old LoginSessions and Tokens
- Prevents "duplicate key" constraint violations when reloading fixtures

---

## API Request/Response Flow

### Generic CRUD Flow (Example: Ticket Create)

```
1. Frontend POST /api/tickets/
   └─ Payload: {
        "title": "Broken AC",
        "description": "AC unit not cooling",
        "section": 1,
        "facility": 2,
        "priority": "high"
      }

2. Django URL routing: tickets/urls.py
   └─ Routes to tickets/api/urls.py

3. REST framework routing in api/urls.py
   └─ POST → TicketListCreateView in views/views.py

4. TicketListCreateView (ListCreateAPIView)
   ├─ Check permissions:
   │  └─ IsWithinOrganizationalScope required
   │  └─ create() allowed for all roles
   ├─ Validate input:
   │  └─ Call TicketSerializer.validate()
   │  └─ Ensure section and facility exist
   ├─ Call perform_create(serializer)
   │  └─ Delegates to services: TicketService.create_ticket()
   └─ Return serialized response (201 Created)

5. TicketService.create_ticket() in services/services.py
   ├─ Validate section/facility exist and user has access
   ├─ Validate organizational scope (user can access this section)
   ├─ Call serializer.save()
   └─ Return created ticket object

6. Ticket.save() (model method)
   ├─ Generate CAMPUS-DEPT-XXXXX ticket_no (organizational numbering)
   ├─ Set status='open' if new
   ├─ Insert into database
   └─ Return saved instance

7. TicketSerializer.to_representation()
   ├─ Convert model to dict
   ├─ Include computed fields:
   │  ├─ section_name (org context)
   │  ├─ facility_name
   │  ├─ raised_by_name (simple string)
   │  ├─ assigned_to_name (simple string)
   │  ├─ available_technicians (org-filtered list of eligible options)
   │  ├─ is_overdue (boolean)
   │  ├─ escalation_level (0/1/2)
   │  └─ days_since_creation (integer)
   ├─ Skip expensive nested fields in list context:
   │  ├─ comments (only in detail view)
   │  └─ feedback (only in detail view)
   └─ Return response body

8. Response JSON:
   {
     "id": 523,
     "ticket_no": "MAIN-IT-00523",
     "title": "Broken AC",
     "status": "open",
     "escalation_level": 0,
     "section": 1,
     "section_name": "NETWORK",
     "facility": 2,
     "facility_name": "Building A",
     "raised_by": 2,
     "raised_by_name": "john.doe",
     "assigned_to": null,
     "assigned_to_name": null,
     "available_technicians": [
       {"id": 4, "name": "tech_maria", "email": "maria@company.com"},
       {"id": 6, "name": "tech_carlos", "email": "carlos@company.com"}
     ],
     "priority": "high",
     "description": "AC unit not cooling",
     "created_at": "2025-01-15T10:30:00Z",
     "updated_at": "2025-01-15T10:30:00Z",
     "resolved_at": null,
     "next_escalation_due": "2025-01-17T10:30:00Z",
     "is_overdue": false,
     "days_since_creation": 0
   }
```
       {"id": 6, "name": "tech_carlos", "email": "carlos@company.com"}
     ],
     "priority": "high",
     "description": "AC unit not cooling",
     "created_at": "2025-01-15T10:30:00Z",
     "updated_at": "2025-01-15T10:30:00Z",
     "resolved_at": null,
     "is_overdue": false,
     "days_since_creation": 0
   }
```

### Pagination Response Format

All list endpoints return paginated responses:

```json
{
  "count": 523,
  "next": "http://api.example.com/api/tickets/?page=2",
  "previous": null,
  "total_pages": 53,
  "current_page": 1,
  "results": [
    { "id": 523, "ticket_no": "TKT-000523", ... },
    { "id": 522, "ticket_no": "TKT-000522", ... },
    ...
  ]
}
```

---

## Ticket Lifecycle Flow

### Status Transition Rules

**Valid Transitions** (enforced in TicketService.validate_status_transition()):

```
open ──→ assigned (when assigned_to is set)
        └──→ pending (technician can set pending reason)
        └──→ escalated (escalation initiated)

assigned ──→ in_progress (technician starts work)
           └──→ pending (issue discovered)
           └──→ escalated (escalation initiated)

in_progress ──→ pending (issue found, need info)
              └──→ resolved (work completed)
              └──→ escalated (escalation initiated)

pending ──→ in_progress (more info received)
         └──→ resolved (resolved despite pending)
         └──→ escalated (escalation initiated)

escalated ──→ open (escalation resolved, back to open)
            └──→ resolved (escalation resolved with closure)

resolved ──→ closed (admin only - final state)
           └──→ open (reopen if needed)

closed: Terminal state (no further transitions)
```

**Escalation Workflow** (organizational 2-level):
- **Level 0** (none): Initial state
- **Level 1** → escalated to section_head after `escalation_threshold_hours` (default: 48)
- **Level 2** → escalated to HOD after another threshold (maximum level)
- **Manual escalation**: Any user with appropriate role can escalate with reason
- **Auto-escalation**: Run `python manage.py process_auto_escalations` (hourly cron)

**Role Permissions**:

| Role | Can Create | Can Update | Can Escalate | Can Close | Can Assign |
|---|---|---|---|---|---|
| user | ✅ | ❌ | ❌ | ❌ | ❌ |
| technician | ✅ | ✅ | ❌ | ❌ | ❌ |
| section_head | ✅ | ✅ | ✅ | ❌ | ✅ |
| hod | ✅ | ✅ | ✅ | ❌ | ✅ |
| director | ❌ | ❌ | ❌ | ❌ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ | ✅ |

### Assignment Validation

When assigning a technician (organization-scoped):

```
1. GET /api/technicians/?section_id=2&campus_id=1
   └─ Returns technicians in section 2 AND on campus 1
   └─ Frontend shows only org-filtered technicians in assignment dropdown

2. PATCH /api/tickets/523/
   └─ Payload: {"assigned_to": 4}

3. TicketService.assign_ticket() in services/services.py
   ├─ Call validate_assignment(ticket, user)
   │  ├─ Check: user.role == 'technician'
   │  ├─ Check: user in ticket.section.technicians
   │  ├─ Check: user.primary_campus matches ticket.campus
   │  └─ Raise InvalidAssignmentException if checks fail
   ├─ Auto-update status if assigning to open ticket
   │  └─ open → assigned (status change)
   └─ Create TicketLog entry (atomic operation)

4. Ticket.change_assignment()
   ├─ Update assigned_to field
   ├─ Create TicketLog entry
   │  ├─ action: 'assignment'
   │  ├─ old_value: null
   │  ├─ new_value: 4
   │  └─ changed_by: request.user
   └─ Save to database (atomic)

5. Response: Updated ticket with new assignment and escalation fields
```

### Audit Trail

Every status/assignment change creates a `TicketLog` entry:

```python
TicketLog entry for status change:
{
  "ticket": 523,
  "old_status": "open",
  "new_status": "assigned",
  "changed_by": 2,
  "changed_by_name": "john.doe",
  "timestamp": "2025-01-15T10:35:00Z",
  "action_type": "status_change"
}

TicketLog entry for assignment:
{
  "ticket": 523,
  "old_assignment": null,
  "new_assignment": 4,
  "changed_by": 2,
  "timestamp": "2025-01-15T10:36:00Z",
  "action_type": "assignment"
}
```

---

## Analytics Data Flow

### Analytics Query Example

```
Frontend GET /api/analytics/tickets/
  ?timeframe=week
  &facility_id=1
  &group_by=day
  &days=30
  &campus_id=1

1. AnalyticsTicketsView in views/views.py
   ├─ Permission: IsWithinOrganizationalScope (role-aware)
   ├─ Parse query parameters
   │  ├─ timeframe: 'week'
   │  ├─ facility_id: 1
   │  ├─ campus_id: 1
   │  ├─ group_by: 'day'
   │  └─ days: 30
   └─ Call TicketAnalytics.get_analytics(filters)

2. TicketAnalytics class in analytics/analytics.py
   ├─ Build org-scoped queryset filters:
   │  ├─ Tickets in facility=1 AND campus=1
   │  ├─ Accessible to user based on organizational_scope
   │  └─ Updated in past 30 days
   ├─ Aggregate by status:
   │  ├─ open_count = count(status='open')
   │  ├─ assigned_count = count(status='assigned')
   │  ├─ escalated_count = count(escalation_level > 0)
   │  ├─ in_progress_count = count(status='in_progress')
   │  ├─ pending_count = count(status='pending')
   │  ├─ resolved_count = count(status='resolved')
   │  └─ closed_count = count(status='closed')
   ├─ Calculate metrics:
   │  ├─ avg_resolution_time = avg(resolved_at - created_at)
   │  ├─ avg_response_time = avg(first_status_change - created_at)
   │  ├─ sla_compliance = count(resolved within SLA) / total_resolved
   │  └─ escalation_rate = escalated_count / total_count
   ├─ Group by day (7 data points for week view):
   │  └─ Day 1: {date, open, assigned, escalated, resolved, ...}
   │  └─ Day 2: {date, open, assigned, escalated, resolved, ...}
   │  └─ ...
   └─ Return aggregated dict

3. Serializer formatting
   ├─ Convert aggregates to JSON
   ├─ Format dates as ISO 8601
   ├─ Round percentages to 2 decimals
   └─ Return response

4. Response JSON:
   {
     "summary": {
       "total_tickets": 523,
       "open": 45,
       "assigned": 23,
       "escalated": 8,
       "in_progress": 12,
       "pending": 8,
       "resolved": 412,
       "closed": 15,
       "avg_resolution_time": "2.5 days",
       "avg_response_time": "4 hours",
       "sla_compliance": 0.94,
       "escalation_rate": 0.15
     },
     "by_day": [
       {
         "date": "2025-01-15",
         "open": 45,
         "assigned": 23,
         "escalated": 2,
         "resolved": 12
       },
       ...
     ]
   }
```

### Technician Analytics Example

```
GET /api/analytics/technicians/?technician_id=4&campus_id=1

AnalyticsTechniciansView in views/views.py
├─ Permission: IsWithinOrganizationalScope
├─ Call TechnicianAnalytics.get_analytics(technician_id=4, campus_id=1)

TechnicianAnalytics.get_analytics() in analytics/analytics.py
├─ Get all org-scoped tickets assigned to technician 4
├─ Filter by technician's campus (organizational scope)
├─ Calculate:
│  ├─ assigned_count = count of assigned tickets
│  ├─ completed_count = count(status='resolved'|'closed')
│  ├─ pending_count = count(status='pending')
│  ├─ avg_completion_time = avg(resolved_at - assigned_at)
│  ├─ avg_rating = avg(feedback.rating) for completed tickets
│  └─ performance_score = (completed / assigned) * avg_rating
├─ Recent activities: Last 5 completed tickets
└─ Return metrics dict

Response:
{
  "technician_id": 4,
  "technician_name": "tech_maria",
  "campus_name": "MAIN",
  "assigned_tickets": 45,
  "completed_tickets": 38,
  "pending_tickets": 7,
  "avg_completion_time": "1.8 days",
  "avg_rating": 4.6,
  "performance_score": 0.84,
  "recent_completions": [
    {"ticket_no": "MAIN-IT-00523", "completed_at": "2025-01-15"},
    ...
  ]
}
```

### Admin Dashboard Analytics

```
GET /api/analytics/admin-dashboard/
  ?days=30

OrganizationalAnalyticsView in views/views.py
├─ Permission: IsWithinOrganizationalScope (role-specific access)
├─ Determine user's role: director | hod | section_head
└─ Call OrganizationalAnalytics.{role}_dashboard()

OrganizationalAnalytics class in analytics/analytics.py

director_dashboard(days=30):
├─ System overview (ALL organizations user has access to):
│  ├─ total_tickets (org-scoped)
│  ├─ status_breakdown (counts by status)
│  ├─ escalation_trends (trending escalations)
│  └─ avg_resolution_time
├─ Campus-level breakdown
├─ Department performance
└─ Overdue tickets

hod_dashboard(days=30):
├─ Department overview:
│  ├─ total_tickets (dept-scoped)
│  ├─ escalated_to_me (level=2 escalations)
│  ├─ open_count
│  └─ avg_resolution_time
├─ Section performance within department
├─ Technician workload
└─ Overdue tickets in dept

section_head_dashboard(days=30):
├─ Section overview:
│  ├─ total_tickets (section-scoped)
│  ├─ escalated_to_me (level=1 escalations)
│  ├─ open_count
│  └─ avg_resolution_time
├─ Technician performance
├─ Overdue tickets in section
└─ Recent activities

Response example (director_dashboard):
{
  "role": "director",
  "organization": "ACME Corp",
  "overview": {
    "total_tickets": 523,
    "open": 45,
    "assigned": 23,
    "escalated": 8,
    "resolved": 412,
    "closed": 35,
    "avg_resolution_time": "2.5 days"
  },
  "escalation_trends": {
    "level_1_escalations": 23,
    "level_2_escalations": 8,
    "escalation_rate": 0.15
  },
  "campus_breakdown": [
    {"campus": "MAIN", "tickets": 300, "open": 25, ...},
    {"campus": "WEST", "tickets": 223, "open": 20, ...}
  ],
  "overdue_tickets": [
    {"ticket_no": "MAIN-IT-00488", "days_overdue": 5, ...},
    ...
  ]
}
```

---

## Module Dependencies

### Import Map (CONSOLIDATED STRUCTURE)

```
From External:
├── django (models, views, admin, forms)
├── django.db (transaction, connection)
├── rest_framework (APIView, generics, serializers, pagination)
├── rest_framework.authtoken (Token)
└── corsheaders (CORS middleware)

tickets/models.py
├── CustomUser (AbstractUser)
├── Ticket (Model)
├── Campus, Department, Section, Organization
├── Facility, Comment, Feedback, TicketLog, CustomUser

tickets/serializers.py
└─ Depends on: models.py, DRF

tickets/api/services/services.py (UNIFIED SERVICE LAYER)
├─ Single TicketService class with all business logic
├─ Depends on: models.py, email_service.py (optional)
└─ No circular imports: views and other modules depend on this

tickets/api/views/views.py (UNIFIED VIEW LAYER)
├─ 20+ view classes for all endpoints
├─ Depends on: models.py, serializers.py, services/services.py
├─ Uses: DRF generics, pagination.py, permissions.py, filters.py
└─ Exports via: views/index.py for clean imports

tickets/api/analytics/analytics.py (UNIFIED ANALYTICS)
├─ 4 analytics classes (TicketAnalytics, TechnicianAnalytics, OrganizationalAnalytics, AdminAnalytics)
├─ Depends on: models.py
└─ Exports via: analytics/index.py for clean imports

tickets/api/simple_auth_views.py
├─ Depends on: models.py, auth_models.py
├─ Uses: DRF Token, permissions.py
└─ Optional: email_service.py (magic link - commented out)

tickets/api/urls.py
├─ Imports from: views/index.py, analytics/index.py, reports/, simple_auth_views.py
└─ Mounts all routes

NO CIRCULAR DEPENDENCIES (services → models only)
```

### Circular Dependency Avoidance

**Good**:
```python
# In views/views.py - Import from consolidated services
from tickets.api.services import TicketService
# ✅ Views call TicketService methods (correct layer order)

service = TicketService()
service.create_ticket(user, section, facility, title, description)

# In simple_auth_views.py
from rest_framework.authtoken.models import Token
# ✅ Uses DRF built-in Token (no circular imports)
```

**Avoid**:
```python
# In models.py
from tickets.api.views import some_view
# ❌ Models should never import views

# In serializers.py
from tickets.api.services import some_service
# ❌ Serializers handle data format, not business logic

# ❌ DEPRECATED - Do not import from old removed files:
from tickets.api.services.ticket_services import ...  # REMOVED
from tickets.api.views.resource_views import ...      # REMOVED
from tickets.api.analytics.views import ...           # REMOVED
```

---

## Adding New Features

### 1. Adding a New API Endpoint

**Scenario**: Add endpoint to get all tickets assigned to current user

**Steps**:

1. **Service Layer** (`tickets/api/services/services.py` - UNIFIED TicketService):
```python
class TicketService:
    def get_user_tickets(self, user):
        """Get all org-scoped tickets accessible to user based on role"""
        if user.organizational_scope == 'section':
            return Ticket.objects.filter(
                section__in=user.sections.all(),
                section__department__campus__in=user.get_accessible_campuses()
            )
        elif user.organizational_scope == 'department':
            return Ticket.objects.filter(
                section__department__in=[user.primary_department]
            )
        elif user.organizational_scope == 'organization':
            return Ticket.objects.all()  # Full org access
        else:
            return Ticket.objects.filter(raised_by=user)
```

2. **View** (`tickets/api/views/views.py` - ADD NEW CLASS):
```python
class UserTicketsListView(generics.ListAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsWithinOrganizationalScope]
    pagination_class = StandardResultsSetPagination
    filter_backends = [OrderingFilter]
    ordering_fields = ['created_at', 'updated_at', 'status']
    
    def get_queryset(self):
        service = TicketService()
        return service.get_user_tickets(self.request.user)
```

3. **Export** (`tickets/api/views/index.py`):
```python
# Add to imports
from .views import UserTicketsListView
```

4. **URL Route** (`tickets/api/urls.py`):
```python
urlpatterns = [
    # ... existing routes
    path('my-tickets/', UserTicketsListView.as_view(), name='user-tickets'),
]
```

5. **Test** (`tickets/tests/test_organizational.py`):
```python
def test_get_user_tickets_respects_org_scope(self):
    # Login as technician in section A
    # GET /api/my-tickets/
    # Verify only section A tickets returned
    pass
```

### 2. Adding a New Status to Ticket Workflow

**Steps**:

1. **Model** (`tickets/models.py` - UPDATE CHOICES):
```python
class Ticket(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('on_hold', 'On Hold'),  # NEW
        ('escalated', 'Escalated'),
    ]
```

2. **Service** (`tickets/api/services/services.py` - UPDATE TicketService):
```python
class TicketService:
    VALID_STATUS_TRANSITIONS = {
        # ... existing transitions
        'pending': ['in_progress', 'resolved', 'on_hold'],  # Added on_hold
        'on_hold': ['in_progress', 'resolved'],  # New from on_hold
    }
    
    def validate_status_transition(self, old_status, new_status, user_role):
        """Enhanced validator for new on_hold status"""
        # Check if transition is valid in VALID_STATUS_TRANSITIONS
        # Consider role-based restrictions
        # Return True or raise InvalidEscalationException
        pass
```

3. **Test** (`tickets/tests/test_organizational.py`):
```python
def test_status_transition_to_on_hold(self):
    # Create ticket in pending
    # Call TicketService.update_ticket_status(status='on_hold')
    # Verify status changed and TicketLog created
    pass
```

### 3. Adding a New Analytics Metric

**Steps**:

1. **Analytics Class** (`tickets/api/analytics/analytics.py` - UPDATE CLASS):
```python
class TicketAnalytics:
    def get_analytics(self, filters):
        # Build org-scoped queryset
        tickets = self._get_filtered_tickets(filters)
        
        # Existing aggregations...
        
        # New metric:
        avg_wait_time = self._calculate_avg_wait_time(tickets)
        escalation_rate = self._calculate_escalation_rate(tickets)
        
        return {
            # ... existing
            'avg_wait_time': avg_wait_time,
            'escalation_rate': escalation_rate,
        }
    
    def _calculate_avg_wait_time(self, tickets):
        """Avg time between created and first assignment"""
        with_assignment = tickets.filter(assigned_at__isnull=False)
        if not with_assignment.exists():
            return None
        total_wait = sum(
            (t.assigned_at - t.created_at).total_seconds() 
            for t in with_assignment
        )
        return total_wait / len(with_assignment)
    
    def _calculate_escalation_rate(self, tickets):
        """Percent of tickets that escalated"""
        escalated = tickets.filter(escalation_level__gt=0).count()
        return escalated / max(tickets.count(), 1)
```

2. **View** (`tickets/api/views/views.py` - ADD ENDPOINT):
```python
class AnalyticsTicketsView(APIView):
    permission_classes = [IsWithinOrganizationalScope]
    
    def get(self, request):
        filters = {...}  # Parse query params
        analytics = TicketAnalytics()
        data = analytics.get_analytics(filters)
        return Response(data)
```

3. **URL Route** (`tickets/api/urls.py`):
```python
urlpatterns = [
    # ... existing
    path('analytics/tickets/', AnalyticsTicketsView.as_view(), name='analytics-tickets'),
]
```

4. **Test** (`tickets/tests/test_organizational.py`):
```python
def test_analytics_escalation_rate(self):
    # Create mixed tickets (escalated + non-escalated)
    # Call analytics endpoint
    # Verify escalation_rate calculated correctly
    pass
```

---

## Summary: Data Flow in 4 Scenarios

### Scenario 1: User Logs In
```
1. POST /api/auth/login/
2. simple_auth_login() hashes password and checks
3. LoginSession + Token created
4. Token returned to frontend
5. Frontend stores token, includes in all requests
```

### Scenario 2: Technician Creates Ticket
```
1. POST /api/tickets/ with data
2. TicketListCreate validates and calls create_ticket()
3. Ticket.save() generates ticket_no, sets status='open'
4. TicketLog created if status changes
5. TicketSerializer formats response with available_technicians
6. JSON response sent to frontend
```

### Scenario 3: Manager Assigns Ticket
```
1. PATCH /api/tickets/523/ with assigned_to=4
2. TicketRetrieveUpdate calls update_ticket()
3. update_ticket() validates assignment via validate_assignment()
4. Ticket.change_assignment() atomically updates + creates TicketLog
5. Status auto-updated from open → assigned
6. Response includes updated ticket with new assignment
```

### Scenario 4: Analytics Dashboard Loads
```
1. GET /api/analytics/admin-dashboard/
2. AdminDashboardAnalyticsView checks IsAuthenticated
3. AdminAnalytics.get_analytics() queries Ticket model
4. Aggregates counts by status, calculates averages
5. If user is admin/manager, includes overdue_tickets
6. Serializer formats response with metadata
7. Paginated JSON returned to frontend with charts data
```

---

## Next Steps

- See [AUTHENTICATION.md](AUTHENTICATION.md) for auth system details
- See [api/GUIDE.md](api/GUIDE.md) for complete endpoint reference
- See [api/ANALYTICS.md](api/ANALYTICS.md) for analytics query parameters
- See [testing/TESTING.md](testing/TESTING.md) for writing tests
- See [testing/SAMPLE_QUERIES.md](testing/SAMPLE_QUERIES.md) for Django ORM examples
