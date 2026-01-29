# Django Resolver Project Structure

## Overview

This document provides a comprehensive overview of the Django Resolver project structure.

## Directory Tree

```
django_resolver/
├── .env                              # Environment variables (not in git)
├── .gitignore                        # Git ignore patterns
├── .github/                          # GitHub configuration
│   └── copilot-instructions.md      # GitHub Copilot instructions
├── LICENSE                           # MIT License
├── README.md                         # Main project README
├── build.sh                          # Build script for deployment
├── db.sqlite3                        # SQLite database (development)
├── manage.py                         # Django management script
├── pytest.ini                        # Pytest configuration
├── render.yaml                       # Render.com deployment config
├── requirements.txt                  # Python dependencies
│
├── docs/                             # 📚 All Documentation
│   ├── INDEX.md                     # Documentation navigation hub
│   ├── api/                         # API documentation
│   │   ├── FRONTEND_API_GUIDE.md    # Complete API reference for frontend
│   │   └── analytics_README.md      # Analytics endpoints documentation
│   ├── architecture/                # Architecture and design documents
│   │   └── api_architecture.md      # API layered architecture details
│   └── testing/                     # Testing documentation
│       ├── README.md                # Test organization and running
│       └── SAMPLE_QUERIES.md        # 20+ Django ORM query examples
│
├── resolver/                         # 🔧 Django Project Configuration
│   ├── __init__.py
│   ├── asgi.py                      # ASGI configuration
│   ├── settings.py                  # Project settings
│   ├── urls.py                      # Root URL configuration
│   └── wsgi.py                      # WSGI configuration
│
└── tickets/                          # 🎫 Main Application
    ├── __init__.py
    ├── admin.py                     # Django admin configuration
    ├── apps.py                      # App configuration
    ├── models.py                    # Data models (CustomUser, Ticket, etc.)
    ├── serializers.py               # DRF serializers
    ├── urls.py                      # App-level URL routing
    │
    ├── api/                         # 🌐 API Layer
    │   ├── __init__.py
    │   ├── urls.py                  # API URL routing
    │   │
    │   ├── analytics/               # Analytics endpoints
    │   │   ├── __init__.py
    │   │   ├── analytics.py         # Analytics business logic
    │   │   ├── index.py             # Clean imports
    │   │   └── views.py             # Analytics API views
    │   │
    │   ├── reports/                 # Report generation
    │   │   ├── __init__.py
    │   │   ├── report_generator.py  # PDF/CSV generation logic
    │   │   └── views.py             # Report API views
    │   │
    │   ├── services/                # Business logic layer
    │   │   ├── __init__.py
    │   │   └── ticket_services.py   # Ticket operations & validations
    │   │
    │   └── views/                   # API views (presentation layer)
    │       ├── __init__.py
    │       ├── index.py             # Clean imports
    │       └── resource_views.py    # CRUD views for all resources
    │
    ├── fixtures/                    # 📦 Test Data
    │   └── tickets_initial_data.json # Sample data (118 records)
    │
    ├── migrations/                  # 🗄️ Database Migrations
    │   ├── __init__.py
    │   ├── 0001_initial.py
    │   ├── 0002_alter_facility_options_alter_section_options.py
    │   └── 0003_alter_ticket_options_ticket_ticket_updated_at_idx_and_more.py
    │
    └── tests/                       # 🧪 Test Suite
        ├── __init__.py
        ├── test_analytics.py        # Analytics endpoint tests
        ├── test_apis.py             # API endpoint tests
        ├── test_caching.py          # Caching behavior tests
        ├── test_models.py           # Model tests
        ├── test_serializers.py      # Serializer tests
        ├── test_ticket_operations.py # Ticket operation tests
        └── test_workflow.py         # Business logic workflow tests
```

## Key Organizational Principles

### 1. Documentation Organization
- All documentation is centralized in `docs/` at project root
- Organized by purpose: `api/`, `architecture/`, `testing/`
- Clear navigation via `docs/INDEX.md`

### 2. Code Architecture
- Layered architecture in `tickets/api/`
- Separation of concerns: views, services
- Domain grouping: analytics, reports as separate modules

### 3. Test Organization
- All tests in `tickets/tests/`
- Named by component: `test_models.py`, `test_apis.py`, etc.
- Test documentation in `docs/testing/`

## Module Purposes

### Root Level
- Configuration files (`requirements.txt`, `pytest.ini`, etc.)
- Main README with project overview
- Build and deployment scripts

### docs/
- Comprehensive documentation organized by topic
- Navigation hub via INDEX.md
- No code, only documentation

### resolver/
- Django project configuration
- Settings, URLs, WSGI/ASGI config
- No business logic

### tickets/
- Main application containing all business logic
- Models, serializers, admin configuration
- API layer in separate `api/` subdirectory

### tickets/api/
- Complete API implementation
- Layered architecture: views → services → models
- Modular design with analytics and reports

### tickets/tests/
- Comprehensive test suite
- Covers models, APIs, workflows
- 40+ test cases

## Import Patterns

### From External Code
```python
# Import services
from tickets.api.services.ticket_services import create_ticket, update_ticket

# Import analytics
from tickets.api.analytics.analytics import TicketAnalytics
```

### Within Module
```python
# Relative imports within same module
from .analytics import TicketAnalytics
```

## Configuration Files

### Environment (.env)
- Not in version control
- Contains secrets and environment-specific settings
- Template: `.env.example` (if created)

### Django Settings (resolver/settings.py)
- Database configuration
- Installed apps
- Middleware
- CORS settings

### Pytest (pytest.ini)
- Test discovery patterns
- Coverage settings
- Django settings module

### Render (render.yaml)
- Cloud deployment configuration
- Services and databases
- Build commands

## File Naming Conventions

### Python Files
- `snake_case.py` for all Python files
- `test_*.py` for test files
- `index.py` for clean imports

### Documentation
- `UPPERCASE_NAME.md` for major documents
- `lowercase_name.md` for specific topics
- `INDEX.md` for navigation hubs

### Directories
- `lowercase` for all directories
- Clear, descriptive names
- No abbreviations unless common (api, utils)

## Adding New Components

### New API Endpoint
1. Add service function in `tickets/api/services/`
2. Create view in `tickets/api/views/resource_views.py`
3. Add URL in `tickets/api/urls.py`
4. Write tests in `tickets/tests/test_apis.py`
5. Update `docs/api/GUIDE.md`

### New Feature Module
1. Create directory in `tickets/api/` (e.g., `notifications/`)
2. Add `__init__.py`, logic files, and views
3. Create tests in `tickets/tests/`
4. Document in `docs/architecture/`

### New Documentation
1. Place in appropriate `docs/` subdirectory
2. Update `docs/INDEX.md` navigation
3. Reference from README.md if important

## See Also

- [Documentation Index](INDEX.md) - Complete documentation navigation
- [API Layers](architecture/LAYERS.md) - Detailed architecture guide
- [README](../README.md) - Project overview and quick start
