"""
Pytest version of test_serializers.py - Serializer validation tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from tickets.serializers import (
    TicketSerializer,
    CommentSerializer,
    UserSerializer,
    FeedbackSerializer,
    SectionSerializer,
)
from tickets.models import CustomUser
from tickets.api.services import TicketService


def test_ticket_serializer(ticket_factory, user_factory, technician_factory):
    """Test ticket serializer"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(
        title="Test Ticket", status="assigned", raised_by=user, assigned_to=technician
    )

    serializer = TicketSerializer(instance=ticket)
    data = serializer.data

    assert data["title"] == "Test Ticket"
    assert data["status"] == "assigned"
    assert data["raised_by"] == user.username
    assert data["assigned_to"]["id"] == technician.id


def test_comment_serializer(db, comment_factory, ticket_factory, user_factory):
    """Test comment serializer"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)
    comment = comment_factory(text="This is a comment.", ticket=ticket, author=user)

    serializer = CommentSerializer(instance=comment)
    data = serializer.data

    assert data["text"] == "This is a comment."
    assert data["author"] == user.username
    assert data["ticket"]["id"] == ticket.id


def test_custom_user_serializer(user_factory):
    """Test custom user serializer"""
    user = user_factory(username="testuser", email="testuser@example.com")
    serializer = UserSerializer(instance=user)
    data = serializer.data

    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"


def test_user_create_serializer(db):
    """Test user serializer create method"""
    data = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "johndoe@test.com",
        "password": "johnpassword",
        "role": "user",
    }

    serializer = UserSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    user = serializer.save()
    assert user.username == "john.doe"
    assert user.email == "johndoe@test.com"


def test_ticket_serializer_create(db, org_aware_user_factory, section, facility):
    """Test ticket serializer create method"""
    user = org_aware_user_factory()
    # Add section access for the user
    user.sections.add(section)

    data = {
        "title": "New Ticket",
        "description": "This is a new ticket.",
        "section_id": section.id,
        "facility_id": facility.id,
        "raised_by": user.id,
        "status": "open",
    }

    serializer = TicketSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    ticket = TicketService.create_ticket(
        data=serializer.validated_data,
        created_by=user,
        section=section,
        facility=facility,
        enable_auto_escalation=True,
    )

    assert ticket.title == "New Ticket"
    assert ticket.raised_by == user
    assert ticket.status == "open"
    assert ticket.assigned_to is None


def test_comment_serializer_create(
    db, comment_factory, ticket_factory, user_factory, technician_factory
):
    """Test comment serializer create method"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user)

    data = {
        "ticket": ticket.id,
        "text": "This is another comment.",
        "author": technician.id,
    }

    serializer = CommentSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    comment = TicketService.create_comment(serializer, technician, ticket.id)

    assert comment.text == "This is another comment."
    assert comment.author == technician
    assert comment.ticket == ticket


def test_feedback_serializer_create(db, feedback_factory, ticket_factory, user_factory):
    """Test feedback serializer creation"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user, status="resolved")

    data = {
        "ticket": ticket.id,
        "rated_by": user.id,
        "rating": 4,
        "comment": "Good service.",
    }

    serializer = FeedbackSerializer(data=data)
    assert serializer.is_valid(), serializer.errors

    feedback = TicketService.create_feedback(serializer, user, ticket_id=ticket.id)

    assert feedback.ticket == ticket
    assert feedback.rated_by == user
    assert feedback.rating == 4
    assert feedback.comment == "Good service."


def test_section_serializer_includes_campus_context(db, section, campus, organization):
    """Test SectionSerializer exposes campus and organization context"""
    serializer = SectionSerializer(instance=section)
    data = serializer.data

    # Verify basic fields
    assert data["id"] == section.id
    assert data["name"] == section.name
    assert data["code"] == section.code

    # Verify department context (returned as nested object)
    assert "department" in data
    assert data["department"]["id"] == section.department.id

    # Verify campus context (nested inside department)
    assert "campus" in data
    assert data["campus"]["id"] == section.department.campus.id
