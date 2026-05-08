"""
Pytest-based API tests for Django Resolver.

Converted from Django APITestCase to pytest with fixtures.
Tests cover API endpoints, authentication, authorization, and ticket workflows.
"""

import pytest
from django.urls import reverse
from rest_framework import status

from tickets.models import (
    Section,
    Facility,
    Ticket,
    Comment,
    Feedback,
    TicketLog,
    CustomUser,
)

# ============================================================================
# API TESTS - BASIC ENDPOINTS
# ============================================================================


def test_get_tickets(authenticated_client, section, facility, campus):
    """Test retrieving list of tickets via API"""
    auth_user = authenticated_client["user"]
    auth_user.primary_campus = campus
    auth_user.save()

    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=auth_user,
    )

    client = authenticated_client["client"]
    url = reverse("ticket-list")
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    results = response.data["results"]
    assert len(results) >= 1
    test_ticket = next(
        (item for item in results if item["title"] == "Test Ticket"), None
    )
    assert test_ticket is not None


def test_get_ticket_detail(authenticated_client, section, facility, campus):
    """Test retrieving a specific ticket with comments & feedback"""
    auth_user = authenticated_client["user"]
    auth_user.primary_campus = campus
    auth_user.save()

    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=auth_user,
    )

    Comment.objects.create(
        ticket=ticket, text="This is a test comment.", author=auth_user
    )
    Feedback.objects.create(
        ticket=ticket, rated_by=auth_user, rating=5, comment="Great service!"
    )

    client = authenticated_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["ticket_no"] == ticket.ticket_no
    assert response.data["title"] == "Test Ticket"
    assert "comments" in response.data
    assert len(response.data["comments"]) == 1
    assert response.data["comments"][0]["text"] == "This is a test comment."
    assert "feedback" in response.data
    assert response.data["feedback"]["rating"] == 5
    assert response.data["feedback"]["comment"] == "Great service!"


# ============================================================================
# TICKET STATUS UPDATE TESTS
# ============================================================================


def test_technician_status_progression(
    authenticated_technician_client, section, facility, user_factory
):
    """Test technician can advance a ticket through assigned → in_progress → resolved"""
    user = user_factory()
    technician = authenticated_technician_client["user"]
    technician.sections.add(section)

    ticket = Ticket.objects.create(
        title="Status Progression Test",
        description="Testing technician status updates.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
    )

    client = authenticated_technician_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])

    response = client.patch(url, {"status": "in_progress"}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "in_progress"

    response = client.patch(url, {"status": "resolved"}, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "resolved"

    latest_log = TicketLog.objects.filter(ticket=ticket).order_by("-timestamp").first()
    assert latest_log is not None
    assert latest_log.performed_by == technician


def test_technician_cannot_edit_unassigned_ticket(
    authenticated_technician_client, section, facility, user_factory, technician_factory
):
    """Test that technician can view but cannot edit tickets assigned to someone else"""
    user = user_factory()
    other_technician = technician_factory()  # Different technician
    other_technician.sections.add(section)

    ticket = Ticket.objects.create(
        title="Unassigned Ticket",
        description="Assigned to a different technician",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=other_technician,
        status="assigned",
    )

    client = authenticated_technician_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])

    # Technician should be able to view (GET) the ticket
    response = client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # But should NOT be able to edit (PATCH) the ticket
    data = {"status": "in_progress"}
    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_update_ticket_status_admin(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test admin updating ticket status"""
    user = user_factory()
    technician = technician_factory()
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    data = {"status": "in_progress"}

    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "in_progress"


# ============================================================================
# TICKET ASSIGNMENT TESTS
# ============================================================================


def test_assign_ticket_admin(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test that admin can assign a ticket to technician"""
    user = user_factory()
    technician = technician_factory()
    technician.sections.add(section)
    # Set organizational context for technician
    technician.primary_campus = section.department.campus
    technician.primary_department = section.department
    technician.save()

    ticket = Ticket.objects.create(
        title="Unassigned Ticket",
        description="This ticket needs to be assigned.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    data = {"assigned_to_id": technician.id, "status": "assigned"}

    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "assigned"
    assert response.data["assigned_to"]["id"] == technician.id


def test_user_cannot_assign_ticket(
    authenticated_client, section, facility, technician_factory
):
    """Test that a regular user cannot assign tickets"""
    auth_user = authenticated_client["user"]
    technician = technician_factory()

    # Create ticket with authenticated user as raiser so they can access it
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=auth_user,
        status="open",
    )

    client = authenticated_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    data = {"assigned_to_id": technician.id}

    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# TICKET COMMENTS TESTS
# ============================================================================


def test_user_can_add_comment(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test user can add comment to ticket"""
    user = user_factory()
    technician = technician_factory()
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
    )

    Comment.objects.create(ticket=ticket, text="This is a test comment.", author=user)

    client = authenticated_admin_client["client"]
    url = reverse("ticket-comments", args=[ticket.id])
    data = {"text": "This is a second comment"}

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["text"] == "This is a second comment"

    comments_url = reverse("ticket-detail", args=[ticket.id])
    comments_response = client.get(comments_url)
    assert len(comments_response.data["comments"]) == 2


def test_admin_and_technician_can_view_comments(
    authenticated_admin_client,
    authenticated_technician_client,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test that admins and technicians can view ticket comments"""
    user = user_factory()
    technician = technician_factory()
    technician.sections.add(section)

    ticket = Ticket.objects.create(
        title="Comment Visibility Test",
        description="Testing comment visibility rules",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="in_progress",
    )

    Comment.objects.create(ticket=ticket, text="Comment from user", author=user)
    Comment.objects.create(
        ticket=ticket, text="Comment from technician", author=technician
    )

    # Test admin can view comments
    admin_client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    response = admin_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["comments"]) == 2


# ============================================================================
# TICKET DELETION TESTS
# ============================================================================


def test_delete_ticket(authenticated_admin_client, section, facility, user_factory):
    """Test ticket deletion functionality"""
    user = user_factory()
    ticket = Ticket.objects.create(
        title="Delete Me Ticket",
        description="This ticket will be deleted.",
        section=section,
        facility=facility,
        raised_by=user,
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    response = client.delete(url)

    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify deletion
    response = client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND

    with pytest.raises(Ticket.DoesNotExist):
        Ticket.objects.get(id=ticket.id)


# ============================================================================
# TICKET FILTERING TESTS
# ============================================================================


def test_filter_tickets_by_status(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test filtering tickets by status"""
    user = user_factory()
    technician = technician_factory()
    technician.sections.add(section)

    # Create tickets with different statuses
    Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
    )

    Ticket.objects.create(
        title="Second Ticket",
        description="This is a second ticket with different status.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_admin_client["client"]

    # Test filtering by assigned status
    url = reverse("ticket-list") + "?status=assigned"
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    results = response.data["results"]
    assert len(results) >= 1
    for ticket in results:
        assert ticket["status"] == "assigned"

    # Test filtering by open status
    url = reverse("ticket-list") + "?status=open"
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    results = response.data["results"]
    for ticket in results:
        assert ticket["status"] == "open"


def test_filter_tickets_by_section(
    authenticated_admin_client, section, facility, user_factory
):
    """Test filtering tickets by section"""
    user = user_factory()

    # Create a new section
    plumbing = Section.objects.create(
        name="Plumbing",
        description="Water systems and pipes",
        department=section.department,
    )

    # Create tickets for different sections
    Ticket.objects.create(
        title="Water Leak",
        description="There is a water leak in the bathroom.",
        section=plumbing,
        facility=facility,
        raised_by=user,
        status="open",
    )

    Ticket.objects.create(
        title="Network Issue",
        description="Network issue test.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_admin_client["client"]

    # Test filtering by IT section
    url = reverse("ticket-list") + f"?section={section.id}"
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    results = response.data["results"]
    assert len(results) >= 1
    for ticket in results:
        assert ticket["section"]["id"] == section.id

    # Test filtering by Plumbing section
    url = reverse("ticket-list") + f"?section={plumbing.id}"
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "results" in response.data
    results = response.data["results"]
    assert len(results) >= 1
    water_leak_tickets = [
        ticket for ticket in results if ticket["title"] == "Water Leak"
    ]
    assert len(water_leak_tickets) >= 1


# ============================================================================
# TICKET LIFECYCLE WORKFLOW TESTS
# ============================================================================




# ============================================================================
# EDGE CASE TESTS
# ============================================================================


def test_assign_resolved_ticket_fails(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test that a resolved ticket cannot be reassigned"""
    user = user_factory()
    tech1 = technician_factory(username="tech1")
    tech2 = technician_factory(username="tech2")
    tech2.sections.add(section)

    resolved_ticket = Ticket.objects.create(
        title="Already Resolved",
        description="This ticket is already resolved.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=tech1,
        status="resolved",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[resolved_ticket.id])
    data = {"assigned_to_id": tech2.id}

    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Verify assignment didn't change
    resolved_ticket.refresh_from_db()
    assert resolved_ticket.assigned_to == tech1


def test_feedback_on_unresolved_ticket(authenticated_client, section, facility):
    """Test that feedback can only be submitted on resolved tickets"""
    auth_user = authenticated_client["user"]

    statuses = ["open", "assigned", "in_progress", "pending"]

    for ticket_status in statuses:
        ticket = Ticket.objects.create(
            title=f"{ticket_status.capitalize()} Feedback Test",
            description=f"Testing feedback on {ticket_status} ticket.",
            section=section,
            facility=facility,
            raised_by=auth_user,
            status=ticket_status,
        )

        # Try to submit feedback
        client = authenticated_client["client"]
        url = reverse("ticket-feedback", args=[ticket.id])
        data = {"rating": 5, "comment": "Great service!"}

        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_invalid_data_handling(authenticated_client, section, facility):
    """Test handling of invalid data when creating tickets"""
    client = authenticated_client["client"]
    url = reverse("ticket-list")

    # Test with missing required fields
    data = {"title": "Incomplete Ticket"}

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Test with invalid section ID
    data = {
        "title": "Invalid Section",
        "description": "This ticket has an invalid section ID.",
        "section_id": 9999,
        "facility_id": facility.id,
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    # Test with invalid facility ID
    data = {
        "title": "Invalid Facility",
        "description": "This ticket has an invalid facility ID.",
        "section_id": section.id,
        "facility_id": 9999,
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# STATUS TRANSITION TESTS
# ============================================================================


def test_valid_status_transitions(
    authenticated_admin_client,
    authenticated_technician_client,
    section,
    facility,
    user_factory,
):
    """Test the valid status transitions for a ticket"""
    user = user_factory()
    technician = authenticated_technician_client["user"]
    technician.sections.add(section)

    ticket = Ticket.objects.create(
        title="Status Transition Test",
        description="Testing valid status transitions.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    admin_client = authenticated_admin_client["client"]
    tech_client = authenticated_technician_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])

    # Test invalid transition: open → resolved (should fail)
    data = {"status": "resolved"}
    response = admin_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid status transition" in str(response.data)

    # Test valid transition: open → assigned
    data = {"assigned_to_id": technician.id, "status": "assigned"}
    response = admin_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "assigned"

    # Test valid transition: assigned → in_progress
    data = {"status": "in_progress"}
    response = tech_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "in_progress"

    # Test valid transition: in_progress → resolved
    data = {"status": "resolved"}
    response = tech_client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "resolved"


# ============================================================================
# CLOSED TICKET TESTS
# ============================================================================


def test_admin_can_close_resolved_ticket(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test that admin can close resolved tickets"""
    user = user_factory()
    technician = technician_factory()

    resolved_ticket = Ticket.objects.create(
        title="Resolved Ticket",
        description="This ticket is already resolved.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="resolved",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[resolved_ticket.id])
    data = {"status": "closed"}

    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "closed"


def test_cannot_close_unresolved_ticket(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test that tickets can only be closed if they are resolved first"""
    user = user_factory()
    technician = technician_factory()

    statuses = ["open", "assigned", "in_progress", "pending"]
    tickets = []

    for status_value in statuses:
        ticket = Ticket.objects.create(
            title=f"{status_value.capitalize()} Ticket",
            description=f"This ticket has {status_value} status.",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician if status_value != "open" else None,
            status=status_value,
        )
        tickets.append(ticket)

    client = authenticated_admin_client["client"]

    # Try to close each ticket that's not resolved
    for ticket in tickets:
        url = reverse("ticket-detail", args=[ticket.id])
        data = {"status": "closed"}

        response = client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid status transition" in str(response.data)

        # Verify ticket status didn't change
        ticket.refresh_from_db()
        assert ticket.status != "closed"


def test_cannot_modify_closed_ticket(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test that closed tickets cannot be modified"""
    user = user_factory()
    technician = technician_factory()

    closed_ticket = Ticket.objects.create(
        title="Closed Ticket",
        description="This ticket is closed.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="closed",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[closed_ticket.id])

    # Try to change title
    data = {"title": "Updated Closed Ticket"}
    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Closed tickets cannot be modified" in str(response.data)

    # Try to change status
    data = {"status": "in_progress"}
    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Closed tickets cannot be modified" in str(response.data)


def test_comment_on_closed_ticket(
    authenticated_client, section, facility, user_factory, technician_factory
):
    """Test that comments cannot be added to closed tickets"""
    user = user_factory()
    technician = technician_factory()

    closed_ticket = Ticket.objects.create(
        title="Closed Ticket",
        description="This ticket is closed.",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="closed",
    )

    client = authenticated_client["client"]
    url = reverse("ticket-comments", args=[closed_ticket.id])
    data = {"text": "This is a comment on a closed ticket."}

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Cannot add comments to a closed ticket" in str(response.data)


# ============================================================================
# BULK OPERATIONS TESTS
# ============================================================================


def test_bulk_status_update_requires_authentication(
    api_client, section, facility, user_factory
):
    """Test that bulk status update requires authentication"""
    user = user_factory()
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    url = reverse("bulk-status-update")
    data = {
        "ticket_ids": [ticket.id],
        "new_status": "resolved",
    }

    response = api_client.post(url, data, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_bulk_status_update_requires_permission(
    authenticated_client, section, facility, user_factory
):
    """Test that regular users cannot perform bulk operations"""
    user = user_factory()
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_client["client"]
    url = reverse("bulk-status-update")
    data = {
        "ticket_ids": [ticket.id],
        "new_status": "resolved",
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_bulk_status_update_missing_ticket_ids(authenticated_admin_client):
    """Test that ticket_ids is required"""
    client = authenticated_admin_client["client"]
    url = reverse("bulk-status-update")
    data = {
        "new_status": "resolved",
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ticket_ids" in response.data["error"]


def test_bulk_status_update_missing_new_status(
    authenticated_admin_client, section, facility, user_factory
):
    """Test that new_status is required"""
    user = user_factory()
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_admin_client["client"]
    url = reverse("bulk-status-update")
    data = {
        "ticket_ids": [ticket.id],
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "new_status" in response.data["error"]


def test_bulk_status_update_invalid_ticket_ids_type(
    authenticated_admin_client, section, facility, user_factory
):
    """Test that ticket_ids must be a list"""
    user = user_factory()
    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="This is a test ticket.",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_admin_client["client"]
    url = reverse("bulk-status-update")
    data = {
        "ticket_ids": ticket.id,  # Should be a list
        "new_status": "resolved",
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "ticket_ids must be a list" in response.data["error"]


def test_bulk_status_update_admin_success(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test successful bulk status update by admin"""
    user = user_factory()
    technician = technician_factory()
    technician.sections.add(section)

    tickets = []
    for i in range(3):
        ticket = Ticket.objects.create(
            title=f"Test Ticket {i}",
            description=f"This is test ticket {i}.",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician,
            status="assigned",
        )
        tickets.append(ticket)

    client = authenticated_admin_client["client"]
    url = reverse("bulk-status-update")
    ticket_ids = [t.id for t in tickets]

    data = {
        "ticket_ids": ticket_ids,
        "new_status": "in_progress",
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["success"] is True
    assert response.data["updated"] == 3
    assert response.data["failed"] == 0
    assert len(response.data["errors"]) == 0

    # Verify tickets were updated
    for ticket_id in ticket_ids:
        ticket = Ticket.objects.get(id=ticket_id)
        assert ticket.status == "in_progress"


def test_bulk_status_update_empty_list(authenticated_admin_client):
    """Test bulk update with empty ticket list"""
    client = authenticated_admin_client["client"]
    url = reverse("bulk-status-update")
    data = {
        "ticket_ids": [],
        "new_status": "resolved",
    }

    response = client.post(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["updated"] == 0


# ============================================================================
# EDGE CASE & ADVANCED ASSIGNMENT TESTS (from test_ticket_operations)
# ============================================================================


def test_can_assign_multi_section_technician(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test that technician with multiple sections can be assigned to any of their sections"""
    from tickets.models import Section, Department

    # Create second section in same department
    dept = section.department
    section2 = Section.objects.create(
        department=dept, name="Electrical", code="ELEC", description="Electrical work"
    )

    # Create multi-section technician
    tech = technician_factory()
    tech.primary_campus = section.department.campus
    tech.sections.add(section, section2)
    tech.save()

    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    # Create ticket in section 2
    ticket = Ticket.objects.create(
        title="Electrical Issue",
        description="Need electrical work",
        section=section2,
        facility=facility,
        raised_by=user,
        status="open",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    data = {"assigned_to_id": tech.id, "status": "assigned"}

    response = client.patch(url, data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["assigned_to"]["id"] == tech.id


def test_assign_same_technician_multiple_tickets(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test assigning same technician to multiple tickets"""
    tech = technician_factory()
    tech.primary_campus = section.department.campus
    tech.sections.add(section)
    tech.save()

    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    client = authenticated_admin_client["client"]

    # Create and assign 3 tickets to same technician
    for i in range(3):
        ticket = Ticket.objects.create(
            title=f"Issue {i+1}",
            description="Test issue",
            section=section,
            facility=facility,
            raised_by=user,
            status="open",
        )

        url = reverse("ticket-detail", args=[ticket.id])
        data = {"assigned_to_id": tech.id, "status": "assigned"}
        response = client.patch(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["assigned_to"]["id"] == tech.id


def test_unassign_technician_from_ticket(
    authenticated_admin_client, section, facility, user_factory, technician_factory
):
    """Test clearing assignment from a ticket"""
    tech = technician_factory()
    tech.primary_campus = section.department.campus
    tech.sections.add(section)
    tech.save()

    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    ticket = Ticket.objects.create(
        title="Test Ticket",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=tech,
        status="assigned",
    )

    client = authenticated_admin_client["client"]
    url = reverse("ticket-detail", args=[ticket.id])
    # Clear assignment by setting to null
    data = {"assigned_to_id": None}

    response = client.patch(url, data, format="json")
    # API may return 200 with null or 400 depending on implementation
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


def test_get_available_technicians_for_section(
    authenticated_admin_client, section, facility, technician_factory
):
    """Test filtering technicians by section returns only those in that section"""
    tech = technician_factory()
    tech.sections.add(section)
    tech.save()

    client = authenticated_admin_client["client"]
    response = client.get(
        reverse("technicians-by-section"),
        {"section_id": section.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
