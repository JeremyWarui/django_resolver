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
        self.assertEqual(self.ticket.description,
                         'The printer in the IT section is not working.')
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

    def test_ticket_creation_and_auto_increment_ticket_no(self):
        """ test ticket creation and auto increment ticket_no"""
        initial_ticket_no = self.ticket.ticket_no
        new_ticket = Ticket.objects.create(
            title="Faulty Monitor",
            description="The monitor in the IT section is not working.",
            section=self.section,
            facility=self.facility,
            raised_by=self.user,
            status='open'
        )
        self.assertTrue(new_ticket.ticket_no != initial_ticket_no)
        self.assertTrue(new_ticket.ticket_no.startswith('TKT-'))
        self.assertTrue(len(new_ticket.ticket_no) == 10)
        self.assertTrue(new_ticket.ticket_no.endswith("002"))

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


class SerializerTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='testuser@example.com',
            password='testpass',
        )
        self.section = Section.objects.create(
            name='IT',
            description='Information Technology'
        )
        self.facility = Facility.objects.create(
            name="Main Block",
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
            status='assigned'
        )
        self.comment = Comment.objects.create(
            ticket=self.ticket,
            text='This is a comment.',
            author=self.user
        )

    def test_ticket_serializer(self):
        """ test ticket serializer"""
        serializer = TicketSerializer(instance=self.ticket)
        data = serializer.data

        self.assertEqual(data['title'], 'Faulty Printer')
        self.assertEqual(data['status'], 'assigned')
        self.assertEqual(data['raised_by'], self.user.username)
        self.assertEqual(data['assigned_to'], self.technician.username)
        self.assertEqual(len(data['comments']), 1)

    def test_comment_serializer(self):
        """ test comment serializer"""
        serializer = CommentSerializer(instance=self.comment)
        data = serializer.data

        self.assertEqual(data['text'], 'This is a comment.')
        self.assertEqual(data['author'], self.user.username)
        self.assertEqual(data['ticket'], str(self.ticket))

    def test_custom_user_serializer(self):
        """ test custom user serializer"""
        serializer = UserSerializer(instance=self.user)
        data = serializer.data

        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['email'], 'testuser@example.com')

    def test_user_create_serializer(self):
        """ test user serializer create method"""
        data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'johndoe@test.com',
            'password': 'johnpassword',
            'role': 'user'
        }

        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        user = serializer.save()
        self.assertEqual(user.username, 'john.doe')
        self.assertEqual(user.email, 'johndoe@test.com')

    def test_ticket_serializer_create(self):
        """ test ticket serializer create method"""
        data = {
            'title': 'New Ticket',
            'description': 'This is a new ticket.',
            'section_id': self.section.id,
            'facility_id': self.facility.id,
            'raised_by_id': self.user.id,
            'status': 'open'
        }
        serializer = TicketSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        ticket = serializer.save()
        self.assertEqual(ticket.title, 'New Ticket')
        self.assertEqual(ticket.raised_by, self.user)
        self.assertEqual(ticket.status, 'open')
        self.assertTrue(ticket.assigned_to is None)

    def test_comment_serializer_create(self):
        """ test comment serializer create method"""
        data = {
            'ticket_id': self.ticket.id,
            'text': 'This is another comment.',
            'author_id': self.technician.id
        }
        serializer = CommentSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        comment = serializer.save()
        self.assertEqual(comment.text, 'This is another comment.')
        self.assertEqual(comment.author, self.technician)
        self.assertEqual(comment.ticket, self.ticket)

    def test_feedback_serializer_create(self):
        """ test feedback serializer creation"""
        data = {
            'ticket_id': self.ticket.id,
            'rated_by_id': self.user.id,
            'rating': 4,
            'comment': 'Good service.'
        }

        serializer = FeedbackSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        feedback = serializer.save()
        self.assertEqual(feedback.ticket, self.ticket)
        self.assertEqual(feedback.rated_by, self.user)
        self.assertEqual(feedback.rating, 4)
        self.assertEqual(feedback.comment, 'Good service.')


class APITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
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
        self.technician = User.objects.create_user(
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
