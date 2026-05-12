# Backend Refactor Plan: Service Desk Alignment
**For Django 6.0, Django REST Framework, Concrete Generic Views, Pytest, Python 3.13**

---

## **Overview**

This plan details how to refactor the backend service desk system to align with the standardized organisational and service catalogue structure described below. It covers model redesign, API refactor, data migration, permissioning, analytics, test updates, and admin/core catalogue management endpoints.

---

## **1. Organisational & Service Catalogue Structure**

### **Entities & Relationships**

#### **Organisational Hierarchy**
- **Department** (global, e.g., "Administration")
- **Campus** (physical location/branch)
- **CampusDepartment**: ties a Department to a Campus, owned by a HOD (Head of Dept at that campus)
- **SectionType**: types of sections under a department (e.g., "Maintenance", "Transport")
- **Section**: a campus-specific instance of SectionType under a CampusDepartment, owned by a HOS (Head of Section)
- **Technician**: assigned to one or more Sections on a campus

#### **Service Catalogue Hierarchy**
- **ServiceCategory**: grouped under SectionType (e.g., "Plumbing")
- **ServiceItem**: granular services under ServiceCategory (e.g., "Leaking Faucet")

#### **Ticket Flow**
- User creates ticket: selects department, service category, service item, and describes the issue, location, etc.
- System resolves:
  - User's campus (from profile)
  - Department & CampusDepartment for that campus
  - SectionType (from ServiceCatalogue)
  - Section under that campus
  - HOD/HOS responsible for routing
  - Available technicians, auto-filtered by campus, department, section

---

## **2. Migration & Refactor Steps**

### **Step 1: Current State Analysis**
- Inventory all existing models, APIs, views, permissions, and tests.
- Identify where campus, role, assignment, and service catalogue logic exists.

### **Step 2: Design/Implement New Models**
- Introduce/modify models with correct relationships:
    - `Department`, `Campus`, `CampusDepartment`, `SectionType`, `Section`, `Technician`, `ServiceCategory`, `ServiceItem`
    - Use explicit foreign keys to define structure.
- Implement uniqueness constraints (e.g., unique per campus/department, campus_department/section_type).

### **Step 3: Data Migration**
- Write Django migration scripts or management commands to:
    - Port/migrate existing data into the new structure.
    - Map users to roles (Manager, HOD, HOS, Technician) and assign correct org/campus/section.
    - Translate old ticket data to reference new structure.
- Test migration on a staging database.

### **Step 4: Update Serializers & Views**
- Update DRF serializers for new models/relationships.
- Refactor or rewrite Concrete Generic Views; enforce use of Concrete Generic Views:
    - Use `.get_queryset()` to enforce role/campus/department/section scoping.
    - Ensure views for ticket creation pull user's campus from user profile/session, automatically associating new tickets.
    - Ensure ticket creation logic walks the organisation structure and service catalogue to resolve correct section, HOD/HOS, and available technicians.

### **Step 5: Permissions & Business Logic**
- Refactor permission classes to:
    - Limit actions/visibility based on role and structure (Manager: whole dept, HOD: campus/department, HOS: campus/section, Technician: assigned section/tickets only).
    - Enforce ticket assignment logic matching new constraints (campus, department, section type).
- Update business logic for dynamic assignment to HOD/HOS/technicians.

### **Step 6: API Updates**
- Version endpoints if breaking changes (e.g., `/api/v2/`).
- Clearly document new endpoints, resource structures, analytics endpoints, and filtering/query params (by campus, department, role).
- Remove deprecated/legacy code and endpoints after successful migration.

### **Step 7: Testing with Pytest**
- Refactor tests to use pytest fixtures and factories reflecting new structure.
- Update test coverage for:
    - Ticket creation—validate campus and catalogue resolution.
    - Role-based access (Manager, HOD, HOS, Technician, Admin).
    - Assignment workflows.
    - Section, campus, and service-based filtering/business logic.
    - Analytics endpoints per role.
- Remove or rewrite any tests referring to deleted/obsolete components/models.

### **Step 8: Validation & UAT**
- Run the full test suite for models, APIs, permissions, and analytics.
- Manual/automated User Acceptance Testing for typical user workflows (ticket submission, assignment, analytics, admin tasks).

### **Step 9: Clean Up**
- Once stable:
    - Remove all legacy or deprecated models, views, and serializer code.
    - Clean project documentation.
    - Optionally, squash migrations.

---

## **3. Admin & Core Catalogue Management**

Provide Django Admin and/or API endpoints for the following:

- **Department**: Add/modify/remove (Superuser/Admin only)
- **Campus**: Add/modify/remove (Superuser/Admin only)
- **CampusDepartment**: Assign department to campus and designate HOD
- **SectionType**: Define global section types under a department
- **Section**: Create a section under CampusDepartment and assign HOS
- **Technician**: Create technician, assign to sections using TechnicianSection table
- **ServiceCategory & ServiceItem**: Define service catalogue at organisation level

**Suggested Endpoints**:
- `POST /api/catalogue/departments/` (Admin-only)
- `POST /api/catalogue/campuses/` (Admin-only)
- `POST /api/org/campus-departments/` (Admin/HOD - depending on granularity)
- `POST /api/org/section-types/` (Admin-only)
- `POST /api/org/sections/` (Admin/HOD)
- `POST /api/org/technicians/` (Admin/HOD/HOS depending on org rules)
- `POST /api/catalogue/service-categories/` (Admin-only)
- `POST /api/catalogue/service-items/` (Admin-only)

---

## **4. Analytics & Dashboards by Role**

Implement view endpoints (e.g. `/api/analytics/...`) returning role-scoped JSON for dashboard visualization.  
Example dashboard widgets and analytic queries per role:

### **A. Admin**
- Global statistics across all departments and campuses:
    - Total tickets (opened, closed, pending, overdue)
    - SLA compliance rates
    - Departmental and campus drilldowns
    - Technician performance across organisation
- Example endpoint:  
    `GET /api/analytics/overview/`
    - Query all tickets, group by department and campus

### **B. Manager (Department, Organisation-wide)**
- All tickets/incidents/requests for their **department** (across all campuses):
    - Open/closed tickets by campus/section/technician
    - Average resolution times per campus/section
    - Ticket type trends and peak request times
    - Technician workload for their department
- Example endpoint:  
    `GET /api/analytics/department/{department_id}/`
    - Aggregates for the department, group by campus/section

### **C. HOD (Department at Campus)**
- All tickets for their **department in their campus**:
    - Tickets by section
    - Section/team utilisation
    - Weekly/monthly ticket inflow/resolution rates
    - Escalation and overdue tickets
- Example endpoint:  
    `GET /api/analytics/hod/campus/{campus_id}/department/{department_id}/`

### **D. HOS (Section at CampusDepartment)**
- Tickets and stats for their **section**:
    - Open/closed tickets and status distribution
    - Technician assignments and workload
    - Section-specific SLA/response stats
- Example endpoint:  
    `GET /api/analytics/hos/section/{section_id}/`

### **E. Technician**
- KPIs for their sections:
    - Tickets completed (today, week, month)
    - Current open assignments
    - Average resolution time
- Example endpoint:  
    `GET /api/analytics/technician/{technician_id}/`

### **F. End User Dashboard (optional)**
- User's submitted tickets, statuses, reopens, feedback opportunity
- Example endpoint:  
    `GET /api/analytics/user/`

---

### **Analytics Implementation Example (DRF View)**
```python
# Example: Manager Analytics View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class DepartmentAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, department_id):
        # filter tickets by department, aggregate as needed
        data = {
            "total_tickets": ...,
            "open_tickets": ...,
            "closed_tickets": ...,
            "by_campus": [...],
            "sla_compliance": ...,
            # etc.
        }
        return Response(data)
```

---

## **5. Expected Project Structure**

```
backend/
├── apps/
│   ├── organisation/
│   │   ├── models.py     # Department, Campus, CampusDepartment, SectionType, Section, Technician
│   │   ├── serializers.py
│   │   ├── views.py      # Concrete generic views + org analytics
│   │   ├── permissions.py
│   │   └── ...
│   ├── catalogue/
│   │   ├── models.py     # ServiceCategory, ServiceItem
│   │   ├── serializers.py
│   │   ├── views.py      # Create/modify catalogue, analytics
│   │   └── ...
│   ├── tickets/
│   │   ├── models.py     # Ticket, assignment/resolution logic
│   │   ├── serializers.py
│   │   ├── views.py      # Concrete generic views, analytics
│   │   └── ...
│   └── users/
│       ├── models.py     # User, Profile (with campus), Role logic
│       └── ...
├── tests/
│   ├── organisation/
│   ├── catalogue/
│   ├── tickets/
│   └── users/
└── ...
```

---

## **6. Special Implementation Notes**

- **User Profile:** Must include campus information. Ticket creation uses this to associate to user's campus.
- **Catalogue Management:** Provide Django Admin and/or protected API endpoints for all core catalogue/org entities.
- **Querysets/Views:** Always filter using user’s role and campus/department/section to prevent cross-leakage.
- **Permissions:** Use Django’s and DRF’s permission system for fine-grained access.
- **Auto-assignment:** When a user submits a ticket:
    - Resolves via Department, ServiceCategory/ServiceItem (to SectionType)
    - Gets correct Section, CampusDepartment
    - Narrows eligible technicians (by section/campus/department)
    - Routes for HOD/HOS approval/assignment.

---

## **7. Example: Ticket Creation Logic**

1. User selects:
    - Department → triggers ServiceCategory list.
    - ServiceCategory → triggers ServiceItem list.

2. On form submission:
    - System looks up user's campus from profile.
    - Maps via catalogue to find correct SectionType and Section.
    - Resolves CampusDepartment (campus + department).
    - Finds eligible technicians (filtered by section, campus, department).
    - Routes ticket to the correct HOD/HOS for approval/assignment.

---

## **8. References & Further Reading**

- [Django 6.0 docs](https://docs.djangoproject.com/en/6.0/)
- [DRF Generic Views](https://www.django-rest-framework.org/api-guide/generic-views/#concrete-generic-views)
- [Pytest Django](https://pytest-django.readthedocs.io)
- [Django Migrations](https://docs.djangoproject.com/en/6.0/topics/migrations/)
- [RBAC in Django](https://docs.djangoproject.com/en/6.0/topics/auth/)

---

## **9. Checklist Table**

| Task                                 | Status   |
|-------------------------------------- |---------|
| Map and document current state        |         |
| Implement/adjust models              |         |
| Catalogue/section/technician admin APIs |      |
| Write data migrations                |         |
| Add/update serializers & views        |         |
| Update permissions/business logic    |         |
| Version/update routes                 |         |
| Add analytics endpoints/dashboards   |         |
| Remove legacy code                   |         |
| Refactor tests for pytest            |         |
| Validate and run all tests           |         |
| Manual UAT                           |         |
| Clean-up docs and codebase           |         |

---
