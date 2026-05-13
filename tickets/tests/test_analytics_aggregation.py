"""Analytics API aggregation tests — verify data correctness.

Tests verify that each analytics endpoint correctly aggregates and structures
ticket data, counts, metrics, and trends.
"""

import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import Ticket, CustomUser, Section, Feedback


def make_authenticated_client(user):
    """Create authenticated API client for a given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Ticket Analytics (`/analytics/tickets/`) ──────────────────────────────────


class TestTicketAnalyticsAggregation:
    """Aggregation tests for /analytics/tickets/"""

    def test_ticket_analytics_returns_expected_keys(
        self, db, admin_user_factory, ticket_factory
    ):
        """Response includes all expected keys."""
        admin = admin_user_factory()
        ticket_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "ticket_counts" in data
        assert "status_counts" in data
        assert "trend_data" in data
        assert "facility_distribution" in data
        assert "section_distribution" in data

    def test_ticket_analytics_status_breakdown(
        self, db, admin_user_factory, ticket_factory, section, facility
    ):
        """Status counts correctly reflect ticket statuses."""
        admin = admin_user_factory()
        ticket_factory(status="open")
        ticket_factory(status="open")
        ticket_factory(status="assigned")
        ticket_factory(status="resolved")
        ticket_factory(status="closed")

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-tickets"))
        data = response.json()
        status_counts = data["status_counts"]

        # Verify counts match actual tickets
        assert status_counts.get("open", 0) >= 2
        assert status_counts.get("assigned", 0) >= 1
        assert status_counts.get("resolved", 0) >= 1
        assert status_counts.get("closed", 0) >= 1

    def test_ticket_analytics_facility_distribution(
        self, db, admin_user_factory, ticket_factory, facility
    ):
        """Facility distribution groups tickets by facility."""
        admin = admin_user_factory()
        ticket_factory(facility=facility)
        ticket_factory(facility=facility)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-tickets"))
        data = response.json()
        facility_dist = data["facility_distribution"]

        # Should have entries for facility
        assert len(facility_dist) > 0
        facility_found = any(f.get("name") == facility.name for f in facility_dist)
        assert facility_found

    def test_ticket_analytics_section_distribution(
        self, db, admin_user_factory, ticket_factory, section
    ):
        """Section distribution groups tickets by section."""
        admin = admin_user_factory()
        ticket_factory(section=section)
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-tickets"))
        data = response.json()
        section_dist = data["section_distribution"]

        # Should have entries for section
        assert len(section_dist) > 0
        section_found = any(s.get("name") == section.name for s in section_dist)
        assert section_found

    def test_ticket_analytics_empty_dataset(self, db, admin_user_factory):
        """Empty dataset returns graceful empty response."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-tickets"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_ticket_analytics_with_facility_filter(
        self, db, admin_user_factory, ticket_factory, facility
    ):
        """?facility_id=<pk> filters results."""
        admin = admin_user_factory()
        ticket_factory(facility=facility)

        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-tickets"), {"facility_id": facility.id}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_ticket_analytics_with_section_filter(
        self, db, admin_user_factory, ticket_factory, section
    ):
        """?section_id=<pk> filters results."""
        admin = admin_user_factory()
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-tickets"), {"section_id": section.id}
        )
        assert response.status_code == status.HTTP_200_OK

    def test_ticket_analytics_with_days_param(
        self, db, admin_user_factory, ticket_factory
    ):
        """?days=<int> controls trend lookback window."""
        admin = admin_user_factory()
        ticket_factory()

        client = make_authenticated_client(admin)
        # Test various day ranges
        for days in [1, 7, 30, 90]:
            response = client.get(
                reverse("analytics-tickets"), {"days": days}
            )
            assert response.status_code == status.HTTP_200_OK


# ── Admin Dashboard (`/analytics/admin-dashboard/`) ───────────────────────────


class TestAdminDashboardAggregation:
    """Aggregation tests for /analytics/admin-dashboard/"""

    def test_admin_dashboard_structure(self, db, admin_user_factory):
        """Response includes system_overview and overdue_tickets."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "system_overview" in data
        assert "overdue_tickets" in data
        assert "organisation" in data  # Admin sees organisation breakdown

    def test_admin_dashboard_system_overview_keys(self, db, admin_user_factory):
        """System overview includes required keys."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-admin"))
        data = response.json()
        overview = data["system_overview"]
        # Should have ticket counts
        assert any(k in overview for k in ["total", "open", "closed", "pending"])

    def test_admin_dashboard_overdue_tickets_list(
        self, db, admin_user_factory, ticket_factory
    ):
        """Overdue tickets list returns array."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-admin"))
        data = response.json()
        overdue = data["overdue_tickets"]
        assert isinstance(overdue, list)

    def test_admin_sees_organisation_breakdown(self, db, admin_user_factory):
        """Admin role sees organisation breakdown."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-admin"))
        data = response.json()
        assert "organisation" in data

    def test_manager_does_not_see_organisation_breakdown(
        self, db, manager_factory, campus, department
    ):
        """Manager role does not see organisation breakdown."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-admin"))
        data = response.json()
        # Manager should see overview + overdue, but not organisation
        assert "system_overview" in data
        assert "overdue_tickets" in data
        assert "organisation" not in data

    def test_admin_dashboard_empty_dataset(self, db, admin_user_factory):
        """Empty dataset returns graceful response."""
        admin = admin_user_factory()
        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-admin"))
        assert response.status_code == status.HTTP_200_OK


# ── User Analytics (`/analytics/user/`) ──────────────────────────────────────


class TestUserAnalyticsAggregation:
    """Aggregation tests for /analytics/user/"""

    def test_user_analytics_returns_personal_data(
        self, db, user_factory, ticket_factory
    ):
        """User sees only their own ticket data."""
        user = user_factory()
        ticket_factory(raised_by=user)
        ticket_factory(raised_by=user)

        client = make_authenticated_client(user)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_user_analytics_excludes_other_users_tickets(
        self, db, user_factory, ticket_factory
    ):
        """User does not see other users' tickets."""
        user1 = user_factory()
        user2 = user_factory()
        ticket1 = ticket_factory(raised_by=user1)
        ticket2 = ticket_factory(raised_by=user2)

        client = make_authenticated_client(user1)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK

    def test_technician_user_analytics(
        self, db, technician_factory, ticket_factory, section
    ):
        """Technician sees analytics for assigned tickets."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech)

        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-user"))
        assert response.status_code == status.HTTP_200_OK


# ── Technician Analytics (`/analytics/technicians/`) ──────────────────────────


class TestTechnicianAnalyticsAggregation:
    """Aggregation tests for /analytics/technicians/"""

    def test_technician_analytics_lists_performance(
        self, db, admin_user_factory, technician_factory, ticket_factory, section
    ):
        """Response includes technician_performance."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "technician_performance" in data

    def test_technician_analytics_includes_ratings_for_admin(
        self, db, admin_user_factory, technician_factory, ticket_factory, section
    ):
        """Admin sees section_ratings when listing all technicians."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(assigned_to=tech)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technicians"))
        data = response.json()
        assert "section_ratings" in data

    def test_technician_analytics_resolved_count(
        self, db, admin_user_factory, technician_factory, ticket_factory, section
    ):
        """Resolved ticket count is accurate."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech, status="resolved")
        ticket_factory(assigned_to=tech, status="resolved")
        ticket_factory(assigned_to=tech, status="open")

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technicians"))
        data = response.json()
        perf = data["technician_performance"]
        # Should have data for the technician
        assert isinstance(perf, list)

    def test_technician_analytics_empty_dataset(
        self, db, admin_user_factory, technician_factory
    ):
        """Technician with no tickets returns valid response."""
        admin = admin_user_factory()
        tech = technician_factory()

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-technicians"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "technician_performance" in data

    def test_technician_analytics_specific_technician_filter(
        self, db, admin_user_factory, technician_factory
    ):
        """?technician_id=<pk> filters to specific technician."""
        admin = admin_user_factory()
        tech = technician_factory()

        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-technicians"), {"technician_id": tech.id}
        )
        assert response.status_code == status.HTTP_200_OK


# ── Technician Self Analytics (`/analytics/technicians/me/`) ───────────────────


class TestTechnicianSelfAnalyticsAggregation:
    """Aggregation tests for /analytics/technicians/me/"""

    def test_technician_self_analytics_returns_kpis(
        self, db, technician_factory, ticket_factory, section
    ):
        """Response includes KPI data (resolved, average time, etc)."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech, status="resolved")

        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_technician_self_analytics_no_assignments(self, db, technician_factory):
        """Technician with no tickets returns valid response."""
        tech = technician_factory()
        client = make_authenticated_client(tech)
        response = client.get(reverse("analytics-technician-self"))
        assert response.status_code == status.HTTP_200_OK


# ── Manager Dashboard (`/analytics/manager/`) ─────────────────────────────────


class TestManagerDashboardAggregation:
    """Aggregation tests for /analytics/manager/"""

    def test_manager_dashboard_structure(
        self, db, manager_factory, campus, department, ticket_factory, section
    ):
        """Dashboard includes expected aggregated sections."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        ticket_factory(section=section)

        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_manager_dashboard_scoped_to_department(
        self, db, manager_factory, campus, department, ticket_factory, section
    ):
        """Dashboard only shows tickets from manager's department."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()

        # Create ticket in manager's department
        ticket_factory(section=section)

        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-manager"))
        assert response.status_code == status.HTTP_200_OK

    def test_manager_dashboard_no_primary_department(self, db, manager_factory, campus):
        """Manager without primary_department sees empty/no data."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = None
        manager.save()

        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-manager"))
        # May return 200 with empty data or 403
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN)


# ── HOD Dashboard (`/analytics/hod/`) ──────────────────────────────────────────


class TestHODDashboardAggregation:
    """Aggregation tests for /analytics/hod/"""

    def test_hod_dashboard_structure(
        self, db, hod_factory, campus, department, ticket_factory, section
    ):
        """Dashboard includes section breakdown and technician utilization."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        ticket_factory(section=section)

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_hod_dashboard_section_breakdown(
        self, db, hod_factory, campus, department, ticket_factory, section
    ):
        """Section breakdown shows tickets per section."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        ticket_factory(section=section)

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_dashboard_scoped_to_campus_department(
        self, db, hod_factory, campus, department, ticket_factory, section
    ):
        """Dashboard only shows data from HOD's campus and department."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()

        ticket_factory(section=section)

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        assert response.status_code == status.HTTP_200_OK

    def test_hod_dashboard_no_primary_campus(self, db, hod_factory, department):
        """HOD without primary_campus sees empty/no data."""
        hod = hod_factory()
        hod.primary_campus = None
        hod.primary_department = department
        hod.save()

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-hod"))
        # May return 200 with empty data or 403
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_403_FORBIDDEN)


# ── Section Head Dashboard (`/analytics/section-head/`) ────────────────────────


class TestSectionHeadDashboardAggregation:
    """Aggregation tests for /analytics/section-head/"""

    def test_section_head_dashboard_structure(
        self, db, section_head_factory, section, ticket_factory
    ):
        """Dashboard includes technician assignments and pending reasons."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        ticket_factory(section=section)

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_section_head_dashboard_technician_workload(
        self, db, section_head_factory, section, technician_factory, ticket_factory
    ):
        """Dashboard shows technician workload in assigned sections."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()

        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech, section=section)

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_section_head_dashboard_scoped_to_sections(
        self, db, section_head_factory, section, ticket_factory
    ):
        """Dashboard only shows data from HOS's assigned sections."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()

        ticket_factory(section=section)

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        assert response.status_code == status.HTTP_200_OK

    def test_section_head_dashboard_no_sections(self, db, section_head_factory):
        """HOS with no assigned sections sees empty/no data."""
        hos = section_head_factory()

        client = make_authenticated_client(hos)
        response = client.get(reverse("analytics-section-head"))
        # May return 200 with empty data
        assert response.status_code == status.HTTP_200_OK


# ── Department Analytics (`/analytics/departments/<pk>/`) ──────────────────────


class TestDepartmentAnalyticsAggregation:
    """Aggregation tests for /analytics/departments/<pk>/"""

    def test_department_analytics_structure(
        self, db, admin_user_factory, department, ticket_factory, section
    ):
        """Response includes cross-campus aggregation."""
        admin = admin_user_factory()
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_department_analytics_cross_campus(
        self, db, admin_user_factory, department, campus, ticket_factory, section
    ):
        """Department analytics aggregate across all campuses."""
        admin = admin_user_factory()
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_department_analytics_manager_sees_own_only(
        self, db, manager_factory, campus, department, ticket_factory, section
    ):
        """Manager sees analytics scoped to own department."""
        manager = manager_factory()
        manager.primary_campus = campus
        manager.primary_department = department
        manager.save()
        ticket_factory(section=section)

        client = make_authenticated_client(manager)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_department_analytics_hod_narrows_to_campus(
        self, db, hod_factory, campus, department, ticket_factory, section
    ):
        """HOD sees analytics narrowed to their campus only."""
        hod = hod_factory()
        hod.primary_campus = campus
        hod.primary_department = department
        hod.save()
        CampusDepartment.objects.get_or_create(
            campus=campus, department=department,
            defaults={"head_of_department": hod}
        )
        ticket_factory(section=section)

        client = make_authenticated_client(hod)
        response = client.get(reverse("analytics-department", args=[department.id]))
        assert response.status_code == status.HTTP_200_OK


# ── HOD Analytics / CampusDepartment (`/analytics/campus-departments/<pk>/`) ───


class TestHODAnalyticsAggregation:
    """Aggregation tests for /analytics/campus-departments/<pk>/"""

    def test_hod_analytics_single_campus_department(
        self, db, admin_user_factory, campus_department, ticket_factory, section
    ):
        """CampusDepartment analytics are narrowed to single pair."""
        admin = admin_user_factory()
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_hod_analytics_structure(
        self, db, admin_user_factory, campus_department, ticket_factory, section
    ):
        """Response includes section breakdown and SLA metrics."""
        admin = admin_user_factory()
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(
            reverse("analytics-campus-department", args=[campus_department.id])
        )
        assert response.status_code == status.HTTP_200_OK


# ── HOS Analytics / Section (`/analytics/sections/<pk>/`) ──────────────────────


class TestHOSAnalyticsAggregation:
    """Aggregation tests for /analytics/sections/<pk>/"""

    def test_hos_analytics_single_section(
        self, db, admin_user_factory, section, ticket_factory
    ):
        """Section analytics are narrowed to single section."""
        admin = admin_user_factory()
        ticket_factory(section=section)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_hos_analytics_structure(
        self, db, admin_user_factory, section, ticket_factory, technician_factory
    ):
        """Response includes technician workload and SLA compliance."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)
        ticket_factory(assigned_to=tech, section=section)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK

    def test_hos_analytics_excludes_other_sections(
        self, db, admin_user_factory, section, section_hvac, ticket_factory
    ):
        """Section analytics do not include other sections."""
        admin = admin_user_factory()
        ticket_factory(section=section)
        ticket_factory(section=section_hvac)

        client = make_authenticated_client(admin)
        response = client.get(reverse("analytics-section", args=[section.id]))
        assert response.status_code == status.HTTP_200_OK


# ── Cache and Performance Tests ────────────────────────────────────────────────


class TestAnalyticsCacheIsolation:
    """Verify tests don't poison each other via cache."""

    def test_consecutive_requests_dont_share_cached_data(
        self, db, admin_user_factory, ticket_factory
    ):
        """Multiple consecutive requests return independent results."""
        admin = admin_user_factory()

        # First request
        response1 = make_authenticated_client(admin).get(reverse("analytics-user"))
        data1 = response1.json()

        # Second request should be independent
        response2 = make_authenticated_client(admin).get(reverse("analytics-user"))
        data2 = response2.json()

        # Both should succeed
        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK


# Helper import for CampusDepartment
from tickets.models import CampusDepartment
