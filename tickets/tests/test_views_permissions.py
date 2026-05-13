"""
API/Views Tests — Permissions, Workflow, and Role-Based Scoping

Covers:
1. Ticket creation via /api/tickets/create/ — campus auto-resolution,
   section linkage via service catalogue, eligible technicians.
2. Role-based list scoping — each role sees only their allowed data.
3. Org hierarchy CRUD — campuses, departments, sections (admin-only writes).
4. Service catalogue CRUD — service categories and items (admin-only writes).
5. HOD/HOS assignment endpoints.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from tickets.models import (
    Campus,
    Department,
    CampusDepartment,
    SectionType,
    Section,
    ServiceCategory,
    ServiceItem,
    Ticket,
    TechnicianSection,
)


# ============================================================================
# HELPERS & SHARED FIXTURES
# ============================================================================



@pytest.fixture
def campus_user(db, user_factory, campus):
    """Regular user already linked to the main campus fixture."""
    u = user_factory(username="campus_user_main")
    u.primary_campus = campus
    u.save()
    return u


@pytest.fixture
def campus_technician(db, technician_factory, campus, section):
    """Technician linked to main campus and section via TechnicianSection."""
    tech = technician_factory(username="campus_tech_main")
    tech.primary_campus = campus
    tech.primary_department = section.campus_department.department
    tech.save()
    tech.sections.add(section)   # creates TechnicianSection row
    return tech


@pytest.fixture
def campus_hod(db, hod_factory, campus, department, campus_department):
    """HOD for the main campus + department."""
    hod = hod_factory(username="hod_main")
    hod.primary_campus = campus
    hod.primary_department = department
    hod.save()
    campus_department.head_of_department = hod
    campus_department.save()
    return hod


@pytest.fixture
def campus_hos(db, section_head_factory, campus, department, section):
    """HOS for the main section."""
    hos = section_head_factory(username="hos_main")
    hos.primary_campus = campus
    hos.primary_department = department
    hos.save()
    section.head_of_section = hos
    section.save()
    hos.sections.add(section)
    return hos


@pytest.fixture
def campus_manager(db, manager_factory, department):
    """Manager scoped to the main department (all campuses)."""
    mgr = manager_factory(username="manager_main")
    mgr.primary_department = department
    mgr.save()
    department.manager_user = mgr
    department.save()
    return mgr


def make_client(user):
    from rest_framework.test import APIClient
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ============================================================================
# 1. TICKET CREATION — campus auto-resolution & catalogue linkage
# ============================================================================


class TestTicketCreateEndpoint:
    """POST /api/tickets/create/ — resolves campus_department and section
    automatically from the authenticated user's primary_campus plus the
    selected department / service_item."""

    def test_creates_ticket_with_resolved_campus_department(
        self, db, campus_user, department, section, service_item
    ):
        """Happy-path: correct campus_department and section in response."""
        client = make_client(campus_user)
        url = reverse("ticket-create")
        data = {
            "department_id": department.id,
            "service_item_id": service_item.id,
            "title": "Laptop screen cracked",
            "description": "My laptop screen has a crack.",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        body = response.data
        assert body["ticket"]["status"] == "open"
        assert body["campus_department"]["campus"]["code"] == campus_user.primary_campus.code
        assert body["campus_department"]["department"]["code"] == department.code
        assert body["section"]["id"] == section.id

    def test_eligible_technicians_include_section_technicians(
        self, db, campus_user, department, section, service_item, campus_technician
    ):
        """Eligible technicians returned are those linked to the resolved section."""
        client = make_client(campus_user)
        url = reverse("ticket-create")
        data = {
            "department_id": department.id,
            "service_item_id": service_item.id,
            "title": "Need IT help",
            "description": "Something broke.",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        tech_ids = [t["id"] for t in response.data["eligible_technicians"]]
        assert campus_technician.id in tech_ids

    def test_no_primary_campus_returns_400(
        self, db, user_factory, department, service_item
    ):
        """User without a primary campus cannot create tickets."""
        user = user_factory(username="no_campus_user")
        # intentionally no primary_campus
        client = make_client(user)
        url = reverse("ticket-create")
        data = {
            "department_id": department.id,
            "service_item_id": service_item.id,
            "title": "Laptop issue",
            "description": "Broken.",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_department_not_on_campus_returns_400(
        self, db, campus_user, service_item
    ):
        """If the chosen department has no CampusDepartment on the user's campus, 400."""
        orphan_dept = Department.objects.create(name="Orphan Dept", code="ORP")
        client = make_client(campus_user)
        url = reverse("ticket-create")
        data = {
            "department_id": orphan_dept.id,
            "service_item_id": service_item.id,
            "title": "Test",
            "description": "Test",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "department_id" in response.data or "non_field_errors" in response.data

    def test_service_item_wrong_department_returns_400(
        self, db, campus_user, campus_department
    ):
        """service_item whose section_type belongs to a different department → 400."""
        other_dept = Department.objects.create(name="Other Dept", code="OTH")
        other_st = SectionType.objects.create(
            department=other_dept, name="Misc", code="MSC"
        )
        other_cat = ServiceCategory.objects.create(
            section_type=other_st, name="General", order=1
        )
        other_item = ServiceItem.objects.create(
            category=other_cat,
            name="Misc Request",
            description="Misc",
        )
        client = make_client(campus_user)
        url = reverse("ticket-create")
        data = {
            "department_id": campus_department.department.id,
            "service_item_id": other_item.id,
            "title": "Mismatch test",
            "description": "Should fail.",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "service_item_id" in response.data

    def test_requires_approval_creates_pending_approval_ticket(
        self, db, campus_user, department, section, service_item_requires_approval
    ):
        """Service items with requires_approval=True produce a pending_approval ticket."""
        client = make_client(campus_user)
        url = reverse("ticket-create")
        data = {
            "department_id": department.id,
            "service_item_id": service_item_requires_approval.id,
            "title": "New workstation request",
            "description": "I need a new workstation.",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["ticket"]["status"] == "pending_approval"

    def test_unauthenticated_cannot_create_ticket(self, db, department, service_item):
        """Unauthenticated request → 401."""
        from rest_framework.test import APIClient
        client = APIClient()
        url = reverse("ticket-create")
        data = {
            "department_id": department.id,
            "service_item_id": service_item.id,
            "title": "Test",
            "description": "Test",
        }
        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 2. ROLE-BASED TICKET LIST SCOPING — GET /api/tickets/
# ============================================================================


class TestTicketListScoping:
    """Each role should only see the tickets their scope permits."""

    @pytest.fixture(autouse=True)
    def setup_tickets(
        self, db, section, facility, campus_user, campus_technician,
        campus_hod, campus_hos, campus_manager,
        admin_user_factory, user_factory, campus,
    ):
        """Create one ticket per role-relevant context."""
        cd = section.campus_department

        # Ticket in scope (main section)
        self.in_scope_ticket = Ticket.objects.create(
            title="In-scope ticket",
            description="Within main section",
            section=section,
            facility=facility,
            raised_by=campus_user,
            campus_department=cd,
        )

        # Ticket in different campus
        other_campus = Campus.objects.create(name="Remote Campus", code="RMT", location="Remote")
        other_dept = Department.objects.create(name="Remote Dept", code="RDPT")
        other_cd = CampusDepartment.objects.create(campus=other_campus, department=other_dept)
        other_st = SectionType.objects.create(department=other_dept, name="Remote ST", code="RST")
        other_section = Section.objects.create(
            campus_department=other_cd,
            section_type=other_st,
            name="Remote Section",
            code="RS",
        )
        other_user = user_factory(username="other_campus_user")

        self.out_of_scope_ticket = Ticket.objects.create(
            title="Out-of-scope ticket",
            description="Different campus entirely",
            section=other_section,
            facility=facility,
            raised_by=other_user,
            campus_department=other_cd,
        )

        admin = admin_user_factory(username="list_test_admin")
        admin.primary_campus = campus
        admin.save()
        self.admin = admin

    def test_admin_sees_all_tickets(self, db):
        client = make_client(self.admin)
        response = client.get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert self.in_scope_ticket.id in ids
        assert self.out_of_scope_ticket.id in ids

    def test_manager_sees_only_department_tickets(self, db, campus_manager, section):
        """Manager scoped to main department — sees in-scope, not out-of-scope."""
        client = make_client(campus_manager)
        response = client.get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert self.in_scope_ticket.id in ids
        assert self.out_of_scope_ticket.id not in ids

    def test_hod_sees_only_campus_tickets(self, db, campus_hod):
        """HOD scoped to main campus — sees in-scope, not other-campus ticket."""
        client = make_client(campus_hod)
        response = client.get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert self.in_scope_ticket.id in ids
        assert self.out_of_scope_ticket.id not in ids

    def test_hos_sees_only_section_tickets(self, db, campus_hos):
        """HOS scoped to their section — sees in-scope ticket only."""
        client = make_client(campus_hos)
        response = client.get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert self.in_scope_ticket.id in ids
        assert self.out_of_scope_ticket.id not in ids

    def test_technician_sees_assigned_section_tickets(self, db, campus_technician):
        """Technician linked to the main section sees that section's tickets."""
        client = make_client(campus_technician)
        response = client.get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data["results"]]
        assert self.in_scope_ticket.id in ids
        assert self.out_of_scope_ticket.id not in ids

    def test_user_sees_only_own_tickets(self, db, campus_user):
        """Regular user only sees tickets they raised."""
        client = make_client(campus_user)
        response = client.get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_200_OK
        for t in response.data["results"]:
            assert t["id"] != self.out_of_scope_ticket.id

    def test_unauthenticated_cannot_list_tickets(self, db):
        from rest_framework.test import APIClient
        response = APIClient().get(reverse("ticket-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 3. ROLE-BASED OBJECT-LEVEL PERMISSIONS — GET/PATCH /api/tickets/<pk>/
# ============================================================================


class TestTicketDetailPermissions:

    def test_user_can_view_own_ticket(self, db, campus_user, section, facility):
        cd = section.campus_department
        ticket = Ticket.objects.create(
            title="My ticket", description="Mine",
            section=section, facility=facility,
            raised_by=campus_user, campus_department=cd,
        )
        client = make_client(campus_user)
        response = client.get(reverse("ticket-detail", args=[ticket.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_user_cannot_view_other_users_ticket(
        self, db, campus_user, user_factory, section, facility
    ):
        other = user_factory(username="other_plain_user")
        cd = section.campus_department
        ticket = Ticket.objects.create(
            title="Their ticket", description="Not mine",
            section=section, facility=facility,
            raised_by=other, campus_department=cd,
        )
        client = make_client(campus_user)
        response = client.get(reverse("ticket-detail", args=[ticket.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_technician_cannot_edit_ticket_not_assigned_to_them(
        self, db, campus_technician, user_factory, technician_factory,
        section, facility
    ):
        other_tech = technician_factory(username="other_tech_obj")
        other_tech.sections.add(section)
        raiser = user_factory(username="raiser_obj")
        cd = section.campus_department
        ticket = Ticket.objects.create(
            title="Not my ticket", description="Assigned elsewhere",
            section=section, facility=facility,
            raised_by=raiser, assigned_to=other_tech,
            campus_department=cd, status="assigned",
        )
        client = make_client(campus_technician)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "in_progress"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hos_can_patch_ticket_in_own_section(
        self, db, campus_hos, campus_user, section, facility
    ):
        cd = section.campus_department
        tech = campus_hos   # HOS has edit rights for their section
        ticket = Ticket.objects.create(
            title="Section ticket", description="HOS editable",
            section=section, facility=facility,
            raised_by=campus_user, campus_department=cd,
            status="open",
        )
        client = make_client(campus_hos)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"title": "Updated by HOS"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_hod_can_patch_ticket_on_own_campus(
        self, db, campus_hod, campus_user, section, facility
    ):
        cd = section.campus_department
        ticket = Ticket.objects.create(
            title="HOD editable ticket", description="On HOD campus",
            section=section, facility=facility,
            raised_by=campus_user, campus_department=cd,
        )
        client = make_client(campus_hod)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"title": "Updated by HOD"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_patch_own_department_ticket(
        self, db, campus_manager, campus_user, section, facility
    ):
        cd = section.campus_department
        ticket = Ticket.objects.create(
            title="Manager editable", description="Dept ticket",
            section=section, facility=facility,
            raised_by=campus_user, campus_department=cd,
        )
        client = make_client(campus_manager)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"title": "Updated by Manager"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# 4. ORG HIERARCHY CRUD — campuses, departments, sections
# ============================================================================


class TestCampusCRUD:

    def test_admin_can_create_campus(self, db, admin_user_factory, campus):
        admin = admin_user_factory(username="admin_campus_test")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        data = {"name": "New Campus", "code": "NEW", "location": "New Location"}
        response = client.post(reverse("campus-list"), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["code"] == "NEW"

    def test_non_admin_cannot_create_campus(self, db, campus_user):
        client = make_client(campus_user)
        data = {"name": "Forbidden Campus", "code": "FBD", "location": "Nowhere"}
        response = client.post(reverse("campus-list"), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_sees_all_campuses(self, db, admin_user_factory, campus):
        admin = admin_user_factory(username="admin_campus_list")
        admin.primary_campus = campus
        admin.save()
        Campus.objects.create(name="Other Campus", code="OTH2", location="Elsewhere")
        client = make_client(admin)
        response = client.get(reverse("campus-list"))
        assert response.status_code == status.HTTP_200_OK
        codes = [c["code"] for c in response.data["results"]]
        assert campus.code in codes
        assert "OTH2" in codes

    def test_non_admin_campus_list_scoped_to_primary(self, db, campus_user, campus):
        """Non-admin/manager sees only their primary campus."""
        Campus.objects.create(name="Hidden Campus", code="HID", location="Hidden")
        client = make_client(campus_user)
        response = client.get(reverse("campus-list"))
        assert response.status_code == status.HTTP_200_OK
        codes = [c["code"] for c in response.data["results"]]
        assert campus.code in codes
        assert "HID" not in codes

    def test_admin_can_update_campus(self, db, admin_user_factory, campus):
        admin = admin_user_factory(username="admin_campus_upd")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        response = client.patch(
            reverse("campus-detail", args=[campus.id]),
            {"location": "Updated Location"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["location"] == "Updated Location"

    def test_non_admin_cannot_update_campus(self, db, campus_user, campus):
        client = make_client(campus_user)
        response = client.patch(
            reverse("campus-detail", args=[campus.id]),
            {"location": "Hack attempt"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestDepartmentCRUD:

    def test_admin_can_create_department(self, db, admin_user_factory, campus):
        admin = admin_user_factory(username="admin_dept_test")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        data = {"name": "New Department", "code": "NDPT"}
        response = client.post(reverse("department-list"), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["code"] == "NDPT"

    def test_non_admin_cannot_create_department(self, db, campus_user):
        client = make_client(campus_user)
        data = {"name": "Forbidden Dept", "code": "FBD"}
        response = client.post(reverse("department-list"), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_department_list_scoped_to_campus_for_non_admin(
        self, db, campus_user, department, campus
    ):
        """Non-admin/manager only sees departments present on their primary campus."""
        from tickets.models import CampusDepartment
        # Create CampusDepartment link so department is visible on campus_user's campus
        CampusDepartment.objects.create(campus=campus, department=department)
        invisible_dept = Department.objects.create(name="Invisible Dept", code="INV")
        # Note: invisible_dept has no CampusDepartment entry for the user's campus
        client = make_client(campus_user)
        response = client.get(reverse("department-list"))
        assert response.status_code == status.HTTP_200_OK
        dept_ids = [d["id"] for d in response.data["results"]]
        assert department.id in dept_ids
        assert invisible_dept.id not in dept_ids

    def test_admin_sees_all_departments(self, db, admin_user_factory, department, campus):
        admin = admin_user_factory(username="admin_dept_all")
        admin.primary_campus = campus
        admin.save()
        invisible_dept = Department.objects.create(name="Invisible Dept 2", code="INV2")
        client = make_client(admin)
        response = client.get(reverse("department-list"))
        assert response.status_code == status.HTTP_200_OK
        dept_ids = [d["id"] for d in response.data["results"]]
        assert department.id in dept_ids
        assert invisible_dept.id in dept_ids

    def test_admin_can_delete_department(self, db, admin_user_factory, campus):
        admin = admin_user_factory(username="admin_dept_del")
        admin.primary_campus = campus
        admin.save()
        dept = Department.objects.create(name="Temp Dept", code="TMP")
        client = make_client(admin)
        response = client.delete(reverse("department-detail", args=[dept.id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_non_admin_cannot_delete_department(self, db, campus_user, department):
        client = make_client(campus_user)
        response = client.delete(reverse("department-detail", args=[department.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestCampusDepartmentCRUD:

    def test_admin_can_create_campus_department(
        self, db, admin_user_factory, campus, department
    ):
        admin = admin_user_factory(username="admin_cd_create")
        admin.primary_campus = campus
        admin.save()
        other_campus = Campus.objects.create(name="CD Test Campus", code="CDT", location="CDT")
        client = make_client(admin)
        data = {"campus_id": other_campus.id, "department_id": department.id}
        response = client.post(reverse("campus-department-list"), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_non_admin_cannot_create_campus_department(
        self, db, campus_user, campus, department
    ):
        other_campus = Campus.objects.create(name="Restricted CD Campus", code="RCD", location="RCD")
        client = make_client(campus_user)
        data = {"campus_id": other_campus.id, "department_id": department.id}
        response = client.post(reverse("campus-department-list"), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_assign_hod(
        self, db, admin_user_factory, campus, campus_department, hod_factory
    ):
        """PATCH /api/campus-departments/<pk>/assign-hod/ by admin succeeds."""
        admin = admin_user_factory(username="admin_hod_assign")
        admin.primary_campus = campus
        admin.save()
        new_hod = hod_factory(username="new_hod_user")
        client = make_client(admin)
        response = client.patch(
            reverse("campus-department-assign-hod", args=[campus_department.id]),
            {"head_of_department_id": new_hod.id},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        campus_department.refresh_from_db()
        assert campus_department.head_of_department == new_hod

    def test_non_admin_cannot_assign_hod(
        self, db, campus_user, campus_department, hod_factory
    ):
        new_hod = hod_factory(username="attempted_hod")
        client = make_client(campus_user)
        response = client.patch(
            reverse("campus-department-assign-hod", args=[campus_department.id]),
            {"head_of_department_id": new_hod.id},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestSectionCRUD:

    def test_admin_can_create_section(
        self, db, admin_user_factory, campus, campus_department, section_type
    ):
        admin = admin_user_factory(username="admin_sect_create")
        admin.primary_campus = campus
        admin.save()
        # Use a fresh section_type to avoid the unique_section_per_campus_department_type constraint
        fresh_st = SectionType.objects.create(
            department=campus_department.department,
            name="New Section Type",
            code="NST",
        )
        client = make_client(admin)
        data = {
            "campus_department_id": campus_department.id,
            "section_type_id": fresh_st.id,
            "name": "New Section",
            "code": "NS",
        }
        response = client.post(reverse("section-list"), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Section"

    def test_non_admin_cannot_create_section(
        self, db, campus_user, campus_department, section_type
    ):
        client = make_client(campus_user)
        data = {
            "campus_department_id": campus_department.id,
            "section_type_id": section_type.id,
            "name": "Forbidden Section",
            "code": "FBS",
        }
        response = client.post(reverse("section-list"), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_assign_hos(
        self, db, admin_user_factory, campus, section, section_head_factory
    ):
        """PATCH /api/sections/<pk>/assign-hos/ by admin succeeds."""
        admin = admin_user_factory(username="admin_hos_assign")
        admin.primary_campus = campus
        admin.save()
        new_hos = section_head_factory(username="new_hos_user")
        client = make_client(admin)
        response = client.patch(
            reverse("section-assign-hos", args=[section.id]),
            {"head_of_section_id": new_hos.id},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        section.refresh_from_db()
        assert section.head_of_section == new_hos

    def test_non_admin_cannot_assign_hos(
        self, db, campus_user, section, section_head_factory
    ):
        new_hos = section_head_factory(username="attempted_hos")
        client = make_client(campus_user)
        response = client.patch(
            reverse("section-assign-hos", args=[section.id]),
            {"head_of_section_id": new_hos.id},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_section_list_admin_sees_all(
        self, db, admin_user_factory, campus, section, section_hvac
    ):
        admin = admin_user_factory(username="admin_sect_all")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        response = client.get(reverse("section-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [s["id"] for s in response.data["results"]]
        assert section.id in ids
        assert section_hvac.id in ids

    def test_section_list_hos_sees_only_own_section(
        self, db, campus_hos, section, section_hvac
    ):
        client = make_client(campus_hos)
        response = client.get(reverse("section-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [s["id"] for s in response.data["results"]]
        assert section.id in ids
        assert section_hvac.id not in ids

    def test_section_list_hod_sees_campus_sections(
        self, db, campus_hod, section, section_hvac
    ):
        """HOD sees all sections on their campus regardless of department."""
        client = make_client(campus_hod)
        response = client.get(reverse("section-list"))
        assert response.status_code == status.HTTP_200_OK
        # section_hvac is on a different campus (see conftest) so not visible
        ids = [s["id"] for s in response.data["results"]]
        assert section.id in ids


# ============================================================================
# 5. SERVICE CATALOGUE CRUD — categories and items
# ============================================================================


class TestServiceCatalogueCRUD:

    def test_admin_can_create_service_category(
        self, db, admin_user_factory, campus, section_type
    ):
        admin = admin_user_factory(username="admin_cat_create")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        data = {
            "section_type_id": section_type.id,
            "name": "Software Requests",
            "description": "Software-related",
            "order": 2,
        }
        response = client.post(reverse("service-category-list"), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Software Requests"

    def test_non_admin_cannot_create_service_category(
        self, db, campus_user, section_type
    ):
        client = make_client(campus_user)
        data = {
            "section_type_id": section_type.id,
            "name": "Forbidden Category",
            "order": 99,
        }
        response = client.post(reverse("service-category-list"), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_any_authenticated_user_can_list_service_categories(
        self, db, campus_user, service_category
    ):
        client = make_client(campus_user)
        response = client.get(reverse("service-category-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [c["id"] for c in response.data["results"]]
        assert service_category.id in ids

    def test_admin_can_create_service_item(
        self, db, admin_user_factory, campus, service_category
    ):
        admin = admin_user_factory(username="admin_item_create")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        data = {
            "category_id": service_category.id,
            "name": "Password Reset",
            "description": "Reset user password",
            "sla_hours": 4,
            "requires_approval": False,
        }
        response = client.post(reverse("service-item-list"), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Password Reset"

    def test_non_admin_cannot_create_service_item(
        self, db, campus_user, service_category
    ):
        client = make_client(campus_user)
        data = {
            "category_id": service_category.id,
            "name": "Forbidden Item",
            "description": "Should not exist",
        }
        response = client.post(reverse("service-item-list"), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_any_authenticated_user_can_list_service_items(
        self, db, campus_user, service_item
    ):
        client = make_client(campus_user)
        response = client.get(reverse("service-item-list"))
        assert response.status_code == status.HTTP_200_OK
        ids = [i["id"] for i in response.data["results"]]
        assert service_item.id in ids

    def test_admin_can_update_service_item(
        self, db, admin_user_factory, campus, service_item
    ):
        admin = admin_user_factory(username="admin_item_upd")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        response = client.patch(
            reverse("service-item-detail", args=[service_item.id]),
            {"sla_hours": 72},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        service_item.refresh_from_db()
        assert service_item.sla_hours == 72

    def test_admin_can_delete_service_category(
        self, db, admin_user_factory, campus, section_type
    ):
        admin = admin_user_factory(username="admin_cat_del")
        admin.primary_campus = campus
        admin.save()
        temp_cat = ServiceCategory.objects.create(
            section_type=section_type, name="Temp Category", order=50
        )
        client = make_client(admin)
        response = client.delete(reverse("service-category-detail", args=[temp_cat.id]))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_unauthenticated_cannot_access_catalogue(self, db, service_category):
        from rest_framework.test import APIClient
        client = APIClient()
        response = client.get(reverse("service-category-list"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ============================================================================
# 6. TECHNICIAN MANAGEMENT — section membership endpoints
# ============================================================================


class TestTechnicianManagement:

    def test_admin_can_add_technician_to_section(
        self, db, admin_user_factory, campus, section, technician_factory
    ):
        admin = admin_user_factory(username="admin_tech_add")
        admin.primary_campus = campus
        admin.save()
        tech = technician_factory(username="tech_to_add")
        tech.primary_campus = campus
        tech.save()
        client = make_client(admin)
        response = client.post(
            reverse("section-add-technician", args=[section.id]),
            {"technician": tech.id},
            format="json",
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        assert TechnicianSection.objects.filter(section=section, technician=tech).exists()

    def test_non_admin_cannot_add_technician(
        self, db, campus_user, section, technician_factory
    ):
        tech = technician_factory(username="tech_blocked")
        client = make_client(campus_user)
        response = client.post(
            reverse("section-add-technician", args=[section.id]),
            {"technician": tech.id},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_technicians_for_section(
        self, db, campus_technician, section, admin_user_factory, campus
    ):
        admin = admin_user_factory(username="admin_tech_list")
        admin.primary_campus = campus
        admin.save()
        client = make_client(admin)
        response = client.get(
            reverse("technicians-by-section"),
            {"section_id": section.id},
        )
        assert response.status_code == status.HTTP_200_OK
        ids = [t["id"] for t in response.data]
        assert campus_technician.id in ids
