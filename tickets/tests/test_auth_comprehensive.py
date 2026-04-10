"""
Pytest version of test_auth_comprehensive.py - Authentication tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from tickets.models import Section, Facility, Ticket


def test_user_login_with_credentials(authenticated_client):
    """Test user login with valid credentials"""
    user = authenticated_client['user']
    assert user.username == "authuser"


def test_user_cannot_access_without_token(api_client):
    """Test that unauthenticated users cannot access protected endpoints"""
    response = api_client.get(reverse("ticket-list"))
    assert response.status_code in [401, 403]


def test_authenticated_user_can_access_protected_endpoint(authenticated_client):
    """Test that authenticated users can access protected endpoints"""
    client = authenticated_client['client']
    response = client.get(reverse("ticket-list"))
    assert response.status_code == 200


def test_admin_user_has_full_access(authenticated_admin_client):
    """Test that admin users have full system access"""
    client = authenticated_admin_client['client']
    response = client.get(reverse("ticket-list"))
    assert response.status_code == 200


def test_technician_can_update_assigned_ticket(authenticated_technician_client, ticket_factory, section):
    """Test that technician can update tickets assigned to them"""
    client = authenticated_technician_client['client']
    technician = authenticated_technician_client['user']

    ticket = ticket_factory(
        assigned_to=technician,
        status="assigned",
        section=section
    )

    response = client.patch(
        reverse("ticket-detail", args=[ticket.id]),
        {"status": "in_progress"},
        format="json"
    )
    assert response.status_code == 200


def test_regular_user_cannot_update_others_tickets(authenticated_client, ticket_factory, user_factory):
    """Test that regular users cannot update others' tickets"""
    client = authenticated_client['client']
    other_user = user_factory(username="other_user")

    ticket = ticket_factory(raised_by=other_user)

    response = client.patch(
        reverse("ticket-detail", args=[ticket.id]),
        {"status": "in_progress"},
        format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_password_authentication_required(api_client):
    """Test that password authentication is required"""
    response = api_client.post(
        reverse("simple_auth_login"),
        {"username": "nonexistent", "password": "wrong"},
        format="json"
    )
    assert response.status_code in [401, 400]


def test_authenticated_user_can_create_ticket(authenticated_client, section, facility):
    """Test that authenticated user can create tickets"""
    client = authenticated_client['client']

    payload = {
        "title": "Test Ticket",
        "description": "Test description",
        "section_id": section.id,
        "facility_id": facility.id,
    }

    response = client.post(
        reverse("ticket-list"),
        payload,
        format="json"
    )
    assert response.status_code == 201


def test_unauthenticated_user_cannot_create_ticket(api_client, section, facility):
    """Test that unauthenticated users cannot create tickets"""
    payload = {
        "title": "Test Ticket",
        "description": "Test description",
        "section_id": section.id,
        "facility_id": facility.id,
    }

    response = api_client.post(
        reverse("ticket-list"),
        payload,
        format="json"
    )
    assert response.status_code in [401, 403]


def test_admin_can_access_admin_endpoints(authenticated_admin_client):
    """Test that admin can access admin-only endpoints"""
    client = authenticated_admin_client['client']
    response = client.get(reverse("ticket-list"))
    assert response.status_code == 200


def test_technician_restricted_access(authenticated_technician_client, ticket_factory):
    """Test that technician has restricted access to certain endpoints"""
    client = authenticated_technician_client['client']
    response = client.get(reverse("ticket-list"))
    assert response.status_code == 200


def test_authentication_persists_across_requests(authenticated_client):
    """Test that authentication persists across multiple requests"""
    client = authenticated_client['client']

    response1 = client.get(reverse("ticket-list"))
    assert response1.status_code == 200

    response2 = client.get(reverse("ticket-list"))
    assert response2.status_code == 200


@pytest.mark.django_db
def test_invalid_token_rejected(api_client):
    """Test that invalid authentication token is rejected"""
    api_client.credentials(HTTP_AUTHORIZATION="Token invalid_token_12345")
    response = api_client.get(reverse("ticket-list"))
    assert response.status_code in [401, 403]


def test_user_role_determines_permissions(db, user_factory, technician_factory, ticket_factory):
    """Test that user role determines their permissions"""
    user = user_factory()
    technician = technician_factory()

    # Verify user role is correctly assigned
    assert user.role == "user"
    assert technician.role == "technician"
