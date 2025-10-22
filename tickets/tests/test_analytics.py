"""
Tests for the analytics functionality.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import Ticket, CustomUser, Feedback, Section, Facility
from tickets.api.analytics.analytics import TicketAnalytics, TechnicianAnalytics, AdminAnalytics


@pytest.fixture
def setup_test_data():
    """
    Create test data for analytics tests.
    """
    # Create sections
    section1 = Section.objects.create(name="IT", description="IT Department")
    section2 = Section.objects.create(
        name="Plumbing", description="Plumbing Department")

    # Create facilities
    facility1 = Facility.objects.create(
        name="Building A", type="building", location="North Campus")
    facility2 = Facility.objects.create(
        name="Building B", type="building", location="South Campus")

    # Create users
    admin = CustomUser.objects.create_user(
        username="admin",
        password="password",
        role="admin",
        first_name="Admin",
        last_name="User"
    )

    technician1 = CustomUser.objects.create_user(
        username="tech1",
        password="password",
        role="technician",
        first_name="Tech",
        last_name="One"
    )
    technician1.sections.add(section1)

    technician2 = CustomUser.objects.create_user(
        username="tech2",
        password="password",
        role="technician",
        first_name="Tech",
        last_name="Two"
    )
    technician2.sections.add(section2)

    user = CustomUser.objects.create_user(
        username="user",
        password="password",
        role="user",
        first_name="Regular",
        last_name="User"
    )

    # Create tickets with different dates
    now = timezone.now()

    # Create tickets for today
    for i in range(5):
        Ticket.objects.create(
            title=f"Today's Ticket {i+1}",
            description=f"Description for ticket {i+1}",
            section=section1 if i % 2 == 0 else section2,
            facility=facility1 if i % 2 == 0 else facility2,
            raised_by=user,
            status="open"
        )

    # Create tickets for yesterday
    yesterday = now - timedelta(days=1)
    for i in range(3):
        ticket = Ticket.objects.create(
            title=f"Yesterday's Ticket {i+1}",
            description=f"Description for ticket {i+1}",
            section=section1 if i % 2 == 0 else section2,
            facility=facility1 if i % 2 == 0 else facility2,
            raised_by=user,
            status="assigned",
            assigned_to=technician1 if i % 2 == 0 else technician2,
        )
        # Update the created_at field to yesterday
        Ticket.objects.filter(id=ticket.id).update(created_at=yesterday)

    # Create tickets for last week
    last_week = now - timedelta(days=7)
    for i in range(10):
        ticket = Ticket.objects.create(
            title=f"Last Week's Ticket {i+1}",
            description=f"Description for ticket {i+1}",
            section=section1 if i % 2 == 0 else section2,
            facility=facility1 if i % 2 == 0 else facility2,
            raised_by=user,
            status="resolved" if i % 2 == 0 else "closed",
            assigned_to=technician1 if i % 2 == 0 else technician2,
        )
        # Update the created_at field to last week
        Ticket.objects.filter(id=ticket.id).update(created_at=last_week)

        # Create feedback for resolved tickets
        if i % 2 == 0:
            feedback = Feedback.objects.create(
                ticket=ticket,
                rated_by=user,
                rating=4.0 + (i % 2),  # Ratings between 4.0 and 5.0
                comment=f"Feedback for ticket {ticket.id}"
            )
            # Update the created_at field to last week
            Feedback.objects.filter(id=feedback.id).update(
                created_at=last_week)

    return {
        "admin": admin,
        "technician1": technician1,
        "technician2": technician2,
        "user": user,
        "section1": section1,
        "section2": section2,
        "facility1": facility1,
        "facility2": facility2
    }


@pytest.mark.django_db
def test_ticket_analytics_counts_by_timeframe(setup_test_data):
    """Test TicketAnalytics.get_ticket_counts_by_timeframe."""
    # Check today's tickets
    today_count = TicketAnalytics.get_ticket_counts_by_timeframe(days=1)
    assert today_count['count'] == 5

    # Check yesterday's tickets
    yesterday_count = TicketAnalytics.get_ticket_counts_by_timeframe(days=2)
    assert yesterday_count['count'] == 8  # 5 today + 3 yesterday

    # Check last week's tickets
    week_count = TicketAnalytics.get_ticket_counts_by_timeframe(days=10)
    assert week_count['count'] == 18  # 5 today + 3 yesterday + 10 last week

    # Check filtering by facility
    facility_count = TicketAnalytics.get_ticket_counts_by_timeframe(
        days=10, facility_id=setup_test_data["facility1"].id)
    # Half of the 18 tickets are for facility1
    assert facility_count['count'] == 9


@pytest.mark.django_db
def test_ticket_analytics_counts_by_status(setup_test_data):
    """Test TicketAnalytics.get_ticket_counts_by_status."""
    status_counts = TicketAnalytics.get_ticket_counts_by_status()

    # Convert to dictionary for easier testing
    status_dict = {item['status']: item['count'] for item in status_counts}

    assert status_dict['open'] == 5
    assert status_dict['assigned'] == 3
    assert status_dict['resolved'] == 5
    assert status_dict['closed'] == 5


@pytest.mark.django_db
def test_technician_analytics_performance(setup_test_data):
    """Test TechnicianAnalytics.get_technician_performance."""
    performance_data = TechnicianAnalytics.get_technician_performance()

    # Check that both technicians are included
    assert len(performance_data) == 2

    # Convert to dictionary for easier testing
    tech_dict = {item['username']: item for item in performance_data}

    # Check technician 1's stats
    tech1 = tech_dict['tech1']
    assert tech1['total_tickets'] > 0
    assert tech1['resolved_tickets'] > 0
    assert tech1['avg_rating'] > 0

    # Check filtering by technician
    tech1_data = TechnicianAnalytics.get_technician_performance(
        technician_id=setup_test_data["technician1"].id)
    assert len(tech1_data) == 1
    assert tech1_data[0]['username'] == 'tech1'


@pytest.mark.django_db
def test_admin_analytics_system_overview(setup_test_data):
    """Test AdminAnalytics.get_system_overview."""
    overview = AdminAnalytics.get_system_overview()

    assert overview['total_tickets'] == 18
    assert overview['open_tickets'] == 5
    assert overview['resolved_tickets'] == 10  # 5 resolved + 5 closed
    assert overview['resolution_rate'] > 0
    assert overview['new_tickets_24h'] == 5  # Today's tickets


@pytest.mark.django_db
def test_ticket_analytics_api_endpoint(setup_test_data, client):
    """Test the ticket analytics API endpoint."""
    # Login as admin
    client.login(username='admin', password='password')

    # Make API request
    url = reverse('analytics-tickets')
    response = client.get(url)

    assert response.status_code == 200
    assert 'ticket_counts' in response.data
    assert 'status_counts' in response.data
    assert 'trend_data' in response.data
    assert 'facility_distribution' in response.data
    assert 'section_distribution' in response.data


@pytest.mark.django_db
def test_admin_analytics_api_endpoint(setup_test_data, client):
    """Test the admin dashboard analytics API endpoint."""
    # Login as admin
    client.login(username='admin', password='password')

    # Make API request
    url = reverse('analytics-admin')
    response = client.get(url)

    assert response.status_code == 200
    assert 'system_overview' in response.data
    assert 'overdue_tickets' in response.data


@pytest.mark.django_db
def test_technician_analytics_api_endpoint(setup_test_data, client):
    """Test the technician analytics API endpoint."""
    # Login as admin
    client.login(username='admin', password='password')

    # Make API request
    url = reverse('analytics-technicians')
    response = client.get(url)

    assert response.status_code == 200
    assert 'technician_performance' in response.data
    assert len(response.data['technician_performance']) == 2  # Two technicians

    # Test filtering by technician
    url = f"{reverse('analytics-technicians')}?technician_id={setup_test_data['technician1'].id}"
    response = client.get(url)

    assert response.status_code == 200
    assert len(response.data['technician_performance']) == 1
    assert response.data['technician_performance'][0]['username'] == 'tech1'
