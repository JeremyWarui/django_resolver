# Backend Filter Updates - November 16, 2025

## Summary
Updated `tickets/api/views/resource_views.py` to support new frontend filtering requirements for unassigned and overdue tickets.

## Changes Made

### File: `tickets/api/views/resource_views.py`

#### Added Imports
```python
from django.utils import timezone
from datetime import timedelta
```

#### Updated `TicketListCreateView` Class
Added custom `get_queryset()` method to handle two new query parameters:

**1. Unassigned Tickets Filter (`assigned_to__isnull`)**
- Query parameter: `?assigned_to__isnull=true`
- Filters tickets where `assigned_to` field is NULL
- Returns only tickets that haven't been assigned to any technician

**2. Overdue Tickets Filter (`is_overdue`)**
- Query parameter: `?is_overdue=true`
- Filters tickets older than 7 days in active states (open, assigned, in_progress)
- Uses Django's timezone-aware datetime for accurate calculations

## API Usage Examples

### Unassigned Tickets
```bash
# Get all unassigned open tickets
GET /api/tickets/?assigned_to__isnull=true&status=open&page=1&page_size=10

# Response (example):
{
  "count": 15,
  "next": "http://localhost:8000/api/tickets/?assigned_to__isnull=true&page=2",
  "previous": null,
  "results": [
    {
      "id": 42,
      "ticket_no": "TKT-042",
      "title": "Broken AC in Room 201",
      "status": "open",
      "assigned_to": null,
      "section": "HVAC",
      "facility": "Building A",
      "raised_by": "john_doe",
      "created_at": "2025-11-15T10:30:00Z"
    }
    // ... more tickets
  ]
}
```

### Overdue Tickets
```bash
# Get all overdue tickets
GET /api/tickets/?is_overdue=true&page=1&page_size=10

# Response (example):
{
  "count": 8,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 23,
      "ticket_no": "TKT-023",
      "title": "Leaking pipe in cafeteria",
      "status": "assigned",
      "assigned_to": {
        "id": 5,
        "username": "tech_jane",
        "first_name": "Jane",
        "last_name": "Smith"
      },
      "created_at": "2025-11-01T08:15:00Z"  // >7 days ago
    }
    // ... more tickets
  ]
}
```

### Combined Filters
```bash
# Unassigned tickets in IT section
GET /api/tickets/?assigned_to__isnull=true&section=2&status=open

# Overdue tickets assigned to specific technician
GET /api/tickets/?is_overdue=true&assigned_to=5
```

## Implementation Details

### Overdue Logic
- **Threshold**: 7 days from `created_at` timestamp
- **Eligible Statuses**: 'open', 'assigned', 'in_progress'
- **Timezone**: Uses Django's `timezone.now()` for accuracy
- **Calculation**: `created_at < (now - 7 days)`

### Query Optimization
- Filters are applied at database level using Django ORM
- Properly indexed fields (`assigned_to`, `created_at`, `status`)
- Works seamlessly with existing pagination
- Compatible with all other filters (status, section, raised_by, etc.)

## Testing

### Manual Testing
```bash
# Start Django dev server
python manage.py runserver

# Test unassigned filter
curl "http://localhost:8000/api/tickets/?assigned_to__isnull=true"

# Test overdue filter
curl "http://localhost:8000/api/tickets/?is_overdue=true"

# Test combined with pagination
curl "http://localhost:8000/api/tickets/?is_overdue=true&page=1&page_size=5"
```

### Expected Behavior
✅ Returns only tickets matching the filter criteria
✅ Pagination works correctly with filtered results
✅ Combined with other filters (status, section, etc.)
✅ Maintains performance with large datasets

## Frontend Integration

The frontend (`Resolver/client`) now automatically uses these filters when:
- User clicks "Unassigned" quick filter button
- User clicks "Overdue" quick filter button
- Quick filter counts are accurately displayed

### Frontend Request Examples
```typescript
// Unassigned tickets
const response = await ticketsService.getTickets({
  assigned_to__isnull: true,
  status: 'open',
  page: 1,
  page_size: 10
});

// Overdue tickets
const response = await ticketsService.getTickets({
  is_overdue: true,
  page: 1,
  page_size: 10
});
```

## Backward Compatibility

✅ All existing API calls continue to work unchanged
✅ New filters are optional query parameters
✅ No breaking changes to serializers or models
✅ No database migrations required

## Performance Considerations

- **Database Indexes**: Ensure `assigned_to` and `created_at` fields are indexed
- **Query Complexity**: O(log n) for indexed lookups
- **Recommended**: Add composite index for common query patterns

### Optional Index Optimization
```python
# In tickets/models.py - Ticket model
class Meta:
    indexes = [
        models.Index(fields=['assigned_to', 'status']),
        models.Index(fields=['created_at', 'status']),
    ]
```

## Deployment Notes

1. ✅ No database migrations needed
2. ✅ No environment variables required
3. ✅ Simply restart Django server to apply changes
4. ⚠️ Consider adding indexes if ticket volume is high (>10,000 tickets)

## Status

✅ **Implementation Complete**
✅ **Backend Ready**
✅ **Frontend Integrated**
🧪 **Ready for Testing**

---
**Date**: November 16, 2025
**Frontend Compatibility**: Resolver Client v0.0.0
