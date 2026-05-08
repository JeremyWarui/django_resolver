# Analytics Module

> 📌 **For complete API reference and other endpoints, see [API Integration Guide](../API_INTEGRATION_GUIDE.md)**  
> This document provides detailed specifications for **analytics endpoints only**.

This module provides comprehensive organization-scoped analytics and reporting for the Django Resolver ticket management system. All analytics respect organizational hierarchy (Organization → Campus → Department → Section) and role-based permissions.

## Available Analytics

### Ticket Analytics (Organization-Scoped)
- Daily, weekly, and monthly ticket counts within accessible organization units
- Ticket distribution by campus, department, and section
- Ticket status distribution with historical trends
- SLA compliance tracking and escalation analysis
- Overdue ticket identification

### Technician Analytics (Department & Section-Scoped)
- Performance metrics for technicians within accessible scope
- Tickets resolved, resolution time, and rating analysis
- Workload distribution across technicians
- Performance comparison by section
- Escalation contribution tracking

### Role-Based Dashboard Endpoints

- **`/api/analytics/manager/`**: Cross-campus department dashboard for managers
- **`/api/analytics/hod/`**: Campus-scoped dashboard for Heads of Department
- **`/api/analytics/section-head/`**: Section-scoped dashboard for Section Heads
- **`/api/analytics/admin-dashboard/`**: System-wide dashboard for admins

## API Endpoints

### `/api/analytics/tickets/`
Provides ticket-related analytics data with organizational filtering.

**Query Parameters:**
- `timeframe`: `day`, `week`, `month` (default: `week`)
- `campus_id`: Filter by campus (org-scoped)
- `department_id`: Filter by department (org-scoped)
- `section_id`: Filter by section (org-scoped)
- `facility_id`: Filter by facility (org-scoped)
- `group_by`: `day`, `week`, `month` for trend data (default: `day`)
- `days`: Number of days for historical data (default: 30)

**Access Control:**
- Users: Own tickets only
- Technicians: Section-scoped tickets
- Section Heads: Section-scoped tickets
- HODs: Campus-scoped tickets
- Managers: Own department across all campuses in their org
- Admins: All tickets

**Example Request:**
```bash
GET /api/analytics/tickets/?timeframe=week&campus_id=1&section_id=2
```

**Example Response:**
```json
{
  "organization": "Kenya School of Government",
  "campus": "Nairobi Campus",
  "period": "Last 7 days",
  "ticket_counts": {
    "total": 45,
    "open": 12,
    "assigned": 8,
    "in_progress": 15,
    "resolved": 10,
    "pending": 0
  },
  "escalation_metrics": {
    "level_0": 12,
    "level_1": 8,
    "level_2": 5,
    "auto_escalated": 3,
    "manual_escalated": 5
  },
  "sla_compliance": {
    "compliant_tickets": 38,
    "breached_tickets": 7,
    "compliance_percentage": 84.4
  },
  "trend_data": [
    {"date": "2026-04-03", "count": 6, "escalated": 1},
    {"date": "2026-04-04", "count": 7, "escalated": 2}
  ],
  "section_distribution": [
    {"name": "Software", "count": 18, "avg_resolution_time": 12.5},
    {"name": "Hardware", "count": 15, "avg_resolution_time": 14.2},
    {"name": "Network", "count": 12, "avg_resolution_time": 10.8}
  ],
  "facility_distribution": [
    {"name": "Server Room A", "count": 25, "escalation_rate": 15},
    {"name": "Computer Lab 1", "count": 12, "escalation_rate": 20}
  ]
}
```

### `/api/analytics/technicians/`
Provides technician performance analytics within organizational scope.

**Query Parameters:**
- `technician_id`: Optional specific technician ID
- `campus_id`: Filter by campus
- `section_id`: Filter by section
- `days`: Number of days for analysis (default: 30)

**Access Control:**
- Technicians: Own metrics only
- Section Heads: Section technicians
- HODs: Campus technicians
- Managers: Own department technicians across all campuses
- Admins: All technicians

**Example Request:**
```bash
GET /api/analytics/technicians/?campus_id=1&days=30
```

**Example Response:**
```json
{
  "organization": "Kenya School of Government",
  "campus": "Nairobi Campus",
  "period": "Last 30 days",
  "technician_performance": [
    {
      "id": 12,
      "username": "tech_alex",
      "full_name": "Alex Kamau",
      "section": "Software",
      "total_tickets": 25,
      "resolved_tickets": 22,
      "pending_tickets": 3,
      "overdue_tickets": 1,
      "avg_rating": 4.6,
      "avg_resolution_time_hours": 8.3,
      "resolution_percentage": 88.0,
      "escalation_count": 2,
      "escalation_rate": 8.0
    }
  ],
  "section_rankings": [
    {
      "section_name": "Software",
      "technician_count": 3,
      "avg_rating": 4.5,
      "avg_resolution_time": 12.0
    },
    {
      "section_name": "Hardware",
      "technician_count": 2,
      "avg_rating": 4.4,
      "avg_resolution_time": 14.2
    }
  ]
}
```

### Role-Based Dashboard Endpoints

#### `/api/analytics/manager/`
Cross-campus department dashboard for managers (own department, all campuses in org).

**Query Parameters:**
- `days`: Number of days to analyze (default: 30)

**Access Control:** Managers (for their department) and admins

**Note:** Requires `primary_department` set on the manager user. Returns the same department code across every campus in the organization.

**Example Response:**
```json
{
  "department": "ICT",
  "organization": "Kenya School of Government",
  "period": "Last 30 days",
  "overview": {
    "total_tickets": 450,
    "open_tickets": 85,
    "escalated_tickets": 12,
    "overdue_tickets": 4,
    "resolution_rate": 82.0,
    "avg_resolution_time": 9.2
  },
  "campuses": [
    {
      "name": "Nairobi Campus",
      "ticket_count": 250,
      "open": 45,
      "escalated": 6,
      "avg_rating": 4.5
    },
    {
      "name": "Mombasa Campus",
      "ticket_count": 200,
      "open": 40,
      "escalated": 6,
      "avg_rating": 4.4
    }
  ],
  "sla_compliance": {
    "compliant": 412,
    "breached": 38,
    "compliance_percentage": 91.6
  },
  "top_technicians": [
    {"name": "Alex Kamau", "section": "Software", "rating": 4.8, "tickets_resolved": 22}
  ]
}
```

#### `/api/analytics/hod/`
Campus-scoped dashboard for Heads of Department (own department on own campus).

**Query Parameters:**
- `days`: Number of days to analyze (default: 30)

**Access Control:** HODs (for their campus) and admins

**Example Response:**
```json
{
  "organization": "Kenya School of Government",
  "campus": "Nairobi Campus",
  "departments": [
    {
      "name": "ICT",
      "ticket_count": 120,
      "open": 25,
      "escalated": 3,
      "avg_rating": 4.6,
      "sections": [
        {"name": "Network", "ticket_count": 60, "technician_count": 3},
        {"name": "Hardware", "ticket_count": 40, "technician_count": 2},
        {"name": "Software", "ticket_count": 20, "technician_count": 1}
      ],
      "escalation_points": [
        {"name": "Network", "escalations": 2},
        {"name": "Hardware", "escalations": 1}
      ]
    }
  ],
  "sla_compliance": {
    "compliant": 105,
    "breached": 15,
    "compliance_percentage": 87.5
  },
  "department_performance": {
    "avg_resolution_time": 10.5,
    "resolution_rate": 81.0,
    "technician_count": 6
  }
}
```

#### `/api/analytics/section-head/`
Section-scoped dashboard for Section Heads.

**Query Parameters:**
- `days`: Number of days to analyze (default: 30)

**Access Control:** Section Heads (for their section) and admins

**Example Response:**
```json
{
  "organization": "Kenya School of Government",
  "campus": "Nairobi Campus",
  "department": "ICT",
  "sections": [
    {
      "name": "Software",
      "ticket_count": 60,
      "open": 12,
      "escalated": 2,
      "technician_count": 3,
      "avg_rating": 4.7,
      "avg_resolution_time": 8.2
    }
  ],
  "technician_workload": [
    {
      "name": "Alex Kamau",
      "total_tickets": 22,
      "open": 4,
      "overdue": 0,
      "avg_rating": 4.8
    }
  ],
  "escalation_tracking": {
    "level_1_escalations": 5,
    "to_hod_escalations": 1,
    "resolved_at_section": 54
  }
}
```

### `/api/analytics/admin-dashboard/`
System-wide analytics for admin oversight.

**Access Control:** Admins only

**Example Response:**
```json
{
  "system_overview": {
    "total_organizations": 1,
    "total_tickets": 1250,
    "open_tickets": 180,
    "escalated_tickets": 42,
    "overdue_tickets": 15,
    "resolution_rate": 81.6,
    "avg_response_time_hours": 9.8,
    "total_technicians": 48
  },
  "campuses": [
    {
      "name": "Nairobi Campus",
      "ticket_count": 450,
      "resolution_rate": 82.0,
      "escalation_rate": 2.7,
      "sla_compliance": 91.6
    },
    {
      "name": "Mombasa Campus",
      "ticket_count": 350,
      "resolution_rate": 80.0,
      "escalation_rate": 3.1,
      "sla_compliance": 89.2
    }
  ],
  "top_performers": [
    {
      "campus": "Nairobi Campus",
      "technician": "Alex Kamau",
      "rating": 4.8,
      "tickets": 22
    }
  ],
  "sla_trends": {
    "trend": "improving",
    "change_percentage": 2.1,
    "overall_compliance": 91.1
  }
}
```

## Permissions & Organizational Scope

| Role | Accessible Scope | Analytics Access |
|------|------------------|------------------|
| `user` | Own tickets | Ticket analytics (personal only) |
| `technician` | Section tickets | Ticket analytics, own performance |
| `head_of_section` | Section tickets | Section analytics, technician performance |
| `hod` | Campus tickets | Campus analytics, technician performance |
| `manager` | Own department, all campuses in org | Manager dashboard (no ticket list/detail) |
| `admin` | All | System dashboard |

## Usage in Frontend

These analytics endpoints are designed to provide data for dashboard visualizations and reporting features. Recommended integrations:

- **Chart.js**: Time-series trends, status distributions, comparative metrics
- **D3.js**: Complex hierarchies and flow visualization
- **Ag-Grid**: Technician performance tables with sorting/filtering

**Example Frontend Usage:**
```javascript
// Get manager dashboard for their department across all campuses
fetch('/api/analytics/manager/?days=30', {
  headers: {'Authorization': `Token ${token}`}
})
.then(r => r.json())
.then(data => {
  // data.overview - key metrics
  // data.campuses - per-campus breakdown
  // data.sla_compliance - compliance tracking
  // data.top_technicians - technician rankings
})
```

## Customizing Analytics

To add new analytics:

1. **Add method to the appropriate analytics class** in [tickets/api/analytics/](../../tickets/api/analytics/):
   - `TicketAnalytics` (`ticket_analytics.py`): Ticket-specific metrics
   - `TechnicianAnalytics` (`technician_analytics.py`): Technician performance
   - `ManagerAnalytics` (`manager_analytics.py`): Manager cross-campus dashboard
   - `HODAnalytics` (`hod_analytics.py`): HOD campus dashboard
   - `SectionHeadAnalytics` (`section_head_analytics.py`): Section head dashboard
   - `AdminAnalytics` (`admin_analytics.py`): System-wide oversight

2. **Ensure organizational scope** using user's accessible boundaries:
   - Check `user.primary_department` / `user.primary_campus`
   - Filter by `user.get_accessible_campuses()`
   - Validate resource ownership via `TicketService` helpers

3. **Update the view** in [tickets/api/analytics/views.py](../../tickets/api/analytics/views.py) — subclass `RoleBasedDashboardView` and set `analytics_method = staticmethod(YourClass.your_method)`

4. **Add a URL pattern** in [tickets/api/urls.py](../../tickets/api/urls.py)

5. **Add tests** to [tickets/tests/test_analytics.py](../../tickets/tests/)

## Examples

### Get ticket analytics for specific section
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/analytics/tickets/?section_id=1&timeframe=week"
```

### Get technician performance for campus
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/analytics/technicians/?campus_id=1&days=30"
```

### Get manager dashboard (cross-campus, own department)
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/analytics/manager/?days=30"
```

### Get HOD dashboard (campus-scoped)
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/analytics/hod/?days=30"
```

### Get section head dashboard (section-scoped)
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/api/analytics/section-head/?days=30"
```
