"""
Pytest-based tests for Django Resolver models.

Converted from Django TestCase to pytest with fixtures.
Tests cover model creation, relationships, and constraints.
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from tickets.models import (
    CustomUser,
    Section,
    Facility,
    Ticket,
    Comment,
    Feedback,
    TicketLog,
    Organization,
    Campus,
    Department,
)

# ============================================================================
# USER TESTS
# ============================================================================


def test_user_creation(user_factory):
    """Test user creation with valid data"""
    user = user_factory(
        username="testuser", email="testuser@example.com", password="testpass"
    )
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.check_password("testpass")


def test_technician_creation(technician_factory):
    """Test technician user creation"""
    technician = technician_factory(
        username="techuser", email="techuser@example.com", password="techpass"
    )
    assert technician.username == "techuser"
    assert technician.email == "techuser@example.com"
    assert technician.role == "technician"
    assert technician.check_password("techpass")


def test_user_role_validation(db):
    """Test that user roles are validated properly"""
    # Test valid roles
    user = CustomUser.objects.create_user(
        username="user1", email="user1@example.com", password="pass123", role="user"
    )
    assert user.role == "user"

    admin = CustomUser.objects.create_user(
        username="admin1", email="admin1@example.com", password="pass123", role="admin"
    )
    assert admin.role == "admin"

    # Test default role
    default_user = CustomUser.objects.create_user(
        username="default", email="default@example.com", password="pass123"
    )
    assert default_user.role == "user"  # Default should be 'user'


# ============================================================================
# SECTION TESTS
# ============================================================================


def test_section_creation(section):
    """Test section creation"""
    assert section.name == "Network Section"
    assert section.code == "NETWORK"
    assert section.department is not None


def test_section_technician_relationship(db, user_factory, technician_factory):
    """Test M2M relationship between sections and technicians"""
    # Create departments and sections
    org = Organization.objects.create(
        name="Test Org", code="TEST", organization_type="corporate"
    )
    campus = Campus.objects.create(name="Main", code="MAIN", organization=org)
    dept1 = Department.objects.create(name="IT", code="IT", campus=campus)
    dept2 = Department.objects.create(name="Facilities", code="FAC", campus=campus)

    plumbing = Section.objects.create(name="Plumbing", code="PLUMB", department=dept2)
    electrical = Section.objects.create(
        name="Electrical", code="ELEC", department=dept2
    )
    it_section = Section.objects.create(name="IT Section", code="IT", department=dept1)

    # Create technicians
    tech1 = technician_factory(username="plumber")
    tech2 = technician_factory(username="electrician")
    tech3 = technician_factory(username="it_tech")

    # Set relationships
    tech1.sections.add(plumbing)
    tech2.sections.add(electrical)
    tech2.sections.add(it_section)  # Electrician also in IT
    tech3.sections.add(it_section)

    # Test relationships from technician to section
    assert tech1.sections.count() == 1
    assert tech1.sections.first() == plumbing

    assert tech2.sections.count() == 2
    assert it_section in tech2.sections.all()
    assert electrical in tech2.sections.all()

    # Test relationships from section to technician
    assert plumbing.technicians.count() == 1
    assert plumbing.technicians.first() == tech1

    assert it_section.technicians.count() == 2
    assert tech2 in it_section.technicians.all()
    assert tech3 in it_section.technicians.all()


# ============================================================================
# FACILITY TESTS
# ============================================================================


def test_facility_creation(facility):
    """Test facility creation"""
    assert facility.name == "Main Building"
    assert facility.type == "building"
    assert facility.status == "active"
    assert facility.location == "123 Main St"


# ============================================================================
# TICKET TESTS
# ============================================================================


def test_ticket_creation(
    ticket_factory, user_factory, technician_factory, section, facility
):
    """Test ticket creation with all relationships"""
    user = user_factory()
    technician = technician_factory()

    ticket = ticket_factory(
        title="Faulty Printer",
        description="The printer in the IT section is not working.",
        status="assigned",
        raised_by=user,
        assigned_to=technician,
        section=section,
        facility=facility,
    )

    assert ticket.title == "Faulty Printer"
    assert ticket.description == "The printer in the IT section is not working."
    assert ticket.section == section
    assert ticket.facility == facility
    assert ticket.raised_by == user
    assert ticket.assigned_to == technician
    assert ticket.status == "assigned"


def test_ticket_status_choices(db, ticket_factory, user_factory):
    """Test ticket status choices and default"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    # Test default status
    assert ticket.status == "open"

    # Test valid status transitions
    valid_statuses = [
        "open",
        "assigned",
        "in_progress",
        "pending",
        "resolved",
        "closed",
    ]

    for status in valid_statuses:
        ticket.change_status(status, performed_by=user)
        ticket.refresh_from_db()
        assert ticket.status == status


def test_ticket_auto_numbering(db, ticket_factory, user_factory, section, facility):
    """Test automatic ticket number generation with correct format"""
    user = user_factory()

    # Create first ticket
    ticket1 = ticket_factory(raised_by=user)

    # Check format of first ticket (organizational format: CAMPUS-DEPT-XXXXX)
    assert ticket1.ticket_no.startswith(
        f"{section.department.campus.code}-{section.department.code}-"
    )
    parts = ticket1.ticket_no.split("-")
    assert len(parts) == 3
    assert len(parts[2]) == 5  # 5-digit sequence number

    # Create more tickets and check sequential numbering
    tickets = [ticket1]
    for i in range(5):
        ticket = ticket_factory(
            title=f"Test Ticket {i}",
            description=f"Auto-number test ticket {i}",
            raised_by=user,
        )
        tickets.append(ticket)

    # Check all have same campus-dept prefix
    for ticket in tickets:
        assert ticket.ticket_no.startswith(
            f"{section.department.campus.code}-{section.department.code}-"
        )


def test_ticket_creation_and_auto_increment_ticket_no(db, ticket_factory, user_factory):
    """Test ticket creation and auto-increment ticket_no"""
    user = user_factory()

    ticket1 = ticket_factory(raised_by=user)
    initial_ticket_no = ticket1.ticket_no

    ticket2 = ticket_factory(title="Faulty Monitor", raised_by=user)

    # Extract sequence numbers (last part after splitting by '-')
    prev_number = int(initial_ticket_no.split("-")[-1])
    new_number = int(ticket2.ticket_no.split("-")[-1])

    assert ticket2.ticket_no != initial_ticket_no
    # Check organizational format (CAMPUS-DEPT-XXXXX)
    assert ticket2.ticket_no.count("-") == 2
    assert new_number > prev_number


def test_ticket_status_after_assignment(
    db, user_factory, technician_factory, ticket_factory
):
    """Test ticket status after assignment"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, assigned_to=None, status="open")

    # Change assignment using model helper
    ticket.change_assignment(technician, performed_by=user)
    ticket.refresh_from_db()

    assert ticket.assigned_to == technician
    assert ticket.status == "assigned"


# ============================================================================
# COMMENT TESTS
# ============================================================================


def test_comment_creation(db, comment_factory, ticket_factory, user_factory):
    """Test comment creation on a ticket"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    comment = comment_factory(
        text="This is a test comment.", ticket=ticket, author=user
    )

    assert comment.ticket == ticket
    assert comment.text == "This is a test comment."
    assert comment.author == user
    assert comment.created_at is not None


# ============================================================================
# FEEDBACK TESTS
# ============================================================================


def test_feedback_creation(db, feedback_factory, ticket_factory, user_factory):
    """Test feedback creation on a ticket"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    feedback = feedback_factory(
        rating=5, comment="Great service", ticket=ticket, rated_by=user
    )

    assert feedback.ticket == ticket
    assert feedback.rating == 5
    assert feedback.comment == "Great service"
    assert feedback.rated_by == user
    assert feedback.created_at is not None


def test_feedback_one_per_ticket_constraint(
    db, feedback_factory, ticket_factory, user_factory
):
    """Test that feedback integrity constraints are enforced"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    # Create first feedback
    feedback_factory(rating=4, comment="Good service", ticket=ticket, rated_by=user)

    # Try to create another feedback for the same ticket - should raise IntegrityError
    with pytest.raises(IntegrityError):
        feedback_factory(
            rating=5, comment="Great service", ticket=ticket, rated_by=user
        )


# ============================================================================
# TICKET LOG TESTS
# ============================================================================


def test_ticket_log_creation(db, ticket_factory, user_factory):
    """Test automatic creation of ticket logs"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    # Create a log entry
    log_entry = TicketLog.objects.create(
        ticket=ticket, performed_by=user, action="Test action"
    )

    # Verify the log was created correctly
    assert log_entry.ticket == ticket
    assert log_entry.performed_by == user
    assert log_entry.action == "Test action"
    assert log_entry.timestamp is not None


def test_ticket_log_on_status_change(db, ticket_factory, user_factory):
    """Test that ticket logs are created when status changes"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    initial_logs = TicketLog.objects.filter(ticket=ticket).count()

    # Change status
    ticket.change_status("in_progress", performed_by=user)

    # Check that log was created
    final_logs = TicketLog.objects.filter(ticket=ticket).count()
    assert final_logs > initial_logs


# ============================================================================
# CHANGE TESTS
# ============================================================================


def test_ticket_change_assignment_creates_log(
    db, ticket_factory, user_factory, technician_factory
):
    """Test that assigning a ticket creates a log entry"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, assigned_to=None)

    logs_before = TicketLog.objects.filter(ticket=ticket).count()

    ticket.change_assignment(technician, performed_by=user)

    logs_after = TicketLog.objects.filter(ticket=ticket).count()
    assert logs_after > logs_before


def test_change_status_sets_resolved_at_and_logs(db, ticket_factory, user_factory):
    """Test that changing status to resolved sets resolved_at timestamp"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user, status="in_progress")

    assert ticket.resolved_at is None

    # Change to resolved
    ticket.change_status("resolved", performed_by=user)
    ticket.refresh_from_db()

    assert ticket.status == "resolved"
    assert ticket.resolved_at is not None


@pytest.mark.slow
def test_bulk_ticket_creation(db, user_factory):
    """Test creating many tickets (slow test)"""
    user = user_factory()
    org = Organization.objects.create(
        name="Test", code="TEST", organization_type="corporate"
    )
    campus = Campus.objects.create(name="Main", code="MAIN", organization=org)
    dept = Department.objects.create(name="IT", code="IT", campus=campus)
    section = Section.objects.create(name="IT Section", code="IT", department=dept)
    facility = Facility.objects.create(
        name="Building",
        type="building",
        status="active",
        location="Main",
        campus=campus,
        department=dept,
    )

    # Create tickets using save() instead of bulk_create to ensure ticket_no generation
    created_tickets = []
    for i in range(100):
        ticket = Ticket(
            title=f"Ticket {i}",
            description=f"Description {i}",
            section=section,
            facility=facility,
            raised_by=user,
        )
        ticket.save()
        created_tickets.append(ticket)

    assert len(created_tickets) == 100
    assert Ticket.objects.filter(raised_by=user).count() == 100
    # Verify all tickets have proper organizational ticket numbers
    for ticket in created_tickets:
        assert ticket.ticket_no.startswith(f"{campus.code}-{dept.code}-")
