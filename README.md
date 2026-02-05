# Django Resolver - Ticket Management System

A Django REST API for managing maintenance tickets, facilities, and user feedback. Designed for organizations with up to 100 users.

**Stack**: Django 5.2.7 | DRF 3.16.1 | PostgreSQL | pytest (89 tests, 86% coverage)

## 🚀 Quick Start

```bash
# Setup
git clone <repository-url> && cd django_resolver
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure .env
DATABASE_URL=postgresql://user:password@localhost:5432/django_resolver
SECRET_KEY=your-secret-key
DEBUG=True

# Initialize
python manage.py migrate
python manage.py loaddata tickets/fixtures/tickets_initial_data.json  # 118 sample records
python manage.py createsuperuser
python manage.py runserver
```

**Access**: http://127.0.0.1:8000 | **Admin**: http://127.0.0.1:8000/admin

### 🔐 Test Login Credentials
Test accounts have unique passwords from fixtures:

```bash
# Regular user
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "jane_user", "password": "janedoe123"}'

# Technician
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "tech_alex", "password": "alexsmith123"}'

# Admin
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_user", "password": "adminuser123"}'
```

See [docs/DEFAULT_CREDENTIALS.md](docs/DEFAULT_CREDENTIALS.md) for complete list of test accounts.

## ✨ Key Features

- **Token Authentication**: Password-based login for all roles (magic link code available but commented out)
- **Ticket Management**: Auto-numbered tickets (TKT-XXXXXX), status workflow, assignment rules
- **Role-Based Access**: User | Admin | Technician | Manager with granular permissions
- **Advanced Filtering**: Status, facility, section, technician, overdue (>7 days)
- **Analytics**: Ticket trends, technician performance, system metrics
- **Reports**: PDF/CSV generation for tickets and analytics
- **Audit Trail**: Complete activity logging with `TicketLog`

## 📡 API Overview

**Base**: `http://127.0.0.1:8000/api/`

### Core Endpoints

```
Tickets:      GET/POST /tickets/          GET/PATCH/DELETE /tickets/{id}/
Technicians:  GET /technicians/?section_id={id}
Users:        GET/POST /users/            GET/PATCH/DELETE /users/{id}/
Facilities:   GET/POST /facilities/       GET/PATCH/DELETE /facilities/{id}/
Sections:     GET/POST /sections/         GET/PATCH/DELETE /sections/{id}/
Comments:     GET/POST /tickets/{id}/comments/
Feedback:     GET/POST /tickets/{id}/feedback/
Analytics:    GET /analytics/tickets/     GET /analytics/technicians/
              GET /analytics/admin-dashboard/
Reports:      GET /reports/types/         GET /reports/generate/
```

### Common Filters

```bash
# Tickets
?status=open|assigned|in_progress|pending|resolved|closed
?assigned_to__isnull=true        # Unassigned tickets
?is_overdue=true                 # Tickets >7 days old
?section=1&facility=1            # By location
?ordering=-updated_at            # Sort by field

# Users
?role=technician|admin|manager|user

# Technicians (for assignment)
?section_id=1                    # Technicians in specific section
```

### Quick Examples

```bash
# Create ticket
curl -X POST http://127.0.0.1:8000/api/tickets/ -H "Content-Type: application/json" \
  -d '{"title":"AC Broken","description":"Room 101","section_id":1,"facility_id":1}'

# Assign ticket
curl -X PATCH http://127.0.0.1:8000/api/tickets/5/ -H "Content-Type: application/json" \
  -d '{"assigned_to_id":3,"status":"assigned"}'

# Get overdue tickets
curl "http://127.0.0.1:8000/api/tickets/?is_overdue=true"

# Weekly analytics
curl "http://127.0.0.1:8000/api/analytics/tickets/?timeframe=week"
```

## 🧪 Testing

```bash
pytest tickets/tests/                               # Run all tests
pytest tickets/tests/ --cov=tickets                 # With coverage
pytest tickets/tests/test_apis.py::APITests -v     # Specific tests
```

**Test Suite**: 6 files, 89 tests, 86% coverage  
**Base Class**: `BaseTicketTestCase` for shared fixtures

## 🏗️ Architecture

**Layered Design**: Models → Services → Views

```
tickets/
├── models.py                  # 7 models (CustomUser, Ticket, Facility, etc.)
├── serializers.py             # 7 DRF serializers
├── api/
│   ├── views/resource_views.py    # CRUD endpoints
│   ├── services/ticket_services.py # Business logic
│   ├── analytics/              # Metrics & reporting
│   └── reports/                # PDF/CSV generation
└── tests/                      # 89 tests with BaseTicketTestCase
```

**Key Patterns**:
- Business logic in `services/`, NOT views
- Atomic state changes via model helpers (`change_status`, `change_assignment`)
- Single composite DB index: `(status, -updated_at)` for 66x query speedup

## 📚 Documentation

**Full Documentation**: [docs/INDEX.md](docs/INDEX.md)

| Guide | Description |
|-------|-------------|
| [Authentication](docs/AUTHENTICATION.md) | Token-based auth, login/logout, test credentials |
| [Default Credentials](docs/DEFAULT_CREDENTIALS.md) | Test account usernames and passwords |
| [API Reference](docs/api/GUIDE.md) | Complete endpoint documentation with examples |
| [Analytics API](docs/api/ANALYTICS.md) | Query parameters and response schemas |
| [Testing Guide](docs/testing/TESTING.md) | Running tests, BaseTicketTestCase usage |
| [Sample Queries](docs/testing/SAMPLE_QUERIES.md) | 20+ Django ORM examples |
| [Architecture](docs/architecture/LAYERS.md) | Layered architecture details |

## 🗄️ Database Models

| Model | Key Features |
|-------|-------------|
| **CustomUser** | Roles: user, admin, technician, manager. Auto-generated usernames |
| **Ticket** | Auto-numbered (TKT-XXXXXX), status workflow, composite index |
| **Facility** | Building, ICT, laundry, kitchen, residential types |
| **Section** | IT, Plumbing, Electrical, HVAC, etc. Linked to technicians |
| **Comment** | Thread-based discussions, blocked on closed tickets |
| **Feedback** | 1-5 star rating, one per ticket, resolved tickets only |
| **TicketLog** | Audit trail with automatic creation via model helpers |

**Status Workflow**: `open → assigned → in_progress → pending ⇄ resolved → closed`

## 🎯 Design Decisions

**Why PostgreSQL?** Superior indexing, concurrency, production-ready  
**Why no caching?** 100-user scale doesn't need it (~0.07s queries with proper indexing)  
**Why single index?** Composite `(status, -updated_at)` covers most common query pattern  
**Why layered architecture?** Testable business logic, clear separation of concerns

## 🚀 Performance

- **Response times**: <100ms for most endpoints
- **Database optimization**: `select_related()`, `prefetch_related()`, composite index
- **Query speedup**: 66x faster (4.7s → 0.07s) with index
- **Test execution**: ~30s for 89 tests using `setUpTestData()`

## 🤝 Contributing

```bash
git checkout -b feature/amazing-feature
# Follow PEP 8, write tests (85%+ coverage), update docs
git commit -m 'Add amazing feature'
git push origin feature/amazing-feature
```

**Guidelines**: Business logic in services | Use model helpers for state changes | Inherit from `BaseTicketTestCase`

## 📄 License

MIT License - see [LICENSE](LICENSE)

---

**Version**: 1.0.0 | **Status**: Production Ready (≤100 users) | **Updated**: January 2026
