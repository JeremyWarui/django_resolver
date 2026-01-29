"""
Base test classes with shared fixtures for all ticket tests.

This module provides reusable test fixtures to eliminate duplication across test files.
Tests inherit from BaseTicketTestCase to get common test data (users, sections, facilities, tickets).

Usage:
    from tickets.tests.base import BaseTicketTestCase
    
    class MyTests(BaseTicketTestCase):
        def test_something(self):
            # Access self.user, self.section, self.facility, etc.
            self.assertEqual(self.user.username, "testuser")
"""

from django.test import TestCase
from django.db import connection
from tickets.models import (
    CustomUser,
    Section,
    Facility,
    Ticket,
    Comment,
    Feedback,
)


class BaseTicketTestCase(TestCase):
    """
    Base test case with common fixtures for all ticket tests.

    Uses setUpTestData() for better performance - fixtures are created once
    per test class rather than once per test method.

    Provides:
        - self.user: Regular user (role='user')
        - self.admin: Admin user (role='admin')
        - self.technician: Technician user (role='technician')
        - self.section: IT section
        - self.section_hvac: HVAC section (for multi-section tests)
        - self.facility: Main Building facility
        - self.ticket: Sample ticket (assigned to technician)
    """

    @classmethod
    def setUpTestData(cls):
        """
        Create shared test data once per test class (faster than setUp).

        Data persists across all test methods in the class but is rolled back
        after the class completes. Don't modify these objects in tests, or create
        new instances if you need to test mutations.
        """
        # Create regular user
        cls.user = CustomUser.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass",
            first_name="Test",
            last_name="User",
            role="user",
        )

        # Create admin user
        cls.admin = CustomUser.objects.create_user(
            username="adminuser",
            email="adminuser@example.com",
            password="adminpass",
            first_name="Admin",
            last_name="User",
            role="admin",
            is_staff=True,
        )

        # Create sections
        cls.section = Section.objects.create(
            name="IT",
            description="Information Technology"
        )

        cls.section_hvac = Section.objects.create(
            name="HVAC",
            description="Heating and cooling"
        )

        # Create facility
        cls.facility = Facility.objects.create(
            name="Main Building",
            type="building",
            status="active",
            location="123 Main St",
        )

        # Create technician and assign to IT section
        cls.technician = CustomUser.objects.create_user(
            username="techuser",
            email="techuser@example.com",
            password="techpass",
            first_name="Tech",
            last_name="User",
            role="technician",
        )
        cls.technician.sections.add(cls.section)

        # Create a sample ticket
        cls.ticket = Ticket.objects.create(
            title="Test Ticket",
            description="This is a test ticket for common test scenarios.",
            section=cls.section,
            facility=cls.facility,
            raised_by=cls.user,
            assigned_to=cls.technician,
            status="assigned",
        )

    def reset_ticket_sequence(self):
        """
        Reset PostgreSQL ticket ID sequence to start from 1.

        Call this in setUp() if your test needs predictable ticket IDs
        (e.g., testing ticket number generation).

        Example:
            def setUp(self):
                self.reset_ticket_sequence()
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "ALTER SEQUENCE tickets_ticket_id_seq RESTART WITH 1;")

    def create_ticket(self, **kwargs):
        """
        Helper to create additional tickets with sensible defaults.

        Args:
            **kwargs: Override any ticket fields

        Returns:
            Ticket: Newly created ticket

        Example:
            ticket = self.create_ticket(title="Custom Ticket", status="open")
        """
        defaults = {
            "title": "Additional Test Ticket",
            "description": "Additional ticket for testing",
            "section": self.section,
            "facility": self.facility,
            "raised_by": self.user,
        }
        defaults.update(kwargs)
        return Ticket.objects.create(**defaults)

    def create_comment(self, ticket=None, author=None, **kwargs):
        """
        Helper to create comments with sensible defaults.

        Args:
            ticket: Ticket to comment on (defaults to self.ticket)
            author: Comment author (defaults to self.user)
            **kwargs: Override any comment fields

        Returns:
            Comment: Newly created comment
        """
        defaults = {
            "ticket": ticket or self.ticket,
            "author": author or self.user,
            "text": "Test comment",
        }
        defaults.update(kwargs)
        return Comment.objects.create(**defaults)

    def create_feedback(self, ticket=None, rated_by=None, **kwargs):
        """
        Helper to create feedback with sensible defaults.

        Args:
            ticket: Ticket to give feedback on (defaults to self.ticket)
            rated_by: User giving feedback (defaults to self.user)
            **kwargs: Override any feedback fields

        Returns:
            Feedback: Newly created feedback
        """
        defaults = {
            "ticket": ticket or self.ticket,
            "rated_by": rated_by or self.user,
            "rating": 4,
            "comment": "Good job",
        }
        defaults.update(kwargs)
        return Feedback.objects.create(**defaults)


class BaseAPITestCase(BaseTicketTestCase):
    """
    Extended base class for API tests with authenticated client.

    Provides everything from BaseTicketTestCase plus:
        - self.client: APIClient instance (from DRF)
        - Automatically authenticates as self.user

    Usage:
        from tickets.tests.base import BaseAPITestCase

        class MyAPITests(BaseAPITestCase):
            def test_api_endpoint(self):
                response = self.client.get('/api/tickets/')
                self.assertEqual(response.status_code, 200)
    """

    def setUp(self):
        """Set up API client and authenticate."""
        from rest_framework.test import APIClient

        self.client = APIClient()
        # Authenticate as regular user by default
        self.client.force_authenticate(user=self.user)

    def authenticate_as(self, user):
        """
        Switch authentication to a different user.

        Args:
            user: User to authenticate as (e.g., self.admin, self.technician)

        Example:
            self.authenticate_as(self.admin)
            response = self.client.delete(f'/api/tickets/{ticket.id}/')
        """
        self.client.force_authenticate(user=user)

    def unauthenticate(self):
        """Remove authentication (test unauthorized access)."""
        self.client.force_authenticate(user=None)
