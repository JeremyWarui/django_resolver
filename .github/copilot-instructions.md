# Copilot Instructions for Django Resolver

## Project Overview
- **Django Resolver** is a Django REST API for managing maintenance tickets, facilities, and user feedback, with role-based access and analytics.
- The main app is `tickets/`, with API logic in `tickets/api/` and analytics in `tickets/api/analytics/`.

## Architecture & Patterns
- **Separation of Concerns:**
  - **Models:** Data schema in `tickets/models.py`.
  - **Serializers:** DRF serializers in `tickets/serializers.py`.
  - **Views:** API endpoints in `tickets/api/views/` (CRUD in `resource_views.py`, analytics in `analytics/views.py`).
  - **Services:** Business logic in `tickets/api/services/` (e.g., `ticket_services.py`).
  - **Analytics:** Reporting logic in `tickets/api/analytics/`.
- **Pagination:** Use custom classes in `tickets/api/pagination.py` for consistent API responses.
- **Index files:** Use `index.py` for cleaner imports in submodules.
- **Business logic belongs in services, not views.**

## Developer Workflows
- **Setup:**
  1. Create `.env` in project root (see `README.md` for keys).
  2. Install dependencies: `pip install -r requirements.txt`
  3. Migrate DB: `python manage.py migrate`
  4. Create superuser: `python manage.py createsuperuser`
  5. (Optional) Load sample data: `python manage.py loaddata tickets/fixtures/tickets_initial_data.json`
- **Run server:** `python manage.py runserver`
- **Run tests:**
  - All: `python manage.py test tickets`
  - Specific: `python manage.py test tickets.tests.test_apis`
  - See `tickets/tests/README.md` for more.
- **Sample Data:** 118 records across all models in `tickets/fixtures/` - see `tickets/fixtures/README.md`

## API & Data Flows
- **Resource endpoints:** `/api/tickets/`, `/api/facilities/`, `/api/sections/`, etc.
- **Analytics endpoints:** `/api/analytics/tickets/`, `/api/analytics/technicians/`, `/api/analytics/admin-dashboard/`
- **Query params:** Analytics endpoints accept `timeframe`, `facility_id`, `section_id`, `technician_id`, `group_by`, `days`.
- **Ticket numbers:** Auto-generated as `TKT-XXXXXX`.
- **Role-based access:** User, Admin, Technician, Manager (see `CustomUser` model).

## Conventions & Practices
- **Follow PEP 8.**
- **Tests:** Place in `tickets/tests/`, grouped by type (models, serializers, apis, workflow).
- **Add new logic in the correct layer:** Models, serializers, services, or views.
- **Use DRF generics for CRUD, custom views for analytics.**
- **Document new endpoints and logic in the relevant `README.md` or docs.**

## Key Files & Directories
- `tickets/api/README.md`: API structure and best practices
- `tickets/docs/analytics_README.md`: Analytics module and endpoints
- `tickets/tests/README.md`: Test structure and commands
- `README.md`: Project overview, setup, and API docs

---
For more, see the above docs or ask for examples from the codebase.
