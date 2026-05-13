# Django Resolver — Documentation Index

> **Kenya School of Government — Multi-Campus Service Desk System**
> Django 6.0.3 · DRF 3.16.1 · PostgreSQL · Token Auth

---

## Quick Links

| What do you need? | Go to |
|-------------------|-------|
| Get the project running | [First Time Setup](FIRST_TIME_SETUP.md) |
| Test user credentials | [Default Credentials](DEFAULT_CREDENTIALS.md) |
| REST API reference | [API Integration Guide](API_INTEGRATION_GUIDE.md) |
| System architecture | [Architecture Guide](ARCHITECTURE_GUIDE.md) |
| Analytics endpoints | [Analytics API](api/ANALYTICS.md) |
| Ticket workflow rules | [Workflow Specification](specifications/WORKFLOW_SPEC.md) |
| Running tests | [Testing Guide](testing/TESTING.md) |
| ORM query examples | [Sample Queries](testing/SAMPLE_QUERIES.md) |

---

## All Documents

### Setup & Operations
- [README](../README.md) — Project overview and quick start
- [First Time Setup](FIRST_TIME_SETUP.md) — Step-by-step local setup guide
- [Default Credentials](DEFAULT_CREDENTIALS.md) — Fixture user accounts and passwords

### API Reference
- [API Integration Guide](API_INTEGRATION_GUIDE.md) — All endpoints, request/response shapes, auth
- [Analytics API](api/ANALYTICS.md) — Analytics endpoints per role

### Architecture
- [Architecture Guide](ARCHITECTURE_GUIDE.md) — System design, org hierarchy, service layer, request flow

### Specifications
- [Workflow Specification](specifications/WORKFLOW_SPEC.md) — Ticket state machine, transition rules, role permissions

### Testing
- [Testing Guide](testing/TESTING.md) — Test suite overview, fixtures, running tests
- [Sample Queries](testing/SAMPLE_QUERIES.md) — Django shell ORM examples for fixture data

---

## Org Hierarchy

```
Campus
  └── CampusDepartment  (Campus + Department + HOD)
        └── Section  (CampusDepartment + SectionType + HOS)
              ├── TechnicianSection  (Technician → Section M2M)
              └── Ticket
                    ├── ServiceItem  (from service catalogue)
                    └── Facility
```

## Role Summary

| Role | Scope |
|------|-------|
| `user` | Own tickets only |
| `technician` | Tickets in assigned sections |
| `head_of_section` | Own section — assigns tickets, manages technicians |
| `hod` | Own campus + department |
| `manager` | Own department across all campuses |
| `admin` | Full system access |

## Ticket Status Machine

```
open → assigned → in_progress ⇄ pending → resolved → closed
pending_approval → (approve) → open
pending_approval → (reject)  → rejected
```
