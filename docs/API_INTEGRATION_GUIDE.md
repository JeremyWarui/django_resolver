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
    "role": "technician"
  }
}

# 3. Use token in all API requests
curl http://localhost:8000/api/tickets/ \
  -H "Authorization: Token abc123xyz789..."
```

### API Base URL
- **Development**: `http://localhost:8000/api/`
- **Production**: `https://your-domain.com/api/`

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
    "role": "technician",
    "primary_campus": {
      "id": 1,
      "name": "MAIN",
      "code": "MAIN"
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

See [Authentication Details](AUTHENTICATION.md) for future implementation.

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
  "page_size": 10,
  "total_pages": 5,
  "current_page": 1,
  "results": [
    { "id": 1, "ticket_no": "MAIN-IT-00001", ... }
  ]
}
```

#### Detail Response
```json
{
  "id": 1,
  "ticket_no": "MAIN-IT-00001",
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

Default behavior: **10 items per page**

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
- `campus_id=1` - Filter by campus
- `section_id=1` - Filter by section
- `assigned_to__isnull=true` - Unassigned tickets
- `escalation_level=1` - Escalated to section head

**Multiple values**:
- `status=open&status=assigned` - OR logic

**Combined example**:
```
GET /api/tickets/?status=open&section_id=1&campus_id=1
```

### Ordering

Supported fields:
- `created_at` - Ascending: `?ordering=created_at` / Descending: `?ordering=-created_at`
- `updated_at` - By default, tickets sorted by `-updated_at` (newest first)
- `status` - Sort by status

**Example**:
```
GET /api/tickets/?ordering=-created_at&ordering=status
```

### Timestamps

All timestamps use ISO 8601 format with UTC timezone:
```
"2024-01-15T10:30:45.123456Z"
```

---

## Organizational Hierarchy Endpoints

### Organizations

#### List All Organizations
```
GET /api/organizations/
```

**Response** (truncated):
```json
{
  "count": 2,
  "results": [
    {
      "id": 1,
      "name": "Government Institution",
      "type": "government",
      "description": "Main organization"
    }
  ]
}
```

#### Create Organization (Admin only)
```
POST /api/organizations/
{
  "name": "New Organization",
  "type": "education",
  "description": "..."
}
```

#### Retrieve Organization
```
GET /api/organizations/{id}/
```

#### Update Organization (Org admin only)
```
PATCH /api/organizations/{id}/
{
  "name": "Updated name"
}
```

---

### Campuses

#### List Campuses (Filtered to User's Accessible Campuses)
```
GET /api/campuses/
```

**Filters**:
- `organization_id=1` - By organization

**Response** (truncated):
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "MAIN Campus",
      "code": "MAIN",
      "organization": 1,
      "location": "Nairobi"
    }
  ]
}
```

#### Create Campus
```
POST /api/campuses/
{
  "name": "West Campus",
  "code": "WEST",
  "organization": 1,
  "location": "Mombasa"
}
```

---

### Departments

#### List Departments (Filtered to Accessible Departments)
```
GET /api/departments/
```

**Filters**:
- `campus_id=1` - By campus
- `organization_id=1` - By organization

**Response** (truncated):
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "name": "IT Department",
      "code": "IT",
      "campus": 1,
      "head_of_department": {
        "id": 5,
        "username": "alex_smith",
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
- `department_id=1` - By department
- `campus_id=1` - By campus

**Response** (includes campus context - R1 Enhancement):
```json
{
  "count": 4,
  "results": [
    {
      "id": 1,
      "name": "Network Section",
      "code": "NETWORK",
      "department": 1,
      "campus_id": 1,
      "campus_display": "MAIN",
      "organization_id": 1,
      "section_head": {
        "id": 6,
        "username": "ben_lucas"
      }
    }
  ]
}
```

#### Create Section
```
POST /api/sections/
{
  "name": "Plumbing",
  "code": "PLUMB",
  "department": 1,
  "section_head": 10
}
```

---

## Ticket Management Endpoints

### List Tickets

#### Get All Tickets (Org-Scoped)
```
GET /api/tickets/
```

**Filters**:
- `status=open` - Filter by status: open, assigned, in_progress, pending, resolved, closed
- `campus_id=1` - Filter by campus
- `section_id=1` - Filter by section
- `assigned_to__isnull=true` - Unassigned tickets only
- `is_overdue=true` - Overdue tickets only
- `escalation_level=1` - Escalated to section head
- `escalation_level=2` - Escalated to HOD
- `priority=high` - Filter by priority: low, medium, high, critical

**Ordering**:
- Default: `-updated_at` (newest first)
- `ordering=created_at` - By creation time
- `ordering=status` - By status

**Example**:
```
GET /api/tickets/?status=open&section_id=1&escalation_level=1&ordering=-created_at
```

**Response** (list view - simplified for performance):
```json
{
  "count": 42,
  "page_size": 10,
  "total_pages": 5,
  "results": [
    {
      "id": 1,
      "ticket_no": "MAIN-IT-00001",
      "title": "Printer not working",
      "status": "open",
      "priority": "low",
      "escalation_level": 0,
      "assigned_to_name": "john_tech",
      "raised_by": {
        "username": "user_sarah"
      },
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T14:20:00Z"
    }
  ]
}
```

### Create Ticket

#### Create New Ticket
```
POST /api/tickets/
{
  "title": "Internet connection down",
  "description": "Floor 3 network not responding",
  "section": 1,
  "facility": 1,
  "priority": "medium"
}
```

**Required fields**:
- `title` - Ticket title
- `section` - Section ID where issue occurs
- `description` - Back-end requires, optional in API

**Optional fields**:
- `facility` - Facility/location
- `priority` - low, medium, high, critical (default: low)

**Response** (201 Created):
```json
{
  "id": 42,
  "ticket_no": "MAIN-IT-00042",
  "title": "Internet connection down",
  "description": "Floor 3 network not responding",
  "status": "open",
  "priority": "medium",
  "section": { "id": 1, "name": "Network" },
  "raised_by": { "id": 2, "username": "user_sarah" },
  "assigned_to": null,
  "created_at": "2024-01-15T15:00:00Z",
  "updated_at": "2024-01-15T15:00:00Z"
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
  "ticket_no": "MAIN-IT-00001",
  "title": "Printer not working",
  "description": "HP printer on floor 2",
  "status": "in_progress",
  "priority": "low",
  "escalation_level": 0,
  "pending_reason": null,
  "pending_comment": null,
  "section": {
    "id": 1,
    "name": "Network",
    "department": { "id": 1, "name": "IT" },
    "campus": { "id": 1, "name": "MAIN" }
  },
  "facility": {
    "id": 5,
    "name": "Floor 2 Printer",
    "location": "2nd Floor"
  },
  "raised_by": {
    "id": 2,
    "username": "user_sarah",
    "email": "jane@example.com"
  },
  "assigned_to": {
    "id": 10,
    "username": "tech_john",
    "role": "technician"
  },
  "available_technicians": [
    { "id": 10, "username": "tech_john" },
    { "id": 11, "username": "tech_alice" }
  ],
  "comments": [
    {
      "id": 1,
      "text": "Looking into it",
      "created_by": { "username": "tech_john" },
      "created_at": "2024-01-15T11:00:00Z"
    }
  ],
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T14:20:00Z"
}
```

### Update Ticket

#### Update Ticket Status
```
PATCH /api/tickets/{id}/
{
  "status": "in_progress"
}
```

**Valid status transitions**:
- `open` → `assigned` (auto-set when assigned_to assigned)
- `assigned` → `in_progress`
- `in_progress` → `pending` (requires pending_reason + pending_comment)
- `in_progress` → `resolved`
- `resolved` → `closed` (Admin/User only, see "Close Ticket")
- `pending` ↔ `in_progress` (cycle)

#### Update Ticket with Assignment
```
PATCH /api/tickets/{id}/
{
  "assigned_to": 10
}
```

**Assignment rules**:
- Only technicians can be assigned
- Technician must have ticket's section in their sections M2M

#### Transition to Pending Status
```
PATCH /api/tickets/{id}/
{
  "status": "pending",
  "pending_reason": "Waiting for user information",
  "pending_comment": "User hasn't responded to question about error code"
}
```

**Requirement**: Both `pending_reason` and `pending_comment` required for pending status

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

**Response** (200 OK):
```json
{
  "id": 1,
  "status": "closed",
  "closed_by": { "id": 2, "username": "user_sarah" },
  "closed_at": "2024-01-15T17:00:00Z",
  "updated_at": "2024-01-15T17:00:00Z"
}
```

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

**Permissions**:
- Any user in org scope can escalate
- Closed tickets cannot be escalated

**Response** (200 OK):
```json
{
  "id": 1,
  "escalation_level": 1,
  "escalated_to": {
    "id": 6,
    "username": "section_head_ben",
    "role": "head_of_section"
  },
  "escalation_reason": "No response from technician",
  "escalated_at": "2024-01-15T16:30:00Z",
  "priority": "medium"
}
```

### Auto-Escalation Query

#### Get Tickets Pending Auto-Escalation
```
GET /api/tickets/?next_escalation_due__lte={date}
```

**Example**:
```
GET /api/tickets/?next_escalation_due__lte=2024-01-15T18:00:00Z
```

**Response**: Lists tickets due for automatic escalation

---

## User Management Endpoints

### List Users (Org-Scoped)
```
GET /api/users/
```

**Filters**:
- `role=technician` - By role
- `campus_id=1` - By campus

**Response** (truncated):
```json
{
  "count": 15,
  "results": [
    {
      "id": 10,
      "username": "tech_john",
      "email": "john@example.com",
      "role": "technician",
      "primary_campus": { "id": 1, "name": "MAIN" }
    }
  ]
}
```

### Get Technicians by Section

#### Get Available Technicians for Assignment
```
GET /api/technicians/?section_id=1&campus_id=1
```

**Returns**: Only technicians in the specified section and campus

**Response**:
```json
{
  "count": 3,
  "results": [
    { "id": 10, "username": "tech_john" },
    { "id": 11, "username": "tech_alice" },
    { "id": 12, "username": "tech_bob" }
  ]
}
```

### Get Assignable Users
```
GET /api/assignable-users/?section_id=1
```

**Returns**: Users who can be assigned to tickets in this section

**Response**: Same format as technicians endpoint

---

## Analytics Endpoints

### Ticket Analytics

#### Get Ticket Metrics
```
GET /api/analytics/tickets/
```

**Query parameters**:
- `timeframe=week` - day, week, month, custom
- `campus_id=1` - Filter by campus
- `section_id=1` - Filter by section
- `facility_id=1` - Filter by facility
- `days=30` - Custom days (with timeframe=custom)
- `group_by=day` - Group by: day, week, month, section, technician

**Response**:
```json
{
  "total_tickets": 156,
  "open_tickets": 23,
  "closed_tickets": 89,
  "average_resolution_time": "4.2 hours",
  "resolution_rate": 85.5,
  "trend": [
    {
      "period": "2024-01-15",
      "created": 5,
      "resolved": 3,
      "open": 22
    }
  ],
  "by_status": {
    "open": 23,
    "assigned": 15,
    "in_progress": 18,
    "pending": 2,
    "resolved": 89,
    "closed": 9
  },
  "by_priority": {
    "low": 45,
    "medium": 78,
    "high": 28,
    "critical": 5
  }
}
```

### Technician Analytics

#### Get Technician Performance Metrics
```
GET /api/analytics/technicians/
```

**Query parameters**:
- `technician_id=10` - Specific technician (required or returns all)
- `campus_id=1` - Filter by campus
- `days=30` - Time period

**Response**:
```json
{
  "technician": { "id": 10, "username": "tech_john" },
  "total_assigned": 34,
  "total_closed": 28,
  "closure_rate": 82.4,
  "average_resolution_time": "3.5 hours",
  "pending_tickets": 6,
  "escalated_tickets": 2,
  "workload": [
    {
      "department": "IT",
      "section": "Network",
      "assigned": 15,
      "closed": 12
    }
  ]
}
```

### Manager Dashboard (Analytics-Only Role)

#### Get Manager Dashboard (Managers/Admins only)
```
GET /api/analytics/manager/
```

**Query parameters**:
- `days=30` - Time period

**Response** (own department across all org campuses):
```json
{
  "department": "ICT",
  "organization": "Kenya School of Government",
  "overview": {
    "total_tickets": 342,
    "open_tickets": 47,
    "closure_rate": 86.2,
    "average_response_time": "2.1 hours"
  },
  "campuses": [
    {
      "campus": "NRB",
      "total": 156,
      "open": 23,
      "closure_rate": 85.5
    }
  ],
  "escalation_trend": [
    { "date": "2024-01-15", "level_1": 3, "level_2": 1 }
  ],
  "sla_compliance": 92.3
}
```

### HOD Dashboard

#### Get HOD Dashboard (HODs/Admins only)
```
GET /api/analytics/hod/
```

**Response**: Campus-level metrics for own department

### Section Head Dashboard

#### Get Section Head Dashboard (Section Heads/Admins only)
```
GET /api/analytics/section-head/
```

**Response**: Section-specific metrics

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

**Response** (201 Created):
```json
{
  "id": 15,
  "ticket": 1,
  "text": "Looking into issue, will update shortly",
  "created_by": { "id": 10, "username": "tech_john" },
  "created_at": "2024-01-15T11:00:00Z"
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

**Response** (201 Created):
```json
{
  "id": 8,
  "ticket": 1,
  "rating": 5,
  "comment": "Technician was very helpful",
  "submitted_by": { "id": 2, "username": "user_sarah" },
  "created_at": "2024-01-15T17:30:00Z"
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
    "assigned_to": ["Technician must have this section in their assignments"]
  }
}
```

**Cross-org access attempt**:
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

# 2. Get available technicians
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
from datetime import datetime, timedelta

TOKEN = "abc123xyz789"
BASE_URL = "http://localhost:8000/api"
HEADERS = {"Authorization": f"Token {TOKEN}"}

# Get ticket metrics for last 7 days
start_date = (datetime.now() - timedelta(days=7)).isoformat()

analytics_res = requests.get(
    f"{BASE_URL}/analytics/tickets/",
    params={
        'timeframe': 'week',
        'campus_id': 1,
        'group_by': 'day'
    },
    headers=HEADERS
)

metrics = analytics_res.json()
print(f"Total tickets: {metrics['total_tickets']}")
print(f"Resolution rate: {metrics['resolution_rate']}%")
print(f"Trends: {metrics['trend']}")
```

---

## Testing Your Integration

### Postman Collection

Import the HTTP requests from [test-requests.http](api/test-requests.http):

1. Open Postman
2. Import the HTTP file (File → Import)
3. Set `baseUrl` variable to `http://localhost:8000/api`
4. Set `token` variable after login request
5. Run requests from the collection

### Test Credentials

See [Default Credentials](DEFAULT_CREDENTIALS.md) for 20+ test accounts with different roles.

---

## Next Steps

### Learn More
- **Workflow rules**: [Workflow Specification](specifications/WORKFLOW_SPEC.md)
- **System architecture**: [Architecture Guide](ARCHITECTURE_GUIDE.md)
- **All endpoints documented in this guide**
- **Analytics details**: [Analytics Guide](api/ANALYTICS.md)

### Start Integrating
1. Use test credentials from [Default Credentials](DEFAULT_CREDENTIALS.md)
2. Try examples above in your language
3. Reference this guide during implementation
4. Check error handling section for edge cases

---

**Last Updated**: March 18, 2026  
**Version**: 1.0  
**Status**: Production Ready  
**Compliance**: ✅ 96% (See [Compliance Audit](compliance/AUDIT_STATUS.md))
