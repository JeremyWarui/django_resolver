"""Analytics tests — one file per analytics class, matching the split layout."""

import pytest
from datetime import timedelta
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from tickets.api.analytics.ticket_analytics import TicketAnalytics
from tickets.api.analytics.technician_analytics import TechnicianAnalytics
from tickets.api.analytics.admin_analytics import AdminAnalytics
from tickets.api.analytics.manager_analytics import ManagerAnalytics
from tickets.api.analytics.hod_analytics import HODAnalytics
from tickets.api.analytics.section_head_analytics import SectionHeadAnalytics

from tickets.models import (
    Ticket,
    CustomUser,
    Section,
    Facility,
    Organization,
    Campus,
    Department,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def analytics_setup(db, user_factory, technician_factory, organization, campus, department, facility):
    """Basic analytics test data — two sections with a full org hierarchy."""
    section1 = Section.objects.create(name="IT Section", code="ITS", department=department)
    section2 = Section.objects.create(name="Plumbing Section", code="PLMB", department=department)

    facility2 = Facility.objects.create(
        name="Building B", type="building", status="active",
        location="South Campus", campus=campus,
    )

    admin = CustomUser.objects.create_user(
        username="analytics_admin", password="password",
        role="admin", first_name="Admin", last_name="User",
    )

    tech1 = technician_factory(username="tech1", first_name="Tech", last_name="One")
    tech1.sections.add(section1)

    tech2 = technician_factory(username="tech2", first_name="Tech", last_name="Two")
    tech2.sections.add(section2)

    user = user_factory(username="analytics_user", first_name="Regular", last_name="User")

    return {
        "section1": section1,
        "section2": section2,
        "facility1": facility,
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
    manager_factory,
    section_head_factory,
):
    """Full org hierarchy for role-based dashboard tests."""
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
    facility_main = Facility.objects.create(
        name="Main Building", type="building", status="active",
        location="Main Campus", campus=campus1,
    )

    # Manager: cross-campus dept scope — needs primary_department, NOT primary_campus
    manager = manager_factory(
        username="manager",
        first_name="Manager",
        last_name="User",
        primary_department=dept_it,
    )

    # HOD: single campus + dept
    hod = hod_factory(
        username="hod",
        first_name="HOD",
        last_name="User",
        primary_campus=campus1,
        primary_department=dept_it,
    )
    hod.sections.add(section_network)

    # Section Head: identified via Section.head_of_section FK (not just M2M)
    section_head = section_head_factory(
        username="head_of_section",
        first_name="Section",
        last_name="Head",
        primary_campus=campus1,
        primary_department=dept_facilities,
    )
    section_electrical.head_of_section = section_head
    section_electrical.save()
    section_head.sections.add(section_electrical)

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

    user = org_aware_user_factory(
        username="org_user", first_name="Regular", last_name="User", role="user"
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
        "manager": manager,
        "hod": hod,
        "head_of_section": section_head,
        "tech1": tech1,
        "tech2": tech2,
        "user": user,
    }


# ============================================================================
# TICKET ANALYTICS
# ============================================================================


def test_ticket_analytics_total_count(db, analytics_setup, ticket_factory):
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    for i in range(5):
        ticket_factory(title=f"Ticket {i}", section=section1, facility=facility1, raised_by=user)

    result = TicketAnalytics.get_ticket_counts_by_timeframe(days=30)
    assert result["count"] >= 5


def test_ticket_analytics_by_status(db, analytics_setup, ticket_factory):
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]
    tech1 = analytics_setup["tech1"]

    for i in range(3):
        ticket_factory(
            title=f"Open {i}", section=section1, facility=facility1,
            raised_by=user, status="open", assigned_to=None,
        )
    for i in range(2):
        ticket_factory(
            title=f"Assigned {i}", section=section1, facility=facility1,
            raised_by=user, assigned_to=tech1, status="assigned",
        )

    counts = TicketAnalytics.get_ticket_counts_by_status()
    statuses = {item["status"]: item["count"] for item in counts}
    assert statuses.get("open", 0) >= 3
    assert statuses.get("assigned", 0) >= 2


def test_ticket_analytics_trends(db, analytics_setup, ticket_factory):
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]
    now = timezone.now()

    for i in range(3):
        ticket_factory(
            title=f"Ticket {i}", raised_by=user, section=section1, facility=facility1,
            created_at=now - timedelta(days=i),
        )

    trend_data = TicketAnalytics.get_ticket_trend_data(days=7)
    assert len(trend_data) > 0


def test_ticket_analytics_filtering_by_section(db, analytics_setup, ticket_factory):
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    section2 = analytics_setup["section2"]
    facility1 = analytics_setup["facility1"]

    for i in range(3):
        ticket_factory(title=f"IT {i}", section=section1, facility=facility1, raised_by=user)
        ticket_factory(title=f"Plumb {i}", section=section2, facility=facility1, raised_by=user)

    assert TicketAnalytics.get_ticket_counts_by_timeframe(days=30, section_id=section1.id)["count"] >= 3
    assert TicketAnalytics.get_ticket_counts_by_timeframe(days=30, section_id=section2.id)["count"] >= 3


def test_ticket_analytics_date_range(db, analytics_setup, ticket_factory):
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]
    now = timezone.now()

    for i in range(10):
        ticket_factory(
            title=f"Ticket {i}", raised_by=user, section=section1, facility=facility1,
            created_at=now - timedelta(days=i),
        )

    cache.clear()
    assert TicketAnalytics.get_ticket_counts_by_timeframe(days=30)["count"] >= 10


def test_ticket_analytics_empty_dataset(db):
    Ticket.objects.all().delete()
    result = TicketAnalytics.get_ticket_counts_by_timeframe(days=1)
    assert result["count"] == 0


def test_ticket_analytics_facility_breakdown(db, organizational_analytics_setup, ticket_factory):
    """TicketAnalytics.get_tickets_by_facility returns per-facility ticket counts."""
    user = organizational_analytics_setup["user"]
    tech1 = organizational_analytics_setup["tech1"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    for i in range(3):
        ticket_factory(
            title=f"Facility Test {i}", assigned_to=tech1,
            section=section_network, facility=facility_main, raised_by=user,
        )

    result = TicketAnalytics.get_tickets_by_facility()
    assert len(result) > 0
    entry = next((r for r in result if r["name"] == "Main Building"), None)
    assert entry is not None
    assert entry["ticket_count"] >= 3


def test_ticket_analytics_facilities_sorted_by_count(
    db, organizational_analytics_setup, ticket_factory
):
    """get_tickets_by_facility returns facilities ordered descending by ticket count."""
    user = organizational_analytics_setup["user"]
    tech1 = organizational_analytics_setup["tech1"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]
    campus1 = organizational_analytics_setup["campus1"]

    facility2 = Facility.objects.create(
        name="Secondary Building", type="building", status="active",
        location="Downtown", campus=campus1,
    )

    for i in range(5):
        ticket_factory(
            title=f"Main {i}", assigned_to=tech1, section=section_network,
            facility=facility_main, raised_by=user,
        )
    for i in range(2):
        ticket_factory(
            title=f"Secondary {i}", assigned_to=tech1, section=section_network,
            facility=facility2, raised_by=user,
        )

    result = TicketAnalytics.get_tickets_by_facility()
    for i in range(len(result) - 1):
        assert result[i]["ticket_count"] >= result[i + 1]["ticket_count"]


# ============================================================================
# TECHNICIAN ANALYTICS
# ============================================================================


def test_technician_analytics_workload(db, analytics_setup, ticket_factory):
    tech1 = analytics_setup["tech1"]
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    for i in range(5):
        ticket_factory(
            title=f"Ticket {i}", assigned_to=tech1,
            section=section1, facility=facility1, raised_by=user,
        )

    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech1.id)
    assert len(performance) > 0
    assert performance[0]["total_tickets"] >= 5


def test_technician_performance_resolved_count(db, analytics_setup, ticket_factory):
    tech1 = analytics_setup["tech1"]
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    for i in range(3):
        ticket = ticket_factory(
            title=f"Ticket {i}", assigned_to=tech1,
            section=section1, facility=facility1, raised_by=user,
        )
        ticket.change_status("resolved", performed_by=tech1)

    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech1.id)
    assert len(performance) > 0
    assert performance[0]["resolved_tickets"] >= 3


def test_technician_analytics_no_assignments(db, technician_factory):
    tech = technician_factory()
    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech.id)
    assert len(performance) > 0
    assert performance[0]["total_tickets"] == 0


def test_technician_performance_status_breakdown(db, analytics_setup, ticket_factory):
    """get_technician_performance includes a per-status ticket count dict."""
    tech1 = analytics_setup["tech1"]
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]

    for st in ["open", "assigned", "in_progress", "pending", "resolved", "closed"]:
        ticket_factory(
            title=f"Status {st}", assigned_to=tech1,
            section=section1, facility=facility1, raised_by=user, status=st,
        )

    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech1.id)
    assert len(performance) > 0
    tech_perf = performance[0]

    assert "tickets_by_status" in tech_perf
    status_dict = tech_perf["tickets_by_status"]
    assert isinstance(status_dict, dict)
    for st in ["open", "assigned", "in_progress", "pending", "resolved", "closed"]:
        assert st in status_dict

    assert sum(status_dict.values()) == tech_perf["total_tickets"]
    assert tech_perf["total_tickets"] >= 6


def test_technician_performance_status_breakdown_empty(db, technician_factory):
    tech = technician_factory()
    performance = TechnicianAnalytics.get_technician_performance(technician_id=tech.id)
    assert len(performance) > 0
    assert performance[0]["tickets_by_status"] == {}


# ============================================================================
# ADMIN ANALYTICS
# ============================================================================


def test_admin_analytics_endpoint_accessible(db, authenticated_admin_client):
    client = authenticated_admin_client["client"]
    response = client.get(reverse("analytics-admin"))
    assert response.status_code == 200


def test_admin_analytics_system_overview_structure(db, analytics_setup):
    """get_system_overview returns summary and users sub-dicts."""
    overview = AdminAnalytics.get_system_overview()

    assert "summary" in overview
    assert "users" in overview
    assert "resolution_rate" in overview

    summary = overview["summary"]
    assert "total_tickets" in summary
    assert "open_tickets" in summary
    assert "resolved_tickets" in summary
    assert "new_24h" in summary
    assert "past_7_days" in summary
    assert "past_30_days" in summary
    assert "avg_resolution_time_hours" in summary
    assert isinstance(summary["total_tickets"], int)

    users = overview["users"]
    assert "total_users" in users
    assert "technicians" in users
    assert "managers" in users
    assert "admins" in users


def test_admin_analytics_overdue_tickets_structure(db):
    """get_overdue_tickets returns a dict with count and tickets list."""
    result = AdminAnalytics.get_overdue_tickets()
    assert "count" in result
    assert "tickets" in result
    assert isinstance(result["tickets"], list)


# ============================================================================
# MANAGER ANALYTICS (cross-campus, own department)
# ============================================================================


def test_manager_dashboard(db, organizational_analytics_setup, ticket_factory):
    """manager_dashboard: correct structure, content, technician data, section data, and sort order."""
    manager = organizational_analytics_setup["manager"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]
    dept_it = organizational_analytics_setup["dept_it"]

    # Create a second section so we can assert descending sort order
    section_support = Section.objects.create(name="Support", code="SUP", department=dept_it)
    tech1.sections.add(section_support)

    for i in range(5):
        ticket_factory(
            title=f"Network {i}", assigned_to=tech1,
            section=section_network, facility=facility_main, raised_by=user,
        )
    for i in range(2):
        t = ticket_factory(
            title=f"Support {i}", assigned_to=tech1,
            section=section_support, facility=facility_main, raised_by=user,
        )
        t.change_status("resolved", performed_by=tech1)

    dashboard = ManagerAnalytics.manager_dashboard(manager, days=30)

    # Top-level keys
    for key in ("department", "overview", "campuses", "sections", "technicians",
                "status_distribution", "escalation_trends", "period_days"):
        assert key in dashboard
    assert dashboard["department"]["code"] == dept_it.code
    assert dashboard["overview"]["total_tickets"] >= 5
    assert isinstance(dashboard["escalation_trends"], dict)

    # Section structure
    assert len(dashboard["sections"]) > 0
    sec = dashboard["sections"][0]
    for field in ("section", "total_tickets", "open_tickets", "escalated_tickets", "avg_resolution_hours"):
        assert field in sec
    for field in ("id", "name", "code"):
        assert field in sec["section"]
    network_entry = next(s for s in dashboard["sections"] if s["section"]["id"] == section_network.id)
    assert network_entry["total_tickets"] >= 5

    # Sections sorted descending by ticket count
    counts = [s["total_tickets"] for s in dashboard["sections"]]
    assert counts == sorted(counts, reverse=True)

    # Technician entry structure
    assert len(dashboard["technicians"]) > 0
    tech_entry = dashboard["technicians"][0]
    for field in ("technician", "total_assigned", "resolved"):
        assert field in tech_entry


def test_manager_dashboard_no_primary_department_returns_empty(db, manager_factory):
    """manager_dashboard returns {} when manager has no primary_department."""
    manager = manager_factory(username="mgr_nodept")
    assert ManagerAnalytics.manager_dashboard(manager, days=30) == {}


def test_manager_dashboard_wrong_role_returns_empty(db, hod_factory):
    """manager_dashboard returns {} for non-manager roles."""
    hod = hod_factory()
    assert ManagerAnalytics.manager_dashboard(hod, days=30) == {}


def test_manager_dashboard_endpoint(db, organizational_analytics_setup, api_client):
    """GET /analytics/manager/ returns 200 for a manager with primary_department."""
    manager = organizational_analytics_setup["manager"]

    from rest_framework.authtoken.models import Token
    token, _ = Token.objects.get_or_create(user=manager)
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    response = api_client.get(reverse("analytics-manager"))
    assert response.status_code == 200
    assert "department" in response.data


# ============================================================================
# HOD ANALYTICS (own campus, own department)
# ============================================================================


def test_hod_dashboard_structure(db, organizational_analytics_setup, ticket_factory):
    """hod_dashboard returns department, overview, sections, technicians."""
    hod = organizational_analytics_setup["hod"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    for i in range(3):
        ticket_factory(
            title=f"HOD Test {i}", assigned_to=tech1,
            section=section_network, facility=facility_main, raised_by=user,
        )

    dashboard = HODAnalytics.hod_dashboard(hod, days=30)

    assert "department" in dashboard
    assert dashboard["department"]["name"] == "IT Department"
    assert dashboard["department"]["campus"] == "Main Campus"
    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 3
    assert "sections" in dashboard
    assert len(dashboard["sections"]) >= 1
    assert "technicians" in dashboard
    assert "escalation_trends" in dashboard


def test_hod_dashboard_section_breakdown(
    db, organizational_analytics_setup, ticket_factory
):
    """HOD sees section performance within their department only."""
    hod = organizational_analytics_setup["hod"]
    tech1 = organizational_analytics_setup["tech1"]
    user = organizational_analytics_setup["user"]
    section_network = organizational_analytics_setup["section_network"]
    facility_main = organizational_analytics_setup["facility_main"]

    for i in range(5):
        ticket_factory(
            title=f"HOD Section {i}", assigned_to=tech1,
            section=section_network, facility=facility_main, raised_by=user,
        )

    dashboard = HODAnalytics.hod_dashboard(hod, days=30)
    assert "sections" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 5

    section_entry = next(
        (s for s in dashboard["sections"] if s["section"]["id"] == section_network.id), None
    )
    assert section_entry is not None
    assert "ticket_count" in section_entry
    assert "sla_compliance" in section_entry
    assert "technician_count" in section_entry


def test_hod_dashboard_wrong_role_returns_empty(db, manager_factory):
    """hod_dashboard returns {} for non-hod roles."""
    manager = manager_factory()
    assert HODAnalytics.hod_dashboard(manager, days=30) == {}


def test_hod_dashboard_missing_campus_returns_empty(db, hod_factory):
    """hod_dashboard returns {} when HOD has no primary_campus."""
    hod = hod_factory()
    assert HODAnalytics.hod_dashboard(hod, days=30) == {}


# ============================================================================
# SECTION HEAD ANALYTICS (own sections only)
# ============================================================================


def test_section_head_dashboard_structure(
    db, organizational_analytics_setup, ticket_factory
):
    """section_head_dashboard returns sections, overview, technicians, pending_reasons."""
    section_head = organizational_analytics_setup["head_of_section"]
    tech2 = organizational_analytics_setup["tech2"]
    user = organizational_analytics_setup["user"]
    section_electrical = organizational_analytics_setup["section_electrical"]
    facility_main = organizational_analytics_setup["facility_main"]

    for i in range(4):
        ticket_factory(
            title=f"HoS Test {i}", assigned_to=tech2,
            section=section_electrical, facility=facility_main, raised_by=user,
        )

    dashboard = SectionHeadAnalytics.section_head_dashboard(section_head, days=30)

    assert "sections" in dashboard
    assert len(dashboard["sections"]) >= 1
    section_entry = dashboard["sections"][0]
    assert section_entry["section"]["department"] == "Facilities"

    assert "overview" in dashboard
    assert dashboard["overview"]["total_tickets"] >= 4

    assert "technicians" in dashboard
    assert "pending_reasons" in dashboard
    assert "escalation_trends" in dashboard


def test_section_head_dashboard_technician_scope(
    db, organizational_analytics_setup, ticket_factory
):
    """Section Head only sees technicians assigned to their section(s)."""
    section_head = organizational_analytics_setup["head_of_section"]
    tech2 = organizational_analytics_setup["tech2"]
    user = organizational_analytics_setup["user"]
    section_electrical = organizational_analytics_setup["section_electrical"]
    facility_main = organizational_analytics_setup["facility_main"]

    for i in range(2):
        ticket_factory(
            title=f"HoS Tech {i}", assigned_to=tech2,
            section=section_electrical, facility=facility_main, raised_by=user,
        )

    dashboard = SectionHeadAnalytics.section_head_dashboard(section_head, days=30)
    tech_ids = [t["technician"]["id"] for t in dashboard["technicians"]]
    assert tech2.id in tech_ids

    # tech1 is in a different section — should not appear
    tech1 = organizational_analytics_setup["tech1"]
    assert tech1.id not in tech_ids


def test_section_head_dashboard_pending_reasons(
    db, organizational_analytics_setup, ticket_factory
):
    """pending_reasons lists reason codes for tickets stuck in pending."""
    section_head = organizational_analytics_setup["head_of_section"]
    tech2 = organizational_analytics_setup["tech2"]
    user = organizational_analytics_setup["user"]
    section_electrical = organizational_analytics_setup["section_electrical"]
    facility_main = organizational_analytics_setup["facility_main"]

    ticket = ticket_factory(
        title="Pending Test", assigned_to=tech2,
        section=section_electrical, facility=facility_main, raised_by=user,
        status="pending", pending_reason="waiting_parts",
        pending_comment="Waiting for spare parts.",
    )

    dashboard = SectionHeadAnalytics.section_head_dashboard(section_head, days=30)
    assert isinstance(dashboard["pending_reasons"], list)
    reasons = [r["pending_reason"] for r in dashboard["pending_reasons"]]
    assert "waiting_parts" in reasons


def test_section_head_dashboard_no_sections_returns_empty(db, section_head_factory):
    """section_head_dashboard returns {} when user is not head_of_section of any section."""
    section_head = section_head_factory()
    # No Section.head_of_section points to this user
    assert SectionHeadAnalytics.section_head_dashboard(section_head, days=30) == {}


def test_section_head_dashboard_wrong_role_returns_empty(db, technician_factory):
    """section_head_dashboard returns {} for non-section-head roles."""
    tech = technician_factory()
    assert SectionHeadAnalytics.section_head_dashboard(tech, days=30) == {}
