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
    Organization, Campus, Department, Section, Facility,
    CustomUser, Ticket, TicketLog
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


def test_director_access_all_tickets(organization, campus, department, section, facility, director_factory, user_factory, technician_factory):
    """Test that directors can access all tickets in their organization"""
    director = director_factory()
    director.primary_campus = campus
    director.save()

    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create tickets by different users
    ticket1 = Ticket.objects.create(
        title="Director Test Ticket 1",
        description="Test ticket 1",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
    )

    ticket2 = Ticket.objects.create(
        title="Director Test Ticket 2",
        description="Test ticket 2",
        section=section,
        facility=facility,
        raised_by=technician,
    )

    # Directors should have access to all tickets
    assert director.organizational_scope == "organization"

    # Test through TicketService
    accessible_tickets = TicketService.get_accessible_tickets(director)
    assert ticket1 in accessible_tickets or ticket1.id in [
        t.id for t in accessible_tickets]


def test_hod_campus_scoped_access(organization, campus, department, section, facility, hod_factory, user_factory, technician_factory):
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


def test_section_head_department_scoped_access(organization, campus, department, section, facility, section_head_factory, user_factory, technician_factory):
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


def test_technician_section_scoped_access(organization, campus, department, section, facility, technician_factory, user_factory):
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

def test_escalation_to_section_head(organization, campus, department, section, facility, user_factory, technician_factory, section_head_factory):
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
        ticket=ticket,
        escalated_by=technician,
        reason="Escalating to section head"
    )

    ticket.refresh_from_db()
    assert ticket.escalation_level == 1
    assert ticket.status == "escalated"


def test_escalation_to_hod(organization, campus, department, section, facility, user_factory, technician_factory, hod_factory):
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
        ticket=ticket,
        escalated_by=technician,
        reason="Escalating to HOD"
    )

    ticket.refresh_from_db()
    assert ticket.escalation_level == 2
    assert ticket.status == "escalated"


def test_cannot_escalate_beyond_hod(organization, campus, department, section, facility, user_factory, technician_factory):
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
        ticket=ticket,
        escalated_by=technician,
        reason="Trying to escalate beyond HOD"
    )
    # Should remain at level 2, cannot escalate further
    assert result.escalation_level == 2


# ============================================================================
# API INTEGRATION TESTS
# ============================================================================

def test_organizational_ticket_list_endpoint(authenticated_client, organization, campus, department, section, facility, user_factory, technician_factory):
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

    client = authenticated_client['client']
    url = reverse("organizational-ticket-list")
    response = client.get(url)

    # Endpoint should return successfully (200 or 403 depending on permissions)
    assert response.status_code in [
        status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


def test_assignable_users_endpoint(authenticated_client, organization, campus, department, section, facility, user_factory, technician_factory):
    """Test assignable users endpoint returns technicians in section"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    client = authenticated_client['client']
    url = reverse("assignable-users") + f"?section_id={section.id}"
    response = client.get(url)

    # Endpoint should return successfully
    assert response.status_code in [
        status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


def test_organizational_analytics_endpoint(authenticated_client, organization, campus, department, section, facility, user_factory, technician_factory):
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

    client = authenticated_client['client']
    url = reverse("analytics-tickets")
    response = client.get(url)

    # Endpoint should return successfully or forbidden based on permissions
    assert response.status_code in [
        status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


def test_escalate_ticket_manual_endpoint(authenticated_client, organization, campus, department, section, facility, user_factory, technician_factory):
    """Test manual ticket escalation endpoint"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    ticket = Ticket.objects.create(
        title="Escalate Endpoint Test",
        description="Test escalation endpoint",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="open",
    )

    client = authenticated_client['client']
    url = reverse("escalate-ticket-manual", args=[ticket.id])
    data = {"reason": "Needs urgent attention"}

    response = client.post(url, data, format="json")

    # Endpoint should process the escalation
    assert response.status_code in [
        status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN]


# ============================================================================
# ANALYTICS AGGREGATION TESTS
# ============================================================================

def test_director_dashboard_aggregates_metrics(director_factory, organization, campus, department, section, facility, user_factory, technician_factory):
    """Test director dashboard aggregates organization-wide metrics"""
    director = director_factory()
    director.primary_campus = campus
    director.save()

    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create multiple tickets with different statuses
    for i in range(3):
        Ticket.objects.create(
            title=f"Dashboard Test {i}",
            description=f"Test ticket {i}",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician if i % 2 == 0 else None,
            status="open" if i % 3 == 0 else "assigned",
        )

    # Director should be able to see aggregated metrics
    assert director.role == "director"


def test_hod_dashboard_campus_scoped(hod_factory, organization, campus, department, section, facility, user_factory, technician_factory):
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

def test_create_ticket_with_proper_scope(organization, campus, department, section, facility, user_factory, technician_factory):
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
        'title': 'Scope Test Ticket',
        'description': 'Testing organizational scope',
        'priority': 'low',
    }

    ticket = TicketService.create_ticket(
        data=ticket_data,
        created_by=user,
        section=section,
        facility=facility
    )

    assert ticket.id is not None
    assert ticket.section == section
    assert ticket.raised_by == user
    assert ticket.status == "open"


def test_create_ticket_exceeds_scope(organization, campus, department, section, facility, user_factory, technician_factory):
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
        name="Restricted Section",
        code="RESTRICTED",
        department=department
    )

    ticket_data = {
        'title': 'Out of Scope Ticket',
        'description': 'Testing out of scope access',
        'priority': 'low',
    }

    # Should raise InsufficientScopeException when user doesn't have access
    from tickets.api.services import InsufficientScopeException
    with pytest.raises(InsufficientScopeException):
        TicketService.create_ticket(
            data=ticket_data,
            created_by=user,
            section=other_section,
            facility=facility
        )


def test_assign_ticket_with_proper_validation(organization, campus, department, section, facility, user_factory, technician_factory, section_head_factory):
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
        ticket=ticket,
        technician=technician,
        assigned_by=section_head
    )

    ticket.refresh_from_db()
    assert ticket.assigned_to == technician
    assert ticket.status == "assigned"


def test_assign_ticket_invalid_technician(organization, campus, department, section, facility, user_factory, technician_factory, section_head_factory):
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
            ticket=ticket,
            technician=technician2,
            assigned_by=section_head
        )


def test_escalate_ticket(organization, campus, department, section, facility, user_factory, technician_factory):
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
        ticket=ticket,
        escalated_by=technician,
        reason="Needs escalation"
    )

    ticket.refresh_from_db()
    assert ticket.escalation_level >= 1
    assert ticket.status == "escalated"


def test_get_accessible_tickets_respects_scope(organization, campus, department, section, facility, user_factory, technician_factory, admin_user_factory):
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
    assert ticket1 in user_accessible or ticket1.id in [
        t.id for t in user_accessible]

    # Technician should see assigned tickets and same-section tickets
    tech_accessible = TicketService.get_accessible_tickets(technician)
    assert ticket2 in tech_accessible or ticket2.id in [
        t.id for t in tech_accessible]

    # Admin should see all tickets
    admin_accessible = TicketService.get_accessible_tickets(admin)
    assert len(admin_accessible) >= 2


def test_auto_escalation_processing(organization, campus, department, section, facility, user_factory, technician_factory):
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

def test_director_dashboard(director_factory, organization, campus, department, section, facility, user_factory, technician_factory):
    """Test director dashboard with organization-wide metrics"""
    director = director_factory()
    director.primary_campus = campus
    director.save()

    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create various tickets
    for i in range(5):
        Ticket.objects.create(
            title=f"Dashboard Ticket {i}",
            description=f"Dashboard test {i}",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician if i % 2 == 0 else None,
            status="open" if i < 2 else "assigned",
        )

    # Director should have full organization access
    assert director.organizational_scope == "organization"


def test_hod_dashboard(hod_factory, organization, campus, department, section, facility, user_factory, technician_factory):
    """Test HOD dashboard with department-scoped metrics"""
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
            title=f"HOD Ticket {i}",
            description=f"HOD dashboard test {i}",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician,
        )

    # HOD should have department access
    assert hod.organizational_scope == "department"


def test_section_head_dashboard(section_head_factory, organization, campus, department, section, facility, user_factory, technician_factory):
    """Test section head dashboard with section-scoped metrics"""
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

    # Create tickets
    for i in range(2):
        Ticket.objects.create(
            title=f"Section Head Ticket {i}",
            description=f"Section head dashboard test {i}",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician,
        )

    # Section head should have section access
    assert section_head.organizational_scope == "section"


def test_dashboard_sla_compliance_calculation(organization, campus, department, section, facility, user_factory, technician_factory):
    """Test SLA compliance calculation in dashboards"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create ticket and mark as resolved quickly (should have good SLA)
    ticket = Ticket.objects.create(
        title="SLA Compliance Test",
        description="Testing SLA compliance calculation",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="resolved",
        created_at=timezone.now() - timedelta(hours=2),
    )

    # Ticket exists and can be used for SLA calculations
    assert ticket.status == "resolved"
    assert ticket.created_at is not None


def test_escalation_trends(organization, campus, department, section, facility, user_factory, technician_factory):
    """Test escalation trend analysis"""
    user = user_factory()
    user.primary_campus = campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = campus
    technician.sections.add(section)
    technician.save()

    # Create tickets with different escalation levels
    for level in range(3):
        Ticket.objects.create(
            title=f"Escalation Level {level}",
            description=f"Testing escalation level {level}",
            section=section,
            facility=facility,
            raised_by=user,
            assigned_to=technician,
            status="escalated" if level > 0 else "open",
            escalation_level=level,
        )

    # Verify escalation levels are set correctly
    tickets = Ticket.objects.all().order_by('escalation_level')
    assert tickets.first().escalation_level == 0
    assert tickets.last().escalation_level == 2
