from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from pygments.lexers.sql import re_psql_command
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

        self.admin = CustomUser.objects.create_user(
            username='adminuser',
            email='adminuser@example.com',
            password='adminpassword',
            role='admin'
        )

        self.ticket.assigned_to = self.technician
        self.ticket.status = 'assigned'
        self.ticket.save()
        self.technician.sections.set([1])
        self.technician.save()

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

    def test_update_ticket_status_technician(self):
        """test to check technician update of ticket """
        url = reverse("ticket-detail", args=[self.ticket.id])
        # print(url)
        data = {
            "status": "in_progress"
        }

        self.client.logout()
        self.client.login(username='techuser', password='techpassword')

        response = self.client.patch(url, data, format="json")
        # print(response, response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_progress")

    def test_update_ticket_status_admin(self):
        """test admin update status"""
        url = reverse("ticket-detail", args=[self.ticket.id])
        # print(url)
        data = {
            "status": "in_progress"
        }
        self.client.logout()
        self.client.login(username='adminuser', password='adminpassword')

        response = self.client.patch(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "in_progress")

    def test_update_ticket_user_cant(self):
        """ test that the user cant update status """
        url = reverse("ticket-detail", args=[self.ticket.id])
        # print(url)
        data = {
            "status": "in_progress"
        }

        self.client.logout()
        self.client.login(username="testuser", password="testpassword")
        response = self.client.patch(url, data, format="json")
        # print(response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("User testuser cannot update status", str(response.data))

    def test_user_can_add_comment(self):
        """user can add comment"""
        url = reverse("ticket-comments", args=[self.ticket.id])
        data = {
            "text": "This is a second comment"
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["text"], "This is a second comment")

        comments_url = reverse("ticket-detail", args=[self.ticket.id])
        comments_response = self.client.get(comments_url)
        self.assertEqual(len(comments_response.data["comments"]), 2)

    def test_get_ticket_detail(self):
        """Test retrieving a specific ticket with comments & feedback"""
        url = reverse("ticket-detail", args=[self.ticket.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['ticket_no'], self.ticket.ticket_no)
        self.assertEqual(response.data['title'], 'Test Ticket')

        # Check that comments are included
        self.assertIn('comments', response.data)
        self.assertEqual(len(response.data['comments']), 1)
        self.assertEqual(response.data['comments']
                         [0]['text'], 'This is a test comment.')

        # Check that feedback is included
        self.assertIn('feedback', response.data)
        self.assertEqual(response.data['feedback']['rating'], 5)
        self.assertEqual(response.data['feedback']
                         ['comment'], 'Great service!')

    def test_assign_ticket_admin(self):
        """Test that admin can assign a ticket to technician"""
        url = reverse("ticket-detail", args=[self.ticket.id])

        # Create a new ticket to assign
        new_ticket = Ticket.objects.create(
            title='Unassigned Ticket',
            description='This ticket needs to be assigned.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )

        # Login as admin
        self.client.logout()
        self.client.login(username='adminuser', password='adminpassword')

        # Assign the ticket to the technician
        data = {
            "assigned_to_id": self.technician.id,
            "status": "assigned"
        }

        url = reverse("ticket-detail", args=[new_ticket.id])
        response = self.client.patch(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'assigned')
        self.assertEqual(response.data['assigned_to']
                         ['id'], self.technician.id)

    def test_resolve_ticket_technician(self):
        """Test that technician can mark a ticket as resolved"""
        # Login as technician
        self.client.logout()
        self.client.login(username='techuser', password='techpassword')

        url = reverse("ticket-detail", args=[self.ticket.id])
        data = {
            "status": "resolved"
        }

        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'resolved')

        # Verify that a ticket log was created for this status change
        latest_log = TicketLog.objects.filter(
            ticket=self.ticket).order_by('-timestamp').first()
        self.assertIsNotNone(latest_log)
        self.assertEqual(latest_log.performed_by, self.technician)
        self.assertIn("Status changed from assigned to resolved",
                      latest_log.action)

    def test_user_cannot_assign_ticket(self):
        """Test that a regular user cannot assign tickets"""
        # Login as regular user
        self.client.logout()
        self.client.login(username='testuser', password='testpassword')

        url = reverse("ticket-detail", args=[self.ticket.id])
        data = {
            "assigned_to_id": self.technician.id
        }

        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("User testuser cannot update status", str(response.data))

    def test_delete_ticket(self):
        """Test ticket deletion functionality"""
        # Create a ticket to delete
        ticket_to_delete = Ticket.objects.create(
            title='Delete Me Ticket',
            description='This ticket will be deleted.',
            section=self.section,
            facility=self.facility,
            raised_by=self.user
        )

        url = reverse("ticket-detail", args=[ticket_to_delete.id])

        # Note: Since explicit permission checks aren't implemented in the views,
        # we're just verifying basic delete functionality
        # Login as admin for this test
        self.client.logout()
        self.client.login(username='adminuser', password='adminpassword')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Verify the ticket is no longer in the database
        with self.assertRaises(Ticket.DoesNotExist):
            Ticket.objects.get(id=ticket_to_delete.id)
