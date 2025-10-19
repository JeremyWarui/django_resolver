import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from tickets.models import Ticket, CustomUser, Section, Facility


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def setup_data(db):
    section = Section.objects.create(
        name='IT',
        description='Information Technology'
    )
    facility = Facility.objects.create(
        name='Main Building',
        type='building',
        status='active',
        location='123 Main St'
    )
    user = CustomUser.objects.create_user(
        username='testuser',
        email='testuser@example.com',
        password='testpass'
    )
    technician = CustomUser.objects.create_user(
        username='techuser',
        email='techuser@example.com',
        password='techpass',
        role='technician'
    )
    admin = CustomUser.objects.create_user(
        username="adminuser",
        email="admin@example.com",
        password="adminpass",
        role="admin"
    )

    return {
        'section': section,
        "facility": facility,
        "user": user,
        "technician": technician,
        "admin": admin
    }

@pytest.mark.django_db
def test_ticket_creation(api_client, setup_data):
    """ user can create a ticket and its starts with open status and no technician"""
    api_client.force_authenticate(user=setup_data['user'])

    payload = {
        "title": "Printer not working",
        "description": "Printer in the admin block is jammed",
        "section_id": setup_data["section"].id,
        "facility_id": setup_data["facility"].id
    }

    response = api_client.post(reverse("ticket-list"), payload, format="json")
    print(response.status_code, response.data)

    assert response.status_code == 201

    ticket = Ticket.objects.get(id=response.data["id"])
    assert ticket.status == "open"
    assert ticket.assigned_to is None
    assert ticket.raised_by == setup_data["user"]

