"""Analytics API permission tests — verify role-based access control.

Tests verify that each analytics endpoint correctly gates access by role
and returns 403 for unauthorized users.
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import CampusDepartment, CustomUser, Department, Section


@pytest.fixture
def api_client_unauthenticated():
    """Unauthenticated API client."""
    return APIClient()


def make_authenticated_client(user):
    """Create authenticated API client for a given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Ticket Analytics (`/analytics/tickets/`) ──────────────────────────────────


class TestTicketAnalyticsPermissions:
    """Permission tests for /analytics/tickets/"""

    def test_admin_can_access_ticket_analytics(self, db, admin_user_factory):
        """Admin can access ticket analytics."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_ticket_analytics(self, db, manager_factory, campus, department):
        """Manager can access ticket analytics."""
        manager = manager_factory(username="mgr_analytics")
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_denied_ticket_analytics(self, db, technician_factory):
        """Technician receives 403 for ticket analytics."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_denied_ticket_analytics(self, db, hod_factory, campus, department):
        """HOD receives 403 for ticket analytics."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_head_of_section_denied_ticket_analytics(self, db, section_head_factory, section):
        """Head of Section receives 403 for ticket analytics."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_ticket_analytics(self, db, user_factory):
        """Regular user receives 403 for ticket analytics."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_ticket_analytics(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Admin Dashboard (`/analytics/admin-dashboard/`) ───────────────────────────


class TestAdminDashboardPermissions:
    """Permission tests for /analytics/admin-dashboard/"""

    def test_admin_can_access_admin_dashboard(self, db, admin_user_factory):
        """Admin can access admin dashboard."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_admin_dashboard(self, db, manager_factory, campus, department):
        """Manager can access admin dashboard (subset view)."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_denied_admin_dashboard(self, db, technician_factory):
        """Technician receives 403 for admin dashboard."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_denied_admin_dashboard(self, db, hod_factory, campus, department):
        """HOD receives 403 for admin dashboard."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_admin_dashboard(self, db, user_factory):
        """Regular user receives 403 for admin dashboard."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── User Analytics (`/analytics/user/`) ──────────────────────────────────────


class TestUserAnalyticsPermissions:
    """Permission tests for /analytics/user/ — all authenticated users can access."""

    def test_admin_can_access_user_analytics(self, db, admin_user_factory):
        """Admin can access user analytics."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_user_analytics(self, db, manager_factory, campus, department):
        """Manager can access user analytics."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_can_access_user_analytics(self, db, hod_factory, campus, department):
        """HOD can access user analytics."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_can_access_user_analytics(self, db, technician_factory):
        """Technician can access user analytics."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_head_of_section_can_access_user_analytics(self, db, section_head_factory, section):
        """Head of Section can access user analytics."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_user_can_access_user_analytics(self, db, user_factory):
        """Regular user can access user analytics."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_unauthenticated_denied_user_analytics(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Technician Analytics (`/analytics/technicians/`) ──────────────────────────


class TestTechnicianAnalyticsPermissions:
    """Permission tests for /analytics/technicians/"""

    def test_admin_can_access_all_technicians(self, db, admin_user_factory, technician_factory):
        """Admin can access all technician analytics."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_inspect_specific_technician(
        self, db, admin_user_factory, technician_factory
    ):
        """Admin can pass ?technician_id=<pk> to inspect specific technician."""
        admin = admin_user_factory()
        tech = technician_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technicians"), {"technician_id": tech.id})
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_technician_analytics(self, db, manager_factory, campus, department):
        """Manager can access technician analytics (cross-department)."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_can_access_campus_technicians(self, db, hod_factory, campus, department):
        """HOD can access technician analytics scoped to their campus."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_cannot_inspect_other_campus_technician(
        self, db, hod_factory, technician_factory, campus, department
    ):
        """HOD cannot access technician from different campus."""
        from tickets.models import Campus as CampusModel
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()

        # Create tech on a different campus
        campus2 = CampusModel.objects.create(name="Other Campus", code="OTH", location="Other")
        tech = technician_factory()
        tech.primary_campus = campus2
        tech.save()

        client = make_authenticated_client(hod)
        response = client.get(
            reverse("analytics-technicians"), {"technician_id": tech.id}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_technician_redirects_to_self_analytics(self, db, technician_factory):
        """Technician calling /technicians/ sees own data only."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK
        # Response should be filtered to own data

    def test_user_denied_technician_analytics(self, db, user_factory):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_technician_analytics(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Technician Self Analytics (`/analytics/technicians/me/`) ───────────────────


class TestTechnicianSelfAnalyticsPermissions:
    """Permission tests for /analytics/technicians/me/"""

    def test_technician_can_access_self_analytics(self, db, technician_factory):
        """Technician can access own analytics."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_inspect_any_technician(
        self, db, admin_user_factory, technician_factory
    ):
        """Admin can pass ?user_id=<pk> to inspect any technician."""
        admin = admin_user_factory()
        tech = technician_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technician-self"), {"user_id": tech.id})
        assert response.status_code == status.HTTP_200_OK

    def test_admin_not_found_for_invalid_technician(self, db, admin_user_factory):
        """Admin gets 404 for non-existent technician."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technician-self"), {"user_id": 99999})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_manager_denied_self_analytics(self, db, manager_factory, campus, department):
        """Manager receives 403."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_denied_self_analytics(self, db, hod_factory, campus, department):
        """HOD receives 403."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_self_analytics(self, db, user_factory):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_self_analytics(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Manager Dashboard (`/analytics/manager/`) ─────────────────────────────────


class TestManagerDashboardPermissions:
    """Permission tests for /analytics/manager/"""

    def test_manager_can_access_dashboard(self, db, manager_factory, campus, department):
        """Manager can access own dashboard."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_access_manager_dashboard(self, db, admin_user_factory):
        """Admin can access manager dashboard."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_denied_manager_dashboard(self, db, technician_factory):
        """Technician receives 403."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_denied_manager_dashboard(self, db, hod_factory, campus, department):
        """HOD receives 403."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_manager_dashboard(self, db, user_factory):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_manager_dashboard(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── HOD Dashboard (`/analytics/hod/`) ──────────────────────────────────────────


class TestHODDashboardPermissions:
    """Permission tests for /analytics/hod/"""

    def test_hod_can_access_dashboard(self, db, hod_factory, campus, department):
        """HOD can access own dashboard."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_access_hod_dashboard(self, db, admin_user_factory):
        """Admin can access HOD dashboard."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_denied_hod_dashboard(self, db, technician_factory):
        """Technician receives 403."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_denied_hod_dashboard(self, db, manager_factory, campus, department):
        """Manager receives 403."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_hod_dashboard(self, db, user_factory):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_hod_dashboard(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Section Head Dashboard (`/analytics/section-head/`) ────────────────────────


class TestSectionHeadDashboardPermissions:
    """Permission tests for /analytics/section-head/"""

    def test_head_of_section_can_access_dashboard(self, db, section_head_factory, section):
        """Head of Section can access own dashboard."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_admin_can_access_section_head_dashboard(self, db, admin_user_factory):
        """Admin can access section head dashboard."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_denied_section_head_dashboard(self, db, technician_factory):
        """Technician receives 403."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manager_denied_section_head_dashboard(self, db, manager_factory, campus, department):
        """Manager receives 403."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_denied_section_head_dashboard(self, db, hod_factory, campus, department):
        """HOD receives 403."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_section_head_dashboard(self, db, user_factory):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_denied_section_head_dashboard(self, api_client_unauthenticated):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── Department Analytics (`/analytics/departments/<pk>/`) ──────────────────────


class TestDepartmentAnalyticsPermissions:
    """Permission tests for /analytics/departments/<pk>/"""

    def test_admin_can_access_any_department(self, db, admin_user_factory, department):
        """Admin can access any department."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_own_department(
        self, db, manager_factory, campus, department
    ):
        """Manager can access only their own department."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_cannot_access_other_department(
        self, db, manager_factory, campus, department
    ):
        """Manager cannot access other departments."""
        from tickets.models import Department as DeptModel
        other_dept = DeptModel.objects.create(name="Other Dept", code="OTHDPT")
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-department", args=[other_dept.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hod_can_access_own_campus_department(
        self, db, hod_factory, campus, department
    ):
        """HOD can access department on their campus."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        # Ensure department is on HOD's campus
        CampusDepartment.objects.get_or_create(
            campus=campus, department=department,
            defaults={"head_of_department": hod}
        )
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_denied_department_analytics(self, db, technician_factory, department):
        """Technician receives 403."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_department_analytics(self, db, user_factory, department):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_department_returns_404(self, db, admin_user_factory):
        """Non-existent department returns 404."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-department", args=[99999]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_denied_department_analytics(
        self, api_client_unauthenticated, department
    ):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(
            reverse("analytics-department", args=[department.id])
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── HOD Analytics / CampusDepartment (`/analytics/campus-departments/<pk>/`) ───


class TestHODAnalyticsPermissions:
    """Permission tests for /analytics/campus-departments/<pk>/"""

    def test_admin_can_access_any_campus_department(self, db, admin_user_factory, campus_department):
        """Admin can access any CampusDepartment."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_own_department_campus_department(
        self, db, manager_factory, campus_department
    ):
        """Manager can access CampusDepartment with their department."""
        manager = manager_factory()
        manager.primary_campus = campus_department.campus
        manager.primary_department = campus_department.department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_200_OK

    def test_hod_can_access_assigned_campus_department(
        self, db, hod_factory, campus_department
    ):
        """HOD can access CampusDepartment they are assigned to head."""
        hod = hod_factory()
        campus_department.head_of_department = hod
        campus_department.save()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_200_OK

    def test_hod_cannot_access_unassigned_campus_department(
        self, db, hod_factory, campus_department
    ):
        """HOD cannot access CampusDepartment they don't head (even on same campus)."""
        hod = hod_factory()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        # Hod is not the head_of_department
        client = make_authenticated_client(hod)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_technician_denied_campus_department_analytics(
        self, db, technician_factory, campus_department
    ):
        """Technician receives 403."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_campus_department_returns_404(self, db, admin_user_factory):
        """Non-existent CampusDepartment returns 404."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-campus-department", args=[99999]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_denied_campus_department_analytics(
        self, api_client_unauthenticated, campus_department
    ):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ── HOS Analytics / Section (`/analytics/sections/<pk>/`) ──────────────────────


class TestHOSAnalyticsPermissions:
    """Permission tests for /analytics/sections/<pk>/"""

    def test_admin_can_access_any_section(self, db, admin_user_factory, section):
        """Admin can access any Section."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_can_access_own_department_section(
        self, db, manager_factory, section
    ):
        """Manager can access Sections under their department."""
        manager = manager_factory()
        manager.primary_campus = section.campus_department.campus
        manager.primary_department = section.campus_department.department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_can_access_own_campus_department_section(
        self, db, hod_factory, section
    ):
        """HOD can access Sections under their CampusDepartment."""
        hod = hod_factory()
        hod.primary_campus = section.campus_department.campus
        hod.primary_department = section.campus_department.department
        hod.save()
        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_head_of_section_can_access_owned_section(
        self, db, section_head_factory, section
    ):
        """HOS can access Sections they head."""
        hos = section_head_factory()
        section.head_of_section = hos
        section.save()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_head_of_section_cannot_access_other_section(
        self, db, section_head_factory, section, section_hvac
    ):
        """HOS cannot access Sections they don't head."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        client = make_authenticated_client(hos)
        # section_hvac is a different section not headed by this HOS
        response = client.get(reverse("analytics-section", args=[section_hvac.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_technician_denied_section_analytics(self, db, technician_factory, section):
        """Technician receives 403."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_denied_section_analytics(self, db, user_factory, section):
        """Regular user receives 403."""
        user = user_factory()
        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_nonexistent_section_returns_404(self, db, admin_user_factory):
        """Non-existent Section returns 404."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-section", args=[99999]))
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_denied_section_analytics(
        self, api_client_unauthenticated, section
    ):
        """Unauthenticated user receives 401."""
        response = api_client_unauthenticated.get(
            reverse("analytics-section", args=[section.id])
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
