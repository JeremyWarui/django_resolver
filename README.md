# Django Resolver - Ticket Management System

> **For detailed setup instructions, see [First Time Setup Guide](docs/FIRST_TIME_SETUP.md)**  
> This README provides quick start steps. The Setup Guide includes detailed troubleshooting and comprehensive explanation.

A Django REST API for managing maintenance tickets across a multi-campus organization. Built for Kenya School of Government with a 6-role access model and full ticket lifecycle management.

**Stack**: Django 6.0.3 | DRF 3.16.1 | PostgreSQL | pytest (~258 tests)

## Quick Start

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
python manage.py loaddata tickets/fixtures/tickets_initial_data.json
python manage.py createsuperuser
python manage.py runserver
```

**Access**: http://127.0.0.1:8000 | **Admin**: http://127.0.0.1:8000/admin

### Test Login Credentials

All fixture users share the password `adminuser123`:

```bash
# Regular user
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "user_sarah", "password": "adminuser123"}'

# Technician
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "tech_alex", "password": "adminuser123"}'

# Admin
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin_user", "password": "adminuser123"}'
```

See [docs/DEFAULT_CREDENTIALS.md](docs/DEFAULT_CREDENTIALS.md) for the complete list of test accounts.

## Key Features

- **Token Authentication**: Password-based login for all roles
- **Ticket Management**: Auto-numbered tickets (`CAMPUS-DEPT-XXXXX`), status workflow, assignment rules
- **Role-Based Access**: 6 roles (`user`, `technician`, `head_of_section`, `hod`, `manager`, `admin`) with granular permissions
- **Service Catalogue**: `ServiceItem`-driven ticket creation with SLA-based `due_date`
- **Advanced Filtering**: Status, section, technician, overdue, escalation level
- **Analytics**: 11 role-specific analytics endpoints
- **Audit Trail**: Complete activity logging with `TicketLog`

## API Overview

**Base**: `http://127.0.0.1:8000/api/`

### Core Endpoints

```
Tickets:          GET /tickets/                    GET/PATCH /tickets/{id}/
Ticket Create:    POST /tickets/create/            (catalogue-based, auto-resolves org structure)
Technicians:      GET /technicians/?section_id={id}
Users:            GET/POST /users/                 GET/PATCH/DELETE /users/{id}/
Facilities:       GET/POST /facilities/            GET/PATCH/DELETE /facilities/{id}/
Campuses:         GET/POST /campuses/
Departments:      GET/POST /departments/
CampusDepts:      GET/POST /campus-departments/
Sections:         GET/POST /sections/              GET/PATCH/DELETE /sections/{id}/
Comments:         GET/POST /tickets/{id}/comments/
Feedback:         GET/POST /tickets/{id}/feedback/
Analytics:        GET /analytics/tickets/          GET /analytics/manager/
                  GET /analytics/hod/              GET /analytics/section-head/
                  GET /analytics/technicians/      GET /analytics/admin-dashboard/
```

### Common Filters

```bash
# Tickets
?status=open|assigned|in_progress|pending|resolved|closed
?assigned_to__isnull=true        # Unassigned tickets
?is_overdue=true                 # Past due_date
?section_id=1                    # By section
?ordering=-updated_at            # Sort by field

# Users
?role=technician|admin|manager|user|hod|head_of_section

# Technicians (for assignment)
?section_id=1                    # Technicians in specific section
```

### Quick Examples

```bash
# Create ticket (catalogue-based — system resolves org structure)
curl -X POST http://127.0.0.1:8000/api/tickets/create/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"department_id":1,"service_item_id":5,"title":"AC Broken","description":"Room 101"}'

# Assign ticket
curl -X PATCH http://127.0.0.1:8000/api/tickets/5/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"assigned_to":3}'

# Get overdue tickets
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/tickets/?is_overdue=true"

# Weekly analytics
curl -H "Authorization: Token YOUR_TOKEN" "http://127.0.0.1:8000/api/analytics/tickets/?timeframe=week"
```

## Testing

```bash
pytest tickets/tests/                               # Run all tests
pytest tickets/tests/ --cov=tickets                 # With coverage
pytest tickets/tests/test_apis.py -v                # Specific file
pytest --create-db                                  # Rebuild test DB after migrations
```

**Test Suite**: 6 files, ~258 tests  
**Base Class**: `BaseAPITestCase` for shared fixtures and `authenticate_as(user)` helper

## Architecture

**Layered Design**: Models → Services → Views

```
tickets/
├── models/                    # Split by domain (organisation, sections, catalogue, tickets, users, facilities)
├── serializers/               # Split by domain (org, sections, catalogue, tickets, users, common)
├── admin.py
├── api/
│   ├── views/                 # Split by domain (ticket_views, org_views, technician_views, catalogue_views, user_views)
│   ├── permissions/           # Split by domain (org, tickets, users)
│   ├── services/              # ticket_service.py, technician_service.py
│   ├── analytics/             # 11 analytics endpoints
│   └── urls.py
└── tests/                     # ~258 tests across 6 files
```

**Org Hierarchy**:
```
Campus  (root — no Organization above it)
  └── CampusDepartment  (Campus + Department + HOD)
        └── Section  (CampusDepartment + SectionType + HOS)
              ├── TechnicianSection  (M2M: Technician ↔ Section)
              └── Ticket
```

**Key Patterns**:
- Business logic in `services/`, NOT views
- State machine via `validate_status_transition()` in services
- Escalation clock starts at `assigned_at` (not `created_at`)
- `manager` role: analytics-only, no direct ticket list/detail

## Documentation

**Full Documentation**: [docs/INDEX.md](docs/INDEX.md)

| Guide | Description |
|-------|-------------|
| [First Time Setup](docs/FIRST_TIME_SETUP.md) | Step-by-step local setup |
| [Architecture Guide](docs/ARCHITECTURE_GUIDE.md) | System design and patterns |
| [API Integration Guide](docs/API_INTEGRATION_GUIDE.md) | Complete endpoint reference |
| [Analytics API](docs/api/ANALYTICS.md) | Analytics query parameters and responses |
| [Workflow Spec](docs/specifications/WORKFLOW_SPEC.md) | Business rules and state machine |
| [Sample Queries](docs/testing/SAMPLE_QUERIES.md) | 20+ Django ORM examples |
| [Default Credentials](docs/DEFAULT_CREDENTIALS.md) | Test account usernames and passwords |

## Database Models

| Model | Key Features |
|-------|-------------|
| **CustomUser** | Roles: user, technician, head_of_section, hod, manager, admin |
| **Campus** | Root entity; code e.g. "NRB", "MSA" |
| **Department** | Global (not campus-scoped); code e.g. "ICT", "ADM" |
| **CampusDepartment** | Joins Campus + Department; holds HOD FK |
| **Section** | Belongs to CampusDepartment; holds HOS FK |
| **TechnicianSection** | M2M join: Technician ↔ Section |
| **ServiceCategory / ServiceItem** | Catalogue; ServiceItem drives section resolution and SLA |
| **Ticket** | Auto-numbered `CAMPUS-DEPT-XXXXX`; full status workflow |
| **Facility** | Physical asset/location for tickets |
| **Comment** | Thread-based discussions |
| **Feedback** | 1–5 star rating, one per ticket |
| **TicketLog** | Immutable audit trail |

**Status Workflow**: `open → assigned → in_progress → pending ⇄ in_progress → resolved → closed`  
Also: `pending_approval → (approve) → open` / `pending_approval → (reject) → rejected`

## Performance

- **Response times**: <100ms for most endpoints
- **Database optimization**: `select_related()`, `prefetch_related()`, composite indexes
- **Escalation**: cron-based via `python manage.py process_auto_escalations`

## Contributing

```bash
git checkout -b feature/amazing-feature
# Follow PEP 8, write tests, update docs
git commit -m 'Add amazing feature'
git push origin feature/amazing-feature
```

**Guidelines**: Business logic in services | Use `TicketService` for all ticket mutations | Inherit from `BaseAPITestCase`

## License

MIT License - see [LICENSE](LICENSE)

---

**Version**: 2.0.0 | **Status**: Production Ready | **Updated**: May 2026
