# Backend Refactor Plan: Service Desk Alignment
**For Django 6.0, Django REST Framework, Concrete Generic Views, Pytest, Python 3.13**

---

## **Overview**

This plan details how to refactor the backend service desk system to align with the standardized organisational and service catalogue structure described below. It covers model redesign, API refactor, data migration, permissioning, and test updates.

---

## **1. Organisational & Service Catalogue Structure**

### **Entities & Relationships**

#### **Organisational Hierarchy**
- **Department** (global, e.g., "Administration")
- **Campus** (physical location/branch)
- **CampusDepartment**: ties a Department to a Campus, owned by a HOD (Head of Dept at that campus)
- **SectionType**: types of sections under a department (e.g., "Maintenance", "Transport").
- **Section**: a campus-specific instance of SectionType under a CampusDepartment, owned by a HOS (Head of Section).
- **Technician**: assigned to one or more Sections on a campus.

#### **Service Catalogue Hierarchy**
- **ServiceCategory**: grouped under SectionType (e.g., "Plumbing")
- **ServiceItem**: granular services under ServiceCategory (e.g., "Leaking Faucet")

#### **Ticket Flow**
- User creates ticket: selects department, service category, service item.
- System resolves:
  - User's campus (from profile).
  - Department & CampusDepartment for that campus.
  - SectionType (from ServiceCatalogue).
  - Section under that campus.
  - HOD/HOS responsible for routing.
  - Available technicians, auto-filtered by campus, department, section.

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
- Refactor or rewrite Concrete Generic Views:
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
- Clearly document new endpoints, resource structures, and filtering/query params (by campus, department, role).
- Remove deprecated/legacy code and endpoints after successful migration.

### **Step 7: Testing with Pytest**
- Refactor tests to use pytest fixtures and factories reflecting new structure.
- Update test coverage for:
    - Ticket creation—validate campus and catalogue resolution.
    - Role-based access (manager, HOD, HOS, technician).
    - Assignment workflows.
    - Section, campus, and service-based filtering/business logic.
- Remove or rewrite any tests referring to deleted/obsolete components/models.

### **Step 8: Validation & UAT**
- Run the full test suite for models, APIs, and permissions.
- Manual/automated User Acceptance Testing for typical user workflows (ticket submission, assignment, analytics).

### **Step 9: Clean Up**
- Once stable:
    - Remove all legacy or deprecated models, views, and serializer code.
    - Clean project documentation.
    - Optionally, squash migrations.

---

## **3. Expected Project Structure**

```
backend/
├── apps/
│   ├── organisation/
│   │   ├── models.py     # Department, Campus, CampusDepartment, SectionType, Section, Technician
│   │   ├── serializers.py
│   │   ├── views.py      # Concrete generic views
│   │   ├── permissions.py
│   │   └── ...
│   ├── catalogue/
│   │   ├── models.py     # ServiceCategory, ServiceItem
│   │   ├── serializers.py
│   │   └── ...
│   ├── tickets/
│   │   ├── models.py     # Ticket, assignment/resolution logic
│   │   ├── serializers.py
│   │   ├── views.py      # Ticket endpoints with campus/org logic
│   │   └── ...
│   └── users/
│       ├── models.py     # User, Profile, Role logic
│       └── ...
├── tests/
│   ├── organisation/
│   ├── catalogue/
│   ├── tickets/
│   └── users/
└── ...
```

---

## **4. Special Implementation Notes**

- **User Profile:** Must include campus information. Use during ticket submission to automatically associate with user's campus.
- **Querysets/Views:** Always filter using user’s campus/role to prevent cross-campus/department leakage.
- **Auto-assignment:** When a user submits a ticket:
    - Department, ServiceCategory, and ServiceItem select resolved SectionType in catalogue.
    - Find CampusDepartment and Section matching user's campus.
    - List only eligible technicians. Assignable by HOD/HOS based on org rules.
- **Permissions:** Fine-grained, leveraging Django’s and DRF’s permission systems.

---

## **5. Example: Ticket Creation Logic**

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

## **6. References & Further Reading**

- [Django 6.0 docs](https://docs.djangoproject.com/en/6.0/)
- [DRF Generic Views](https://www.django-rest-framework.org/api-guide/generic-views/#concrete-generic-views)
- [Pytest Django](https://pytest-django.readthedocs.io)
- [Django Migrations](https://docs.djangoproject.com/en/6.0/topics/migrations/)
- [RBAC in Django](https://docs.djangoproject.com/en/6.0/topics/auth/)

---

## **7. Checklist Table**

| Task                                 | Status   |
|-------------------------------------- |---------|
| Map and document current state        |         |
| Implement/adjust models              |         |
| Write data migrations                |         |
| Add/update serializers & views        |         |
| Update permissions                   |         |
| Version/update routes                 |         |
| Remove legacy code                   |         |
| Refactor tests for pytest            |         |
| Validate and run all tests           |         |
| Manual UAT                           |         |
| Clean-up docs and codebase           |         |

---

**Contact the lead architect for ERDs, data migration helpers, or further integration advice.**