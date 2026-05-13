# Architecture Guide - Django Resolver

[← Back to Index](INDEX.md) | [← Back to README](../README.md)

**Complete system architecture overview for developers.** This guide explains how Django Resolver is designed.

**Audience**: Backend developers, systems architects  
**Time to read**: 15-20 minutes

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architectural Layers](#architectural-layers)
3. [Request Flow](#request-flow)
4. [Ticket Lifecycle](#ticket-lifecycle)
5. [Organizational Hierarchy](#organizational-hierarchy)
6. [Role-Based Access Control](#role-based-access-control)
7. [Data Models](#data-models)
8. [Authentication Flow](#authentication-flow)
9. [Escalation System](#escalation-system)
10. [Key Design Patterns](#key-design-patterns)

---

## System Overview

### Technology Stack
- **Framework**: Django 6.0.3 + Django REST Framework 3.16.1
- **Database**: PostgreSQL 12+
- **Authentication**: Token-based (password-based login)
- **API Style**: REST with JSON requests/responses
- **Testing**: pytest with ~258 test cases

### Core Purpose
Enterprise-grade REST API for managing maintenance tickets in organizations with multi-level hierarchies (Campus → CampusDepartment → Section).

### Key Features
- **Organizational Hierarchy**: Multi-level department structures
- **Role-Based Access Control**: 6 roles with scope-based permissions
- **Automatic Escalation**: 2-level escalation workflow
- **Ticket Numbering**: `CAMPUS-DEPT-XXXXX` format
- **Analytics**: Role-specific dashboards and reporting
- **Audit Logging**: Complete change history

---

## Architectural Layers

Django Resolver uses a **4-layer architecture** separating concerns:

```
┌─────────────────────────────────────┐
│  HTTP Layer (Django URLs)           │ Entry point - URL routing
├─────────────────────────────────────┤
│  Views Layer (DRF Views)            │ Request handling, permissions
├─────────────────────────────────────┤
│  Service Layer (Business Logic)     │ Core operations, validation
├─────────────────────────────────────┤
│  Model Layer (Django ORM)           │ Data schema, relationships
└─────────────────────────────────────┘
```

### Layer 1: Models (`tickets/models/` package)
**Responsibility**: Data schema and validation
- Split into modules by domain (`organisation.py`, `sections.py`, `catalogue.py`, `facilities.py`, `tickets.py`, `users.py`)
- Includes model methods for business logic
- Automatic ticket number generation on save

**Key Models**:
```
Campus  (root entity — no Organization above it)
  └── CampusDepartment  (Campus + Department + HOD)
        └── Section  (CampusDepartment + SectionType + HOS)
              ├── TechnicianSection  (M2M: Technician ↔ Section)
              └── Ticket
                    ├── ServiceItem → ServiceCategory → SectionType
                    └── Facility
```

`Department` is **global** (not owned by any campus). `CampusDepartment` is the join table linking a Campus and a Department.

### Layer 2: Services (`tickets/api/services/`)
**Responsibility**: Business logic and validation
- **Create operations**: `create_ticket()` with scope validation
- **Update operations**: `update_ticket_status()` with state machine validation
- **Escalation**: `escalate_ticket()` with level tracking
- **Permissions**: All methods validate user org scope before execution
- **Audit**: Changes logged to TicketLog automatically

**Key Service Methods**:
- `create_ticket()` - Scope-validated creation
- `assign_ticket()` - Technician assignment with constraints
- `escalate_ticket()` - Manual escalation handling
- `update_ticket_status()` - State machine enforcement
- `close_ticket()` - User/admin closure permissions
- `process_auto_escalations()` - Scheduled escalation

### Layer 3: Views (`tickets/api/views/` package)
**Responsibility**: HTTP request handling and permissions
- Split into modules by domain:
  - `ticket_views.py` — TicketListCreateView, TicketCreateView, TicketDetailView
  - `org_views.py` — Campus, Department, CampusDepartment, Section CRUD
  - `technician_views.py` — TechnicianSection assignment
  - `catalogue_views.py` — ServiceCategory, ServiceItem
  - `user_views.py` — UserListCreateView, TechniciansBySectionView
- DRF generic views for CRUD; custom `APIView` subclasses for complex operations
- **Delegation**: Views delegate to TicketService, not direct ORM access

### Layer 4: Serializers (`tickets/serializers/` package)
**Responsibility**: Data transformation (request/response serialization)
- Split into modules: `org.py`, `sections.py`, `catalogue.py`, `facilities.py`, `tickets.py`, `users.py`, `common.py`
- TicketSerializer with conditional nested object inclusion
- Read/write split pattern used throughout

**Optimization**: List views skip expensive nested queries for performance

---

## Request Flow

Complete flow from HTTP request to response:

```
1. HTTP Request arrives
   ↓
2. Django URL Router (tickets/api/urls.py)
   - Matches path to View class
   ↓
3. View Class (tickets/api/views/<module>.py)
   - Checks authentication (token required)
   - Validates permission class
   ↓
4. Service Layer (tickets/api/services/)
   - Validates business rules
   - Checks organizational scope
   - Performs operation on models
   - Logs changes to TicketLog
   ↓
5. Model Layer (tickets/models/)
   - Updates database
   - Runs model validations
   ↓
6. Service returns result/exceptions
   ↓
7. View formats response
   - Serializes model to JSON
   - Sets proper HTTP status code
   ↓
8. HTTP Response sent to client
```

**Example: Update Ticket Status**
```
POST /api/tickets/1/update-status/
  ↓
POST data: {"new_status": "in_progress"}
  ↓
View: validates permission + org scope
  ↓
Service: TicketService.update_ticket_status() checks:
  - Valid status transition
  - User has permission for new status
  - Ticket in correct org scope
  ↓
Model: Ticket.save() runs, creates TicketLog entry
  ↓
Response: 200 OK with updated ticket
```

---

## Ticket Lifecycle

### State Machine

```
┌─────────┐
│  OPEN   │ ← Initial state when created
└────┬────┘
     │ (assign technician)
     ↓
┌─────────────┐
│   ASSIGNED  │ ← Auto-set when assigned_to filled
└────┬────────┘
     │ (technician starts work)
     ↓
┌──────────────┐
│  IN_PROGRESS │ ← Work actively happening
└────┬─────────┘
     │
     ├─→ (needs info from user)
     │   ↓
     │  ┌─────────┐
     │  │ PENDING │ ← Waiting for response
     │  └────┬────┘
     │       │ (user responds)
     │       →─ (back to IN_PROGRESS)
     │
     └─→ (work complete)
         ↓
    ┌──────────┐
    │ RESOLVED │ ← Ready for user acceptance
    └────┬─────┘
         │ (user accepts or admin reviews)
         ↓
    ┌──────────┐
    │  CLOSED  │ ← Final state, immutable
    └──────────┘
```

Additionally:
```
pending_approval → (approve) → open
pending_approval → (reject)  → rejected
```

### Escalation Levels

Automatic escalation triggered by time thresholds (measured from `assigned_at`):

```
Level 0 (No Escalation)
  ↓ [After 48 hours from assignment]
Level 1 (Section Head Escalation)
  ↓ [After 24 hours more]
Level 2 (HOD Escalation)
  → Max level reached
```

**Priority Auto-Escalation**:
- Ticket starts as `LOW` priority
- On Level 1 escalation → `MEDIUM`
- On Level 2 escalation → `HIGH`
- After 72 hrs total → Auto-marked `CRITICAL`

---

## Organizational Hierarchy

### Structure

```
Campus  (root entity — no Organization above it)
  └── CampusDepartment  (Campus + Department + HOD)
        └── Section  (CampusDepartment + SectionType + HOS)
              ├── TechnicianSection  (M2M: Technician ↔ Section)
              └── Ticket
```

`Department` is a global entity. `CampusDepartment` is the join table that binds a Department to a specific Campus and records its HOD.

**Example**:
```
Campus NRB (Nairobi)
  └── CampusDepartment: NRB + ICT (HOD: hod_ict_nrb)
        └── Section: ICT Support NRB  (HOS: hos_ict_nrb)
              ├── Technician: tech_alex
              └── Ticket: NRB-ICT-00001

Campus MSA (Mombasa)
  └── CampusDepartment: MSA + ICT (separate CampusDepartment row)
        └── Section: ICT Support MSA
```

### Ticket Placement Logic

**Key Rule**: Tickets are identified by `section_id` (primary key), NOT section name.

```
Ticket created with section_id=1
  ↓ Via FK relationships:
  Section 1 → CampusDepartment 1 → Campus 1
  ↓
Automatic derivation:
  ticket_no = f"{campus.code}-{department.code}-{ticket.id:05d}"
  Example: "NRB-ICT-00001"
```

### Ticket Creation via Catalogue

`POST /api/tickets/create/` auto-resolves the org structure:
- Request: `{ department_id, service_item_id, title, description }`
- Uses `user.primary_campus` + `department_id` to find `CampusDepartment`
- Uses `service_item → category → section_type` to find the appropriate `Section`
- Response: `{ ticket, campus_department, section, eligible_technicians }`

---

## Role-Based Access Control

### Permission Model

| Role | Scope | Permissions |
|------|-------|-------------|
| `user` | Own tickets only | Create tickets, comment on own, submit feedback |
| `technician` | Tickets in assigned sections (via TechnicianSection) | + Update status |
| `head_of_section` | Own section | + Assign tickets, manage technicians |
| `hod` | Own CampusDepartment (campus + department pair) | View all dept tickets on own campus |
| `manager` | Own department across all campuses | Analytics only, no direct ticket list/detail |
| `admin` | System | Full access, bypass all checks |

### Permissions Package (`tickets/api/permissions/`)
- `org.py` → `IsWithinOrganizationalScope`, `CanManageSectionTechnicians`
- `tickets.py` → `CanViewTicket`, `CanEditTicket`, `CanAssignTickets`, `CanEscalateTickets`
- `users.py` → `CanManageUsers`, `IsTechnicianOrAdmin`

### Scope Enforcement

**Method**: `TicketService.get_accessible_tickets(user)` returns scope-limited queryset

`manager` ticket scope: `section__campus_department__department__code == user.primary_department.code` across all campuses.

---

## Data Models

### Model Package (`tickets/models/`)

| File | Models |
|------|--------|
| `organisation.py` | Campus, Department, CampusDepartment |
| `sections.py` | SectionType, Section, TechnicianSection |
| `catalogue.py` | ServiceCategory, ServiceItem |
| `facilities.py` | Facility |
| `tickets.py` | Ticket, Comment, Feedback, TicketLog |
| `users.py` | CustomUser |

**CustomUser**:
- Roles: `user`, `technician`, `head_of_section`, `hod`, `manager`, `admin`
- Fields: `primary_campus`, `primary_department`
- `TechnicianSection` M2M links technicians to sections

**Ticket**:
- Status: `open`, `assigned`, `in_progress`, `pending`, `resolved`, `closed`, `pending_approval`, `rejected`
- Priority: `low`, `medium`, `high`, `critical` (auto-escalates)
- Escalation: `escalation_level` 0–2, `next_escalation_due` (based on `assigned_at`)
- Pending: `pending_reason`, `pending_comment` (both required for `status=pending`)
- Auto-generates: `ticket_no` in format `CAMPUS-DEPT-XXXXX`

**TicketLog**: Immutable audit trail recording status changes, assignments, escalations

---

## Authentication Flow

### Password-Based Login (Current)

```
1. Client POST /api/auth/login/
   {username, password}
   ↓
2. Django auth backend validates credentials
   ↓
3. Token created/retrieved from Token model
   ↓
4. Response: {token, user_data}
   ↓
5. Client uses: Authorization: Token {token}
   for all subsequent requests
```

**All roles use password login** — determined by `user.role` field.

### Magic Link (Future)

Code is preserved but commented out for future implementation when email service is configured.

---

## Escalation System

### Auto-Escalation Process

```
Runs via: python manage.py process_auto_escalations (or scheduled task)

For each assigned ticket:
  1. Check if next_escalation_due <= now()
  2. Check if auto_escalation_enabled = True
  3. Check escalation_level < 2
  
  If all true:
    - Level 1: Notify head_of_section, set priority=MEDIUM
    - Level 2: Notify HOD, set priority=HIGH
    - After 72h: Auto-mark priority=CRITICAL
    - Log in TicketLog
```

**Important**: Escalation clock starts at `assigned_at`, not `created_at`. Unassigned tickets never escalate.

### Manual Escalation

```
POST /api/tickets/{id}/escalate/
{reason: "Needs urgent attention"}

Service validates:
  - Ticket not closed
  - Escalation allowed by role
  - Next level exists
  
Then:
  - Update escalation_level
  - Update priority (per spec)
  - Log the escalation reason
```

---

## Key Design Patterns

### 1. **Consolidated Services Pattern**
- Single `TicketService` class handles all ticket operations
- No scattered business logic in views
- Easy to test, maintain, and extend

### 2. **Scope-Based Access Control**
- Every operation validates org scope
- `TicketService.get_accessible_tickets(user)` returns properly filtered queryset
- No "accidental" cross-campus data access

### 3. **State Machine for Ticket Status**
- `validate_status_transition()` enforces valid flows
- `PENDING` status requires both `pending_reason` + `pending_comment`
- Cannot transition from invalid states

### 4. **Immutable Audit Trail**
- TicketLog records all changes
- Timestamps, `performed_by` user, action description
- Enables compliance reporting

### 5. **Automatic Ticket Numbering**
- `CAMPUS-DEPT-XXXXX` format generated on ticket creation
- Includes organizational context
- Auto-incrementing within department (all sections in the same department share one counter)

### 6. **Conditional Serialization**
- List views: simplified serialization (faster queries)
- Detail views: full nested objects
- Role-based `get_fields()` overrides strip fields below required role thresholds

---

## Performance Optimizations

### Database Indexes
```python
class Ticket(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['status']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['escalation_level', '-escalated_at']),
        ]
```

### Query Optimization
- `select_related()` for FK: section, assigned_to, facility
- `prefetch_related()` for reverse: comments, logs (only detail views)
- List views exclude M2M relationships

---

## Deployment Architecture

```
┌──────────────┐
│   Client     │ (Browser, Mobile App, API Consumer)
│  (HTTP/REST) │
└──────┬───────┘
       │
┌──────▼──────────────────┐
│   Web Server (Gunicorn) │ (Production WSGI server)
│   [multiple workers]    │
└──────┬──────────────────┘
       │
┌──────▼──────────────────┐
│  Django Application     │ (This project)
│  - models/             │
│  - api/views/          │
│  - api/services/       │
└──────┬──────────────────┘
       │
┌──────▼──────────────────┐
│  PostgreSQL Database   │ (Persistent data)
└───────────────────────┘
```

---

## Next Steps

### Learn More
- **API integration**: [API Integration Guide](API_INTEGRATION_GUIDE.md)
- **Ticket workflow rules**: [Workflow Specification](specifications/WORKFLOW_SPEC.md)
- **Analytics endpoints**: [Analytics API](api/ANALYTICS.md)

### Start Building
1. Review this guide for architecture concepts
2. Check [Testing Guide](testing/TESTING.md) for test patterns
3. Use [Sample Queries](testing/SAMPLE_QUERIES.md) for ORM examples

---

**Last Updated**: May 13, 2026  
**Version**: 2.0  
**Compliance**: See [Compliance Audit](compliance/AUDIT_STATUS.md)
