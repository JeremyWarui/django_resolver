"""
Pytest version of test_models.py - Model creation and validation tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from tickets.models import (
    CustomUser, Section, Facility, Ticket, Comment, Feedback, TicketLog
)

User = get_user_model()


# ============================================================================
# USER TESTS
# ============================================================================

def test_user_creation(user_factory):
    """Test user creation"""
    user = user_factory(username="testuser", email="testuser@example.com", password="testpass")
    assert user.username == "testuser"
    assert user.email == "testuser@example.com"
    assert user.check_password("testpass")


def test_technician_creation(technician_factory):
    """Test technician creation"""
    technician = technician_factory(
        username="techuser",
        email="techuser@example.com",
        password="techpass"
    )
    assert technician.username == "techuser"
    assert technician.email == "techuser@example.com"
    assert technician.role == "technician"
    assert technician.check_password("techpass")


def test_user_role_validation(db):
    """Test that user roles are validated properly"""
    # Test valid roles
    user = CustomUser(username="user1", email="user1@example.com", role="user")
    user.set_password("pass123")
    user.save()
    assert user.role == "user"

    admin = CustomUser(username="admin1", email="admin1@example.com", role="admin")
    admin.set_password("pass123")
    admin.save()
    assert admin.role == "admin"

    # Test default role
    default_user = CustomUser(username="default", email="default@example.com")
    default_user.set_password("pass123")
    default_user.save()
    assert default_user.role == "user"  # Default should be 'user'


# ============================================================================
# SECTION TESTS
# ============================================================================

def test_section_creation(db):
    """Test section creation"""
    section = Section.objects.create(
        name="IT",
        description="Information Technology"
    )
    assert section.name == "IT"
    assert section.description == "Information Technology"


def test_section_technician_relationship(db, technician_factory):
    """Test M2M relationship between sections and technicians"""
    # Create sections
    plumbing = Section.objects.create(name="Plumbing", description="Water systems")
    electrical = Section.objects.create(name="Electrical", description="Electrical systems")
    it_section = Section.objects.create(name="IT", description="IT systems")

    # Create technicians
    tech1 = technician_factory(username="plumber")
    tech2 = technician_factory(username="electrician")
    tech3 = technician_factory(username="it_tech")

    # Set relationships
    tech1.sections.add(plumbing)
    tech2.sections.add(electrical)
    tech3.sections.add(it_section)
    tech2.sections.add(it_section)  # Electrician also in IT

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
    assert tech3 in it_section.technicians.all()
    assert tech2 in it_section.technicians.all()


# ============================================================================
# FACILITY TESTS
# ============================================================================

def test_facility_creation(db):
    """Test facility creation"""
    facility = Facility.objects.create(
        name="Main Building",
        type="building",
        status="active",
        location="123 Main St"
    )
    assert facility.name == "Main Building"
    assert facility.type == "building"
    assert facility.status == "active"
    assert facility.location == "123 Main St"


# ============================================================================
# TICKET TESTS
# ============================================================================

def test_ticket_creation(ticket_factory, user_factory, technician_factory):
    """Test ticket creation"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(
        title="Faulty Printer",
        description="The printer in the IT section is not working.",
        raised_by=user,
        assigned_to=technician,
        status="assigned"
    )
    assert ticket.title == "Faulty Printer"
    assert ticket.description == "The printer in the IT section is not working."
    assert ticket.raised_by == user
    assert ticket.assigned_to == technician
    assert ticket.status == "assigned"


def test_ticket_auto_numbering(db, ticket_factory, user_factory):
    """Test that ticket numbers are automatically generated with correct format"""
    user = user_factory()
    
    # Check format of first ticket
    ticket1 = ticket_factory(raised_by=user)
    assert ticket1.ticket_no.startswith("TKT-")
    assert len(ticket1.ticket_no) == 10

    # Create more tickets and check sequential numbering
    tickets = [ticket1]
    for i in range(5):
        ticket = ticket_factory(
            title=f"Test Ticket {i}",
            description=f"Auto-number test ticket {i}",
            raised_by=user
        )
        tickets.append(ticket)

    # Check that numbers are sequential
    for i in range(1, len(tickets)):
        prev_num = int(tickets[i - 1].ticket_no.split("-")[1])
        curr_num = int(tickets[i].ticket_no.split("-")[1])
        assert curr_num == prev_num + 1


def test_ticket_creation_and_auto_increment_ticket_no(db, ticket_factory, user_factory):
    """Test ticket creation and auto increment ticket_no"""
    user = user_factory()
    
    ticket1 = ticket_factory(raised_by=user)
    initial_ticket_no = ticket1.ticket_no
    
    ticket2 = ticket_factory(
        title="Faulty Monitor",
        description="The monitor is not working.",
        raised_by=user
    )
    
    prev_number = int(initial_ticket_no.split("-")[-1])
    new_number = int(ticket2.ticket_no.split("-")[-1])
    
    assert ticket2.ticket_no != initial_ticket_no
    assert ticket2.ticket_no.startswith("TKT-")
    assert len(ticket2.ticket_no) == 10
    assert new_number == prev_number + 1


def test_ticket_status_choices(db, ticket_factory, user_factory):
    """Test ticket status choices and default"""
    user = user_factory()
    
    # Test default status
    ticket = ticket_factory(raised_by=user)
    assert ticket.status == "open"  # Default should be 'open'

    # Test valid statuses
    valid_statuses = ["open", "assigned", "in_progress", "pending", "resolved", "closed"]

    for status in valid_statuses:
        ticket.change_status(status, performed_by=user)
        ticket.refresh_from_db()
        assert ticket.status == status


def test_ticket_status_after_assignment(db, ticket_factory, user_factory, technician_factory):
    """Test ticket status after assignment"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, assigned_to=None, status="open")
    
    ticket.change_assignment(technician, performed_by=user)
    ticket.refresh_from_db()
    
    assert ticket.assigned_to == technician
    assert ticket.status == "assigned"


# ============================================================================
# FEEDBACK TESTS
# ============================================================================

def test_feedback_one_per_ticket_constraint(db, feedback_factory, ticket_factory, user_factory):
    """Test that only one feedback can be attached to a ticket"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)
    
    # Create first feedback
    feedback_factory(rating=4, comment="Good service", ticket=ticket, submitted_by=user)
    
    # Try to create another feedback for the same ticket - should raise IntegrityError
    with pytest.raises(IntegrityError):
        feedback_factory(rating=5, comment="Great service", ticket=ticket, submitted_by=user)


# ============================================================================
# TICKET LOG TESTS
# ============================================================================

def test_ticket_log_creation(db, ticket_factory, user_factory):
    """Test automatic creation of ticket logs"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)
    
    # Create a log entry
    log_entry = TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action="Test action"
    )

    # Verify the log was created correctly
    assert log_entry.ticket == ticket
    assert log_entry.performed_by == user
    assert log_entry.action == "Test action"
    assert log_entry.timestamp is not None


def test_change_status_sets_resolved_at_and_logs(db, ticket_factory, user_factory, technician_factory):
    """Test that change_status sets resolved_at and creates log"""
    user = user_factory()
    technician = technician_factory()
    
    ticket = ticket_factory(raised_by=user, status="in_progress")
    assert ticket.resolved_at is None

    # Change to resolved
    ticket.change_status("resolved", performed_by=technician)
    ticket.refresh_from_db()
    
    assert ticket.resolved_at is not None

    latest_log = TicketLog.objects.filter(ticket=ticket).order_by("-timestamp").first()
    assert latest_log is not None
    assert latest_log.performed_by == technician
    assert "Status changed from" in latest_log.action

    # Change back to open
    ticket.change_status("open", performed_by=user)
    ticket.refresh_from_db()
    
    assert ticket.resolved_at is None
    latest_log = TicketLog.objects.filter(ticket=ticket).order_by("-timestamp").first()
    assert latest_log.performed_by == user


def test_change_assignment_creates_log_and_updates_assigned_to(db, ticket_factory, user_factory, technician_factory):
    """Test that change_assignment updates assigned_to and creates log"""
    user = user_factory()
    technician = technician_factory()
    
    ticket = ticket_factory(raised_by=user, assigned_to=None, status="open")
    
    logs_before = TicketLog.objects.filter(ticket=ticket).count()
    
    ticket.change_assignment(technician, performed_by=user)
    ticket.refresh_from_db()
    
    assert ticket.assigned_to == technician
    
    logs_after = TicketLog.objects.filter(ticket=ticket).count()
    assert logs_after > logs_before
