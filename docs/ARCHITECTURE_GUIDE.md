# Architecture Guide - Django Resolver

[← Back to Index](INDEX.md) | [← Back to README](../README.md) | [Detailed Reference →](CODEBASE_ARCHITECTURE.md)

**Complete system architecture overview for developers.** This guide explains how Django Resolver is designed. For detailed technical reference, see [Codebase Architecture](CODEBASE_ARCHITECTURE.md).

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
- **Framework**: Django 5.2.7 + Django REST Framework 3.16.1
- **Database**: PostgreSQL 12+
- **Authentication**: Token-based (password-based login)
- **API Style**: REST with JSON requests/responses
- **Testing**: pytest with 157+ test cases

### Core Purpose
Enterprise-grade REST API for managing maintenance tickets in organizations with multi-level hierarchies (Organization → Campus → Department → Section).

### Key Features
- ✅ **Organizational Hierarchy**: Multi-level department structures
- ✅ **Role-Based Access Control**: 6 roles with scope-based permissions
- ✅ **Automatic Escalation**: 2-level escalation workflow
- ✅ **Ticket Numbering**: `CAMPUS-DEPT-XXXXX` format
- ✅ **Analytics**: Role-specific dashboards and reporting
- ✅ **Audit Logging**: Complete change history

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

### Layer 1: Models (`tickets/models.py`)
**Responsibility**: Data schema and validation
- Single file contains all models (Django best practice)
- 8 core models: Organization, Campus, Department, Section, Facility, CustomUser, Ticket, TicketLog
- Includes model methods for business logic
- Automatic ticket number generation on save

**Key Models**:
```python
# Organization → Campus → Department → Section hierarchy
Organization (name, type: gov/education/healthcare/corporate)
  ├─ Campus (code, location)
  │   ├─ Department (head_of_department FK)
  │   │   ├─ Section (head_of_section FK)
  │   │   └─ Facility (for section)
  │   └─ Ticket (created by campus users)
CustomUser (role: user/tech/head_of_section/hod/manager/admin)
Ticket (status, priority, escalation_level, pending_reason/comment)
```

### Layer 2: Services (`tickets/api/services/services.py`)
**Responsibility**: Business logic and validation (consolidated in single `TicketService` class)
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

### Layer 3: Views (`tickets/api/views/views.py`)
**Responsibility**: HTTP request handling and permissions (consolidated in single file with 20+ view classes)
- DRF generic views for CRUD: `ListCreateAPIView`, `RetrieveUpdateDestroyAPIView`
- Custom views for complex operations: `APIView` subclasses for escalation
- **Permissions**: All views require `IsWithinOrganizationalScope` permission
- **Delegation**: Views delegate to TicketService, not direct ORM access

**View Organization**:
- Hierarchy: Organization, Campus, Department, Section views
- Tickets: List, detail, create, escalation endpoints
- Analytics: Role-specific dashboard views
- Bulk operations: BulkTicketStatusUpdateView

### Layer 4: Serializers (`tickets/serializers.py`)
**Responsibility**: Data transformation (request/response serialization)
- TicketSerializer with conditional nested object inclusion
- UserSerializer for user representation
- SectionSerializer with campus context fields (R1 Enhancement)
- CommentSerializer, FeedbackSerializer for related data

**Optimization**: List views skip expensive nested queries for performance (100x faster)

---

## Request Flow

Complete flow from HTTP request to response:

```
1. HTTP Request arrives
   ↓
2. Django URL Router (urls.py)
   - Matches path to View class
   ↓
3. View Class (views.py)
   - Checks authentication (token required)
   - Validates IsWithinOrganizationalScope permission
   ↓
4. Service Layer (services.py)
   - Validates business rules
   - Checks organizational scope
   - Performs operation on models
   - Logs changes to TicketLog
   ↓
5. Model Layer (models.py)
   - Updates database
   - Runs model validations
   - Triggers signals if configured
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
View: TicketUpdateView validates permission + org scope
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
     │  │ PENDING │ ← Waiting for response (Spec requirement)
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

### Escalation Levels

Automatic escalation triggered by time thresholds:

```
Level 0 (No Escalation)
  ↓ [After 48 hours]
Level 1 (Section Head Escalation)
  ↓ [After 72 hours total]
Level 2 (HOD Escalation)
  → Max level reached
```

**Priority Auto-Escalation** (Spec feature):
- `OPEN` ticket starts as `LOW` priority
- On Level 1 escalation → `MEDIUM`
- On Level 2 escalation → `HIGH`
- After 72hrs total → Auto-marked `CRITICAL`

---

## Organizational Hierarchy

### Structure

```
Organization (e.g., "Government Institution")
  ├─ Campus MAIN (Nairobi)
  │   ├─ Department IT (Head: hod_alex)
  │   │   ├─ Section Network (Leader: head_of_section_ben)
  │   │   │   ├─ Technician: tech_alex
  │   │   │   └─ Technician: tech_john
  │   │   └─ Section OSS (Leader: head_of_section_mike)
  │   │
  │   └─ Department Operations (Head: hod_maria)
  │       ├─ Section Plumbing (Leader: head_of_section_linda)
  │       └─ Section Electrical (Leader: head_of_section_david)
  │
  ├─ Campus WEST (Mombasa)
  │   └─ [Similar Department/Section structure]
  │
  └─ Campus DOWNTOWN (Downtown Nairobi)
      └─ [Similar Department/Section structure]
```

### Ticket Placement Logic

**Key Rule**: Tickets are identified by `section_id` (primary key), NOT section name.

```
Ticket created with section_id=1
  ↓ Via FK relationships:
  Section 1 → Department 1 → Campus 1
  ↓
Automatic derivation:
  ticket_no = f"{campus.code}-{department.code}-{ticket.id:05d}"
  Example: "MAIN-IT-00001"
```

**Benefit**: Handles multi-campus sections with same name without collision

---

## Role-Based Access Control

### Permission Model

| Role | Scope | Permissions |
|------|-------|-------------|
| `user` | Section | Create tickets, comment own, submit feedback |
| `technician` | Section | + Update status, assign within section |
| `head_of_section` | Section | + Escalate, manage escalations |
| `hod` | Department | View all dept tickets, final escalation point |
| `manager` | Own department, all campuses in org | Analytics only, no ticket list/detail |
| `admin` | System | Full access, bypass all checks |

### Scope Enforcement

Every view enforces:
```python
@permission_classes([IsWithinOrganizationalScope])
def view_function(...):
    # Only users in same org can access
    # Tickets filtered to user's accessible campus/dept/section
```

**Method**: `user.get_accessible_tickets()` returns scope-limited queryset

---

## Data Models

### Consolidated in Single File (`tickets/models.py`)

**Organization Models**:
- `Organization` - Root entity, tracks type and location
- `Campus` - Geographic/operational divisions
- `Department` - Functional divisions within campus
- `Section` - Specialized units (where technicians work)
- `Facility` - Physical assets/locations for tickets

**User Models**:
- `CustomUser` - Extended Django User with roles and scope
  - Roles: user, technician, head_of_section, hod, manager, admin
  - Fields: primary_campus, primary_department, sections (M2M)

**Ticket Models**:
- `Ticket` - Core ticket entity
  - Fields: section (FK), facility (FK), raised_by (FK), assigned_to (FK)
  - Status options: open, assigned, in_progress, pending, resolved, closed
  - Priority: low, medium, high, critical (auto-escalates)
  - Escalation: level 0-2, next_escalation_due, auto_escalation_enabled
  - Pending: pending_reason, pending_comment (both required for status=pending)
  - Auto-generates: ticket_no in format `CAMPUS-DEPT-XXXXX`

- `TicketLog` - Immutable audit trail
  - Records: status changes, assignments, escalations, closures

- `Comment`, `Feedback` - Ticket-related data

### Relationships

```
Organization ← Campus → Department → Section
                           ↓
                       Facility
                           ↓
Ticket (section FK) ← Comment (ticket FK)
    ↓
    ├─ assigned_to (CustomUser FK)
    ├─ raised_by (CustomUser FK)
    └─ facility (Facility FK)
```

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

**All roles use password login** - determined by user.role field

### Magic Link (Future)

Code is preserved but commented out for future implementation when email service is configured.

---

## Escalation System

### Auto-Escalation Process

```
Runs via: python manage.py process_auto_escalations (or scheduled task)

For each ticket:
  1. Check if next_escalation_due <= now()
  2. Check if auto_escalation_enabled = True
  3. Check escalation_level < 2
  
  If all true:
    - Level 1: Notify head_of_section, set priority=MEDIUM
    - Level 2: Notify HOD, set priority=HIGH
    - After 72h: Auto-mark priority=CRITICAL
    - Create notification record
    - Log in TicketLog
```

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
  - Notify escalation recipient
```

---

## Key Design Patterns

### 1. **Consolidated Services Pattern**
- Single `TicketService` class handles all ticket operations
- No scattered business logic in views
- Easy to test, maintain, and extend

### 2. **Scope-Based Access Control**
- Every operation validates org scope
- `user.get_accessible_tickets()` returns properly filtered queryset
- No "accidental" cross-org data access

### 3. **State Machine for Ticket Status**
- `validate_status_transition()` enforces valid flows
- PENDING status requires both reason + comment
- Cannot transition from invalid states

### 4. **Immutable Audit Trail**
- TicketLog records all changes
- Timestamps, performed_by user, action description
- Enables compliance reporting

### 5. **Automatic Ticket Numbering**
- `CAMPUS-DEPT-XXXXX` format generated on ticket creation
- Includes organizational context
- Auto-incrementing within department

### 6. **Conditional Serialization**
- List views: simplified serialization (faster queries)
- Detail views: full nested objects
- Controlled via `skip_available_technicians` context flag

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
- Result: 66x faster for organizational queries

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
│  - Models              │
│  - Views               │
│  - Services            │
└──────┬──────────────────┘
       │
┌──────▼──────────────────┐
│  PostgreSQL Database   │ (Persistent data)
└───────────────────────┘
```

---

## Next Steps

### Learn More
- **How to add features**: See "Adding New Features" in [Codebase Architecture](CODEBASE_ARCHITECTURE.md)
- **Complete technical details**: [Codebase Architecture](CODEBASE_ARCHITECTURE.md)
- **API integration**: [API Integration Guide](API_INTEGRATION_GUIDE.md)
- **Ticket workflow rules**: [Workflow Specification](specifications/WORKFLOW_SPEC.md)

### Start Building
1. Review this guide for architecture concepts
2. Check [Testing Guide](testing/TESTING.md) for test patterns
3. Use [Sample Queries](testing/SAMPLE_QUERIES.md) for ORM examples
4. Reference [Codebase Architecture](CODEBASE_ARCHITECTURE.md) for implementation details

---

**Last Updated**: March 18, 2026  
**Version**: 1.0  
**Compliance**: ✅ 96% (See [Compliance Audit](compliance/AUDIT_STATUS.md))
