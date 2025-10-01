from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from .models import *
from .serializers import *
from django.utils import timezone
from datetime import timedelta


# Create your tests here.
User = get_user_model()

class ModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass'
        )
        self.section = Section.objects.create(
            name='IT',
            description='Information Technology'
        )
        self.facility = Facility.objects.create(
            name='Main Building',
            type='building',
            status='active',
            location='123 Main St'
        )
        self.technician = User.objects.create_user(
            username='techuser',
            email='techuser@example.com',
            password='techpass',
            role='technician'
        )
        self.ticket = Ticket.objects.create(
            title='Faulty Printer',
            description='The printer in the IT section is not working.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            assigned_to=self.technician,
            status='assigned',
        )
    
    def test_user_creation(self):
        """test the user creation"""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'testuser@example.com')
        self.assertTrue(self.user.check_password('testpass'))
    
    def test_section_creation(self):
        """test the section creation"""
        self.assertEqual(self.section.name, 'IT')
        self.assertEqual(self.section.description, 'Information Technology')

    def test_technician_creation(self):
        """test the technician creation"""
        self.assertEqual(self.technician.username, 'techuser')
        self.assertEqual(self.technician.email, 'techuser@example.com')
        self.assertEqual(self.technician.role, 'technician')
        self.assertTrue(self.technician.check_password('techpass'))
    
    def test_ticket_creation(self):
        """ test ticket creation"""
        self.assertEqual(self.ticket.title, 'Faulty Printer')
        self.assertEqual(self.ticket.description, 'The printer in the IT section is not working.')
        self.assertEqual(self.ticket.section, self.section)
        self.assertEqual(self.ticket.facility, self.facility)
        self.assertEqual(self.ticket.raised_by, self.user)
        self.assertEqual(self.ticket.assigned_to, self.technician)
        self.assertEqual(self.ticket.status, 'assigned')

    def test_ticket_is_overdue(self):
        """ test ticket is_overdue method"""
        old_ticket = Ticket.objects.create(
            title='Old Ticket',
            description='This ticket is old and should be overdue.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
        )
        old_ticket.created_at = timezone.now() - timedelta(hours=25)
        old_ticket.save()
        self.assertTrue(old_ticket.is_overdue())
        self.assertFalse(self.ticket.is_overdue())

    def test_ticket_set_to_pending_overdue_ticket(self):
        """ test ticket set_to_pending method"""
        old_ticket = Ticket.objects.create(
            title='Old Ticket',
            description='This ticket is old and should be overdue.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
        )
        old_ticket.created_at = timezone.now() - timedelta(hours=25)
        old_ticket.save()
        self.assertTrue(old_ticket.status, 'open')
        if old_ticket.is_overdue():
            old_ticket.set_to_pending()

        self.assertEqual(old_ticket.status, 'pending')

    def test_ticket_status_after_assignment(self):
        """test ticket status after assignment"""
        self.ticket.assigned_to = self.technician
        self.ticket.save()
        self.assertEqual(self.ticket.status, 'assigned')

    def test_ticket_count(self):
        """ test total tickets class method"""
        initial_count = Ticket.total_tickets()
        Ticket.objects.create(
            title='New Ticket',
            description='This is a new ticket.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open',
        )
        self.assertEqual(Ticket.total_tickets(), initial_count + 1)
    
    def test_ticket_comments_count(self):
        """ test comments count method"""
        Comment.objects.create(
            ticket=self.ticket,
            text='This is a comment.',
            author=self.user
        )
        Comment.objects.create(
            ticket=self.ticket,
            text='This is another comment.',
            author=self.technician
        )
        self.assertEqual(self.ticket.comments_count(), 2)