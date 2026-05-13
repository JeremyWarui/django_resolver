# API Integration Guide - Django Resolver

[← Back to Index](INDEX.md) | [← Back to README](../README.md)

**Complete guide for frontend developers integrating with the Django Resolver API.** This guide covers authentication, all endpoints, and analytics. For role-based dashboard details, see [Analytics API](api/ANALYTICS.md).

**Audience**: Frontend developers, API consumers, integration engineers  
**Time to read**: 20-30 minutes

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [API Conventions](#api-conventions)
4. [Organizational Hierarchy Endpoints](#organizational-hierarchy-endpoints)
5. [Ticket Management Endpoints](#ticket-management-endpoints)
6. [Escalation Endpoints](#escalation-endpoints)
7. [User Management Endpoints](#user-management-endpoints)
8. [Analytics Endpoints](#analytics-endpoints)
9. [Error Handling](#error-handling)
10. [Code Examples](#code-examples)

---

## Getting Started

### Quick Start (5 minutes)

```bash
# 1. Get test credentials from docs/DEFAULT_CREDENTIALS.md
# Example: username=user_sarah, password=adminuser123

# 2. Login and get token
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"user_sarah","password":"adminuser123"}'

# Response:
{
  "token": "abc123xyz789...",
  "user": {
    "id": 2,
    "username": "user_sarah",
    "email": "jane@example.com",
    "role": "user"
  }
}

# 3. Use token in all API requests
curl http://localhost:8000/api/tickets/ \
  -H "Authorization: Token abc123xyz789..."
```

### API Base URL
- **Development**: `http://localhost:8000/api/`
- **Production**: `https://django-resolver.onrender.com/api/`

---

## Authentication

### Password-Based Login (Current)

All users authenticate using username and password credentials.

#### Endpoint
```
POST /api/auth/login/
```

#### Request
```json
{
  "username": "user_sarah",
  "password": "adminuser123"
}
```

#### Response (200 OK)
```json
{
  "token": "abc123xyz789...",
  "user": {
    "id": 2,
    "username": "user_sarah",
    "email": "jane@example.com",
    "first_name": "Jane",
    "last_name": "Doe",
    "role": "user",
    "primary_campus": {
      "id": 1,
      "name": "Nairobi Campus",
      "code": "NRB"
    }
  }
}
```

#### Error (401 Unauthorized)
```json
{
  "error": "Invalid credentials"
}
```

### Using Token in Requests

All API endpoints require authentication via **Bearer Token**:

```
Authorization: Token {token}
```

**Example with curl**:
```bash
curl http://localhost:8000/api/tickets/ \
  -H "Authorization: Token abc123xyz789..."
```

**Example with JavaScript fetch**:
```javascript
const token = localStorage.getItem('auth_token');

fetch('http://localhost:8000/api/tickets/', {
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  }
})
  .then(r => r.json())
  .then(data => console.log(data));
```

**Example with Axios**:
```javascript
const instance = axios.create({
  baseURL: 'http://localhost:8000/api/',
  headers: {
    'Authorization': `Token ${token}`
  }
});
```

### Magic Link (Future)

Email-based magic links are commented out for future implementation. Enable when email service is configured.

---

## API Conventions

### Response Format

All responses are JSON with these conventions:

#### List Response (paginated)
```json
{
  "count": 42,
  "next": "http://api/tickets/?page=2",
  "previous": null,
  "page_size": 20,
  "total_pages": 3,
  "current_page": 1,
  "results": [
    { "id": 1, "ticket_no": "NRB-ICT-00001", ... }
  ]
}
```

#### Detail Response
```json
{
  "id": 1,
  "ticket_no": "NRB-ICT-00001",
  "status": "open",
  "created_at": "2024-01-15T10:30:00Z",
  ...
}
```

#### Error Response
```json
{
  "error": "Error message",
  "details": { "field": ["Error description"] }
}
```

### Pagination

Default behavior: **20 items per page** (max 100)

**Query parameters**:
- `page=1` - Retrieve specific page
- `page_size=50` - Items per page (override default)

**Example**:
```
GET /api/tickets/?page=2&page_size=20
```

### Filtering

Many endpoints support filtering via query parameters.

**Common filters**:
- `status=open` - Filter by status
- `section_id=1` - Filter by section
- `assigned_to__isnull=true` - Unassigned tickets
- `escalation_level=1` - Escalated to section head

**Combined example**:
```
GET /api/tickets/?status=open&section_id=1
```

### Ordering

Supported fields:
- `created_at` - Ascending: `?ordering=created_at` / Descending: `?ordering=-created_at`
- `updated_at` - By default, tickets sorted by `-updated_at` (newest first)
- `status` - Sort by status

**Example**:
```
GET /api/tickets/?ordering=-created_at
```

### Timestamps

All timestamps use ISO 8601 format with UTC timezone:
```
"2024-01-15T10:30:45.123456Z"
```

---

## Organizational Hierarchy Endpoints

The hierarchy is: **Campus → CampusDepartment → Section**

`Department` is a global entity. `CampusDepartment` is the join table binding a Department to a Campus (with its HOD).

### Campuses

#### List Campuses
```
GET /api/campuses/
```

**Response** (truncated):
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "Nairobi Campus",
      "code": "NRB"
    }
  ]
}
```

#### Create Campus (Admin only)
```
POST /api/campuses/
{
  "name": "Mombasa Campus",
  "code": "MSA"
}
```

---

### Departments

#### List Departments (Global — not campus-scoped)
```
GET /api/departments/
```

**Response** (truncated):
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "ICT",
      "code": "ICT"
    }
  ]
}
```

---

### Campus Departments

`CampusDepartment` is the join between a Campus and a Department. It also holds the HOD for that campus+department pair.

#### List CampusDepartments
```
GET /api/campus-departments/
```

**Filters**:
- `campus_id=1` - By campus
- `department_id=1` - By department

**Response** (truncated):
```json
{
  "count": 8,
  "results": [
    {
      "id": 1,
      "campus": { "id": 1, "code": "NRB", "name": "Nairobi Campus" },
      "department": { "id": 1, "code": "ICT", "name": "ICT" },
      "head_of_department": {
        "id": 5,
        "username": "hod_ict_nrb",
        "role": "hod"
      }
    }
  ]
}
```

---

### Sections

#### List Sections (Filtered to User's Sections)
```
GET /api/sections/
```

**Filters**:
- `campus_department_id=1` - By CampusDepartment

**Response** (includes campus context):
```json
{
  "count": 4,
  "results": [
    {
      "id": 1,
      "name": "ICT Support",
      "campus_code": "NRB",
      "department_code": "ICT",
      "display_name": "NRB-ICT Support",
      "section_type": 1,
      "head_of_section": {
        "id": 6,
        "username": "hos_ict_nrb"
      }
    }
  ]
}
```

#### Create Section (Admin/HOD)
```
POST /api/sections/
{
  "name": "Networking",
  "campus_department": 1,
  "section_type": 1
}
```

---

## Ticket Management Endpoints

### List Tickets

#### Get All Tickets (Scope-filtered by role)
```
GET /api/tickets/
```

**Filters**:
- `status=open` - Filter by status: `open`, `assigned`, `in_progress`, `pending`, `resolved`, `closed`
- `section_id=1` - Filter by section
- `assigned_to__isnull=true` - Unassigned tickets only
- `is_overdue=true` - Overdue tickets only
- `escalation_level=1` - Escalated to section head
- `escalation_level=2` - Escalated to HOD
- `priority=high` - Filter by priority: `low`, `medium`, `high`, `critical`

**Ordering**:
- Default: `-updated_at` (newest first)

**Response** (list view - simplified for performance):
```json
{
  "count": 42,
  "page_size": 20,
  "total_pages": 3,
  "results": [
    {
      "id": 1,
      "ticket_no": "NRB-ICT-00001",
      "title": "Printer not working",
      "status": "open",
      "priority": "low",
      "escalation_level": 0,
      "assigned_to_name": "tech_alex",
      "raised_by": {
        "username": "user_sarah"
      },
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T14:20:00Z"
    }
  ]
}
```

### Create Ticket (Catalogue-based flow)

#### Create New Ticket
```
POST /api/tickets/create/
{
  "department_id": 1,
  "service_item_id": 5,
  "title": "Internet connection down",
  "description": "Floor 3 network not responding"
}
```

The system uses `user.primary_campus` + `department_id` to find the `CampusDepartment`, then uses `service_item → category → section_type` to find the correct `Section`.

If `service_item.requires_approval = True`, the ticket starts as `pending_approval` instead of `open`.

**Response** (201 Created):
```json
{
  "ticket": {
    "id": 42,
    "ticket_no": "NRB-ICT-00042",
    "title": "Internet connection down",
    "status": "open",
    "priority": "low"
  },
  "campus_department": { "id": 1, "campus": "NRB", "department": "ICT" },
  "section": { "id": 1, "name": "ICT Support", "display_name": "NRB-ICT Support" },
  "eligible_technicians": [
    { "id": 10, "username": "tech_alex" }
  ]
}
```

### Retrieve Ticket

#### Get Ticket Details (Full nested objects)
```
GET /api/tickets/{id}/
```

**Response** (200 OK - detailed view):
```json
{
  "id": 1,
  "ticket_no": "NRB-ICT-00001",
  "title": "Printer not working",
  "description": "HP printer on floor 2",
  "status": "in_progress",
  "priority": "low",
  "escalation_level": 0,
  "pending_reason": null,
  "pending_comment": null,
  "section": {
    "id": 1,
    "name": "ICT Support",
    "display_name": "NRB-ICT Support",
    "campus_code": "NRB",
    "department_code": "ICT"
  },
  "facility": {
    "id": 5,
    "name": "Floor 2 Printer",
    "location": "2nd Floor"
  },
  "raised_by": {
    "id": 2,
    "username": "user_sarah"
  },
  "assigned_to": {
    "id": 10,
    "username": "tech_alex",
    "role": "technician"
  },
  "available_technicians": [
    { "id": 10, "username": "tech_alex" },
    { "id": 11, "username": "tech_alice" }
  ],
  "comments": [
    {
      "id": 1,
      "text": "Looking into it",
      "created_by": { "username": "tech_alex" },
      "created_at": "2024-01-15T11:00:00Z"
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T14:20:00Z"
}
```

Note: `available_technicians` and `organizational_path` are stripped for roles below `head_of_section`.

### Update Ticket

#### Update Ticket Status
```
PATCH /api/tickets/{id}/
{
  "status": "in_progress"
}
```

**Valid status transitions**:
- `open` → `assigned` (auto-set when `assigned_to` is assigned)
- `assigned` → `in_progress`
- `in_progress` → `pending` (requires `pending_reason` + `pending_comment`)
- `in_progress` → `resolved`
- `resolved` → `closed` (user who raised it or admin)
- `pending` ↔ `in_progress` (cycle)

#### Transition to Pending Status
```
PATCH /api/tickets/{id}/
{
  "status": "pending",
  "pending_reason": "Waiting for user information",
  "pending_comment": "User hasn't responded to question about error code"
}
```

**Requirement**: Both `pending_reason` and `pending_comment` required for pending status.

#### Response (200 OK)
```json
{
  "id": 1,
  "status": "pending",
  "pending_reason": "Waiting for user information",
  "pending_comment": "User hasn't responded to question about error code",
  "updated_at": "2024-01-15T16:00:00Z"
}
```

### Close Ticket

#### Close Ticket (User/Admin only)
```
POST /api/tickets/{id}/close/
{
  "reason": "Issue resolved"
}
```

**Permissions**:
- User who raised ticket can close
- Admin can always close

---

## Escalation Endpoints

### Manual Escalation

#### Escalate Ticket to Next Level
```
POST /api/tickets/{id}/escalate/
{
  "reason": "No response from technician"
}
```

**Escalation levels**:
- Level 0 (none) → Level 1 (Section Head)
- Level 1 (Section Head) → Level 2 (HOD)
- Cannot escalate from Level 2

**Response** (200 OK):
```json
{
  "id": 1,
  "escalation_level": 1,
  "escalation_reason": "No response from technician",
  "escalated_at": "2024-01-15T16:30:00Z",
  "priority": "medium"
}
```

---

## User Management Endpoints

### List Users (Scope-filtered)
```
GET /api/users/
```

**Filters**:
- `role=technician` - By role

### Get Technicians by Section

#### Get Available Technicians for Assignment
```
GET /api/technicians/?section_id=1
```

**Returns**: Only technicians assigned to the specified section (via `TechnicianSection`).

**Response**:
```json
{
  "count": 3,
  "results": [
    { "id": 10, "username": "tech_alex" },
    { "id": 11, "username": "tech_alice" }
  ]
}
```

---

## Analytics Endpoints

All 11 analytics endpoints are available. See [Analytics API](api/ANALYTICS.md) for full documentation.

### Quick Reference

| Endpoint | Access |
|----------|--------|
| `GET /api/analytics/tickets/` | admin, manager |
| `GET /api/analytics/admin-dashboard/` | admin, manager |
| `GET /api/analytics/user/` | all authenticated |
| `GET /api/analytics/technicians/` | admin, manager, hod, technician (own data) |
| `GET /api/analytics/technicians/me/` | technician, admin |
| `GET /api/analytics/manager/` | manager, admin |
| `GET /api/analytics/hod/` | hod, admin |
| `GET /api/analytics/section-head/` | head_of_section, admin |
| `GET /api/analytics/departments/<pk>/` | admin, manager (own dept), hod (own campus) |
| `GET /api/analytics/campus-departments/<pk>/` | admin, manager, hod (assigned only) |
| `GET /api/analytics/sections/<pk>/` | admin, manager, hod, head_of_section (own) |

### Manager Dashboard
```
GET /api/analytics/manager/
```

**Response** (own department across all campuses):
```json
{
  "department": "ICT",
  "period": "Last 30 days",
  "overview": {
    "total_tickets": 342,
    "open_tickets": 47,
    "closure_rate": 86.2
  },
  "campuses": [
    {
      "campus": "NRB",
      "total": 156,
      "open": 23,
      "closure_rate": 85.5
    },
    {
      "campus": "MSA",
      "total": 186,
      "open": 24,
      "closure_rate": 87.1
    }
  ],
  "sla_compliance": 92.3
}
```

### HOD Dashboard
```
GET /api/analytics/hod/
```

**Response**: Campus-level metrics for own CampusDepartment.

### Section Head Dashboard
```
GET /api/analytics/section-head/
```

**Response**: Section-specific metrics.

---

## Comments & Feedback

### Create Comment

#### Post Comment on Ticket
```
POST /api/comments/
{
  "ticket": 1,
  "text": "Looking into issue, will update shortly"
}
```

### Submit Feedback

#### Post Feedback on Resolved Ticket
```
POST /api/feedback/
{
  "ticket": 1,
  "rating": 5,
  "comment": "Technician was very helpful"
}
```

---

## Error Handling

### Common Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Bad Request | Invalid input data |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Permission denied (org scope) |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Invalid status transition |
| 422 | Unprocessable | Business logic violation |
| 500 | Server Error | Internal error |

### Error Response Format

```json
{
  "error": "Invalid status transition",
  "details": {
    "status": ["Cannot transition from 'closed' to 'pending'"]
  }
}
```

### Common Validation Errors

**Pending status without reason/comment**:
```json
{
  "error": "Invalid request",
  "details": {
    "pending_reason": ["This field is required when status=pending"],
    "pending_comment": ["This field is required when status=pending"]
  }
}
```

**Invalid technician assignment**:
```json
{
  "error": "Invalid assignment",
  "details": {
    "assigned_to": ["Technician must have this section in their TechnicianSection assignments"]
  }
}
```

**Out-of-scope access attempt**:
```json
{
  "error": "Access denied",
  "details": "Insufficient organizational scope"
}
```

---

## Code Examples

### Example 1: Login & List Tickets (JavaScript)

```javascript
async function loginAndListTickets() {
  // 1. Login
  const loginRes = await fetch('http://localhost:8000/api/auth/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: 'user_sarah',
      password: 'adminuser123'
    })
  });

  const { token } = await loginRes.json();
  localStorage.setItem('auth_token', token);

  // 2. List tickets with auth
  const ticketsRes = await fetch(
    'http://localhost:8000/api/tickets/?status=open&section_id=1',
    {
      headers: { 'Authorization': `Token ${token}` }
    }
  );

  const tickets = await ticketsRes.json();
  console.log('Open tickets:', tickets.results);
}

loginAndListTickets();
```

### Example 2: Assign Ticket (Python)

```python
import requests

TOKEN = "abc123xyz789"
BASE_URL = "http://localhost:8000/api"
HEADERS = {"Authorization": f"Token {TOKEN}"}

# 1. Get ticket details
ticket_res = requests.get(f"{BASE_URL}/tickets/1/", headers=HEADERS)
ticket = ticket_res.json()

# 2. Get available technicians for the section
techs_res = requests.get(
    f"{BASE_URL}/technicians/?section_id={ticket['section']['id']}",
    headers=HEADERS
)
technicians = techs_res.json()

# 3. Assign to first available
tech_id = technicians['results'][0]['id']
update_res = requests.patch(
    f"{BASE_URL}/tickets/1/",
    headers=HEADERS,
    json={"assigned_to": tech_id}
)

print(f"Assigned to: {update_res.json()['assigned_to']}")
```

### Example 3: Handle Pending Status (JavaScript)

```javascript
async function transitionToPending(ticketId, token) {
  const pendingData = {
    status: 'pending',
    pending_reason: 'Waiting for hardware verification',
    pending_comment: 'User needs to confirm hardware model number'
  };

  const res = await fetch(`http://localhost:8000/api/tickets/${ticketId}/`, {
    method: 'PATCH',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(pendingData)
  });

  if (!res.ok) {
    const error = await res.json();
    console.error('Failed to transition:', error);
    return;
  }

  const updated = await res.json();
  console.log('Ticket now pending for:', updated.pending_reason);
}
```

### Example 4: Get Analytics (Python)

```python
import requests

TOKEN = "abc123xyz789"
BASE_URL = "http://localhost:8000/api"
HEADERS = {"Authorization": f"Token {TOKEN}"}

# Get manager dashboard (cross-campus, own department)
analytics_res = requests.get(
    f"{BASE_URL}/analytics/manager/",
    params={'days': 30},
    headers=HEADERS
)

metrics = analytics_res.json()
print(f"Department: {metrics['department']}")
print(f"Total tickets: {metrics['overview']['total_tickets']}")
for campus in metrics['campuses']:
    print(f"  {campus['campus']}: {campus['total']} tickets")
```

---

## Testing Your Integration

### Test Credentials

See [Default Credentials](DEFAULT_CREDENTIALS.md) for test accounts with different roles. All fixture users share the password `adminuser123`.

Key seed users:

| Username | Role | Campus |
|----------|------|--------|
| `admin_user` | admin | NRB |
| `manager_ict` | manager | NRB |
| `hod_ict_nrb` | hod | NRB |
| `hos_ict_nrb` | head_of_section | NRB |
| `tech_alex` | technician | NRB |
| `user_sarah` | user | NRB |
| `user_msa` | user | MSA |

---

## Next Steps

### Learn More
- **Workflow rules**: [Workflow Specification](specifications/WORKFLOW_SPEC.md)
- **System architecture**: [Architecture Guide](ARCHITECTURE_GUIDE.md)
- **Analytics details**: [Analytics Guide](api/ANALYTICS.md)

### Start Integrating
1. Use test credentials from [Default Credentials](DEFAULT_CREDENTIALS.md)
2. Try examples above in your language
3. Reference this guide during implementation
4. Check error handling section for edge cases

---

**Last Updated**: May 13, 2026  
**Version**: 2.0  
**Status**: Production Ready  
**Compliance**: See [Compliance Audit](compliance/AUDIT_STATUS.md)
