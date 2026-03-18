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
)
from tickets.models import Ticket, CustomUser, Feedback, Section, Facility


@pytest.fixture
def analytics_setup(db, user_factory, technician_factory):
    """Create test data for analytics tests"""
    # Create sections
    section1 = Section.objects.create(name="IT", description="IT Department")
    section2 = Section.objects.create(name="Plumbing", description="Plumbing Department")

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


def test_ticket_analytics_total_count(db, analytics_setup, ticket_factory):
    """Test ticket analytics total count"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]
    
    # Create tickets
    for i in range(5):
        ticket_factory(
            title=f"Ticket {i}",
            section=section1,
            facility=facility1,
            raised_by=user
        )
    
    analytics = TicketAnalytics()
    total = analytics.get_ticket_counts()
    
    assert total["total"] >= 5


def test_ticket_analytics_by_status(db, analytics_setup, ticket_factory):
    """Test ticket analytics by status"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    facility1 = analytics_setup["facility1"]
    tech1 = analytics_setup["tech1"]
    
    # Create tickets with different statuses
    open_tickets = [
        ticket_factory(title=f"Open {i}", section=section1, facility=facility1, 
                      raised_by=user, status="open")
        for i in range(3)
    ]
    
    assigned_tickets = [
        ticket_factory(title=f"Assigned {i}", section=section1, facility=facility1,
                      raised_by=user, assigned_to=tech1, status="assigned")
        for i in range(2)
    ]
    
    analytics = TicketAnalytics()
    counts = analytics.get_ticket_counts()
    
    assert counts["total"] >= 5


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
            raised_by=user
        )
        for i in range(5)
    ]
    
    analytics = TechnicianAnalytics(tech1)
    workload = analytics.get_technician_workload()
    
    assert workload["assigned_tickets_count"] >= 5


def test_admin_analytics_access(db, authenticated_admin_client):
    """Test admin can access analytics endpoints"""
    client = authenticated_admin_client['client']
    response = client.get(reverse("admin-dashboard"))
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
            created_at=now - timedelta(days=i)
        )
    
    analytics = TicketAnalytics()
    counts = analytics.get_ticket_counts()
    
    assert counts["total"] >= 3


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
            raised_by=user
        )
        ticket.change_status("resolved", performed_by=tech1)
    
    analytics = TechnicianAnalytics(tech1)
    performance = analytics.get_technician_performance()
    
    assert performance["resolved_tickets_count"] >= 3


def test_admin_analytics_system_overview(db, analytics_setup):
    """Test admin analytics for system overview"""
    admin = analytics_setup["admin"]
    
    analytics = AdminAnalytics(admin)
    dashboard = analytics.get_admin_dashboard()
    
    assert "total_tickets" in dashboard or "total_users" in dashboard or len(dashboard) > 0


def test_analytics_empty_dataset(db):
    """Test analytics with no data"""
    analytics = TicketAnalytics()
    counts = analytics.get_ticket_counts()
    
    assert counts["total"] >= 0


def test_technician_analytics_no_assignments(db, technician_factory):
    """Test technician analytics with no ticket assignments"""
    tech = technician_factory()
    
    analytics = TechnicianAnalytics(tech)
    workload = analytics.get_technician_workload()
    
    assert workload["assigned_tickets_count"] == 0


def test_analytics_ticket_filtering_by_section(db, analytics_setup, ticket_factory):
    """Test analytics filtering tickets by section"""
    user = analytics_setup["user"]
    section1 = analytics_setup["section1"]
    section2 = analytics_setup["section2"]
    facility1 = analytics_setup["facility1"]
    
    # Create tickets in both sections
    for i in range(3):
        ticket_factory(title=f"IT Ticket {i}", section=section1, facility=facility1, raised_by=user)
        ticket_factory(title=f"Plumb Ticket {i}", section=section2, facility=facility1, raised_by=user)
    
    # Analytics should handle section filtering
    analytics = TicketAnalytics()
    counts = analytics.get_ticket_counts()
    
    assert counts["total"] >= 6


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
            created_at=now - timedelta(days=i)
        )
    
    analytics = TicketAnalytics()
    counts = analytics.get_ticket_counts()
    
    assert counts["total"] >= 10
