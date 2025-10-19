import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from tickets.models import Ticket, CustomUser, Section, Facility, Comment, Feedback


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def setup_data(db):
    section = Section.objects.create(
        name='IT',
        description='Information Technology'
    )

    hvac = Section.objects.create(
        name="HVAC",
        description="Air Conditioning systems."
    )

    electrical = Section.objects.create(
        name="Electrical",
        description="Electricity installations and fixtures."
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
        role='technician',
    )

    hvac_technician = CustomUser.objects.create_user(
        username='hvac_tech',
        email='hvactech@example.com',
        password='hvac123',
        role='technician'
    )

    electrician = CustomUser.objects.create_user(
        username='electrical_tech',
        email='electricaltech@example.com',
        password='electrician123',
        role='technician'
    )

    admin = CustomUser.objects.create_user(
        username="adminuser",
        email="admin@example.com",
        password="adminpass",
        role="admin"
    )

    technician.sections.add(section)

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

@pytest.mark.django_db
def test_admin_can_assign_ticket(api_client, setup_data):
    """ Admin assigns ticket to technician in same section as ticket section"""
    ticket = Ticket.objects.create(
        title="Network issue",
        description="WiFi is down",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        status="Open"
    )

    payload = {
        "assigned_to_id": setup_data["technician"].id,
        "status": "assigned"
    }

    print(ticket, payload)
    # ✅ authenticate as admin
    api_client.force_authenticate(user=setup_data["admin"])

    response = api_client.patch(reverse("ticket-detail", args=[ticket.id]), payload, format="json")
    print(response.status_code, response.data)

    assert response.status_code in [200, 202]

    ticket.refresh_from_db()
    assert ticket.assigned_to == setup_data["technician"]
    assert ticket.status == "assigned"

@pytest.mark.django_db
def test_admin_cant_assign_ticket_to_technician_not_in_section(api_client, setup_data):
    """ Admin cant assign ticket to technician not in section as ticket section"""
    plumber = CustomUser.objects.create_user(
        username='plumber_tech',
        email='plumbertech@example.com',
        password='plumber123',
        role='technician'
    )

    plumbing = Section.objects.create(
        name="Plumbing",
        description="Plumbing systems such as water and piping."
    )

    plumber.sections.add(plumbing)

    api_client.force_authenticate(user=setup_data["admin"])

    ticket = Ticket.objects.create(
        title="Network issue",
        description="WiFi is down",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        status="open"
    )

    payload = {
        "assigned_to_id": plumber.id,
        "status": "assigned"
    }

    print(ticket, payload)

    response = api_client.patch(reverse("ticket-detail", args=[ticket.id]), payload, format="json")
    print(response.status_code, response.data)

    assert response.status_code in [400, 404]

    ticket.refresh_from_db()
    assert ticket.assigned_to is None
    assert ticket.status == "open"

@pytest.mark.django_db
def test_technician_can_update_ticket_status(api_client, setup_data):
    """ Technician updates ticket from assigned to in_progress to resolved """
    ticket = Ticket.objects.create(
        title="Email down",
        description="Outlook not syncing",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="Assigned"
    )

    payload = {
        "status": "in_progress"
    }
    api_client.force_authenticate(user=setup_data['technician'])

    response = api_client.patch(reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [200, 202]
    ticket.refresh_from_db()
    assert ticket.status == "in_progress"

    payload = {
        "status": "resolved"
    }
    response = api_client.patch(reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [200, 202]
    ticket.refresh_from_db()
    assert ticket.status == "resolved"

@pytest.mark.django_db
def test_user_cant_update_ticket_status(api_client, setup_data):
    """ User cannot updates ticket from assigned to in_progress to resolved """
    ticket = Ticket.objects.create(
        title="Email down",
        description="Outlook not syncing",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="assigned"
    )

    user2 = CustomUser.objects.create_user(
        username="user2",
        password="userpass123",
        email="user2@example.com",
        role="user"
    )

    payload = {
        "status": "in_progress"
    }

    api_client.force_authenticate(user=user2)

    response = api_client.patch(reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [400, 404]
    ticket.refresh_from_db()
    assert ticket.status == "assigned"

    payload = {
        "status": "resolved"
    }
    response = api_client.patch(reverse('ticket-detail', args=[ticket.id]), payload, format="json")
    assert response.status_code in [400, 404]
    ticket.refresh_from_db()
    assert ticket.status == "assigned"

@pytest.mark.django_db()
def test_technician_or_admin_add_comment_to_ticket(api_client, setup_data):
    """ test that comments can be added to a ticket """
    ticket = Ticket.objects.create(
        title="Email down",
        description="Outlook not syncing",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="in_progress"
    )
    api_client.force_authenticate(user=setup_data['technician'])
    payload = {
        "text": "It is now working!",
    }

    response = api_client.post(reverse("ticket-comments", args=[ticket.id]), payload, format="json")
    print(response.status_code, response.data)
    assert response.status_code == 201
    comment_tech = Comment.objects.first()
    assert comment_tech.author == setup_data["technician"]
    assert comment_tech.text == payload['text']

    api_client.force_authenticate(user=setup_data['admin'])
    admin_payload = {
        "text": "Great to hear!",
    }
    response = api_client.post(reverse("ticket-comments", args=[ticket.id]), admin_payload, format="json")
    print(response.status_code, response.data)
    assert response.status_code == 201
    admin_comment = Comment.objects.last()
    assert admin_comment.text == admin_payload["text"]
    assert admin_comment.author == setup_data["admin"]

@pytest.mark.django_db()
def test_user_can_submit_feedback(api_client, setup_data):
    """ User submits feedback after ticket is resolved """
    ticket = Ticket.objects.create(
        title="Email fixed",
        description="Problem resolved",
        section=setup_data["section"],
        facility=setup_data["facility"],
        raised_by=setup_data["user"],
        assigned_to=setup_data["technician"],
        status="Resolved"
    )

    api_client.force_authenticate(user=setup_data["user"])
    payload = {
        "rating": 5,
        "comment": "Great job!"
    }

    response = api_client.post(reverse("ticket-feedback", args=[ticket.id]), payload, format="json" )
    assert response.status_code == 201
    feedback = Feedback.objects.get(ticket=ticket)
    assert feedback.rating == 5
    assert feedback.rated_by == setup_data["user"]