# Testing Guide

[← Back to Index](../INDEX.md) | [Sample Queries →](SAMPLE_QUERIES.md)

---

## Overview

The test suite covers the full application stack: ticket workflow, role-based permissions,
organisational scoping, and analytics. All tests use `pytest-django` with shared fixtures
defined in `conftest.py`.

**Total:** ~258 tests across 6 test files.

---

## Running Tests

```bash
# Full suite
pytest

# Single file
pytest tickets/tests/test_views_permissions.py -v

# Single test
pytest tickets/tests/test_apis.py::test_technician_status_progression -v

# Rebuild test DB after schema changes
pytest --create-db

# Coverage HTML report
pytest --cov=tickets --cov-report=html
```

---

## Test Files

### `test_views_permissions.py` — 55 tests
CRUD operations and role-based access control across all resource endpoints.

| Class | What it covers |
|-------|---------------|
| `TestTicketCreateEndpoint` | Ticket creation via `/tickets/create/` — org routing, service catalogue, approval flow |
| `TestTicketListScoping` | Each role sees only their scoped tickets on `GET /tickets/` |
| `TestTicketDetailPermissions` | Object-level read/write permissions per role |
| `TestCampusCRUD` | Campus create/list/update — admin-only writes, scoped reads |
| `TestDepartmentCRUD` | Department create/list/delete — admin-only writes |
| `TestCampusDepartmentCRUD` | CampusDepartment create and HOD assignment |
| `TestSectionCRUD` | Section create/list/assign-HOS |
| `TestServiceCatalogueCRUD` | ServiceCategory and ServiceItem admin CRUD |
| `TestTechnicianManagement` | Assign/remove technicians from sections |

---

### `test_apis.py` — 23 tests
Complex multi-step workflow and integration scenarios.

| Area | What it covers |
|------|---------------|
| Status transitions | Valid and invalid ticket state changes |
| Comments | Add/view comments, closed-ticket blocking |
| Feedback | Submit feedback, unresolved-ticket blocking |
| Bulk updates | `POST /tickets/bulk-status-update/` — auth, validation, success |
| Assignment | Multi-section technicians, duplicate assignment, unassignment |
| Technicians by section | `GET /users/technicians/?section_id=` |

---

### `test_ticket_workflow_e2e.py` — 26 tests
End-to-end ticket lifecycle — each test class covers one stage of the workflow.

| Stage | Class | Tests |
|-------|-------|-------|
| 1 – Creation & Routing | `TestTicketCreationAndRouting` | POST to `/tickets/create/`, org structure auto-resolution |
| 2 – Approval | `TestTicketApprovalAndRouting` | HOD approve/reject `pending_approval` tickets |
| 3 – Assignment | `TestTicketAssignmentConstraints` | Campus/section/role constraints on who can be assigned |
| 4 – Technician work | `TestTechnicianWorkflow` | `assigned → in_progress → pending → in_progress` |
| 5 – Resolution | `TestTicketResolution` | Resolve, immutability, feedback |
| 6 – Closure | `TestTicketClosure` | Close, unresolved-close block, closed-modify block |
| E2E | `TestCompleteTicketLifecycle` | Full lifecycle including approval-required path |

---

### `test_analytics_permissions.py` — 77 tests
Role-based access control for all 11 analytics endpoints.

Every endpoint is tested against every role. Expects `200` for authorised roles and
`403`/`401` for all others.

| Endpoint | Authorised roles |
|----------|-----------------|
| `GET /analytics/tickets/` | admin, manager |
| `GET /analytics/admin-dashboard/` | admin, manager |
| `GET /analytics/user/` | all authenticated |
| `GET /analytics/technicians/` | admin, manager, hod, technician |
| `GET /analytics/technicians/me/` | technician, admin |
| `GET /analytics/manager/` | manager, admin |
| `GET /analytics/hod/` | hod, admin |
| `GET /analytics/section-head/` | head_of_section, admin |
| `GET /analytics/departments/<pk>/` | admin, manager (own dept), hod (own campus) |
| `GET /analytics/campus-departments/<pk>/` | admin, manager (own dept), hod (assigned) |
| `GET /analytics/sections/<pk>/` | admin, manager, hod, head_of_section (own) |

---

### `test_analytics_aggregation.py` — 45 tests
Data correctness: response structure, metric calculations, query-param filtering.

| Class | What it covers |
|-------|---------------|
| `TestTicketAnalyticsAggregation` | Status breakdown, facility/section distribution, `?days=` filter |
| `TestAdminDashboardAggregation` | system_overview, overdue_tickets, organisation breakdown (admin only) |
| `TestUserAnalyticsAggregation` | Personal ticket data isolation |
| `TestTechnicianAnalyticsAggregation` | Performance metrics, section ratings |
| `TestManagerDashboardAggregation` | Department-scoped data |
| `TestHODDashboardAggregation` | Campus+department-scoped data |
| `TestSectionHeadDashboardAggregation` | Section-scoped technician workload |
| `TestDepartmentAnalyticsAggregation` | Cross-campus aggregation |
| `TestHODAnalyticsAggregation` | Single CampusDepartment boundary |
| `TestHOSAnalyticsAggregation` | Single section boundary |

---

### `test_analytics_scoping.py` — 32 tests
Organisational boundary enforcement — verifies data isolation across roles.

| Class | What it covers |
|-------|---------------|
| `TestManagerScoping` | Manager sees only own department (cross-campus) |
| `TestHODScoping` | HOD sees only their campus+department pair |
| `TestHeadOfSectionScoping` | HOS sees only assigned sections |
| `TestTechnicianScoping` | Technician sees only own KPIs |
| `TestCrossBoundaryProtection` | No data leakage across depts/campuses/sections |
| `TestAdminOverrides` | Admin can access any scope |
| `TestScopingEdgeCases` | Missing primary fields, non-existent IDs |

---

## Fixtures (`conftest.py`)

### User factories
| Fixture | Role created |
|---------|-------------|
| `user_factory` | `user` |
| `admin_user_factory` | `admin` |
| `technician_factory` | `technician` |
| `section_head_factory` | `head_of_section` |
| `hod_factory` | `hod` |
| `manager_factory` | `manager` |

### Org hierarchy
```
campus
  └── campus_department  (campus + department + HOD)
        └── section  (campus_department + section_type + HOS)
```

| Fixture | Model |
|---------|-------|
| `campus` | `Campus` |
| `department` | `Department` |
| `campus_department` | `CampusDepartment` |
| `section_type` | `SectionType` |
| `section` | `Section` |
| `section_hvac` | Second `Section` on same campus (different dept) |
| `facility` | `Facility` |

### Service catalogue
| Fixture | Model |
|---------|-------|
| `service_category` | `ServiceCategory` |
| `service_item` | `ServiceItem` (requires_approval=False) |
| `service_item_requires_approval` | `ServiceItem` (requires_approval=True) |

### Composite
| Fixture | What it provides |
|---------|-----------------|
| `ticket_factory` | Callable — creates `Ticket` with sensible defaults |
| `comment_factory` | Callable — creates `Comment` |
| `feedback_factory` | Callable — creates `Feedback` |
| `basic_setup` | Dict with user, admin, technician, campus, section, facility |
| `org_aware_user_factory` | Callable — creates user pre-linked to campus+department |
| `api_client` | Unauthenticated `APIClient` |
| `authenticated_client` | Authenticated as regular user |
| `authenticated_admin_client` | Authenticated as admin |
| `authenticated_technician_client` | Authenticated as technician in section |

---

## Role Reference

| Role | Ticket scope | Analytics access |
|------|-------------|-----------------|
| `user` | Own tickets only | Personal dashboard |
| `technician` | Assigned section tickets | Self KPIs |
| `head_of_section` | Own section tickets | Section analytics |
| `hod` | Campus + department tickets | CampusDept analytics |
| `manager` | Department tickets (all campuses) | Department analytics |
| `admin` | All tickets | Full system |

---

## Org Schema

```
Campus  ←─────────────────────────────────────────┐
  │                                                 │
  └── CampusDepartment (campus + department + HOD) │
        └── Section (campus_dept + section_type)   │
              ├── TechnicianSection (technician M2M)│
              └── Ticket                           │
                    ├── ServiceItem                 │
                    └── Facility ─────────────────→┘
```

---

## Coverage Gaps (Known)

These endpoints exist but have no dedicated tests yet:

| Endpoint | Priority |
|----------|----------|
| `POST /tickets/<id>/escalate/` — `TicketEscalationView` | High |
| `GET /tickets/organizational/` — `OrganizationalTicketListView` | Medium |
| `GET/DELETE /technician-sections/` — CRUD on assignments | Medium |
| Bulk update with invalid transitions (partial failure) | Medium |
| Report endpoints `/reports/generate/` and `/reports/types/` | Low |
