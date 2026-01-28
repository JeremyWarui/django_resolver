# Tickets API Module

This module contains the API layer for Django Resolver, organized using a layered architecture pattern.

## Directory Structure

```
tickets/api/
├── __init__.py
├── urls.py                          # Main API URL routing
├── analytics/                       # Analytics endpoints
│   ├── analytics.py                # Business logic for analytics
│   ├── views.py                    # API views for analytics
│   └── index.py                    # Clean imports
├── reports/                         # Report generation
│   ├── report_generator.py         # PDF/CSV generation logic
│   └── views.py                    # Report API views
├── services/                        # Business logic layer
│   └── ticket_services.py          # Ticket operations and validations
├── utils/                           # Shared utilities
│   ├── cache_utils.py              # Caching patterns and invalidation
│   ├── pagination.py               # Custom pagination classes
│   └── signals.py                  # Django signals for cache invalidation
└── views/                           # API views (presentation layer)
    ├── resource_views.py           # CRUD views for resources
    └── index.py                    # Clean imports
```

## Architecture Principles

### Layered Architecture
The API follows a strict layered architecture:

1. **Views Layer** (`views/`, `analytics/views.py`, `reports/views.py`)
   - Handles HTTP request/response
   - Delegates to services for business logic
   - Thin controllers with minimal logic

2. **Services Layer** (`services/`)
   - Contains all business logic
   - Validates status transitions
   - Enforces role permissions
   - Handles complex operations

3. **Models Layer** (in `tickets/models.py`)
   - Data schema and simple model methods
   - Helper methods for atomic operations

4. **Utilities** (`utils/`)
   - Shared functionality across layers
   - Caching, pagination, signals

### Key Architectural Rules

❌ **DON'T:**
- Put business logic in views
- Create `TicketLog` entries manually
- Modify closed tickets without checking
- Bypass services layer

✅ **DO:**
- Use services for all business logic
- Call model helper methods for status changes
- Validate permissions in services
- Cache expensive queries

## Module Details

### Analytics (`analytics/`)
- **Purpose:** Provide aggregated data for dashboards
- **Caching:** 5-10 minute TTL for heavy queries
- **Files:**
  - `analytics.py`: Data aggregation logic
  - `views.py`: API endpoints

### Reports (`reports/`)
- **Purpose:** Generate PDF and CSV reports
- **Features:** Ticket reports, technician performance
- **Files:**
  - `report_generator.py`: Report generation logic
  - `views.py`: Report download endpoints

### Services (`services/`)
- **Purpose:** Centralized business logic
- **Pattern:** Service functions called by views
- **Files:**
  - `ticket_services.py`: Ticket CRUD, validation, status transitions

### Utils (`utils/`)
- **Purpose:** Shared utilities
- **Files:**
  - `cache_utils.py`: `CacheKeyBuilder`, `CacheInvalidator`, caching decorators
  - `pagination.py`: `StandardResultsSetPagination` with metadata
  - `signals.py`: Automatic cache invalidation on model changes

### Views (`views/`)
- **Purpose:** API endpoints for resources
- **Pattern:** DRF generics for CRUD operations
- **Files:**
  - `resource_views.py`: All CRUD endpoints
  - `index.py`: Clean imports for URLs

## Common Patterns

### Adding a New Endpoint

1. **Add Service Function** (if business logic needed)
```python
# services/ticket_services.py
def my_business_logic(ticket, user):
    # Validation
    # Business rules
    # Return result
```

2. **Create View**
```python
# views/resource_views.py
class MyView(generics.ListAPIView):
    def get_queryset(self):
        # Delegate to service if needed
        return my_service_function()
```

3. **Add URL Route**
```python
# urls.py
path('my-endpoint/', MyView.as_view(), name='my-endpoint'),
```

### Adding Caching

```python
from tickets.api.utils.cache_utils import CacheKeyBuilder, get_or_set_cache

# In view
cache_key = CacheKeyBuilder.my_cache_key(param1, param2)
data = get_or_set_cache(cache_key, lambda: expensive_function(), timeout=300)
```

### Cache Invalidation

Handled automatically via signals in `utils/signals.py`. When models change, relevant caches are cleared.

## Testing

Test files mirror the structure:
- `tests/test_apis.py` - API endpoint tests
- `tests/test_workflow.py` - Business logic tests
- `tests/test_caching.py` - Caching behavior tests

## See Also

- [API Architecture Documentation](../../docs/architecture/api_architecture.md)
- [Caching Guide](../../docs/architecture/CACHING_GUIDE.md)
- [Analytics API](../../docs/api/analytics_README.md)
