# Analytics Module

> 📌 **For complete API reference and other endpoints, see [API Integration Guide](../API_INTEGRATION_GUIDE.md)** (NEW)  
> This document provides detailed specifications for **analytics endpoints only**.

This module provides comprehensive analytics and reporting capabilities for the Django Resolver ticket management system.

## Available Analytics

### Ticket Analytics
- Daily, weekly, and monthly ticket counts
- Ticket distribution by facility and section
- Ticket status distribution
- Trend analysis for ticket creation over time

### Technician Analytics
- Performance metrics for technicians
- Tickets resolved and resolution time
- Overall rating and feedback analysis
- Section-based technician performance

### Admin Dashboard Analytics
- System-wide overview metrics
- Ticket resolution rates and response times
- Overdue ticket tracking and reporting

## API Endpoints

### `/api/analytics/tickets/`
Provides ticket-related analytics data.

**Query Parameters:**
- `timeframe`: day, week, month (default: day)
- `facility_id`: Optional facility ID to filter by
- `section_id`: Optional section ID to filter by
- `group_by`: day, week, month for trend data (default: day)
- `days`: Number of days for historical data (default: 30)

**Example Response:**
```json
{
  "ticket_counts": {
    "period": "Last 7 days",
    "count": 23
  },
  "status_counts": [
    {"status": "open", "count": 10},
    {"status": "assigned", "count": 5},
    {"status": "resolved", "count": 8}
  ],
  "trend_data": [
    {"period": "2023-10-15", "count": 3},
    {"period": "2023-10-16", "count": 5}
  ],
  "facility_distribution": [
    {"name": "Building A", "ticket_count": 15},
    {"name": "ICT Lab", "ticket_count": 8}
  ],
  "section_distribution": [
    {"name": "Plumbing", "ticket_count": 12},
    {"name": "Electrical", "ticket_count": 10}
  ]
}
```

### `/api/analytics/technicians/`
Provides technician performance analytics.

**Query Parameters:**
- `technician_id`: Optional specific technician to analyze

**Example Response:**
```json
{
  "technician_performance": [
    {
      "id": 1,
      "username": "john.doe",
      "full_name": "John Doe",
      "total_tickets": 25,
      "resolved_tickets": 20,
      "pending_tickets": 5,
      "overdue_tickets": 2,
      "avg_rating": 4.5,
      "avg_resolution_time": 8.3,
      "resolution_percentage": 80.0
    }
  ],
  "section_ratings": [
    {
      "section_name": "Electrical",
      "technician_count": 3,
      "avg_rating": 4.7
    }
  ]
}
```

### `/api/analytics/admin-dashboard/`
Provides system-wide analytics for admin dashboard.

**Example Response:**
```json
{
  "system_overview": {
    "total_tickets": 150,
    "open_tickets": 25,
    "resolved_tickets": 120,
    "resolution_rate": 80.0,
    "new_tickets_24h": 12,
    "tickets_past_week": 48,
    "tickets_past_month": 150,
    "avg_response_time_hours": 4.2
  },
  "overdue_tickets": [
    {
      "id": 1,
      "ticket_no": "TKT-000001",
      "title": "Leaking pipe in Building A",
      "status": "open",
      "section": "Plumbing",
      "facility": "Building A",
      "assigned_to": "john.doe",
      "age_hours": 48.5,
      "created_at": "2023-10-20T10:30:00Z"
    }
  ]
}
```

## Permissions

- Regular users can only access ticket analytics
- Technicians can access ticket analytics and their own performance metrics
- Managers and admins can access all analytics

## Usage in Frontend

These analytics endpoints are designed to provide data for dashboard visualizations and reporting features. You can use them with charting libraries like Chart.js, D3.js, or any other visualization tool.

## Customizing Analytics

To add new analytics:
1. Add new methods to the appropriate analytics class in `analytics.py`
2. Update the corresponding view in `analytics_views.py` to include the new data
3. Use the new data in your frontend dashboard