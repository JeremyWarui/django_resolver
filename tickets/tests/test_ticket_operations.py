"""
Tests for ticket creation, updating, and technician assignment.
Run with: python manage.py test tickets.tests.test_ticket_operations
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from tickets.models import Ticket, CustomUser, Section, Facility


class TicketOperationsTestCase(TestCase):
    """Test ticket POST/PATCH operations and technician filtering."""

    def setUp(self):
        """Set up test data."""
        # Create sections
        self.section_hvac = Section.objects.create(
            name="HVAC", description="Heating and cooling"
        )
        self.section_plumbing = Section.objects.create(
            name="Plumbing", description="Water systems"
        )

        # Create facility
        self.facility = Facility.objects.create(
            name="Main Building", type="building")

        # Create users
        self.user = CustomUser.objects.create_user(
            username="testuser",
            password="testpass",
            first_name="Test",
            last_name="User",
            role="user",
        )

        self.admin = CustomUser.objects.create_user(
            username="admin",
            password="testpass",
            first_name="Admin",
            last_name="User",
            role="admin",
        )

        self.tech_hvac = CustomUser.objects.create_user(
            username="hvac.tech",
            password="testpass",
            first_name="HVAC",
            last_name="Tech",
            role="technician",
        )
        self.tech_hvac.sections.add(self.section_hvac)

        self.tech_plumbing = CustomUser.objects.create_user(
            username="plumb.tech",
            password="testpass",
            first_name="Plumb",
            last_name="Tech",
            role="technician",
        )
        self.tech_plumbing.sections.add(self.section_plumbing)

        self.tech_both = CustomUser.objects.create_user(
            username="multi.tech",
            password="testpass",
            first_name="Multi",
            last_name="Tech",
            role="technician",
        )
        self.tech_both.sections.add(self.section_hvac, self.section_plumbing)

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_ticket(self):
        """Test creating a new ticket."""
        data = {
            "title": "Broken AC",
            "description": "AC not working",
            "section_id": self.section_hvac.id,
            "facility_id": self.facility.id,
        }

        response = self.client.post("/api/tickets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Broken AC")
        self.assertEqual(response.data["status"], "open")
        self.assertIsNotNone(response.data["ticket_no"])
        self.assertTrue(response.data["ticket_no"].startswith("TKT-"))

    def test_ticket_includes_available_technicians(self):
        """Test that ticket response includes available technicians."""
        data = {
            "title": "Broken AC",
            "description": "AC not working",
            "section_id": self.section_hvac.id,
            "facility_id": self.facility.id,
        }

        response = self.client.post("/api/tickets/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("available_technicians", response.data)

        # Should have 2 technicians (hvac.tech and multi.tech)
        available_techs = response.data["available_technicians"]
        self.assertEqual(len(available_techs), 2)

        tech_usernames = [t["username"] for t in available_techs]
        self.assertIn("hvac.tech", tech_usernames)
        self.assertIn("multi.tech", tech_usernames)
        self.assertNotIn("plumb.tech", tech_usernames)

    def test_assign_technician_to_ticket(self):
        """Test assigning a technician to a ticket."""
        # Switch to admin to perform assignment
        self.client.force_authenticate(user=self.admin)

        # Create ticket
        ticket = Ticket.objects.create(
            title="Broken AC",
            description="AC not working",
            section=self.section_hvac,
            facility=self.facility,
            raised_by=self.user,
        )

        # Assign technician
        data = {"assigned_to_id": self.tech_hvac.id}
        response = self.client.patch(
            f"/api/tickets/{ticket.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assigned_to"]["id"], self.tech_hvac.id)
        self.assertEqual(response.data["status"], "assigned")

    def test_cannot_assign_wrong_section_technician(self):
        """Test that assigning technician from wrong section fails."""
        # Switch to admin to perform assignment
        self.client.force_authenticate(user=self.admin)

        # Create HVAC ticket
        ticket = Ticket.objects.create(
            title="Broken AC",
            description="AC not working",
            section=self.section_hvac,
            facility=self.facility,
            raised_by=self.user,
        )

        # Try to assign plumbing technician (should fail)
        data = {"assigned_to_id": self.tech_plumbing.id}
        response = self.client.patch(
            f"/api/tickets/{ticket.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_assign_multi_section_technician(self):
        """Test that technician with multiple sections can be assigned."""
        # Switch to admin to perform assignment
        self.client.force_authenticate(user=self.admin)

        # Create HVAC ticket
        ticket = Ticket.objects.create(
            title="Broken AC",
            description="AC not working",
            section=self.section_hvac,
            facility=self.facility,
            raised_by=self.user,
        )

        # Assign multi-section technician (should work)
        data = {"assigned_to_id": self.tech_both.id}
        response = self.client.patch(
            f"/api/tickets/{ticket.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["assigned_to"]["id"], self.tech_both.id)

    def test_update_ticket_status(self):
        """Test updating ticket status."""
        ticket = Ticket.objects.create(
            title="Broken AC",
            description="AC not working",
            section=self.section_hvac,
            facility=self.facility,
            raised_by=self.user,
            assigned_to=self.tech_hvac,
        )
        ticket.status = "assigned"
        ticket.save()

        # Authenticate as technician to update status
        self.client.force_authenticate(user=self.tech_hvac)

        # Update to in_progress
        data = {"status": "in_progress"}
        response = self.client.patch(
            f"/api/tickets/{ticket.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_progress")

    def test_get_technicians_by_section(self):
        """Test fetching technicians filtered by section."""
        # Authenticate as admin to access technicians endpoint
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(
            f"/api/technicians/?section_id={self.section_hvac.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include hvac.tech and multi.tech, but not plumb.tech
        usernames = [t["username"] for t in response.data]
        self.assertIn("hvac.tech", usernames)
        self.assertIn("multi.tech", usernames)
        self.assertNotIn("plumb.tech", usernames)

    def test_get_all_technicians(self):
        """Test fetching all technicians without section filter."""
        # Authenticate as admin to access technicians endpoint
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/technicians/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should include all 3 test technicians
        usernames = [t["username"] for t in response.data]
        self.assertIn("hvac.tech", usernames)
        self.assertIn("plumb.tech", usernames)
        self.assertIn("multi.tech", usernames)

    def test_update_multiple_fields(self):
        """Test updating title, description, and status together."""
        # Switch to admin to perform assignment
        self.client.force_authenticate(user=self.admin)

        ticket = Ticket.objects.create(
            title="Old Title",
            description="Old description",
            section=self.section_hvac,
            facility=self.facility,
            raised_by=self.user,
        )

        data = {
            "title": "Updated Title",
            "description": "Updated description",
            "assigned_to_id": self.tech_hvac.id,
        }

        response = self.client.patch(
            f"/api/tickets/{ticket.id}/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Updated Title")
        self.assertEqual(response.data["description"], "Updated description")
        self.assertEqual(response.data["assigned_to"]["id"], self.tech_hvac.id)
