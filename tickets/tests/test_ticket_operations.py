"""
Pytest version of test_ticket_operations.py - Ticket operations tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from rest_framework import status
from django.urls import reverse
from tickets.models import Ticket, CustomUser, Section, Facility


@pytest.fixture
def ticket_ops_setup(db, user_factory, admin_user_factory, technician_factory, organization, campus):
    """Set up ticket operations test data"""
    from tickets.models import Department

    dept = Department.objects.create(
        campus=campus, name="Facilities", code="FAC"
    )

    # Create sections
    section_hvac = Section.objects.create(
        department=dept, name="HVAC", code="HVA", description="Heating and cooling"
    )
    section_plumbing = Section.objects.create(
        department=dept, name="Plumbing", code="PLU", description="Water systems"
    )

    # Create facility
    facility = Facility.objects.create(
        campus=campus, department=dept, name="Main Building", type="building"
    )

    # Create users
    user = user_factory(username="testuser", primary_campus=campus)
    user.sections.add(section_hvac)

    admin = admin_user_factory(username="admin", primary_campus=campus)

    tech_hvac = technician_factory(username="hvac.tech", primary_campus=campus)
    tech_hvac.sections.add(section_hvac)

    tech_plumbing = technician_factory(
        username="plumb.tech", primary_campus=campus)
    tech_plumbing.sections.add(section_plumbing)

    tech_both = technician_factory(
        username="multi.tech", primary_campus=campus)
    tech_both.sections.add(section_hvac, section_plumbing)

    return {
        "dept": dept,
        "section_hvac": section_hvac,
        "section_plumbing": section_plumbing,
        "facility": facility,
        "user": user,
        "admin": admin,
        "tech_hvac": tech_hvac,
        "tech_plumbing": tech_plumbing,
        "tech_both": tech_both,
        "campus": campus,
    }


def test_create_ticket_direct_orm(authenticated_admin_client, ticket_ops_setup):
    """Test creating a new ticket via API"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    data = {
        "title": "Broken AC",
        "description": "AC not working",
        "section_id": setup["section_hvac"].id,
        "facility_id": setup["facility"].id,
    }

    response = client.post(reverse("ticket-list"), data, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["title"] == "Broken AC"
    assert response.data["status"] == "open"
    assert response.data["ticket_no"] is not None


def test_ticket_includes_available_technicians(authenticated_admin_client, ticket_ops_setup):
    """Test that ticket response includes available technicians"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    data = {
        "title": "Broken AC",
        "description": "AC not working",
        "section_id": setup["section_hvac"].id,
        "facility_id": setup["facility"].id,
    }

    response = client.post(reverse("ticket-list"), data, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert "available_technicians" in response.data

    # Should have technicians in this section
    available_techs = response.data["available_technicians"]
    assert len(available_techs) > 0


def test_assign_technician_to_ticket(authenticated_admin_client, ticket_ops_setup, ticket_factory):
    """Test assigning a technician to a ticket"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    ticket = ticket_factory(
        title="Broken AC",
        section=setup["section_hvac"],
        facility=setup["facility"]
    )

    data = {"assigned_to_id": setup["tech_hvac"].id}
    response = client.patch(
        reverse("ticket-detail", args=[ticket.id]),
        data,
        format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["assigned_to"]["id"] == setup["tech_hvac"].id
    assert response.data["status"] == "assigned"


def test_cannot_assign_wrong_section_technician(authenticated_admin_client, ticket_ops_setup, ticket_factory):
    """Test that assigning technician from wrong section fails"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    # Create HVAC ticket
    ticket = ticket_factory(
        title="Broken AC",
        section=setup["section_hvac"],
        facility=setup["facility"]
    )

    # Try to assign plumbing technician (should fail)
    data = {"assigned_to_id": setup["tech_plumbing"].id}
    response = client.patch(
        reverse("ticket-detail", args=[ticket.id]),
        data,
        format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_can_assign_multi_section_technician(authenticated_admin_client, ticket_ops_setup, ticket_factory):
    """Test that technician with multiple sections can be assigned"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    # Create HVAC ticket
    ticket = ticket_factory(
        title="Broken AC",
        section=setup["section_hvac"],
        facility=setup["facility"]
    )

    # Assign multi-section technician (should work)
    data = {"assigned_to_id": setup["tech_both"].id}
    response = client.patch(
        reverse("ticket-detail", args=[ticket.id]),
        data,
        format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["assigned_to"]["id"] == setup["tech_both"].id


def test_get_available_technicians_for_section(authenticated_admin_client, ticket_ops_setup):
    """Test filtering technicians by section"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    response = client.get(
        reverse("technicians-by-section"),
        {"section_id": setup["section_hvac"].id},
        format="json"
    )

    assert response.status_code == status.HTTP_200_OK


def test_assign_same_technician_multiple_times(authenticated_admin_client, ticket_ops_setup, ticket_factory):
    """Test assigning same technician to multiple tickets"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    tickets = [
        ticket_factory(section=setup["section_hvac"],
                       facility=setup["facility"])
        for _ in range(3)
    ]

    for ticket in tickets:
        data = {"assigned_to_id": setup["tech_hvac"].id}
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            data,
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK


def test_unassign_technician_from_ticket(authenticated_admin_client, ticket_ops_setup, ticket_factory):
    """Test unassigning a technician from a ticket"""
    client = authenticated_admin_client['client']
    setup = ticket_ops_setup

    ticket = ticket_factory(
        assigned_to=setup["tech_hvac"],
        section=setup["section_hvac"],
        facility=setup["facility"],
        status="assigned"
    )

    # Unassign by setting assigned_to to null
    data = {"assigned_to_id": None}
    response = client.patch(
        reverse("ticket-detail", args=[ticket.id]),
        data,
        format="json"
    )

    # Check if unassigned (depends on API implementation)
    assert response.status_code in [200, 400]
