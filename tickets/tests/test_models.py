from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import IntegrityError, connection
from tickets.models import *
from django.utils import timezone
from datetime import timedelta

# Create your tests here.
User = get_user_model()


class ModelTests(TestCase):

    def setUp(self):
        # Reset Postgres sequence so IDs start from 1 again
        with connection.cursor() as cursor:
            cursor.execute("ALTER SEQUENCE tickets_ticket_id_seq RESTART WITH 1;")
        self.user = CustomUser.objects.create_user(
            username="testuser", email="testuser@example.com", password="testpass"
        )
        self.section = Section.objects.create(
            name="IT", description="Information Technology"
        )
        self.facility = Facility.objects.create(
            name="Main Building",
            type="building",
            status="active",
            location="123 Main St",
        )
        self.technician = CustomUser.objects.create_user(
            username="techuser",
            email="techuser@example.com",
            password="techpass",
            role="technician",
        )
        self.ticket = Ticket.objects.create(
            title="Faulty Printer",
            description="The printer in the IT section is not working.",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            assigned_to=self.technician,
            status="assigned",
        )

    def test_user_creation(self):
        """test the user creation"""
        self.assertEqual(self.user.username, "testuser")
        self.assertEqual(self.user.email, "testuser@example.com")
        self.assertTrue(self.user.check_password("testpass"))

    def test_section_creation(self):
        """test the section creation"""
        self.assertEqual(self.section.name, "IT")
        self.assertEqual(self.section.description, "Information Technology")

    def test_technician_creation(self):
        """test the technician creation"""
        self.assertEqual(self.technician.username, "techuser")
        self.assertEqual(self.technician.email, "techuser@example.com")
        self.assertEqual(self.technician.role, "technician")
        self.assertTrue(self.technician.check_password("techpass"))

    def test_ticket_creation(self):
        """test ticket creation"""
        self.assertEqual(self.ticket.title, "Faulty Printer")
        self.assertEqual(
            self.ticket.description, "The printer in the IT section is not working."
        )
        self.assertEqual(self.ticket.section, self.section)
        self.assertEqual(self.ticket.facility, self.facility)
        self.assertEqual(self.ticket.raised_by, self.user)
        self.assertEqual(self.ticket.assigned_to, self.technician)
        self.assertEqual(self.ticket.status, "assigned")

    def test_ticket_auto_numbering(self):
        """Test that ticket numbers are automatically generated with correct format"""
        # Check format of first ticket
        self.assertTrue(self.ticket.ticket_no.startswith("TKT-"))
        self.assertEqual(len(self.ticket.ticket_no), 10)

        # Create more tickets and check sequential numbering
        tickets = []
        for i in range(5):
            ticket = Ticket.objects.create(
                title=f"Test Ticket {i}",
                description=f"Auto-number test ticket {i}",
                section=self.section,
                facility=self.facility,
                raised_by=self.user,
                status="open",
            )
            tickets.append(ticket)

        # Check that numbers are sequential
        for i in range(1, len(tickets)):
            prev_num = int(tickets[i - 1].ticket_no.split("-")[1])
            curr_num = int(tickets[i].ticket_no.split("-")[1])
            self.assertEqual(prev_num + 1, curr_num)

    def test_section_technician_relationship(self):
        """Test M2M relationship between sections and technicians"""
        # Create additional sections and technicians
        plumbing = Section.objects.create(name="Plumbing", description="Water systems")
        electrical = Section.objects.create(
            name="Electrical", description="Electrical systems"
        )

        tech1 = CustomUser.objects.create_user(
            username="plumber",
            email="plumber@example.com",
            password="pass123",
            role="technician",
        )

        tech2 = CustomUser.objects.create_user(
            username="electrician",
            email="electrician@example.com",
            password="pass123",
            role="technician",
        )

        # Set relationships
        tech1.sections.add(plumbing)
        tech2.sections.add(electrical)
        self.technician.sections.add(self.section)
        tech2.sections.add(self.section)  # Electrician also in IT

        # Test relationships from technician to section
        self.assertEqual(tech1.sections.count(), 1)
        self.assertEqual(tech1.sections.first(), plumbing)

        self.assertEqual(tech2.sections.count(), 2)
        self.assertTrue(self.section in tech2.sections.all())
        self.assertTrue(electrical in tech2.sections.all())

        # Test relationships from section to technician
        self.assertEqual(plumbing.technicians.count(), 1)
        self.assertEqual(plumbing.technicians.first(), tech1)

        self.assertEqual(self.section.technicians.count(), 2)
        self.assertTrue(self.technician in self.section.technicians.all())
        self.assertTrue(tech2 in self.section.technicians.all())

    def test_ticket_status_after_assignment(self):
        """test ticket status after assignment"""
        self.ticket.assigned_to = self.technician
        # Use model helper to change assignment and log atomically
        self.ticket.change_assignment(self.technician, performed_by=self.user)
        self.assertEqual(self.ticket.status, "assigned")

    def test_ticket_creation_and_auto_increment_ticket_no(self):
        """test ticket creation and auto increment ticket_no"""
        initial_ticket_no = self.ticket.ticket_no
        new_ticket = Ticket.objects.create(
            title="Faulty Monitor",
            description="The monitor in the IT section is not working.",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status="open",
        )
        prev_number = int(initial_ticket_no.split("-")[-1])
        new_number = int(new_ticket.ticket_no.split("-")[-1])
        self.assertTrue(new_ticket.ticket_no != initial_ticket_no)
        self.assertTrue(new_ticket.ticket_no.startswith("TKT-"))
        self.assertTrue(len(new_ticket.ticket_no) == 10)
        self.assertEqual(new_number, prev_number + 1)

    def test_user_role_validation(self):
        """Test that user roles are validated properly"""
        # Test valid roles
        user = CustomUser(username="user1", email="user1@example.com", role="user")
        user.set_password("pass123")
        user.save()
        self.assertEqual(user.role, "user")

        admin = CustomUser(username="admin1", email="admin1@example.com", role="admin")
        admin.set_password("pass123")
        admin.save()
        self.assertEqual(admin.role, "admin")

        # Test default role
        default_user = CustomUser(
            username="default",
            email="default@example.com",
        )
        default_user.set_password("pass123")
        default_user.save()
        self.assertEqual(default_user.role, "user")  # Default should be 'user'

    def test_ticket_status_choices(self):
        """Test ticket status choices and default"""
        # Test default status
        new_ticket = Ticket.objects.create(
            title="Status Test",
            description="Testing status choices",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
        )
        self.assertEqual(new_ticket.status, "open")  # Default should be 'open'

        # Test valid statuses
        valid_statuses = [
            "open",
            "assigned",
            "in_progress",
            "pending",
            "resolved",
            "closed",
        ]

        for status in valid_statuses:
            # Use the model helper to change status and log atomically
            new_ticket.change_status(status, performed_by=self.user)
            retrieved_ticket = Ticket.objects.get(pk=new_ticket.pk)
            self.assertEqual(retrieved_ticket.status, status)

    def test_feedback_one_per_ticket_constraint(self):
        """Test that only one feedback can be attached to a ticket"""
        # Create a feedback for the ticket
        Feedback.objects.create(
            ticket=self.ticket, rated_by=self.user, rating=4, comment="Good service"
        )

        # Try to create another feedback for the same ticket
        with self.assertRaises(IntegrityError):
            Feedback.objects.create(
                ticket=self.ticket,
                rated_by=self.user,
                rating=5,
                comment="Great service",
            )

    def test_ticket_log_creation(self):
        """Test automatic creation of ticket logs"""
        # Create a log entry
        log_entry = TicketLog.objects.create(
            ticket=self.ticket, performed_by=self.user, action="Test action"
        )

        # Verify the log was created correctly
        self.assertEqual(log_entry.ticket, self.ticket)
        self.assertEqual(log_entry.performed_by, self.user)
        self.assertEqual(log_entry.action, "Test action")
        self.assertIsNotNone(log_entry.timestamp)
        Comment.objects.create(
            ticket=self.ticket, text="This is another comment.", author=self.technician
        )
        # self.assertEqual(self.ticket.comments_count(), 2)

    def test_change_status_sets_resolved_at_and_logs(self):
        """Ensure change_status sets resolved_at for resolving statuses and creates a log with performed_by."""
        # Create a ticket that is currently in progress
        ticket = Ticket.objects.create(
            title="Resolve Test",
            description="Testing change_status",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status="in_progress",
        )

        # No resolved_at initially
        self.assertIsNone(ticket.resolved_at)

        # Change to resolved and assert resolved_at is set and a log is created
        ticket.change_status("resolved", performed_by=self.technician)
        ticket.refresh_from_db()
        self.assertIsNotNone(ticket.resolved_at)

        latest_log = (
            TicketLog.objects.filter(ticket=ticket).order_by("-timestamp").first()
        )
        self.assertIsNotNone(latest_log)
        self.assertEqual(latest_log.performed_by, self.technician)
        self.assertIn("Status changed from", latest_log.action)

        # Changing back to open should clear resolved_at and create a log
        ticket.change_status("open", performed_by=self.user)
        ticket.refresh_from_db()
        self.assertIsNone(ticket.resolved_at)
        latest_log = (
            TicketLog.objects.filter(ticket=ticket).order_by("-timestamp").first()
        )
        self.assertEqual(latest_log.performed_by, self.user)

    def test_change_assignment_creates_log_and_updates_assigned_to(self):
        """Ensure change_assignment updates assigned_to and creates a log with performed_by."""
        ticket = Ticket.objects.create(
            title="Assign Test",
            description="Testing change_assignment",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status="open",
        )

        # Initially unassigned
        self.assertIsNone(ticket.assigned_to)

        # Assign to technician
        ticket.change_assignment(self.technician, performed_by=self.user)
        ticket.refresh_from_db()
        self.assertEqual(ticket.assigned_to, self.technician)

        latest_log = (
            TicketLog.objects.filter(ticket=ticket).order_by("-timestamp").first()
        )
        self.assertIsNotNone(latest_log)
        self.assertEqual(latest_log.performed_by, self.user)
        self.assertIn("Assigned to", latest_log.action)
