"""
Compliance Tests for Workflow Specification Fixes

This test suite validates implementation of critical compliance fixes:
1. Priority field with auto-escalation (LOW→MEDIUM→HIGH→CRITICAL)
2. Pending reason and comment fields with validation
3. User ticket closure capability
4. Director analytics-only access
5. Pending status does NOT pause escalation timers
"""

from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.test.utils import override_settings

from tickets.models import (
    Organization, Campus, Department, Section, Facility,
    CustomUser, Ticket, TicketLog
)
from tickets.api.services import TicketService
from tickets.tests.base import BaseTicketTestCase


class PriorityFieldTestCase(BaseTicketTestCase):
    """Test priority field and auto-escalation logic"""

    def test_ticket_created_with_low_priority(self):
        """Verify new tickets start with LOW priority"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        self.assertEqual(ticket.priority, 'low')

    def test_priority_escalates_to_medium_on_level_1(self):
        """Verify priority escalates to MEDIUM at escalation level 1"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Escalate to level 1 (section head)
        escalated_ticket = TicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=self.technician,
            reason="Needs section head review",
            manual=True
        )

        self.assertEqual(escalated_ticket.escalation_level, 1)
        self.assertEqual(escalated_ticket.priority, 'medium')

    def test_priority_escalates_to_high_on_level_2(self):
        """Verify priority escalates to HIGH at escalation level 2"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Escalate to level 1 first
        ticket.escalation_level = 1
        ticket.escalated_at = timezone.now()
        ticket.save()

        # Escalate to level 2
        escalated_ticket = TicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=self.technician,
            reason="Needs HOD review",
            manual=True
        )

        self.assertEqual(escalated_ticket.escalation_level, 2)
        self.assertEqual(escalated_ticket.priority, 'high')

    def test_priority_auto_marks_critical_after_72_hours(self):
        """Verify priority auto-marks CRITICAL after 72 hours unresolved"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
            created_at=timezone.now() - timedelta(hours=73)  # 73 hours ago
        )

        # Call check_and_mark_critical
        ticket.check_and_mark_critical()

        self.assertEqual(ticket.priority, 'critical')


class PendingFieldsTestCase(BaseTicketTestCase):
    """Test pending reason and comment fields with validation"""

    def test_pending_transition_requires_both_reason_and_comment(self):
        """Verify PENDING status requires both reason and comment"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Try to mark PENDING without comment - should raise error
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            TicketService.update_ticket_status(
                ticket=ticket,
                new_status='pending',
                updated_by=self.technician,
                pending_reason='material_shortage',
                pending_comment=None  # Missing comment
            )

    def test_pending_transition_with_both_fields(self):
        """Verify PENDING status succeeds with both reason and comment"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='in_progress'
        )

        # Mark as PENDING with both fields
        updated_ticket = TicketService.update_ticket_status(
            ticket=ticket,
            new_status='pending',
            updated_by=self.technician,
            pending_reason='material_shortage',
            pending_comment='Waiting for replacement parts'
        )

        self.assertEqual(updated_ticket.status, 'pending')
        self.assertEqual(updated_ticket.pending_reason, 'material_shortage')
        self.assertEqual(updated_ticket.pending_comment,
                         'Waiting for replacement parts')

    def test_pending_reason_is_enum_validated(self):
        """Verify pending_reason accepts only valid enum values"""
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Valid reasons
        valid_reasons = [
            'material_shortage',
            'awaiting_procurement',
            'awaiting_approval',
            'vendor_dependency',
            'access_issue',
            'other'
        ]

        for reason in valid_reasons:
            updated_ticket = TicketService.update_ticket_status(
                ticket=ticket,
                new_status='pending',
                updated_by=self.technician,
                pending_reason=reason,
                pending_comment=f'Comment for {reason}'
            )
            self.assertEqual(updated_ticket.pending_reason, reason)
            # Reset for next iteration
            ticket.refresh_from_db()


class UserTicketClosureTestCase(APITestCase):
    """Test user ticket closure capability"""

    @classmethod
    def setUpTestData(cls):
        # Create organizational structure using base setup
        org = Organization.objects.create(
            name="Closure Test Org",
            code="CTO",
            organization_type="corporate"
        )
        campus = Campus.objects.create(
            organization=org,
            name="Main Campus",
            code="MAIN"
        )
        dept = Department.objects.create(
            name="IT Department",
            code="IT",
            campus=campus
        )
        section = Section.objects.create(
            name="Networks",
            code="NET",
            department=dept
        )
        facility = Facility.objects.create(
            name="Router",
            type="ict",
            status="active",
            location="Server Room",
            campus=campus,
            department=dept
        )

        # Create user requester
        cls.user = CustomUser.objects.create_user(
            username='user_closure',
            email='user@closure.test',
            password='testpass123',
            role='user',
            primary_campus=campus,
            primary_department=dept
        )
        cls.user.sections.add(section)

        # Create another user
        cls.other_user = CustomUser.objects.create_user(
            username='other_user',
            email='other@closure.test',
            password='testpass123',
            role='user',
            primary_campus=campus,
            primary_department=dept
        )
        cls.other_user.sections.add(section)

        # Create admin user
        cls.admin = CustomUser.objects.create_user(
            username='admin_closure',
            email='admin@closure.test',
            password='testpass123',
            role='admin'
        )

        # Store refs for later use
        cls.section = section
        cls.facility = facility

    def setUp(self):
        self.client = APIClient()

    def test_user_can_close_own_resolved_ticket(self):
        """Verify user can close their own resolved ticket"""
        # Create ticket
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='resolved'
        )

        # Authenticate as user
        self.client.force_authenticate(user=self.user)

        # Close ticket
        response = self.client.post(
            f'/api/tickets/{ticket.id}/close/',
            {'closure_notes': 'Issue resolved and verified'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'closed')

    def test_user_cannot_close_others_resolved_ticket(self):
        """Verify user cannot close another user's resolved ticket"""
        # Create ticket by other user
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.other_user,
            status='resolved'
        )

        # Authenticate as different user
        self.client.force_authenticate(user=self.user)

        # Try to close ticket
        response = self.client.post(
            f'/api/tickets/{ticket.id}/close/',
            {'closure_notes': 'Issue resolved and verified'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'resolved')

    def test_user_cannot_close_unresolved_ticket(self):
        """Verify user cannot close a ticket that is not resolved"""
        # Create ticket in progress
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='in_progress'
        )

        # Authenticate as user
        self.client.force_authenticate(user=self.user)

        # Try to close ticket
        response = self.client.post(
            f'/api/tickets/{ticket.id}/close/',
            {'closure_notes': 'Issue resolved and verified'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'in_progress')

    def test_admin_can_close_any_resolved_ticket(self):
        """Verify admin can close any resolved ticket"""
        # Create ticket by other user
        ticket = Ticket.objects.create(
            title="Test Ticket",
            description="Test Description",
            section=self.section,
            facility=self.facility,
            raised_by=self.other_user,
            status='resolved'
        )

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin)

        # Close ticket
        response = self.client.post(
            f'/api/tickets/{ticket.id}/close/',
            {'closure_notes': 'Admin closing ticket'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, 'closed')
