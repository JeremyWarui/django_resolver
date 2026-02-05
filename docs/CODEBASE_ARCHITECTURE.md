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
│
├── views/                     # Presentation layer
│   ├── index.py              # Clean exports
│   └── resource_views.py     # CRUD endpoints (ListCreate, RetrieveUpdate)
│
├── services/                  # Business logic layer
│   ├── __init__.py
│   └── ticket_services.py    # Ticket operations & validation
│
├── analytics/                 # Analytics module
│   ├── analytics.py          # Analytics business logic
│   ├── views.py              # Analytics endpoints
│   └── index.py              # Clean exports
│
└── reports/                   # Report generation
    ├── report_generator.py   # PDF/CSV logic
    └── views.py              # Report endpoints
```

#### API Layer Breakdown

**`views/resource_views.py`** - REST Endpoints
- `SectionListCreate`, `SectionRetrieveUpdate` - Section CRUD
- `FacilityListCreate`, `FacilityRetrieveUpdate` - Facility CRUD
- `TicketListCreate`, `TicketRetrieveUpdate` - Ticket CRUD
- `CommentListCreate` - Create comments
- `FeedbackListCreate` - Create feedback
- `UserList` - List users (technicians for assignment)
- `TechnicianListView` - Filtered technicians by section

**`services/ticket_services.py`** - Business Logic
- `validate_status_transition(old_status, new_status, user_role)` - Enforces workflow rules
- `validate_assignment(ticket, user)` - Ensures technician belongs to ticket's section
- `create_ticket()`, `update_ticket()` - Delegates to model helpers
- Status transition matrix (which statuses can transition to which)

**`simple_auth_views.py`** - Authentication
- `check_auth_method()` - Returns current auth strategy
- `simple_auth_login()` - Password-based login → Token generation
- `simple_logout()` - Invalidates token, logs session
- `user_profile()` - Returns current user data
- `register_user()` - Create new user account
- *Commented*: Magic link functions for future implementation

**`analytics/analytics.py`** - Analytics Logic
- `TicketAnalytics` class: Query aggregation (open, resolved, avg response time, etc.)
- `TechnicianAnalytics` class: Technician performance (assigned, completed, etc.)
- `AdminAnalytics` class: System overview (total tickets, avg resolution time, etc.)
- Temporal aggregation: day/week/month grouping
- Date range filtering: past N days

**`reports/report_generator.py`** - Report Generation
- PDF generation from ticket data
- CSV export functionality
- Filtering by status, facility, date range

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
   └─ POST → TicketListCreate view (from resource_views.py)

4. TicketListCreate (ListCreateAPIView)
   ├─ Check permissions:
   │  └─ IsAuthenticated required
   │  └─ create() allowed for all roles
   ├─ Validate input:
   │  └─ Call TicketSerializer.validate()
   │  └─ Ensure section and facility exist
   ├─ Call perform_create(serializer)
   │  └─ Delegates to services: ticket_services.create_ticket()
   └─ Return serialized response (201 Created)

5. ticket_services.create_ticket()
   ├─ Validate section/facility exist
   ├─ Call serializer.save()
   └─ Return created ticket object

6. Ticket.save() (model method)
   ├─ Generate ticket_no if not set (TKT-{id:06d})
   ├─ Set status='open' if new
   ├─ Insert into database
   └─ Return saved instance

7. TicketSerializer.to_representation()
   ├─ Convert model to dict
   ├─ Include computed fields:
   │  ├─ assigned_to_name (simple string)
   │  ├─ available_technicians (list of eligible assignment options)
   │  ├─ is_overdue (boolean)
   │  └─ days_since_creation (integer)
   ├─ Skip expensive nested fields in list context:
   │  ├─ comments (only in detail view)
   │  └─ feedback (only in detail view)
   └─ Return response body

8. Response JSON:
   {
     "id": 523,
     "ticket_no": "TKT-000523",
     "title": "Broken AC",
     "status": "open",
     "section": 1,
     "section_name": "HVAC",
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

**Valid Transitions** (enforced in `validate_status_transition()`):

```
open ──→ assigned (when assigned_to is set)
        └──→ pending (technician can set pending reason)

assigned ──→ in_progress (technician starts work)
           └──→ pending (issue discovered)

in_progress ──→ pending (issue found, need info)
              └──→ resolved (work completed)

pending ──→ in_progress (more info received)
         └──→ resolved (resolved despite pending)

resolved ──→ closed (admin/manager only)

closed: No further transitions (terminal state)
```

**Role Permissions**:

| Role | Can Create | Can Update | Can Close | Can Assign |
|---|---|---|---|---|
| user | ✅ | ❌ | ❌ | ❌ |
| technician | ✅ | ✅ | ❌ | ❌ |
| manager | ✅ | ✅ | ✅ | ✅ |
| admin | ✅ | ✅ | ✅ | ✅ |

### Assignment Validation

When assigning a technician:

```
1. GET /api/technicians/?section_id=2
   └─ Returns technicians belonging to section 2
   └─ Frontend shows these in assignment dropdown

2. PATCH /api/tickets/523/
   └─ Payload: {"assigned_to": 4}

3. ticket_services.update_ticket()
   ├─ Call validate_assignment(ticket, user)
   │  ├─ Check: user.role == 'technician'
   │  ├─ Check: user in ticket.section.technicians
   │  └─ Raise ValidationError if checks fail
   ├─ Auto-update status if assigning to open ticket
   │  └─ open → assigned (status change)
   └─ Call ticket.change_assignment(user, performed_by=request.user)

4. Ticket.change_assignment()
   ├─ Update assigned_to field
   ├─ Create TicketLog entry
   │  ├─ action: 'assignment'
   │  ├─ old_value: null
   │  ├─ new_value: 4
   │  └─ changed_by: request.user
   └─ Save to database (atomic)

5. Response: Updated ticket with new assignment
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

1. TicketAnalyticsView in analytics/views.py
   ├─ Permission: IsAuthenticated (all users)
   ├─ Parse query parameters
   │  ├─ timeframe: 'week'
   │  ├─ facility_id: 1
   │  ├─ group_by: 'day'
   │  └─ days: 30
   └─ Call TicketAnalytics.get_analytics(filters)

2. TicketAnalytics class in analytics/analytics.py
   ├─ Build queryset filters:
   │  ├─ Tickets in facility=1
   │  └─ Updated in past 30 days
   ├─ Aggregate by status:
   │  ├─ open_count = count(status='open')
   │  ├─ assigned_count = count(status='assigned')
   │  ├─ in_progress_count = count(status='in_progress')
   │  ├─ pending_count = count(status='pending')
   │  ├─ resolved_count = count(status='resolved')
   │  └─ closed_count = count(status='closed')
   ├─ Calculate metrics:
   │  ├─ avg_resolution_time = avg(resolved_at - created_at)
   │  ├─ avg_response_time = avg(first_status_change - created_at)
   │  └─ total_tickets = count(*)
   ├─ Group by day (7 data points for week view):
   │  └─ Day 1: {date, open, assigned, resolved, ...}
   │  └─ Day 2: {date, open, assigned, resolved, ...}
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
       "in_progress": 12,
       "pending": 8,
       "resolved": 412,
       "closed": 23,
       "avg_resolution_time": "2.5 days",
       "avg_response_time": "4 hours"
     },
     "by_day": [
       {
         "date": "2025-01-15",
         "open": 45,
         "assigned": 23,
         "resolved": 12
       },
       ...
     ]
   }
```

### Technician Analytics Example

```
GET /api/analytics/technicians/?technician_id=4

TechnicianAnalytics.get_analytics(technician_id=4)
├─ Get all tickets assigned to technician 4
├─ Calculate:
│  ├─ assigned_count
│  ├─ completed_count = count(status='resolved'|'closed')
│  ├─ pending_count
│  ├─ avg_completion_time = avg(resolved_at - assigned_at)
│  └─ performance_rating = completed_count / total_count
└─ Return metrics

Response:
{
  "technician_id": 4,
  "technician_name": "tech_maria",
  "assigned_tickets": 45,
  "completed_tickets": 38,
  "pending_tickets": 7,
  "avg_completion_time": "1.8 days",
  "performance_rating": 0.84
}
```

### Admin Dashboard Analytics

```
GET /api/analytics/admin-dashboard/

AdminAnalytics.get_analytics()
├─ System overview:
│  ├─ total_tickets
│  ├─ total_users
│  ├─ total_technicians
│  └─ average_resolution_time
├─ Overdue tickets (>7 days open/assigned/in_progress)
│  └─ Only visible to admin/manager roles
├─ Status distribution:
│  └─ Pie chart data
└─ Recent tickets:
   └─ Last 10 tickets

Response includes:
- System statistics (counts, averages)
- Overdue ticket list (admin/manager only)
- Status breakdown
- Recent activity
```

---

## Module Dependencies

### Import Map

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
├── Facility, Section, Comment, Feedback, TicketLog

tickets/serializers.py
└─ Depends on: models.py, DRF

tickets/api/services/ticket_services.py
└─ Depends on: models.py

tickets/api/views/resource_views.py
├─ Depends on: models.py, serializers.py, services/ticket_services.py
└─ Uses: DRF generics, pagination.py, permissions.py

tickets/api/analytics/analytics.py
└─ Depends on: models.py

tickets/api/analytics/views.py
├─ Depends on: analytics.py, serializers.py
└─ Uses: DRF APIView, permissions.py

tickets/api/simple_auth_views.py
├─ Depends on: models.py, auth_models.py
├─ Uses: DRF Token, permissions.py
└─ Optional: email_service.py (magic link - commented out)

tickets/api/urls.py
├─ Imports from: views/, analytics/, reports/, simple_auth_views.py
└─ Mounts all routes
```

### Circular Dependency Avoidance

**Good**:
```python
# In views/resource_views.py
from tickets.api.services.ticket_services import update_ticket
# ✅ Views call services (correct layer order)

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
```

---

## Adding New Features

### 1. Adding a New API Endpoint

**Scenario**: Add endpoint to get all tickets assigned to current user

**Steps**:

1. **Service Layer** (`tickets/api/services/ticket_services.py`):
```python
def get_user_tickets(user):
    """Get all tickets accessible to user based on role"""
    if user.role == 'technician':
        return Ticket.objects.filter(assigned_to=user)
    elif user.role in ['admin', 'manager']:
        return Ticket.objects.all()
    else:
        return Ticket.objects.filter(raised_by=user)
```

2. **View** (`tickets/api/views/resource_views.py`):
```python
class UserTicketsListView(generics.ListAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        return get_user_tickets(self.request.user)
```

3. **URL Route** (`tickets/api/urls.py`):
```python
urlpatterns = [
    # ... existing routes
    path('my-tickets/', UserTicketsListView.as_view(), name='user-tickets'),
]
```

4. **Test** (`tickets/tests/test_apis.py`):
```python
def test_get_user_tickets(self):
    # Login as technician
    # GET /api/my-tickets/
    # Verify only assigned tickets returned
    pass
```

### 2. Adding a New Status to Ticket Workflow

**Steps**:

1. **Model** (`tickets/models.py`):
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
    ]
```

2. **Service** (`tickets/api/services/ticket_services.py`):
```python
VALID_STATUS_TRANSITIONS = {
    # ... existing transitions
    'pending': ['in_progress', 'resolved', 'on_hold'],  # Added
    'on_hold': ['in_progress', 'resolved'],  # New from on_hold
}
```

3. **Test** (`tickets/tests/test_workflow.py`):
```python
def test_status_transition_to_on_hold(self):
    # Create ticket in pending
    # Transition to on_hold
    # Verify status changed and TicketLog created
    pass
```

### 3. Adding a New Analytics Metric

**Steps**:

1. **Analytics Class** (`tickets/api/analytics/analytics.py`):
```python
class TicketAnalytics:
    def get_analytics(self, filters):
        # ... existing aggregations
        # New metric:
        avg_wait_time = self._calculate_avg_wait_time(tickets)
        
        return {
            # ... existing
            'avg_wait_time': avg_wait_time,
        }
    
    def _calculate_avg_wait_time(self, tickets):
        """Avg time between created and first assignment"""
        # Logic here
        pass
```

2. **Update Response** in `analytics/views.py` or serializer

3. **Test** (`tickets/tests/test_analytics.py`):
```python
def test_analytics_avg_wait_time(self):
    # Create tickets with known wait times
    # Call analytics endpoint
    # Verify metric calculated correctly
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
