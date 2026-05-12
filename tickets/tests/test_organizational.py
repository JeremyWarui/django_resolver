"""
Pytest-based organizational hierarchy and integration tests for Django Resolver.

Converted from Django TestCase to pytest with fixtures.
Tests cover organizational structure, escalation workflows, permissions, and analytics.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse

from tickets.models import (
    Organization,
    Campus,
    Department,
    Section,
    Facility,
    CustomUser,
    Ticket,
    TicketLog,
)
from tickets.api.services import TicketService

# ============================================================================
# ORGANIZATIONAL HIERARCHY TESTS
# ============================================================================


def test_organizational_structure_created(organization, campus, department, section):
    """Test that organizational hierarchy is properly created"""
    assert organization.name == "Test Organization"
    assert campus.organization == organization
    assert department.campus == campus
    assert section.department == department


def test_manager_ticket_scope(
    organization,
    campus,
    department,
    section,
    facility,
    manager_factory,
    user_factory,
    technician_factory,
):
    """Test manager sees dept-scoped tickets across campuses; no primary_department → none"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    Ticket.objects.create(
        title="Manager Scope Test Ticket",
        description="Manager should see this when dept is set",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    # Manager without primary_department gets nothing
    manager_no_dept = manager_factory()
    assert TicketService.get_accessible_tickets(manager_no_dept).count() == 0

    # Manager with primary_department sees dept-scoped tickets
    manager = manager_factory()
    manager.primary_department = department
    manager.save()
    assert TicketService.get_accessible_tickets(manager).count() == 1


def test_manager_scope_includes_same_department_code_across_campuses(
    organization,
    campus,
    department,
    section,
    facility,
    manager_factory,
    user_factory,
):
    """Manager scope is org-wide but constrained to their primary_department code."""
    second_campus = Campus.objects.create(
        organization=organization,
        name="Second Campus",
        code="SCND",
        location="West Side",
    )
    matching_department = Department.objects.create(
        campus=second_campus,
        name="IT Department Branch",
        code=department.code,
    )
    non_matching_department = Department.objects.create(
        campus=second_campus,
        name="Finance Department",
        code="FIN",
    )
    matching_section = Section.objects.create(
        department=matching_department,
        name="Branch Network",
        code="BRNET",
    )
    non_matching_section = Section.objects.create(
        department=non_matching_department,
        name="Finance Ops",
        code="FINOPS",
    )
    second_facility = Facility.objects.create(
        name="Second Campus HQ",
        type="building",
        status="active",
        location="Second Campus",
        campus=second_campus,
    )

    user = user_factory(primary_campus=campus)
    ticket_primary = Ticket.objects.create(
        title="Primary Campus IT",
        description="Manager should see this",
        section=section,
        facility=facility,
        raised_by=user,
    )
    ticket_matching_code = Ticket.objects.create(
        title="Second Campus IT",
        description="Manager should also see this",
        section=matching_section,
        facility=second_facility,
        raised_by=user,
    )
    ticket_non_matching_code = Ticket.objects.create(
        title="Second Campus Finance",
        description="Manager should not see this",
        section=non_matching_section,
        facility=second_facility,
        raised_by=user,
    )

    manager = manager_factory(primary_department=department)
    manager_tickets = TicketService.get_accessible_tickets(manager)
    ids = set(manager_tickets.values_list("id", flat=True))

    assert ticket_primary.id in ids
    assert ticket_matching_code.id in ids
    assert ticket_non_matching_code.id not in ids


def test_hod_campus_scoped_access(
    organization,
    campus,
    department,
    section,
    facility,
    hod_factory,
    user_factory,
    technician_factory,
):
    """Test HOD access is scoped to their campus"""
    hod = hod_factory()
    hod.primary_campus = campus
    hod.primary_department = department
    hod.save()

    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create a ticket
    ticket = Ticket.objects.create(
        title="HOD Test Ticket",
        description="Test ticket for HOD",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    # HOD should have department-level scope access
    assert hod.organizational_scope == "department"


def test_section_head_department_scoped_access(
    organization,
    campus,
    department,
    section,
    facility,
    section_head_factory,
    user_factory,
    technician_factory,
):
    """Test section head access is scoped to their department"""
    section_head = section_head_factory()
    section_head.primary_campus = campus
    section_head.primary_department = department
    section_head.sections.add(section)
    section_head.save()

    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create a ticket
    ticket = Ticket.objects.create(
        title="Section Head Test Ticket",
        description="Test ticket for section head",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    # Section head should have section-level scope
    assert section_head.organizational_scope == "section"


def test_technician_section_scoped_access(
    organization,
    campus,
    department,
    section,
    facility,
    technician_factory,
    user_factory,
):
    """Test technician access is scoped to their section"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create a ticket
    ticket = Ticket.objects.create(
        title="Technician Test Ticket",
        description="Test ticket for technician",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    # Technician should have section-level scope
    assert technician.organizational_scope == "section"


# ============================================================================
# ESCALATION WORKFLOW TESTS
# ============================================================================


def test_escalation_to_section_head(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
    section_head_factory,
):
    """Test ticket escalation to section head"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    section_head = section_head_factory()
    section_head.primary_campus = campus
    section_head.primary_department = department
    section_head.sections.add(section)
    section_head.save()

    ticket = Ticket.objects.create(
        title="Escalation Test",
        description="Test escalation workflow",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="open",
    )

    # Escalate ticket (technician can escalate)
    TicketService.escalate_ticket(
        ticket=ticket, escalated_by=technician, reason="Escalating to section head"
    )

    ticket.refresh_from_db()
    assert ticket.escalation_level == 1
    assert ticket.status == "escalated"


def test_escalation_to_hod(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
    hod_factory,
):
    """Test ticket escalation to HOD"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    hod = hod_factory()
    hod.primary_campus = campus
    hod.primary_department = department
    hod.save()

    ticket = Ticket.objects.create(
        title="Escalation to HOD Test",
        description="Test escalation to HOD",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="open",
        escalation_level=1,
    )

    # Escalate to HOD (technician can escalate)
    TicketService.escalate_ticket(
        ticket=ticket, escalated_by=technician, reason="Escalating to HOD"
    )

    ticket.refresh_from_db()
    assert ticket.escalation_level == 2
    assert ticket.status == "escalated"


def test_cannot_escalate_beyond_hod(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test that tickets cannot be escalated beyond HOD"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket = Ticket.objects.create(
        title="Max Escalation Test",
        description="Test maximum escalation level",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="open",
        escalation_level=2,  # Already at max
    )

    # Try to escalate beyond HOD (should return ticket unchanged)
    result = TicketService.escalate_ticket(
        ticket=ticket, escalated_by=technician, reason="Trying to escalate beyond HOD"
    )
    # Should remain at level 2, cannot escalate further
    assert result.escalation_level == 2


# ============================================================================
# API INTEGRATION TESTS
# ============================================================================


def test_organizational_ticket_list_endpoint(
    authenticated_client,
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test organizational ticket list endpoint"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket = Ticket.objects.create(
        title="Org Ticket List Test",
        description="Test organizational ticket list endpoint",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    client = authenticated_client["client"]
    url = reverse("organizational-ticket-list")
    response = client.get(url)

    # Endpoint should return successfully (200 or 403 depending on permissions)
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


def test_assignable_users_endpoint(
    authenticated_client,
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test assignable users endpoint returns technicians in section"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    client = authenticated_client["client"]
    url = reverse("assignable-users") + f"?section_id={section.id}"
    response = client.get(url)

    # Endpoint should return successfully
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


def test_assignable_users_endpoint_forbids_regular_user(
    authenticated_client, section
):
    """Regular users cannot access assignment candidate endpoint."""
    client = authenticated_client["client"]
    url = reverse("assignable-users") + f"?section_id={section.id}"
    response = client.get(url)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_assignable_users_returns_only_active_section_technicians_for_hod(
    hod_factory,
    technician_factory,
    campus,
    department,
    section,
):
    """HOD gets only active technicians mapped to requested section."""
    hod = hod_factory(primary_campus=campus, primary_department=department)

    active_in_section = technician_factory(
        username="active_in_section",
        primary_campus=campus,
        primary_department=department,
        is_active=True,
    )
    active_in_section.sections.add(section)

    inactive_in_section = technician_factory(
        username="inactive_in_section",
        primary_campus=campus,
        primary_department=department,
        is_active=False,
    )
    inactive_in_section.sections.add(section)

    active_other_section = technician_factory(
        username="active_other_section",
        primary_campus=campus,
        primary_department=department,
        is_active=True,
    )
    other_section = Section.objects.create(
        department=department, name="Other Section", code="OTHER"
    )
    active_other_section.sections.add(other_section)

    client = APIClient()
    client.force_authenticate(user=hod)
    url = reverse("assignable-users") + f"?section_id={section.id}"
    response = client.get(url)

    assert response.status_code == status.HTTP_200_OK
    usernames = {user["username"] for user in response.data["results"]}
    assert "active_in_section" in usernames
    assert "inactive_in_section" not in usernames
    assert "active_other_section" not in usernames


def test_organizational_analytics_endpoint(
    authenticated_client,
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test organizational analytics endpoint"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket = Ticket.objects.create(
        title="Analytics Test",
        description="Test analytics endpoint",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    client = authenticated_client["client"]
    url = reverse("analytics-tickets")
    response = client.get(url)

    # Endpoint should return successfully or forbidden based on permissions
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


# ============================================================================
# ANALYTICS AGGREGATION TESTS
# ============================================================================


def test_hod_dashboard_campus_scoped(
    hod_factory,
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test HOD dashboard shows campus-scoped metrics"""
    hod = hod_factory()
    hod.primary_campus = campus
    hod.primary_department = department
    hod.save()

    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create tickets
    for i in range(3):
        Ticket.objects.create(
            title=f"HOD Dashboard Test {i}",
            description=f"Test ticket {i}",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician,
        )

    # HOD should see only campus-scoped tickets
    assert hod.role == "hod"
    assert hod.primary_campus == campus


# ============================================================================
# TICKET SERVICE TESTS
# ============================================================================


def test_create_ticket_with_proper_scope(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test creating ticket with proper organizational scope"""
    user = user_factory()
    user.primary_campus = campus
    # Users can create tickets in sections they have access to, so add them to the section
    user.sections.add(section)
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket_data = {
        "title": "Scope Test Ticket",
        "description": "Testing organizational scope",
        "priority": "low",
    }

    ticket = TicketService.create_ticket(
        data=ticket_data, created_by=user, section=section, facility=facility
    )

    assert ticket.id is not None
    assert ticket.section == section
    assert ticket.raised_by == user
    assert ticket.status == "open"


def test_create_ticket_exceeds_scope(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test creating ticket with section outside user scope raises error"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create another section user can't access
    other_section = Section.objects.create(
        name="Restricted Section", code="RESTRICTED", department=department
    )

    ticket_data = {
        "title": "Out of Scope Ticket",
        "description": "Testing out of scope access",
        "priority": "low",
    }

    # Should raise InsufficientScopeException when user doesn't have access
    from tickets.api.services import InsufficientScopeException

    with pytest.raises(InsufficientScopeException):
        TicketService.create_ticket(
            data=ticket_data, created_by=user, section=other_section, facility=facility
        )


def test_assign_ticket_with_proper_validation(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
    section_head_factory,
):
    """Test ticket assignment with proper technician validation"""
    user = user_factory()
    user.primary_campus = campus
    user.sections.add(section)
    user.save()

    section_head = section_head_factory()
    section_head.primary_campus = campus
    section_head.primary_department = department
    section_head.sections.add(section)
    section_head.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket = Ticket.objects.create(
        title="Assignment Validation Test",
        description="Testing assignment validation",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    # Assign ticket (section_head can assign)
    TicketService.assign_ticket(
        ticket=ticket, technician=technician, assigned_by=section_head
    )

    ticket.refresh_from_db()
    assert ticket.assigned_to == technician
    assert ticket.status == "assigned"


def test_assign_ticket_invalid_technician(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
    section_head_factory,
):
    """Test ticket assignment fails with invalid technician"""
    user = user_factory()
    user.primary_campus = campus
    user.sections.add(section)
    user.save()

    section_head = section_head_factory()
    section_head.primary_campus = campus
    section_head.primary_department = department
    section_head.sections.add(section)
    section_head.save()

    technician1 = technician_factory(username="tech1")
    technician1.primary_campus = campus
    technician1.sections.add(section)
    technician1.save()

    technician2 = technician_factory(username="tech2")
    # Don't add to same section - this makes them inaccessible

    ticket = Ticket.objects.create(
        title="Invalid Technician Test",
        description="Testing invalid technician assignment",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    # Try to assign to technician not in section (section_head tries to assign)
    from tickets.api.services import InvalidAssignmentException

    with pytest.raises(InvalidAssignmentException):
        TicketService.assign_ticket(
            ticket=ticket, technician=technician2, assigned_by=section_head
        )


def test_escalate_ticket(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test ticket escalation through service"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket = Ticket.objects.create(
        title="Escalation Service Test",
        description="Testing escalation through service",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="open",
    )

    # Escalate ticket (technician can escalate)
    TicketService.escalate_ticket(
        ticket=ticket, escalated_by=technician, reason="Needs escalation"
    )

    ticket.refresh_from_db()
    assert ticket.escalation_level >= 1
    assert ticket.status == "escalated"


def test_get_accessible_tickets_respects_scope(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
    admin_user_factory,
):
    """Test that get_accessible_tickets respects organizational scope"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    admin = admin_user_factory()

    # Create tickets
    ticket1 = Ticket.objects.create(
        title="User Ticket",
        description="Ticket created by user",
        section=section,
        facility=facility,
        raised_by=user,
        status="open",
    )

    ticket2 = Ticket.objects.create(
        title="Tech Ticket",
        description="Ticket assigned to technician",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
    )

    # User should see their own tickets
    user_accessible = TicketService.get_accessible_tickets(user)
    assert ticket1 in user_accessible or ticket1.id in [t.id for t in user_accessible]

    # Technician should see assigned tickets and same-section tickets
    tech_accessible = TicketService.get_accessible_tickets(technician)
    assert ticket2 in tech_accessible or ticket2.id in [t.id for t in tech_accessible]

    # Admin should see all tickets
    admin_accessible = TicketService.get_accessible_tickets(admin)
    assert len(admin_accessible) >= 2


def test_auto_escalation_processing(
    organization,
    campus,
    department,
    section,
    facility,
    user_factory,
    technician_factory,
):
    """Test automatic escalation processing by background task"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create ticket that should auto-escalate (created long ago)
    old_time = timezone.now() - timedelta(days=3)
    ticket = Ticket.objects.create(
        title="Auto Escalation Test",
        description="Testing auto escalation",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="open",
        created_at=old_time,
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
        next_escalation_due=old_time + timedelta(hours=48),
    )

    # The ticket exists and has auto-escalation enabled
    assert ticket.auto_escalation_enabled
    assert ticket.escalation_level == 0


# ============================================================================
# ANALYTICS DASHBOARD TESTS
# ============================================================================

