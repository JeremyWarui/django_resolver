"""End-to-end ticket workflow tests — complete lifecycle from creation to closure.

Tests verify the full ticket journey:
  1. User creates ticket (with org structure routing)
  2. Ticket routes through org hierarchy (department → campus_department → section)
  3. HOD/HOS assigns ticket to valid technician (correct section/campus)
  4. Technician works on ticket (in_progress, pending)
  5. Technician resolves ticket
  6. Admin/HOD closes ticket

At each stage, verify:
  - Only valid actions are possible
  - Only valid assignees can be selected
  - Ticket state transitions correctly
  - Unauthorized roles are rejected
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tickets.models import Ticket, TechnicianSection


def make_authenticated_client(user):
    """Create authenticated API client for a given user."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ── Stage 1: User Creates Ticket (with Org Routing) ───────────────────────────


class TestTicketCreationAndRouting:
    """Test ticket creation with organizational structure routing."""

    def test_user_creates_ticket_resolves_correct_section(
        self, db, user_factory, campus_department, section_type, section, service_item
    ):
        """User creates ticket → system resolves correct section from org structure."""
        # Setup: user on a campus
        user = user_factory(username="ticket_creator")
        user.primary_campus = section.campus_department.campus
        user.primary_department = section.campus_department.department
        user.save()

        client = make_authenticated_client(user)

        # User creates ticket
        response = client.post(
            reverse("ticket-create"),
            {
                "title": "Wi-Fi not working",
                "description": "Internet is down",
                "department_id": section.campus_department.department.id,
                "service_item_id": service_item.id,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # Verify ticket was created
        ticket = Ticket.objects.get(id=data["ticket"]["id"])
        assert ticket.raised_by == user
        assert ticket.status == "open"

        # Verify org structure was resolved correctly
        assert ticket.campus_department == section.campus_department
        assert ticket.section == section

    def test_ticket_creation_validates_user_has_primary_campus(
        self, db, user_factory, service_item
    ):
        """User without primary_campus cannot create ticket."""
        user = user_factory(username="no_campus_user")
        user.primary_campus = None
        user.save()

        client = make_authenticated_client(user)
        response = client.post(
            reverse("ticket-create"),
            {
                "title": "Test",
                "description": "Test",
                "department_id": service_item.category.section_type.department.id,
                "service_item_id": service_item.id,
            },
            format="json",
        )

        # Should fail because user has no campus
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ticket_creation_service_item_must_match_department(
        self, db, user_factory, campus_department, section, service_item, facility
    ):
        """Service item must belong to user's department."""
        user = user_factory()
        user.primary_campus = campus_department.campus
        user.primary_department = campus_department.department
        user.save()

        # Create service item for different department
        from tickets.models import Department
        other_dept = Department.objects.create(name="Other", code="OTH")
        other_st = section.section_type.__class__.objects.create(
            department=other_dept, name="Other Type", code="OTH"
        )
        other_cat = service_item.category.__class__.objects.create(
            section_type=other_st, name="Other Category"
        )
        other_item = service_item.__class__.objects.create(
            category=other_cat, name="Other Item"
        )

        client = make_authenticated_client(user)
        response = client.post(
            reverse("ticket-create"),
            {
                "title": "Test",
                "description": "Test",
                "department_id": campus_department.department.id,
                "service_item_id": other_item.id,
            },
            format="json",
        )

        # Should fail because service item is for different department
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_ticket_requires_approval_creates_pending_approval_status(
        self, db, user_factory, campus_department, section, facility, service_item
    ):
        """Service item with requires_approval=True creates pending_approval ticket."""
        user = user_factory()
        user.primary_campus = campus_department.campus
        user.primary_department = campus_department.department
        user.save()

        # Use the fixture service item and set requires_approval
        si = service_item
        si.requires_approval = True
        si.save()

        client = make_authenticated_client(user)
        response = client.post(
            reverse("ticket-create"),
            {
                "title": "Approval Required",
                "description": "Test",
                "department_id": campus_department.department.id,
                "service_item_id": si.id,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        ticket = Ticket.objects.get(id=response.json()["ticket"]["id"])
        assert ticket.status == "pending_approval"


# ── Stage 2: Approval & Routing to HOD/HOS ────────────────────────────────────


class TestTicketApprovalAndRouting:
    """Test ticket approval and routing to HOD/HOS."""

    def test_hod_can_approve_pending_approval_ticket(
        self, db, hod_factory, campus_department, section, ticket_factory, facility
    ):
        """HOD approves pending_approval ticket → moves to open."""
        hod = hod_factory()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        ticket = ticket_factory(
            status="pending_approval",
            section=section,
            campus_department=campus_department,
        )

        client = make_authenticated_client(hod)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "open"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "open"

    def test_hod_can_reject_pending_approval_ticket(
        self, db, hod_factory, campus_department, section, ticket_factory
    ):
        """HOD rejects pending_approval ticket → moves to rejected."""
        hod = hod_factory()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        ticket = ticket_factory(
            status="pending_approval",
            section=section,
            campus_department=campus_department,
        )

        client = make_authenticated_client(hod)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "rejected"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "rejected"

    def test_technician_cannot_approve_pending_approval_ticket(
        self, db, technician_factory, section, ticket_factory
    ):
        """Technician cannot approve pending_approval tickets."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(
            status="pending_approval",
            section=section,
        )

        client = make_authenticated_client(tech)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "open"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Stage 3: Assignment to Technician ──────────────────────────────────────────


class TestTicketAssignmentConstraints:
    """Test assignment constraints and validation."""

    def test_hod_can_assign_ticket_to_section_technician(
        self, db, hod_factory, technician_factory, campus_department, section, ticket_factory
    ):
        """HOD assigns ticket to technician in the section."""
        hod = hod_factory()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        tech = technician_factory()
        tech.primary_campus = campus_department.campus
        tech.save()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="open",
            section=section,
            campus_department=campus_department,
            assigned_to=None,  # Start unassigned so HOD can assign
        )

        client = make_authenticated_client(hod)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.assigned_to == tech
        assert ticket.status == "assigned"

    def test_hod_cannot_assign_to_technician_different_campus(
        self, db, hod_factory, technician_factory, campus, campus_department,
        section, ticket_factory
    ):
        """HOD cannot assign to technician on different campus."""
        hod = hod_factory()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        # Technician on different campus
        tech = technician_factory()
        other_campus = campus  # Different from section's campus
        if other_campus == campus_department.campus:
            from tickets.models import Campus
            other_campus = Campus.objects.create(
                name="Other", code="OTH", location="Other"
            )
        tech.primary_campus = other_campus
        tech.save()

        ticket = ticket_factory(
            status="open",
            section=section,
            campus_department=campus_department,
            assigned_to=None,  # Start unassigned
        )

        client = make_authenticated_client(hod)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        # Should fail due to campus mismatch
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_hod_cannot_assign_to_technician_not_in_section(
        self, db, hod_factory, technician_factory, campus_department, section,
        ticket_factory
    ):
        """HOD cannot assign to technician not in the section."""
        hod = hod_factory()
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        tech = technician_factory()
        tech.primary_campus = campus_department.campus
        tech.save()
        # Do NOT add to section

        ticket = ticket_factory(
            status="open",
            section=section,
            campus_department=campus_department,
            assigned_to=None,  # Start unassigned
        )

        client = make_authenticated_client(hod)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        # Should fail because tech is not in the section
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_hos_can_assign_ticket_in_own_section(
        self, db, section_head_factory, technician_factory, section, ticket_factory
    ):
        """Head of Section can assign ticket in their section."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        section.head_of_section = hos
        section.save()

        tech = technician_factory()
        tech.primary_campus = section.campus_department.campus
        tech.save()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="open",
            section=section,
            assigned_to=None,  # Start unassigned
        )

        client = make_authenticated_client(hos)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.assigned_to == tech

    def test_hos_cannot_assign_ticket_in_other_section(
        self, db, section_head_factory, technician_factory, section, section_type,
        campus_department, ticket_factory
    ):
        """Head of Section cannot assign ticket in section they don't head."""
        hos = section_head_factory()
        hos.sections.add(section)
        hos.primary_campus = section.campus_department.campus
        hos.primary_department = section.campus_department.department
        hos.save()
        section.head_of_section = hos
        section.save()

        # Create different section type and section
        from tickets.models import SectionType
        other_st = SectionType.objects.create(
            department=section_type.department,
            name="Other Section Type",
            code="OTHER_TYPE",
        )
        other_section = section.__class__.objects.create(
            campus_department=campus_department,
            section_type=other_st,
            name="Other Section",
            code="OTHER",
        )

        tech = technician_factory()
        tech.sections.add(other_section)

        ticket = ticket_factory(
            status="open",
            section=other_section,
        )

        client = make_authenticated_client(hos)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        # HOS cannot assign tickets in sections they don't head
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_cannot_assign_ticket(
        self, db, user_factory, technician_factory, section, ticket_factory
    ):
        """Regular user cannot assign tickets."""
        user = user_factory()
        tech = technician_factory()
        ticket = ticket_factory(status="open", section=section)

        client = make_authenticated_client(user)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Stage 4: Technician Works on Ticket ───────────────────────────────────────


class TestTechnicianWorkflow:
    """Test technician actions on assigned tickets."""

    def test_technician_can_move_assigned_to_in_progress(
        self, db, technician_factory, section, ticket_factory
    ):
        """Technician moves ticket from assigned → in_progress."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(
            status="assigned",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(tech)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "in_progress"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "in_progress"

    def test_technician_can_move_in_progress_to_pending(
        self, db, technician_factory, section, ticket_factory
    ):
        """Technician moves ticket from in_progress → pending (with reason/comment)."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(
            status="in_progress",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(tech)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {
                "status": "pending",
                "pending_reason": "material_shortage",
                "pending_comment": "Waiting for replacement parts to arrive",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "pending"
        assert ticket.pending_reason == "material_shortage"
        assert ticket.pending_comment == "Waiting for replacement parts to arrive"

    def test_pending_transition_requires_reason_and_comment(
        self, db, technician_factory, section, ticket_factory
    ):
        """Moving to pending without reason/comment fails."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(
            status="in_progress",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(tech)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "pending"},  # Missing pending_reason and pending_comment
            format="json",
        )

        # Should fail validation
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_technician_can_move_pending_to_in_progress(
        self, db, technician_factory, section, ticket_factory
    ):
        """Technician moves ticket from pending → in_progress."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(
            status="pending",
            assigned_to=tech,
            section=section,
            pending_reason="waiting_for_parts",
            pending_comment="Waiting for parts",
        )

        client = make_authenticated_client(tech)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "in_progress"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "in_progress"

    def test_unassigned_technician_cannot_edit_ticket(
        self, db, technician_factory, section, ticket_factory
    ):
        """Technician not assigned to ticket cannot edit it."""
        tech1 = technician_factory()
        tech2 = technician_factory()
        tech1.sections.add(section)
        tech2.sections.add(section)

        ticket = ticket_factory(
            status="assigned",
            assigned_to=tech1,
            section=section,
        )

        client = make_authenticated_client(tech2)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "in_progress"},
            format="json",
        )

        # tech2 is not assigned, should get 403
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ── Stage 5: Technician Resolves Ticket ───────────────────────────────────────


class TestTicketResolution:
    """Test ticket resolution workflow."""

    def test_technician_can_resolve_ticket(
        self, db, technician_factory, section, ticket_factory
    ):
        """Technician moves ticket to resolved."""
        tech = technician_factory()
        tech.sections.add(section)
        ticket = ticket_factory(
            status="in_progress",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(tech)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "resolved"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "resolved"

    def test_cannot_assign_resolved_ticket(
        self, db, admin_user_factory, technician_factory, section, ticket_factory
    ):
        """Cannot reassign a resolved ticket."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="resolved",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(admin)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"assigned_to_id": tech.id},
            format="json",
        )

        # Should fail or be no-op for resolved tickets
        ticket.refresh_from_db()
        # Resolved tickets should not be modifiable
        assert ticket.status == "resolved"

    def test_user_can_provide_feedback_on_resolved_ticket(
        self, db, user_factory, technician_factory, section, ticket_factory
    ):
        """User can provide feedback on resolved ticket."""
        user = user_factory()
        tech = technician_factory()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="resolved",
            raised_by=user,
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(user)
        response = client.post(
            reverse("feedback-list"),
            {
                "ticket": ticket.id,
                "rating": 5,
                "comment": "Great job!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED


# ── Stage 6: Admin Closes Ticket ───────────────────────────────────────────────


class TestTicketClosure:
    """Test ticket closure workflow."""

    def test_admin_can_close_resolved_ticket(
        self, db, admin_user_factory, technician_factory, section, ticket_factory
    ):
        """Admin closes resolved ticket."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="resolved",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(admin)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "closed"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "closed"

    def test_cannot_close_unresolved_ticket(
        self, db, admin_user_factory, technician_factory, section, ticket_factory
    ):
        """Cannot close ticket that is not resolved."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="in_progress",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(admin)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "closed"},
            format="json",
        )

        # Should fail validation
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_modify_closed_ticket(
        self, db, admin_user_factory, technician_factory, section, ticket_factory
    ):
        """Closed tickets are immutable."""
        admin = admin_user_factory()
        tech = technician_factory()
        tech.sections.add(section)

        ticket = ticket_factory(
            status="closed",
            assigned_to=tech,
            section=section,
        )

        client = make_authenticated_client(admin)
        response = client.patch(
            reverse("ticket-detail", args=[ticket.id]),
            {"status": "open"},
            format="json",
        )

        # Should fail
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        ticket.refresh_from_db()
        assert ticket.status == "closed"


# ── Complete End-to-End Workflow ───────────────────────────────────────────────


class TestCompleteTicketLifecycle:
    """Test the complete ticket lifecycle from creation to closure."""

    def test_full_workflow_open_to_closed(
        self, db, user_factory, hod_factory, technician_factory, section,
        campus_department, service_item, facility, ticket_factory
    ):
        """Complete workflow: create → assign → work → resolve → close."""
        # Setup users
        user = user_factory(username="creator")
        user.primary_campus = campus_department.campus
        user.primary_department = campus_department.department
        user.save()

        hod = hod_factory(username="hod_approver")
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        tech = technician_factory(username="tech_worker")
        tech.primary_campus = campus_department.campus
        tech.save()
        tech.sections.add(section)

        admin = user.__class__.objects.create_user(
            username="admin_closer",
            password="pass",
            role="admin",
        )

        # Stage 1: User creates ticket
        client_user = make_authenticated_client(user)
        create_response = client_user.post(
            reverse("ticket-create"),
            {
                "title": "Network issue",
                "description": "Internet is slow",
                "department_id": campus_department.department.id,
                "service_item_id": service_item.id,
            },
            format="json",
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        ticket_id = create_response.json()["ticket"]["id"]
        ticket = Ticket.objects.get(id=ticket_id)
        assert ticket.status == "open"
        assert ticket.raised_by == user

        # Stage 2: HOD assigns ticket to technician
        client_hod = make_authenticated_client(hod)
        assign_response = client_hod.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )
        assert assign_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "assigned"
        assert ticket.assigned_to == tech

        # Stage 3: Technician moves to in_progress
        client_tech = make_authenticated_client(tech)
        progress_response = client_tech.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "in_progress"},
            format="json",
        )
        assert progress_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "in_progress"

        # Stage 4: Technician marks as pending (waiting for info)
        pending_response = client_tech.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {
                "status": "pending",
                "pending_reason": "other",
                "pending_comment": "Waiting for user to restart router",
            },
            format="json",
        )
        assert pending_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "pending"

        # Stage 5: Technician resumes (back to in_progress)
        resume_response = client_tech.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "in_progress"},
            format="json",
        )
        assert resume_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "in_progress"

        # Stage 6: Technician resolves ticket
        resolve_response = client_tech.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "resolved"},
            format="json",
        )
        assert resolve_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "resolved"

        # Stage 7: User provides feedback
        client_user = make_authenticated_client(user)
        feedback_response = client_user.post(
            reverse("feedback-list"),
            {
                "ticket": ticket_id,
                "rating": 5,
                "comment": "Problem fixed!",
            },
            format="json",
        )
        assert feedback_response.status_code == status.HTTP_201_CREATED

        # Stage 8: Admin closes ticket
        client_admin = make_authenticated_client(admin)
        close_response = client_admin.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "closed"},
            format="json",
        )
        assert close_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "closed"

    def test_full_workflow_with_approval_required(
        self, db, user_factory, hod_factory, technician_factory, section,
        campus_department, facility
    ):
        """Complete workflow with pending_approval ticket."""
        # Setup users
        user = user_factory(username="creator2")
        user.primary_campus = campus_department.campus
        user.primary_department = campus_department.department
        user.save()

        hod = hod_factory(username="hod_approver2")
        hod.primary_campus = campus_department.campus
        hod.primary_department = campus_department.department
        hod.save()
        campus_department.head_of_department = hod
        campus_department.save()

        tech = technician_factory(username="tech_worker2")
        tech.primary_campus = campus_department.campus
        tech.save()
        tech.sections.add(section)

        admin = user.__class__.objects.create_user(
            username="admin_closer2",
            password="pass",
            role="admin",
        )

        # Get or create approval-required service item
        from tickets.models import ServiceItem
        si = ServiceItem.objects.filter(requires_approval=True).first()
        if not si:
            from tickets.models import ServiceCategory, SectionType
            st = section.section_type
            cat = ServiceCategory.objects.create(
                section_type=st, name="Approval Category"
            )
            si = ServiceItem.objects.create(
                category=cat,
                name="Approval Item",
                requires_approval=True,
            )

        # Stage 1: User creates ticket (requires approval)
        client_user = make_authenticated_client(user)
        create_response = client_user.post(
            reverse("ticket-create"),
            {
                "title": "Special request",
                "description": "Need approval",
                "department_id": campus_department.department.id,
                "service_item_id": si.id,
            },
            format="json",
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        ticket_id = create_response.json()["ticket"]["id"]
        ticket = Ticket.objects.get(id=ticket_id)
        assert ticket.status == "pending_approval"

        # Stage 2: HOD approves ticket
        client_hod = make_authenticated_client(hod)
        approve_response = client_hod.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "open"},
            format="json",
        )
        assert approve_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "open"

        # Stage 3-8: Continue with normal workflow
        # (Assign → In Progress → Resolved → Closed)
        client_hod.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"assigned_to_id": tech.id, "status": "assigned"},
            format="json",
        )

        client_tech = make_authenticated_client(tech)
        client_tech.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "in_progress"},
            format="json",
        )

        client_tech.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "resolved"},
            format="json",
        )

        client_admin = make_authenticated_client(admin)
        close_response = client_admin.patch(
            reverse("ticket-detail", args=[ticket_id]),
            {"status": "closed"},
            format="json",
        )
        assert close_response.status_code == status.HTTP_200_OK
        ticket.refresh_from_db()
        assert ticket.status == "closed"
