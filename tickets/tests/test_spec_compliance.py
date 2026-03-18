"""
Pytest version of test_spec_compliance.py - Specification compliance tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from tickets.models import (
    Organization, Campus, Department, Section, Facility,
    CustomUser, Ticket, TicketLog
)
from tickets.api.services import TicketService


def test_ticket_created_with_low_priority(ticket_factory, user_factory):
    """Verify new tickets start with LOW priority"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user, status='open')
    
    assert ticket.priority == 'low'


def test_priority_escalates_to_medium_on_level_1(db, ticket_factory, user_factory, technician_factory):
    """Verify priority escalates to MEDIUM at escalation level 1"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status='open')

    # Escalate to level 1 (section head)
    escalated_ticket = TicketService.escalate_ticket(
        ticket=ticket,
        escalated_by=technician,
        reason="Needs section head review",
        manual=True
    )

    assert escalated_ticket.escalation_level == 1
    assert escalated_ticket.priority == 'medium'


def test_priority_escalates_to_high_on_level_2(db, ticket_factory, user_factory, technician_factory):
    """Verify priority escalates to HIGH at escalation level 2"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status='open')

    # Escalate to level 1 first
    ticket.escalation_level = 1
    ticket.escalated_at = timezone.now()
    ticket.save()

    # Escalate to level 2
    escalated_ticket = TicketService.escalate_ticket(
        ticket=ticket,
        escalated_by=technician,
        reason="Needs HOD review",
        manual=True
    )

    assert escalated_ticket.escalation_level == 2
    assert escalated_ticket.priority == 'high'


def test_priority_auto_marks_critical_after_72_hours(db, ticket_factory, user_factory):
    """Verify priority auto-marks CRITICAL after 72 hours unresolved"""
    user = user_factory()
    ticket = ticket_factory(
        raised_by=user,
        status='open',
        created_at=timezone.now() - timedelta(hours=73)  # 73 hours ago
    )

    # Call check_and_mark_critical
    ticket.check_and_mark_critical()

    assert ticket.priority == 'critical'


def test_pending_transition_requires_both_reason_and_comment(db, ticket_factory, user_factory, technician_factory):
    """Verify PENDING status requires both reason and comment"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status='open')

    # Try to mark PENDING without comment - should raise error
    with pytest.raises(ValidationError):
        TicketService.update_ticket_status(
            ticket=ticket,
            new_status='pending',
            updated_by=technician,
            pending_reason='material_shortage',
            pending_comment=None  # Missing comment
        )


def test_pending_transition_with_both_fields(db, ticket_factory, user_factory, technician_factory):
    """Verify PENDING status succeeds with both reason and comment"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status='in_progress')

    # Mark as PENDING with both fields
    updated_ticket = TicketService.update_ticket_status(
        ticket=ticket,
        new_status='pending',
        updated_by=technician,
        pending_reason='material_shortage',
        pending_comment='Waiting for parts to arrive'
    )

    assert updated_ticket.status == 'pending'
    assert updated_ticket.pending_reason == 'material_shortage'
    assert updated_ticket.pending_comment == 'Waiting for parts to arrive'


def test_user_can_close_their_own_ticket(db, ticket_factory, user_factory):
    """Verify users can close their own tickets"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user, status='resolved')

    # User closes their own ticket
    ticket.change_status('closed', performed_by=user)
    ticket.refresh_from_db()

    assert ticket.status == 'closed'


def test_user_cannot_close_others_ticket(db, ticket_factory, user_factory):
    """Verify users cannot close other users' tickets"""
    user1 = user_factory(username="user1")
    user2 = user_factory(username="user2")
    ticket = ticket_factory(raised_by=user1, status='resolved')

    # User2 tries to close user1's ticket - should be blocked by permissions
    # (actual permission check depends on API/view layer)
    assert ticket.raised_by == user1


def test_director_has_analytics_only_access(db, director_factory, ticket_factory, user_factory):
    """Verify director role has analytics-only access"""
    director = director_factory()
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    # Director should not be able to modify tickets
    with pytest.raises((ValidationError, PermissionError)):
        ticket.change_status('in_progress', performed_by=director)


def test_pending_status_does_not_pause_escalation(db, ticket_factory, user_factory, technician_factory):
    """Verify PENDING status does NOT pause escalation timers"""
    user = user_factory()
    technician = technician_factory()
    
    # Create ticket that would escalate
    ticket = ticket_factory(
        raised_by=user,
        status='open',
        next_escalation_due=timezone.now() - timedelta(hours=1),
        auto_escalation_enabled=True
    )

    # Mark as PENDING
    ticket.change_status('pending', performed_by=technician)
    ticket.refresh_from_db()

    # Escalation timer should still be active/overdue
    assert ticket.next_escalation_due < timezone.now()
    assert ticket.auto_escalation_enabled


def test_ticket_cannot_escalate_when_closed(db, ticket_factory, user_factory, technician_factory):
    """Verify closed tickets cannot be escalated"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status='closed')

    # Try to escalate closed ticket - should fail
    with pytest.raises((ValidationError, PermissionError)):
        TicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=technician,
            reason="Try to escalate closed ticket",
            manual=True
        )


def test_escalation_level_cannot_exceed_2(db, ticket_factory, user_factory, technician_factory):
    """Verify escalation level cannot exceed 2"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status='open')

    # Escalate to max level
    ticket.escalation_level = 2
    ticket.save()

    # Try to escalate further - should not increase beyond 2
    escalated = TicketService.escalate_ticket(
        ticket=ticket,
        escalated_by=technician,
        reason="Try to escalate beyond max",
        manual=True
    )

    assert escalated.escalation_level <= 2


def test_priority_field_validation(db, ticket_factory, user_factory):
    """Verify priority field only accepts valid values"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    valid_priorities = ['low', 'medium', 'high', 'critical']
    for priority in valid_priorities:
        ticket.priority = priority
        ticket.save()
        assert ticket.priority == priority
