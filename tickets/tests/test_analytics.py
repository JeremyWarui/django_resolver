"""
Tests for the analytics functionality, including data consistency and edge cases.
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

    # print(Ticket.objects.all())

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

    # print(Ticket.objects.filter(created_at=yesterday))

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

    # print(Ticket.objects.filter(created_at=last_week))
    # print(Ticket.objects.filter(facility=facility1))

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
    # print(today_count)
    assert today_count['count'] == 5

    # Check yesterday's tickets
    yesterday_count = TicketAnalytics.get_ticket_counts_by_timeframe(days=2)
    # print(yesterday_count)
    assert yesterday_count['count'] == 8  # 5 today + 3 yesterday

    # Check last week's tickets
    week_count = TicketAnalytics.get_ticket_counts_by_timeframe(days=10)
    # print(week_count)
    assert week_count['count'] == 18  # 5 today + 3 yesterday + 10 last week

    # Check filtering by facility
    facility1_count = TicketAnalytics.get_ticket_counts_by_timeframe(
        days=10, facility_id=setup_test_data["facility1"].id)
    # print(facility1_count)
    facility2_count = TicketAnalytics.get_ticket_counts_by_timeframe(
        days=10, facility_id=setup_test_data["facility2"].id)
    # print(facility2_count)

    assert facility1_count['count'] == 10
    assert facility2_count["count"] == 8


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
    print(overview)

    assert overview['total_tickets'] == 18
    assert overview['open_tickets'] == 5
    assert overview['resolved_tickets'] == 10  # 5 resolved + 5 closed
    assert overview['resolution_rate'] > 0
    assert overview['new_tickets_24h'] == 5  # Today's tickets


@pytest.mark.django_db
def test_admin_analytics_avg_response_time_hours(setup_test_data):
    """
    Verify that avg_resolution_time_hours is computed correctly
    from created_at → resolved_at duration across tickets.
    """
    Ticket.objects.all().delete()

    overview = AdminAnalytics.get_system_overview()
    # Use the new key
    assert 'avg_resolution_time_hours' in overview
    assert overview['avg_resolution_time_hours'] is None

    # Define the time difference for a precise 5-hour duration
    created_at = timezone.now() - timedelta(hours=10)
    resolved_at = timezone.now() - timedelta(hours=5)  # 5 hours after creation

    # 1. Create the ticket (status is initially 'open')
    test_ticket = Ticket.objects.create(
        title='Resolution Time Test',
        description='Testing average resolution time',
        status='open',  # Start open
        section=setup_test_data['section1'],
        facility=setup_test_data['facility1'],
        raised_by=setup_test_data['user'],
    )

    # 2. Use .update() to simulate the history
    # Set created_at to 10 hours ago
    Ticket.objects.filter(id=test_ticket.id).update(created_at=created_at)

    # 3. Simulate the resolution event by setting status to resolved and resolved_at
    Ticket.objects.filter(id=test_ticket.id).update(
        status='resolved',
        resolved_at=resolved_at,
        updated_at=resolved_at  # updated_at should also be set to this time
    )

    # Calculate the expected value (10 hours ago to 5 hours ago = 5 hours)
    expected_hours = 5.0

    overview_updated = AdminAnalytics.get_system_overview()

    assert overview_updated['avg_resolution_time_hours'] is not None
    # Assert that the calculated value is exactly 5.0 hours
    assert overview_updated['avg_resolution_time_hours'] == expected_hours


@pytest.mark.django_db
def test_admin_analytics_get_overdue_tickets(setup_test_data):
    """
    Verify that get_overdue_tickets returns tickets older than 24h
    which are still open/assigned/in_progress/pending.
    """
    Ticket.objects.all().delete()

    now = timezone.now()

    # Create an overdue open ticket (created 2 days ago)
    overdue_ticket = Ticket.objects.create(
        title='Overdue Ticket',
        description='Should appear in overdue list',
        status='open',
        facility=setup_test_data["facility1"],
        section=setup_test_data["section1"],
        raised_by=setup_test_data["user"],
    )

    # FIX: Update the dates using .update() to bypass auto_now logic and set it 2 days ago
    Ticket.objects.filter(id=overdue_ticket.id).update(
        created_at=now - timedelta(days=2),
        updated_at=now - timedelta(days=2)
    )

    # Create a non-overdue (fresh) ticket (created 1 hour ago)
    recent_ticket = Ticket.objects.create(
        title='Recent Ticket',
        description='Should NOT appear in overdue list',
        status='open',
        facility=setup_test_data["facility1"],
        section=setup_test_data["section1"],
        raised_by=setup_test_data["user"],

    )
    # Set created_at 1 hour ago (not overdue)
    Ticket.objects.filter(id=recent_ticket.id).update(
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1)
    )

    # Create a resolved (old but not overdue by definition)
    resolved_ticket = Ticket.objects.create(
        title='Resolved Ticket',
        description='Should NOT appear in overdue list',
        status='resolved',
        facility=setup_test_data["facility1"],
        section=setup_test_data["section1"],
        raised_by=setup_test_data["user"],
        created_at=now - timedelta(days=3),
        updated_at=now - timedelta(days=2)
    )

    overdue_tickets = AdminAnalytics.get_overdue_tickets()

    # Confirm only the overdue open ticket appears
    assert isinstance(overdue_tickets, list)
    assert len(overdue_tickets) >= 1
    ticket_titles = [t['title'] for t in overdue_tickets]

    assert 'Overdue Ticket' in ticket_titles
    assert 'Recent Ticket' not in ticket_titles
    assert 'Resolved Ticket' not in ticket_titles

    # Validate age hours are correctly calculated (> 24)
    for t in overdue_tickets:
        assert t['age_hours'] >= 24
        assert t['status'] in ['open', 'assigned', 'in_progress', 'pending']


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


@pytest.fixture
def setup_consistency_data(db):
    """Create basic set of tickets with various statuses for consistency tests"""
    # Create required related objects
    section = Section.objects.create(name="Test Section")
    facility = Facility.objects.create(name="Test Facility")
    user = CustomUser.objects.create(username="testuser")
    technician = CustomUser.objects.create(
        username="techtester", role="technician")

    # Create tickets with different statuses
    now = timezone.now()

    # Open ticket
    Ticket.objects.create(
        ticket_no="TKT-001",
        title="Open Ticket",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
        created_at=now - timedelta(days=2)
    )

    # Resolved ticket with proper resolved_at
    resolved_ticket = Ticket.objects.create(
        ticket_no="TKT-002",
        title="Resolved Ticket",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="resolved",
        created_at=now - timedelta(days=1)
    )
    resolved_ticket.status = "resolved"
    # This should set resolved_at through model logic
    resolved_ticket.save(performed_by=technician)

    # Closed ticket with proper resolved_at
    closed_ticket = Ticket.objects.create(
        ticket_no="TKT-003",
        title="Closed Ticket",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="closed",
        created_at=now - timedelta(days=1)
    )
    closed_ticket.status = "closed"
    # This should set resolved_at through model logic
    closed_ticket.save(performed_by=technician)

    # In progress ticket
    Ticket.objects.create(
        ticket_no="TKT-004",
        title="In Progress Ticket",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="in_progress",
        created_at=now
    )

    return {
        'section': section,
        'facility': facility,
        'user': user,
        'technician': technician
    }


class TestAnalyticsConsistency:
    """Test suite for verifying analytics data consistency"""

    def test_resolved_tickets_count_consistency(self, setup_consistency_data):
        """
        Verify that the number of resolved tickets in analytics matches
        the actual number of resolved/closed tickets with resolved_at timestamps
        """
        # Get analytics data
        overview = AdminAnalytics.get_system_overview()
        resolved_count_from_analytics = overview['resolved_tickets']

        # Get actual data - both conditions must be met
        actual_resolved_count = Ticket.objects.filter(
            status__in=['resolved', 'closed'],
            resolved_at__isnull=False
        ).count()

        # Also get just status-based count for comparison
        status_based_count = Ticket.objects.filter(
            status__in=['resolved', 'closed']
        ).count()

        # Verify consistency
        assert resolved_count_from_analytics == actual_resolved_count, (
            f"Analytics shows {resolved_count_from_analytics} resolved tickets, "
            f"but there are {actual_resolved_count} tickets that are both "
            f"resolved/closed AND have resolved_at timestamps"
        )

        # Verify that all resolved/closed tickets have resolved_at
        assert actual_resolved_count == status_based_count, (
            f"Found {status_based_count} tickets marked as resolved/closed "
            f"but only {actual_resolved_count} have resolved_at timestamps. "
            "All resolved/closed tickets should have resolved_at set."
        )

    def test_open_tickets_count_consistency(self, setup_consistency_data):
        """
        Verify that the number of open tickets in analytics matches
        the actual number of tickets with 'open' status
        """
        # Get analytics data
        overview = AdminAnalytics.get_system_overview()
        open_count_from_analytics = overview['open_tickets']

        # Get actual count
        actual_open_count = Ticket.objects.filter(status='open').count()

        assert open_count_from_analytics == actual_open_count, (
            f"Analytics shows {open_count_from_analytics} open tickets, "
            f"but there are actually {actual_open_count} tickets with 'open' status"
        )

    def test_resolution_rate_consistency(self, setup_consistency_data):
        """
        Verify that the resolution rate calculation is consistent with
        the ratio of resolved tickets to total tickets
        """
        # Get analytics data
        overview = AdminAnalytics.get_system_overview()
        resolution_rate_from_analytics = overview['resolution_rate']

        # Calculate actual rate
        total_tickets = Ticket.objects.count()
        resolved_tickets = Ticket.objects.filter(
            status__in=['resolved', 'closed'],
            resolved_at__isnull=False
        ).count()

        expected_rate = (resolved_tickets / total_tickets *
                         100) if total_tickets else 0
        expected_rate = round(expected_rate, 2)

        assert resolution_rate_from_analytics == expected_rate, (
            f"Analytics shows {resolution_rate_from_analytics}% resolution rate, "
            f"but actual calculation gives {expected_rate}%"
        )

    def test_resolution_time_consistency(self, setup_consistency_data):
        """
        Verify that resolution time calculations are consistent with
        the actual time differences in the database
        """
        # Get analytics data
        overview = AdminAnalytics.get_system_overview()
        avg_resolution_hours = overview['avg_resolution_time_hours']

        # Get resolved tickets
        resolved_tickets = Ticket.objects.filter(
            status__in=['resolved', 'closed'],
            resolved_at__isnull=False
        )

        # Calculate actual average resolution time
        total_hours = 0
        for ticket in resolved_tickets:
            resolution_time = ticket.resolved_at - ticket.created_at
            total_hours += resolution_time.total_seconds() / 3600

        expected_avg_hours = (
            round(total_hours / resolved_tickets.count(), 2)
            if resolved_tickets.exists() else None
        )

        assert avg_resolution_hours == expected_avg_hours, (
            f"Analytics shows average resolution time of {avg_resolution_hours} hours, "
            f"but actual calculation gives {expected_avg_hours} hours"
        )

    def test_tickets_by_age_consistency(self, setup_consistency_data):
        """
        Verify that ticket age calculations are consistent with
        the actual creation dates in the database
        """
        # Get analytics data
        overview = AdminAnalytics.get_system_overview()

        # Test last 24 hours
        now = timezone.now()
        day_ago = now - timedelta(days=1)
        actual_new_tickets = Ticket.objects.filter(
            created_at__gte=day_ago).count()
        assert overview['new_tickets_24h'] == actual_new_tickets, (
            "Mismatch in number of tickets created in last 24 hours"
        )

        # Test last week
        week_ago = now - timedelta(days=7)
        actual_week_tickets = Ticket.objects.filter(
            created_at__gte=week_ago).count()
        assert overview['tickets_past_week'] == actual_week_tickets, (
            "Mismatch in number of tickets created in last week"
        )

        # Test last month
        month_ago = now - timedelta(days=30)
        actual_month_tickets = Ticket.objects.filter(
            created_at__gte=month_ago).count()
        assert overview['tickets_past_month'] == actual_month_tickets, (
            "Mismatch in number of tickets created in last month"
        )


@pytest.mark.django_db
class TestAnalyticsEdgeCases:
    """Test suite for edge cases in analytics functionality"""

    def test_empty_database_analytics(self, db):
        """Test analytics behavior with no data in the database"""
        # Clean the database
        Ticket.objects.all().delete()
        CustomUser.objects.all().delete()
        Section.objects.all().delete()
        Facility.objects.all().delete()

        # Test ticket analytics with empty database
        ticket_counts = TicketAnalytics.get_ticket_counts_by_timeframe()
        assert ticket_counts['count'] == 0, "Empty database should return 0 tickets"

        status_counts = TicketAnalytics.get_ticket_counts_by_status()
        assert len(
            status_counts) == 0, "Empty database should return no status counts"

        facility_dist = TicketAnalytics.get_tickets_by_facility()
        assert len(
            facility_dist) == 0, "Empty database should return no facility distribution"

        # Test technician analytics with empty database
        tech_performance = TechnicianAnalytics.get_technician_performance()
        assert len(
            tech_performance) == 0, "Empty database should return no technician performance data"

        tech_ratings = TechnicianAnalytics.get_technician_ratings_by_section()
        assert len(
            tech_ratings) == 0, "Empty database should return no technician ratings"

        # Test admin analytics with empty database
        overview = AdminAnalytics.get_system_overview()
        assert overview['total_tickets'] == 0, "Empty database should show 0 total tickets"
        assert overview['resolution_rate'] == 0, "Empty database should show 0% resolution rate"
        assert overview['avg_resolution_time_hours'] is None, "Empty database should show None for avg resolution time"

        overdue = AdminAnalytics.get_overdue_tickets()
        assert len(overdue) == 0, "Empty database should show no overdue tickets"

    def test_single_ticket_analytics(self, db):
        """Test analytics behavior with just one ticket"""
        # Create minimum required objects
        section = Section.objects.create(name="Test Section")
        facility = Facility.objects.create(name="Test Facility")
        user = CustomUser.objects.create_user(
            username="testuser",
            password="password",
            role="user"
        )

        # Create a single ticket
        ticket = Ticket.objects.create(
            title="Single Ticket",
            description="Test",
            section=section,
            facility=facility,
            raised_by=user,
            status="open"
        )

        # Test ticket analytics
        ticket_counts = TicketAnalytics.get_ticket_counts_by_timeframe()
        assert ticket_counts['count'] == 1, "Should count single ticket"

        status_counts = TicketAnalytics.get_ticket_counts_by_status()
        assert len(status_counts) == 1, "Should show one status count"
        assert status_counts[0]['status'] == 'open', "Should show correct status"

        # Test admin analytics
        overview = AdminAnalytics.get_system_overview()
        assert overview['total_tickets'] == 1, "Should show 1 total ticket"
        assert overview['open_tickets'] == 1, "Should show 1 open ticket"
        assert overview['resolved_tickets'] == 0, "Should show 0 resolved tickets"
        assert overview['resolution_rate'] == 0, "Should show 0% resolution rate"

    def test_invalid_technician_analytics(self, db):
        """Test technician analytics with invalid or edge case scenarios"""
        # Create a technician with no assigned tickets
        tech = CustomUser.objects.create_user(
            username="lonelytechnician",
            password="password",
            role="technician"
        )

        # Test technician analytics
        tech_performance = TechnicianAnalytics.get_technician_performance(
            tech.id)
        assert len(tech_performance) == 1, "Should return data for technician"
        assert tech_performance[0]['total_tickets'] == 0, "Should show 0 total tickets"
        assert tech_performance[0]['resolved_tickets'] == 0, "Should show 0 resolved tickets"
        assert tech_performance[0]['resolution_percentage'] == 0, "Should show 0% resolution rate"

    def test_boundary_conditions(self, db):
        """Test analytics with boundary conditions like extremely old tickets"""
        section = Section.objects.create(name="Test Section")
        facility = Facility.objects.create(name="Test Facility")
        user = CustomUser.objects.create_user(
            username="testuser",
            password="password",
            role="user"
        )

        # Create a very old ticket
        old_date = timezone.now() - timedelta(days=365*10)  # 10 years ago
        old_ticket = Ticket.objects.create(
            title="Very Old Ticket",
            description="Test",
            section=section,
            facility=facility,
            raised_by=user,
            status="open"
        )
        # Update the creation date manually
        Ticket.objects.filter(id=old_ticket.id).update(
            created_at=old_date,
            updated_at=old_date
        )

        # Test ticket analytics
        ticket_counts = TicketAnalytics.get_ticket_counts_by_timeframe(
            days=365*10+1)
        assert ticket_counts['count'] == 1, "Should count very old ticket when timeframe is sufficient"

        ticket_counts = TicketAnalytics.get_ticket_counts_by_timeframe(days=1)
        assert ticket_counts['count'] == 0, "Should not count very old ticket in recent timeframe"

        # Test admin analytics with old ticket
        overview = AdminAnalytics.get_system_overview()
        assert overview['total_tickets'] == 1, "Should count very old ticket in total"
        assert overview['new_tickets_24h'] == 0, "Should not count very old ticket in last 24h"

        # Test overdue tickets with old ticket
        overdue = AdminAnalytics.get_overdue_tickets()
        assert len(
            overdue) == 1, "Very old open ticket should be counted as overdue"
        assert overdue[0]['age_hours'] > 24, "Age hours should be greater than 24 for old ticket"
