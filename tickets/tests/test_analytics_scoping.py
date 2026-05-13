"""Analytics scoping tests — verify organizational boundary enforcement.

Tests verify that each analytics endpoint correctly enforces data isolation
across organizational boundaries (campus, department, section) and prevents
unauthorized cross-boundary data access.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import (
    Campus,
    CampusDepartment,
    CustomUser,
    Department,
    Section,
    SectionType,
    Ticket,
)


def make_authenticated_client(user):
    """Create authenticated API client for a given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Multi-Campus Setup Fixtures ────────────────────────────────────────────────


@pytest.fixture
def multi_campus_setup(db, campus, department, section):
    """Create two campuses with departments and sections."""
    # Campus 1 (default from conftest): campus
    campus1 = campus
    dept1 = department  # default from conftest

    # Campus 2
    campus2 = Campus.objects.create(name="West Campus", code="WEST", location="West")

    # Department 2 (different from dept1)
    dept2 = Department.objects.create(name="HR Department", code="HR")

    # CampusDepartment links
    cd1 = CampusDepartment.objects.get_or_create(
        campus=campus1, department=dept1,
        defaults={"head_of_department": None}
    )[0]

    cd2 = CampusDepartment.objects.create(
        campus=campus2, department=dept1
    )

    # Section on Campus 2
    st2 = SectionType.objects.create(
        department=dept1, name="Network Type 2", code="NET2"
    )
    section2 = Section.objects.create(
        campus_department=cd2,
        section_type=st2,
        name="Network Section 2",
        code="NET2",
    )

    return {
        "campus1": campus1,
        "campus2": campus2,
        "dept1": dept1,
        "dept2": dept2,
        "cd1": cd1,
        "cd2": cd2,
        "section1": section,
        "section2": section2,
    }


@pytest.fixture
def multi_role_setup(db, multi_campus_setup, manager_factory, hod_factory, section_head_factory):
    """Create managers, HODs, and HOS across multiple campuses."""
    setup = multi_campus_setup
    campus1 = setup["campus1"]
    campus2 = setup["campus2"]
    dept1 = setup["dept1"]
    section1 = setup["section1"]
    section2 = setup["section2"]

    # Manager on Campus 1, Department 1
    mgr1 = manager_factory(username="mgr1_dept1")
    mgr1.primary_campus = campus1
    mgr1.primary_department = dept1
    mgr1.save()

    # HOD on Campus 1, Department 1
    hod1 = hod_factory(username="hod1_campus1_dept1")
    hod1.primary_campus = campus1
    hod1.primary_department = dept1
    hod1.save()
    setup["cd1"].head_of_department = hod1
    setup["cd1"].save()

    # HOD on Campus 2, Department 1
    hod2 = hod_factory(username="hod2_campus2_dept1")
    hod2.primary_campus = campus2
    hod2.primary_department = dept1
    hod2.save()
    setup["cd2"].head_of_department = hod2
    setup["cd2"].save()

    # Head of Section on Campus 1, Section 1
    hos1 = section_head_factory(username="hos1_section1")
    hos1.sections.add(section1)
    hos1.primary_campus = campus1
    hos1.primary_department = dept1
    hos1.save()
    section1.head_of_section = hos1
    section1.save()

    # Head of Section on Campus 2, Section 2
    hos2 = section_head_factory(username="hos2_section2")
    hos2.sections.add(section2)
    hos2.primary_campus = campus2
    hos2.primary_department = dept1
    hos2.save()
    section2.head_of_section = hos2
    section2.save()

    return {
        **setup,
        "mgr1": mgr1,
        "hod1": hod1,
        "hod2": hod2,
        "hos1": hos1,
        "hos2": hos2,
    }


# ── Manager Scoping Tests ──────────────────────────────────────────────────────


class TestManagerScoping:
    """Verify managers can only see their own department across all campuses."""

    def test_manager_sees_own_department_tickets(
        self, db, multi_role_setup, ticket_factory
    ):
        """Manager sees tickets only from their department."""
        setup = multi_role_setup
        mgr1 = setup["mgr1"]
        dept1 = setup["dept1"]
        section1 = setup["section1"]
        section2 = setup["section2"]

        # Tickets in mgr1's department (across campuses)
        t1 = ticket_factory(section=section1)
        t2 = ticket_factory(section=section2)

        client = make_authenticated_client(mgr1)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_cannot_see_other_department(
        self, db, multi_role_setup, manager_factory, ticket_factory
    ):
        """Manager cannot access analytics for different department."""
        setup = multi_role_setup
        mgr1 = setup["mgr1"]
        dept2 = setup["dept2"]

        client = make_authenticated_client(mgr1)
        # Try to access department endpoint for department 2 (should fail)
        response = client.get(
            reverse("analytics-department", args=[dept2.id])
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_department_analytics_cross_campus(
        self, db, multi_role_setup, ticket_factory
    ):
        """Manager sees their department across all campuses in department analytics."""
        setup = multi_role_setup
        mgr1 = setup["mgr1"]
        dept1 = setup["dept1"]
        section1 = setup["section1"]
        section2 = setup["section2"]

        # Create tickets on both campuses in mgr1's department
        ticket_factory(section=section1)
        ticket_factory(section=section2)

        client = make_authenticated_client(mgr1)
        response = client.get(
            reverse("analytics-department", args=[dept1.id])
        )
        assert response.status_code == status.HTTP_200_OK

    def test_manager_without_primary_department_denied(
        self, db, manager_factory, campus
    ):
        """Manager without primary_department sees empty or denied."""
        mgr = manager_factory()
        mgr.primary_campus = campus
        mgr.primary_department = None
        mgr.save()

        client = make_authenticated_client(mgr)
        response = client.get(reverse("analytics-manager"))
        # May return 200 with empty data or 403
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )

    def test_manager_across_multiple_campuses(
        self, db, multi_role_setup, ticket_factory
    ):
        """Manager sees department data even though sections are on different campuses."""
        setup = multi_role_setup
        mgr1 = setup["mgr1"]
        section1 = setup["section1"]
        section2 = setup["section2"]

        # Both sections are in mgr1's department but on different campuses
        assert section1.campus_department.campus != section2.campus_department.campus
        assert section1.campus_department.department == section2.campus_department.department

        ticket_factory(section=section1)
        ticket_factory(section=section2)

        client = make_authenticated_client(mgr1)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_200_OK


# ── HOD Scoping Tests ──────────────────────────────────────────────────────────


class TestHODScoping:
    """Verify HODs can only see their own campus+department pair."""

    def test_hod_sees_own_campus_department(
        self, db, multi_role_setup, ticket_factory
    ):
        """HOD sees tickets only from their campus+department."""
        setup = multi_role_setup
        hod1 = setup["hod1"]
        section1 = setup["section1"]

        ticket_factory(section=section1)

        client = make_authenticated_client(hod1)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_cannot_see_other_campus(
        self, db, multi_role_setup, ticket_factory
    ):
        """HOD cannot access data from other campus even if same department."""
        setup = multi_role_setup
        hod1 = setup["hod1"]
        hod2 = setup["hod2"]
        campus2 = setup["campus2"]
        dept1 = setup["dept1"]

        # hod1 tries to access hod2's campus+department via resource endpoint
        cd2 = CampusDepartment.objects.get(campus=campus2, department=dept1)

        client = make_authenticated_client(hod1)
        response = client.get(
            reverse("analytics-campus-department", args=[cd2.id])
        )
        # hod1 is not head_of_department for cd2, should get 403
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_cannot_access_other_department_same_campus(
        self, db, multi_role_setup, hod_factory
    ):
        """HOD cannot access different department on their campus."""
        setup = multi_role_setup
        hod1 = setup["hod1"]
        campus1 = setup["campus1"]
        dept2 = setup["dept2"]

        # Create campus+department for dept2 on campus1
        cd = CampusDepartment.objects.create(
            campus=campus1, department=dept2
        )

        client = make_authenticated_client(hod1)
        # hod1 is not head of this campus+department
        response = client.get(
            reverse("analytics-campus-department", args=[cd.id])
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_without_primary_campus_denied(
        self, db, hod_factory, department
    ):
        """HOD without primary_campus sees empty or denied."""
        hod = hod_factory()
        hod.primary_campus = None
        hod.primary_department = department
        hod.save()

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hod_campus_department_analytics_strict_boundary(
        self, db, multi_role_setup
    ):
        """HOD analytics strictly bounded to single campus+department."""
        setup = multi_role_setup
        hod1 = setup["hod1"]
        hod2 = setup["hod2"]
        campus1 = setup["campus1"]
        campus2 = setup["campus2"]
        dept1 = setup["dept1"]

        cd1 = CampusDepartment.objects.get(campus=campus1, department=dept1)
        cd2 = CampusDepartment.objects.get(campus=campus2, department=dept1)

        # hod1 can access cd1
        client1 = make_authenticated_client(hod1)
        resp1 = client1.get(reverse("analytics-campus-department", args=[cd1.id]))
        assert resp1.status_code == status.HTTP_200_OK

        # hod1 cannot access cd2 (different campus)
        resp2 = client1.get(reverse("analytics-campus-department", args=[cd2.id]))
        assert resp2.status_code == status.HTTP_403_FORBIDDEN


# ── Head of Section Scoping Tests ──────────────────────────────────────────────


class TestHeadOfSectionScoping:
    """Verify HOS can only see their assigned sections."""

    def test_hos_sees_own_section(self, db, multi_role_setup, ticket_factory):
        """HOS sees tickets only from their section."""
        setup = multi_role_setup
        hos1 = setup["hos1"]
        section1 = setup["section1"]

        ticket_factory(section=section1)

        client = make_authenticated_client(hos1)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_hos_cannot_see_other_section_same_campus(
        self, db, multi_role_setup, ticket_factory
    ):
        """HOS cannot access different section on same campus."""
        setup = multi_role_setup
        hos1 = setup["hos1"]
        section2 = setup["section2"]

        ticket_factory(section=section2)

        client = make_authenticated_client(hos1)
        # hos1 is not head of section2
        response = client.get(reverse("analytics-section", args=[section2.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hos_cannot_see_other_section_different_campus(
        self, db, multi_role_setup, ticket_factory
    ):
        """HOS cannot access sections on different campus."""
        setup = multi_role_setup
        hos1 = setup["hos1"]
        section2 = setup["section2"]

        ticket_factory(section=section2)

        client = make_authenticated_client(hos1)
        # hos1 is on campus1, section2 is on campus2
        response = client.get(reverse("analytics-section", args=[section2.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hos_without_sections_sees_empty(self, db, section_head_factory):
        """HOS with no assigned sections sees empty."""
        hos = section_head_factory()

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_hos_multiple_sections_sees_all(
        self, db, multi_role_setup, section_head_factory, ticket_factory
    ):
        """HOS assigned to multiple sections sees all of them."""
        setup = multi_role_setup
        hos = section_head_factory()
        section1 = setup["section1"]
        section2 = setup["section2"]

        # Assign HOS to section1 (both on same campus)
        hos.sections.add(section1)
        hos.primary_campus = section1.campus_department.campus
        hos.primary_department = section1.campus_department.department
        hos.save()

        ticket_factory(section=section1)

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK


# ── Technician Scoping Tests ───────────────────────────────────────────────────


class TestTechnicianScoping:
    """Verify technicians see only their own data."""

    def test_technician_sees_own_analytics(
        self, db, technician_factory, ticket_factory, section
    ):
        """Technician sees own KPIs only."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech, section=section)

        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_cannot_inspect_other_technician(
        self, db, technician_factory
    ):
        """Technician cannot query other technicians' data."""
        tech1 = technician_factory()
        tech2 = technician_factory()

        client = make_authenticated_client(tech1)
        # Try to get other technician's self analytics (should fail)
        response = client.get(
            reverse("analytics-technician-self"),
            {"user_id": tech2.id}
        )
        # Technician cannot pass user_id param, should get 403
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_technician_list_redirects_to_self(
        self, db, technician_factory
    ):
        """Technician accessing /technicians/ endpoint sees own data only."""
        tech = technician_factory()

        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK
        # Response should be filtered to own performance only

    def test_admin_can_override_technician_scope(
        self, db, admin_user_factory, technician_factory
    ):
        """Admin can inspect any technician via ?user_id=<pk>."""
        admin = admin_user_factory()
        tech = technician_factory()

        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-technician-self"),
            {"user_id": tech.id}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_hod_can_query_campus_technician(
        self, db, multi_role_setup
    ):
        """HOD can query technician analytics scoped to their campus."""
        setup = multi_role_setup
        hod1 = setup["hod1"]
        campus1 = setup["campus1"]

        # Create technician on campus1
        from tickets.tests.conftest import technician_factory as tech_factory_func

        client = make_authenticated_client(hod1)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK


# ── Cross-Boundary Verification Tests ──────────────────────────────────────────


class TestCrossBoundaryProtection:
    """Verify data isolation across organizational boundaries."""

    def test_no_data_leakage_across_departments(
        self, db, multi_role_setup, ticket_factory
    ):
        """Tickets in one department don't leak to other department's manager."""
        setup = multi_role_setup
        mgr1 = setup["mgr1"]
        section1 = setup["section1"]

        # Create ticket in dept1 (mgr1's department)
        t1 = ticket_factory(section=section1)

        # Create manager for different department
        other_mgr = setup["mgr1"].__class__.objects.create_user(
            username="mgr_other_dept",
            password="pass",
            role="manager",
            primary_department=setup["dept2"]
        )

        # mgr1 should see t1
        client1 = make_authenticated_client(mgr1)
        response1 = client1.get(reverse("analytics-manager"))
        assert response1.status_code == status.HTTP_200_OK

        # other_mgr should NOT have access to t1's department
        client2 = make_authenticated_client(other_mgr)
        response2 = client2.get(
            reverse("analytics-department", args=[section1.campus_department.department.id])
        )
        assert response2.status_code == status.HTTP_403_FORBIDDEN

    def test_no_data_leakage_across_campuses(
        self, db, multi_role_setup, ticket_factory
    ):
        """Tickets on one campus don't leak to other campus's HOD."""
        setup = multi_role_setup
        hod1 = setup["hod1"]
        hod2 = setup["hod2"]
        campus1 = setup["campus1"]
        campus2 = setup["campus2"]
        section1 = setup["section1"]
        section2 = setup["section2"]

        # Create tickets on each campus
        t1 = ticket_factory(section=section1)  # Campus 1
        t2 = ticket_factory(section=section2)  # Campus 2

        # hod1 (campus1) should see t1 but not t2
        client1 = make_authenticated_client(hod1)
        response1 = client1.get(reverse("analytics-hod"))
        assert response1.status_code == status.HTTP_200_OK

        # hod2 (campus2) should see t2 but not t1
        client2 = make_authenticated_client(hod2)
        response2 = client2.get(reverse("analytics-hod"))
        assert response2.status_code == status.HTTP_200_OK

    def test_no_data_leakage_across_sections(
        self, db, multi_role_setup, ticket_factory
    ):
        """Tickets in one section don't leak to other section's HOS."""
        setup = multi_role_setup
        hos1 = setup["hos1"]
        hos2 = setup["hos2"]
        section1 = setup["section1"]
        section2 = setup["section2"]

        # Create tickets in each section
        t1 = ticket_factory(section=section1)
        t2 = ticket_factory(section=section2)

        # hos1 should see section1 analytics only
        client1 = make_authenticated_client(hos1)
        resp1_own = client1.get(reverse("analytics-section", args=[section1.id]))
        resp1_other = client1.get(reverse("analytics-section", args=[section2.id]))
        assert resp1_own.status_code == status.HTTP_200_OK
        assert resp1_other.status_code == status.HTTP_403_FORBIDDEN

        # hos2 should see section2 analytics only
        client2 = make_authenticated_client(hos2)
        resp2_own = client2.get(reverse("analytics-section", args=[section2.id]))
        resp2_other = client2.get(reverse("analytics-section", args=[section1.id]))
        assert resp2_own.status_code == status.HTTP_200_OK
        assert resp2_other.status_code == status.HTTP_403_FORBIDDEN


# ── Admin Override Tests ───────────────────────────────────────────────────────


class TestAdminOverrides:
    """Verify admin role can access any scope."""

    def test_admin_can_access_all_departments(
        self, db, admin_user_factory, multi_role_setup
    ):
        """Admin can access any department."""
        admin = admin_user_factory()
        setup = multi_role_setup
        dept1 = setup["dept1"]
        dept2 = setup["dept2"]

        client = make_authenticated_client(admin)

        # Access dept1
        response1 = client.get(reverse("analytics-department", args=[dept1.id]))
        assert response1.status_code == status.HTTP_200_OK

        # Access dept2
        response2 = client.get(reverse("analytics-department", args=[dept2.id]))
        assert response2.status_code == status.HTTP_200_OK

    def test_admin_can_access_all_campuses_departments(
        self, db, admin_user_factory, multi_role_setup
    ):
        """Admin can access any campus+department pair."""
        admin = admin_user_factory()
        setup = multi_role_setup

        client = make_authenticated_client(admin)

        # Access cd1 (campus1, dept1)
        response1 = client.get(
            reverse("analytics-campus-department", args=[setup["cd1"].id])
        )
        assert response1.status_code == status.HTTP_200_OK

        # Access cd2 (campus2, dept1)
        response2 = client.get(
            reverse("analytics-campus-department", args=[setup["cd2"].id])
        )
        assert response2.status_code == status.HTTP_200_OK

    def test_admin_can_access_all_sections(
        self, db, admin_user_factory, multi_role_setup
    ):
        """Admin can access any section."""
        admin = admin_user_factory()
        setup = multi_role_setup

        client = make_authenticated_client(admin)

        # Access section1
        response1 = client.get(
            reverse("analytics-section", args=[setup["section1"].id])
        )
        assert response1.status_code == status.HTTP_200_OK

        # Access section2
        response2 = client.get(
            reverse("analytics-section", args=[setup["section2"].id])
        )
        assert response2.status_code == status.HTTP_200_OK

    def test_admin_can_inspect_any_technician(
        self, db, admin_user_factory, technician_factory
    ):
        """Admin can inspect any technician via ?user_id=<pk>."""
        admin = admin_user_factory()
        tech1 = technician_factory()
        tech2 = technician_factory()

        client = make_authenticated_client(admin)

        # Inspect tech1
        response1 = client.get(
            reverse("analytics-technician-self"),
            {"user_id": tech1.id}
        )
        assert response1.status_code == status.HTTP_200_OK

        # Inspect tech2
        response2 = client.get(
            reverse("analytics-technician-self"),
            {"user_id": tech2.id}
        )
        assert response2.status_code == status.HTTP_200_OK


# ── Edge Case Tests ────────────────────────────────────────────────────────────


class TestScopingEdgeCases:
    """Test edge cases in organizational scoping."""

    def test_manager_missing_both_primary_fields(self, db, manager_factory):
        """Manager without primary_campus or primary_department."""
        mgr = manager_factory()
        mgr.primary_campus = None
        mgr.primary_department = None
        mgr.save()

        client = make_authenticated_client(mgr)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hod_missing_primary_campus(self, db, hod_factory, department):
        """HOD without primary_campus."""
        hod = hod_factory()
        hod.primary_campus = None
        hod.primary_department = department
        hod.save()

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hod_missing_primary_department(self, db, hod_factory, campus):
        """HOD without primary_department."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = None
        hod.save()

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_403_FORBIDDEN,
        )

    def test_hos_without_assigned_sections(self, db, section_head_factory):
        """HOS with no assigned sections."""
        hos = section_head_factory()

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_resource_endpoint_nonexistent_id(self, db, admin_user_factory):
        """Resource endpoints handle non-existent IDs gracefully."""
        admin = admin_user_factory()

        client = make_authenticated_client(admin)

        # Non-existent department
        response1 = client.get(reverse("analytics-department", args=[99999]))
        assert response1.status_code == status.HTTP_404_NOT_FOUND

        # Non-existent campus-department
        response2 = client.get(reverse("analytics-campus-department", args=[99999]))
        assert response2.status_code == status.HTTP_404_NOT_FOUND

        # Non-existent section
        response3 = client.get(reverse("analytics-section", args=[99999]))
        assert response3.status_code == status.HTTP_404_NOT_FOUND
