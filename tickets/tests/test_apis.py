from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from tickets.models import *
from tickets.serializers import *
from django.utils import timezone
from datetime import timedelta

User = get_user_model()

class APITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpassword'
        )
        self.client.login(username='testuser', password='testpassword')

        self.section = Section.objects.create(
            name='IT',
            description='Information Technology'
        )

        self.facility = Facility.objects.create(
            name='Main Office',
            type='Office',
            status='Active',
            location='Building A'
        )

        self.ticket = Ticket.objects.create(
            title='Test Ticket',
            description='This is a test ticket.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user
        )

        self.technician = CustomUser.objects.create_user(
            username='techuser',
            email='techuser@example.com',
            password='techpassword',
            role='technician'
        )
        self.ticket.assigned_to = self.technician
        self.ticket.status = 'assigned'
        self.ticket.save()

        self.comment = Comment.objects.create(
            ticket=self.ticket,
            text='This is a test comment.',
            author=self.user
        )
        self.feedback = Feedback.objects.create(
            ticket=self.ticket,
            rated_by=self.user,
            rating=5,
            comment='Great service!'
        )

    def test_get_tickets(self):
        url = reverse('ticket-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Test Ticket')

    def test_create_ticket(self):
        url = reverse('ticket-list')
        data = {
            'title': 'New Ticket',
            'description': 'This is a new ticket.',
            'section_id': self.section.id,
            'facility_id': self.facility.id,
            'raised_by_id': self.user.id,
            'status': 'open'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'New Ticket')
        self.assertEqual(response.data['status'], 'open')