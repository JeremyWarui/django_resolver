"""
Pytest version of test_analytics.py - Analytics functionality tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from tickets.api.analytics.analytics import (
    TicketAnalytics,
    TechnicianAnalytics,
    AdminAnalytics,
    OrganizationalAnalytics,
)
from tickets.models import (
    Ticket,
    CustomUser,
    Feedback,
    Section,
    Facility,
    Organization,
    Campus,
    Department,
)

# Import analytics classes for testing
from tickets.api.analytics.analytics import TechnicianAnalytics


@pytest.fixture
def analytics_setup(db, user_factory, technician_factory):
    """Create test data for analytics tests"""
    # Create sections
    section1 = Section.objects.create(name="IT", description="IT Department")
    section2 = Section.objects.create(
        name="Plumbing", description="Plumbing Department"
    )

    # Create facilities
    facility1 = Facility.objects.create(
        name="Building A", type="building", location="North Campus"
    )
    facility2 = Facility.objects.create(
        name="Building B", type="building", location="South Campus"
    )

    # Create users
    admin = CustomUser.objects.create_user(
        username="admin",
        password="password",
        role="admin",
        first_name="Admin",
        last_name="User",
    )

    tech1 = technician_factory(username="tech1", first_name="Tech", last_name="One")
    tech1.sections.add(section1)

    tech2 = technician_factory(username="tech2", first_name="Tech", last_name="Two")
    tech2.sections.add(section2)

    user = user_factory(username="user", first_name="Regular", last_name="User")

    return {
        "section1": section1,
        "section2": section2,
        "facility1": facility1,
        "facility2": facility2,
        "admin": admin,
        "tech1": tech1,
        "tech2": tech2,
        "user": user,
    }


@pytest.fixture
def organizational_analytics_setup(
    db,
    org_aware_user_factory,
    technician_factory,
    hod_factory,
    director_factory,
    section_head_factory,
):
    """Create test data for organizational role-based analytics"""
    # Create organizational hierarchy
    org = Organization.objects.create(
        name="Test Corp", code="TCORP", organization_type="corporate"
    )
    campus1 = Campus.objects.create(
        name="Main Campus", code="MAIN", organization=org, location="Downtown"
    )
    campus2 = Campus.objects.create(
        name="West Campus", code="WEST", organization=org, location="West Side"
    )
    dept_it = Department.objects.create(name="IT Department", code="IT", campus=campus1)
    dept_facilities = Department.objects.create(
        name="Facilities", code="FAC", campus=campus1
    )
    section_network = Section.objects.create(
        name="Network", code="NET", department=dept_it
    )
    section_electrical = Section.objects.create(
        name="Electrical", code="ELEC", department=dept_facilities
    )

    # Create facilities
    facility_main = Facility.objects.create(
        name="Main Building",
        type="building",
        status="active",
        location="Main Campus",
        campus=campus1,
    )

    # Create roles
    # Director - org-wide access
    director = director_factory(
        username="manager",
        first_name="Director",
        last_name="User",
        primary_campus=campus1,
    )

    # HOD - campus level
    hod = hod_factory(
        username="hod",
        first_name="HOD",
        last_name="User",
        primary_campus=campus1,
        primary_department=dept_it,
    )
    hod.sections.add(section_network)

    # Section Head - department level
    section_head = section_head_factory(
        username="head_of_section",
        first_name="Section",
        last_name="Head",
        primary_campus=campus1,
        primary_department=dept_facilities,
    )
    section_head.sections.add(section_electrical)

    # Technicians
    tech1 = technician_factory(
        username="tech_it",
        first_name="IT",
        last_name="Tech",
        primary_campus=campus1,
        primary_department=dept_it,
    )
    tech1.sections.add(section_network)

    tech2 = technician_factory(
        username="tech_facilities",
        first_name="Facilities",
        last_name="Tech",
        primary_campus=campus1,
        primary_department=dept_facilities,
    )
    tech2.sections.add(section_electrical)

    # Regular user
    user = org_aware_user_factory(
        username="user", first_name="Regular", last_name="User", role="user"
    )

    return {
        "org": org,
        "campus1": campus1,
        "campus2": campus2,
        "dept_it": dept_it,
        "dept_facilities": dept_facilities,
        "section_network": section_network,
        "section_electrical": section_electrical,
        "facility_main": facility_main,
        "manager": director,
        "hod": hod,
        "head_of_section": section_head,
        "tech1": tech1,
        "tech2": tech2,
        "user": user,
    }


def test_ticket_analytics_total_count(db, analytics_setup, ticket_factory):
    """Test ticket analytics total count"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    # Create tickets
    for i in range(5):
        ticket_factory(
            title=f"Ticket {i}", section=section1, facility=facility1, raised_by=user
        )

    # Get all tickets created in last 30 days
    result = TicketAnalytics.get_ticket_counts_by_timeframe(days=30)

    assert result["count"] >= 5


def test_ticket_analytics_by_status(db, analytics_setup, ticket_factory):
    """Test ticket analytics by status"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]
    tech1 = analytics_setup["tech1"]

    # Create tickets with different statuses
    open_tickets = [
        ticket_factory(
            title=f"Open {i}",
            section=section1,
            facility=facility1,
            raised_by=user,
            status="open",
        )
        for i in range(3)
    ]

    assigned_tickets = [
        ticket_factory(
            title=f"Assigned {i}",
            section=section1,
            facility=facility1,
            raised_by=user,
            assigned_to=tech1,
            status="assigned",
        )
        for i in range(2)
    ]

    # Get counts by status
    counts = TicketAnalytics.get_ticket_counts_by_status()

    # Should have at least open and assigned statuses
    statuses = {item["status"]: item["count"] for item in counts}
    assert statuses.get("open", 0) >= 3
    assert statuses.get("assigned", 0) >= 2


def test_technician_analytics_workload(db, analytics_setup, ticket_factory):
    """Test technician analytics for workload"""
    tech1 = analytics_setup["tech1"]
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    # Create tickets assigned to tech1
    tickets = [
        ticket_factory(
            title=f"Ticket {i}",
            assigned_to=tech1,
            section=section1,
            facility=facility1,
            raised_by=user,
        )
        for i in range(5)
    ]

    # Get technician performance
    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech1.id)

    assert len(performance) > 0
    assert performance[0]["total_tickets"] >= 5


def test_admin_analytics_access(db, authenticated_admin_client):
    """Test admin can access analytics endpoints"""
    client = authenticated_admin_client["client"]
    response = client.get(reverse("analytics-admin"))
    assert response.status_code == 200


def test_ticket_analytics_trends(db, analytics_setup, ticket_factory):
    """Test ticket analytics trend tracking"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    now = timezone.now()

    # Create tickets spread over multiple days
    for i in range(3):
        ticket_factory(
            title=f"Ticket {i}",
            raised_by=user,
            section=section1,
            facility=facility1,
            created_at=now - timedelta(days=i),
        )

    # Get trend data for last 7 days
    trend_data = TicketAnalytics.get_ticket_trend_data(days=7)

    assert len(trend_data) > 0


def test_technician_performance_metrics(db, analytics_setup, ticket_factory):
    """Test technician analytics performance metrics"""
    tech1 = analytics_setup["tech1"]
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    # Create and resolve tickets
    for i in range(3):
        ticket = ticket_factory(
            title=f"Ticket {i}",
            assigned_to=tech1,
            section=section1,
            facility=facility1,
            raised_by=user,
        )
        ticket.change_status("resolved", performed_by=tech1)

    # Get technician performance
    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech1.id)

    assert len(performance) > 0
    assert performance[0]["resolved_tickets"] >= 3


def test_admin_analytics_system_overview(db, analytics_setup):
    """Test admin analytics for system overview"""
    admin = analytics_setup["admin"]

    overview = AdminAnalytics.get_system_overview()

    assert "total_tickets" in overview
    assert isinstance(overview["total_tickets"], int)


def test_analytics_empty_dataset(db):
    """Test analytics with no data"""
    # Clear all tickets
    Ticket.objects.all().delete()

    result = TicketAnalytics.get_ticket_counts_by_timeframe(days=1)

    assert result["count"] == 0


def test_technician_analytics_no_assignments(db, technician_factory):
    """Test technician analytics with no ticket assignments"""
    tech = technician_factory()

    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech.id)

    assert len(performance) > 0
    assert performance[0]["total_tickets"] == 0


def test_analytics_ticket_filtering_by_section(db, analytics_setup, ticket_factory):
    """Test analytics filtering tickets by section"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    section2 = analytics_setup["section2"]
    facility1 = analytics_setup["facility1"]

    # Create tickets in both sections
    for i in range(3):
        ticket_factory(
            title=f"IT Ticket {i}", section=section1, facility=facility1, raised_by=user
        )
        ticket_factory(
            title=f"Plumb Ticket {i}",
            section=section2,
            facility=facility1,
            raised_by=user,
        )

    # Analytics should handle section filtering
    section1_counts = TicketAnalytics.get_ticket_counts_by_timeframe(
        days=30, section_id=section1.id
    )
    section2_counts = TicketAnalytics.get_ticket_counts_by_timeframe(
        days=30, section_id=section2.id
    )

    assert section1_counts["count"] >= 3
    assert section2_counts["count"] >= 3


def test_analytics_date_range(db, analytics_setup, ticket_factory):
    """Test analytics with date range filtering"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    now = timezone.now()

    # Create tickets over a range
    for i in range(10):
        ticket_factory(
            title=f"Ticket {i}",
            raised_by=user,
            section=section1,
            facility=facility1,
            created_at=now - timedelta(days=i),
        )

    # Get tickets created in last 30 days
    result = TicketAnalytics.get_ticket_counts_by_timeframe(days=30)

    assert result["count"] >= 10


# ============================================================================
# ORGANIZATIONAL ROLE-BASED ANALYTICS TESTS
# ============================================================================


def test_director_dashboard(db, organizational_analytics_setup, ticket_factory):
    """Test director dashboard showing organization-wide metrics"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create tickets across departments
    for i in range(5):
        ticket_factory(
            title=f"Director Test Ticket {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
        )

    # Get director dashboard
    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Should have organization-level metrics
    assert "organization" in dashboard
    assert dashboard["organization"]["name"] == "Test Corp"
    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 5
    assert "campuses" in dashboard  # Campus-level breakdown
    assert len(dashboard["campuses"]) >= 1


def test_hod_dashboard(db, organizational_analytics_setup, ticket_factory):
    """Test HOD dashboard showing campus-level metrics"""
    hod = organizational_analytics_setup["hod"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create tickets in HOD's campus
    for i in range(3):
        ticket_factory(
            title=f"HOD Test Ticket {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
        )

    # Get HOD dashboard
    dashboard = OrganizationalAnalytics.hod_dashboard(hod, days=30)

    # Should have campus-level metrics
    assert "campus" in dashboard
    assert dashboard["campus"]["name"] == "Main Campus"
    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 3
    assert "departments" in dashboard  # Department breakdown
    assert len(dashboard["departments"]) >= 1


def test_section_head_dashboard(db, organizational_analytics_setup, ticket_factory):
    """Test Section Head dashboard showing department-level metrics"""
    section_head = organizational_analytics_setup["head_of_section"]
    tech2 = organizational_analytics_setup["tech2"]
    user = organizational_analytics_setup["user"]
    section_electrical = organizational_analytics_setup["section_electrical"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create tickets in section head's department
    for i in range(4):
        ticket_factory(
            title=f"Section Head Test Ticket {i}",
            assigned_to=tech2,
            section=section_electrical,
            facility=facility_main,
            raised_by=user,
        )

    # Get section head dashboard
    dashboard = OrganizationalAnalytics.head_of_section_dashboard(section_head, days=30)

    # Should have department-level metrics
    assert "department" in dashboard
    assert dashboard["department"]["name"] == "Facilities"
    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 4
    assert "technicians" in dashboard  # Technician list


def test_director_dashboard_escalation_trends(
    db, organizational_analytics_setup, ticket_factory
):
    """Test director dashboard includes escalation trends"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create tickets
    for i in range(2):
        ticket = ticket_factory(
            title=f"Escalation Test {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
        )

    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Should track escalation trends (may be empty if no escalations yet)
    assert "escalation_trends" in dashboard
    assert isinstance(dashboard["escalation_trends"], dict)


def test_director_dashboard_top_technicians(
    db, organizational_analytics_setup, ticket_factory
):
    """Test director dashboard shows top technicians"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create resolved tickets assigned to tech1
    for i in range(3):
        ticket = ticket_factory(
            title=f"Resolved Test {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
        )
        ticket.change_status("resolved", performed_by=tech1)

    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Should include top technicians
    assert "top_technicians" in dashboard
    assert len(dashboard["top_technicians"]) > 0


def test_hod_dashboard_department_performance(
    db, organizational_analytics_setup, ticket_factory
):
    """Test HOD dashboard shows department performance"""
    hod = organizational_analytics_setup["hod"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create multiple tickets
    for i in range(5):
        ticket_factory(
            title=f"Dept Performance {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
            status="open",
        )

    dashboard = OrganizationalAnalytics.hod_dashboard(hod, days=30)

    # Should have department metrics
    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 5
    assert "departments" in dashboard


# ============================================================================
# NEW TESTS - Analytics Gap Fixes
# ============================================================================


def test_director_dashboard_facility_metrics(
    db, organizational_analytics_setup, ticket_factory
):
    """Test director dashboard includes facility-level metrics"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create tickets for specific facility
    for i in range(3):
        ticket_factory(
            title=f"Facility Test {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
            status="open",
        )

    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Should include facilities breakdown
    assert "facilities" in dashboard
    assert isinstance(dashboard["facilities"], list)
    assert len(dashboard["facilities"]) > 0

    # Facility structure validation
    facility = dashboard["facilities"][0]
    assert "facility" in facility
    assert "id" in facility["facility"]
    assert "name" in facility["facility"]
    assert "type" in facility["facility"]
    assert "status" in facility["facility"]
    assert "campus" in facility["facility"]

    # Facility metrics validation
    assert "total_tickets" in facility
    assert "open_tickets" in facility
    assert "resolved_tickets" in facility
    assert "overdue_tickets" in facility
    assert "avg_resolution_hours" in facility

    # Verify facility has tickets
    facility_found = [
        f for f in dashboard["facilities"] if f["facility"]["id"] == facility_main.id
    ]
    assert len(facility_found) == 1
    assert facility_found[0]["total_tickets"] >= 3


def test_director_dashboard_section_metrics(
    db, organizational_analytics_setup, ticket_factory
):
    """Test director dashboard includes organization-wide section metrics"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Create tickets in specific section
    for i in range(4):
        ticket_factory(
            title=f"Section Test {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
            status="open" if i % 2 == 0 else "resolved",
        )

    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Should include sections breakdown
    assert "sections" in dashboard
    assert isinstance(dashboard["sections"], list)
    assert len(dashboard["sections"]) > 0

    # Section structure validation
    section = dashboard["sections"][0]
    assert "section" in section
    assert "id" in section["section"]
    assert "name" in section["section"]
    assert "code" in section["section"]
    assert "department" in section["section"]
    assert "campus" in section["section"]
    assert "head_of_section" in section["section"]

    # Section metrics validation
    assert "total_tickets" in section
    assert "open_tickets" in section
    assert "resolved_tickets" in section
    assert "escalated_tickets" in section
    assert "avg_resolution_hours" in section
    assert "technician_count" in section

    # Verify section has tickets
    section_found = [
        s for s in dashboard["sections"] if s["section"]["id"] == section_network.id
    ]
    assert len(section_found) == 1
    assert section_found[0]["total_tickets"] >= 4


def test_technician_performance_status_breakdown(db, analytics_setup, ticket_factory):
    """Test technician performance includes tickets by status breakdown"""
    tech1 = analytics_setup["tech1"]
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    # Create tickets with various statuses
    statuses = ["open", "assigned", "in_progress", "pending", "resolved", "closed"]
    for status in statuses:
        ticket_factory(
            title=f"Status {status}",
            assigned_to=tech1,
            section=section1,
            facility=facility1,
            raised_by=user,
            status=status,
        )

    # Get technician performance
    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech1.id)

    assert len(performance) > 0
    tech_perf = performance[0]

    # Verify tickets_by_status exists
    assert "tickets_by_status" in tech_perf
    assert isinstance(tech_perf["tickets_by_status"], dict)

    # Verify status breakdown contains expected statuses
    status_dict = tech_perf["tickets_by_status"]
    assert "open" in status_dict
    assert "assigned" in status_dict
    assert "in_progress" in status_dict
    assert "pending" in status_dict
    assert "resolved" in status_dict
    assert "closed" in status_dict

    # Verify count matches
    total_from_breakdown = sum(status_dict.values())
    assert total_from_breakdown == tech_perf["total_tickets"]
    assert total_from_breakdown >= 6


def test_technician_performance_status_breakdown_empty(db, technician_factory):
    """Test technician performance status breakdown with no assignments"""
    tech = technician_factory()

    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech.id)

    assert len(performance) > 0
    tech_perf = performance[0]

    # Should have empty status breakdown when no tickets
    assert "tickets_by_status" in tech_perf
    assert isinstance(tech_perf["tickets_by_status"], dict)
    assert len(tech_perf["tickets_by_status"]) == 0


def test_director_dashboard_facilities_sorted(
    db, organizational_analytics_setup, ticket_factory
):
    """Test director dashboard facilities are sorted by ticket count descending"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    campus1 = organizational_analytics_setup["campus1"]

    # Create second facility in same organization
    facility2 = Facility.objects.create(
        name="Secondary Building",
        type="building",
        status="active",
        location="Downtown",
        campus=campus1,
    )

    # Create more tickets for facility_main
    facility_main = organizational_analytics_setup["facility_main"]
    for i in range(5):
        ticket_factory(
            title=f"Main Facility {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
            status="open",
        )

    # Create fewer tickets for facility2
    for i in range(2):
        ticket_factory(
            title=f"Secondary Facility {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility2,
            raised_by=user,
            status="open",
        )

    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Verify facilities are sorted by ticket count
    facilities = dashboard["facilities"]
    for i in range(len(facilities) - 1):
        assert facilities[i]["total_tickets"] >= facilities[i + 1]["total_tickets"]

    # facility_main should be first
    assert facilities[0]["facility"]["id"] == facility_main.id
    assert facilities[0]["total_tickets"] >= 5


def test_director_dashboard_sections_sorted(
    db, organizational_analytics_setup, ticket_factory
):
    """Test director dashboard sections are sorted by ticket count descending"""
    director = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    campus1 = organizational_analytics_setup["campus1"]
    facility_main = organizational_analytics_setup["facility_main"]

    # Get existing section
    section_network = organizational_analytics_setup["section_network"]

    # Create second section in same department
    dept_it = section_network.department
    section_electrical = Section.objects.create(
        name="Electrical", code="ELEC", department=dept_it
    )

    # Create more tickets for section_network
    for i in range(5):
        ticket_factory(
            title=f"Network Ticket {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
            status="open",
        )

    # Add tech1 to electrical section
    tech1.sections.add(section_electrical)

    # Create fewer tickets for section_electrical
    for i in range(2):
        ticket_factory(
            title=f"Electrical Ticket {i}",
            assigned_to=tech1,
            section=section_electrical,
            facility=facility_main,
            raised_by=user,
            status="open",
        )

    dashboard = OrganizationalAnalytics.director_dashboard(director, days=30)

    # Verify sections are sorted by ticket count
    sections = dashboard["sections"]
    for i in range(len(sections) - 1):
        assert sections[i]["total_tickets"] >= sections[i + 1]["total_tickets"]


def test_manager_dashboard(db, organizational_analytics_setup, ticket_factory):
    """Test manager dashboard shows cross-campus department metrics"""
    manager = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]
    dept_it = organizational_analytics_setup["dept_it"]

    # Give manager a primary_department so manager_dashboard works
    manager.primary_department = dept_it
    manager.save()

    # Create tickets in the manager's department
    for i in range(4):
        ticket_factory(
            title=f"Manager Test Ticket {i}",
            assigned_to=tech1,
            section=section_network,
            facility=facility_main,
            raised_by=user,
        )

    dashboard = OrganizationalAnalytics.manager_dashboard(manager, days=30)

    assert "department" in dashboard
    assert dashboard["department"]["code"] == dept_it.code
    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 4
    assert "campuses" in dashboard
    assert "sections" in dashboard
    assert "technicians" in dashboard
    assert "status_distribution" in dashboard
    assert "escalation_trends" in dashboard


def test_manager_dashboard_no_department_returns_empty(db, director_factory):
    """Test manager_dashboard returns empty dict when manager has no primary_department"""
    manager = director_factory(username="mgr_nodept")
    # No primary_department set
    result = OrganizationalAnalytics.manager_dashboard(manager, days=30)
    assert result == {}


def test_manager_dashboard_endpoint(db, organizational_analytics_setup, api_client):
    """Test manager can access /analytics/manager/ endpoint"""
    manager = organizational_analytics_setup["manager"]
    dept_it = organizational_analytics_setup["dept_it"]
    manager.primary_department = dept_it
    manager.save()

    from rest_framework.authtoken.models import Token

    token, _ = Token.objects.get_or_create(user=manager)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    response = api_client.get(reverse("analytics-manager"))
    assert response.status_code == 200
    assert "department" in response.data
