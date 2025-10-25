"""
Tests to verify consistency between analytics calculations and actual data.
These tests ensure that our analytics accurately reflect the state of the database.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from tickets.models import Ticket, Section, Facility, CustomUser
from tickets.api.analytics.analytics import AdminAnalytics


@pytest.fixture
def setup_basic_data(db):
    """Create a basic set of tickets with various statuses"""
    # Create required related objects
    section = Section.objects.create(name="Test Section")
    facility = Facility.objects.create(name="Test Facility")
    user = CustomUser.objects.create(username="testuser")
    technician = CustomUser.objects.create(username="techtester", role="technician")

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
    resolved_ticket.save()  # This should set resolved_at through model logic

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
    closed_ticket.save()  # This should set resolved_at through model logic

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


@pytest.mark.django_db
class TestAnalyticsConsistency:
    """Test suite for verifying analytics data consistency"""

    def test_resolved_tickets_count_consistency(self, setup_basic_data):
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

    def test_open_tickets_count_consistency(self, setup_basic_data):
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

    def test_resolution_rate_consistency(self, setup_basic_data):
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
        
        expected_rate = (resolved_tickets / total_tickets * 100) if total_tickets else 0
        expected_rate = round(expected_rate, 2)

        assert resolution_rate_from_analytics == expected_rate, (
            f"Analytics shows {resolution_rate_from_analytics}% resolution rate, "
            f"but actual calculation gives {expected_rate}%"
        )

    def test_resolution_time_consistency(self, setup_basic_data):
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

    def test_tickets_by_age_consistency(self, setup_basic_data):
        """
        Verify that ticket age calculations are consistent with
        the actual creation dates in the database
        """
        # Get analytics data
        overview = AdminAnalytics.get_system_overview()
        
        # Test last 24 hours
        now = timezone.now()
        day_ago = now - timedelta(days=1)
        actual_new_tickets = Ticket.objects.filter(created_at__gte=day_ago).count()
        assert overview['new_tickets_24h'] == actual_new_tickets, (
            "Mismatch in number of tickets created in last 24 hours"
        )

        # Test last week
        week_ago = now - timedelta(days=7)
        actual_week_tickets = Ticket.objects.filter(created_at__gte=week_ago).count()
        assert overview['tickets_past_week'] == actual_week_tickets, (
            "Mismatch in number of tickets created in last week"
        )

        # Test last month
        month_ago = now - timedelta(days=30)
        actual_month_tickets = Ticket.objects.filter(created_at__gte=month_ago).count()
        assert overview['tickets_past_month'] == actual_month_tickets, (
            "Mismatch in number of tickets created in last month"
        )