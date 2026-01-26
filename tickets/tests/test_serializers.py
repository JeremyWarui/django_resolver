from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from tickets.models import Ticket, CustomUser
from tickets.serializers import *
from tickets.api.services import ticket_services as services
from django.utils import timezone
from datetime import timedelta

# User = get_user_model()


class SerializerTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass",
        )
        self.section = Section.objects.create(
            name="IT", description="Information Technology"
        )
        self.facility = Facility.objects.create(
            name="Main Block", type="building", status="active", location="123 Main St"
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
        self.comment = Comment.objects.create(
            ticket=self.ticket, text="This is a comment.", author=self.user
        )

    def test_ticket_serializer(self):
        """test ticket serializer"""
        serializer = TicketSerializer(instance=self.ticket)
        data = serializer.data

        self.assertEqual(data["title"], "Faulty Printer")
        self.assertEqual(data["status"], "assigned")
        self.assertEqual(data["raised_by"], self.user.username)
        self.assertEqual(data["assigned_to"]["id"], self.technician.id)
        self.assertEqual(len(data["comments"]), 1)

    def test_comment_serializer(self):
        """test comment serializer"""
        serializer = CommentSerializer(instance=self.comment)
        data = serializer.data

        self.assertEqual(data["text"], "This is a comment.")
        self.assertEqual(data["author"], self.user.username)
        self.assertEqual(data["ticket"]["id"], self.ticket.id)

    def test_custom_user_serializer(self):
        """test custom user serializer"""
        serializer = UserSerializer(instance=self.user)
        data = serializer.data

        self.assertEqual(data["username"], "testuser")
        self.assertEqual(data["email"], "testuser@example.com")

    def test_user_create_serializer(self):
        """test user serializer create method"""
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "johndoe@test.com",
            "password": "johnpassword",
            "role": "user",
        }

        serializer = UserSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        user = serializer.save()
        self.assertEqual(user.username, "john.doe")
        self.assertEqual(user.email, "johndoe@test.com")

    def test_ticket_serializer_create(self):
        """test ticket serializer create method"""
        data = {
            "title": "New Ticket",
            "description": "This is a new ticket.",
            "section_id": self.section.id,
            "facility_id": self.facility.id,
            "raised_by": self.user.id,
            "status": "open",
        }
        serializer = TicketSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        ticket = services.create_ticket(serializer, self.user)
        self.assertEqual(ticket.title, "New Ticket")
        self.assertEqual(ticket.raised_by, self.user)
        self.assertEqual(ticket.status, "open")
        self.assertTrue(ticket.assigned_to is None)

    def test_comment_serializer_create(self):
        """test comment serializer create method"""
        data = {
            "ticket": self.ticket.id,
            "text": "This is another comment.",
            "author": self.technician.id,
        }
        serializer = CommentSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

        # comment = serializer.save()
        comment = services.create_comment(serializer, self.technician, self.ticket.id)
        self.assertEqual(comment.text, "This is another comment.")
        self.assertEqual(comment.author, self.technician)
        self.assertEqual(comment.ticket, self.ticket)

    def test_feedback_serializer_create(self):
        """test feedback serializer creation"""
        self.ticket.status = "resolved"
        self.ticket.save()

        data = {
            "ticket": self.ticket.id,
            "rated_by": self.user.id,
            "rating": 4,
            "comment": "Good service.",
        }

        serializer = FeedbackSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        feedback = services.create_feedback(
            serializer, self.user, ticket_id=self.ticket.id
        )
        self.assertEqual(feedback.ticket, self.ticket)
        self.assertEqual(feedback.rated_by, self.user)
        self.assertEqual(feedback.rating, 4)
        self.assertEqual(feedback.comment, "Good service.")
