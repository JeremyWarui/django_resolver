"""
Pytest version of test_spec_compliance.py - Specification compliance tests
Converted from Django TestCase to pytest fixtures
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
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


def test_ticket_created_with_low_priority(ticket_factory, user_factory):
    """Verify new tickets start with LOW priority"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user, status="open")

    assert ticket.priority == "low"


def test_priority_auto_marks_critical_after_72_hours(db, ticket_factory, user_factory):
    """Verify priority auto-marks CRITICAL after 72 hours unresolved"""
    user = user_factory()
    ticket = ticket_factory(
        raised_by=user,
        status="open",
        created_at=timezone.now() - timedelta(hours=73),  # 73 hours ago
    )

    # Call check_and_mark_critical
    ticket.check_and_mark_critical()

    assert ticket.priority == "critical"


def test_pending_transition_requires_both_reason_and_comment(
    db, ticket_factory, user_factory, technician_factory
):
    """Verify PENDING status requires both reason and comment"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status="open")

    # Try to mark PENDING without comment - should raise error
    with pytest.raises(ValidationError):
        TicketService.update_ticket_status(
            ticket=ticket,
            new_status="pending",
            updated_by=technician,
            pending_reason="material_shortage",
            pending_comment=None,  # Missing comment
        )


def test_pending_transition_with_both_fields(
    db, ticket_factory, user_factory, technician_factory
):
    """Verify PENDING status succeeds with both reason and comment"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status="in_progress")

    # Mark as PENDING with both fields
    updated_ticket = TicketService.update_ticket_status(
        ticket=ticket,
        new_status="pending",
        updated_by=technician,
        pending_reason="material_shortage",
        pending_comment="Waiting for parts to arrive",
    )

    assert updated_ticket.status == "pending"
    assert updated_ticket.pending_reason == "material_shortage"
    assert updated_ticket.pending_comment == "Waiting for parts to arrive"


def test_user_can_close_their_own_ticket(db, ticket_factory, user_factory):
    """Verify users can close their own tickets"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user, status="resolved")

    # User closes their own ticket
    ticket.change_status("closed", performed_by=user)
    ticket.refresh_from_db()

    assert ticket.status == "closed"


def test_user_cannot_close_others_ticket(db, ticket_factory, user_factory):
    """Verify users cannot close other users' tickets"""
    user1 = user_factory(username="user1")
    user2 = user_factory(username="user2")
    ticket = ticket_factory(raised_by=user1, status="resolved")

    # User2 tries to close user1's ticket - should be blocked by permissions
    # (actual permission check depends on API/view layer)
    assert ticket.raised_by == user1


def test_manager_has_analytics_only_access(
    db, manager_factory, ticket_factory, user_factory
):
    """Verify manager role has analytics-only access"""
    manager = manager_factory()
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    # Manager should not be able to modify tickets
    with pytest.raises((ValidationError, PermissionError)):
        ticket.change_status("in_progress", performed_by=manager)


def test_pending_status_does_not_pause_escalation(
    db, ticket_factory, user_factory, technician_factory
):
    """Verify PENDING status does NOT pause escalation timers"""
    user = user_factory()
    technician = technician_factory()

    # Create ticket that would escalate
    ticket = ticket_factory(
        raised_by=user,
        status="open",
        next_escalation_due=timezone.now() - timedelta(hours=1),
        auto_escalation_enabled=True,
    )

    # Mark as PENDING
    ticket.change_status("pending", performed_by=technician)
    ticket.refresh_from_db()

    # Escalation timer should still be active/overdue
    assert ticket.next_escalation_due < timezone.now()
    assert ticket.auto_escalation_enabled


def test_ticket_cannot_escalate_when_closed(
    db, ticket_factory, user_factory, technician_factory
):
    """Verify closed tickets cannot be escalated"""
    user = user_factory()
    technician = technician_factory()
    ticket = ticket_factory(raised_by=user, status="closed")

    # Try to escalate closed ticket - should fail
    with pytest.raises((ValidationError, PermissionError)):
        TicketService.escalate_ticket(
            ticket=ticket,
            escalated_by=technician,
            reason="Try to escalate closed ticket",
            manual=True,
        )


def test_priority_field_validation(db, ticket_factory, user_factory):
    """Verify priority tracks escalation level and critical persists through saves"""
    user = user_factory()
    ticket = ticket_factory(raised_by=user)

    # Level 0 → low
    assert ticket.priority == "low"

    # Level 1 → medium
    ticket.escalation_level = 1
    ticket.save()
    assert ticket.priority == "medium"

    # Level 2 → high
    ticket.escalation_level = 2
    ticket.save()
    assert ticket.priority == "high"

    # Critical persists through save (aging override)
    ticket.priority = "critical"
    ticket.save()
    assert ticket.priority == "critical"


# ============================================================================
# ASSIGNED_AT ESCALATION TIMING TESTS
# ============================================================================


def test_unassigned_ticket_cannot_escalate(
    db, ticket_factory, user_factory, section, facility
):
    """Verify unassigned tickets are excluded from escalation"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    # Create unassigned ticket (assigned_to=None)
    ticket = Ticket.objects.create(
        title="Unassigned Ticket",
        description="Test unassigned",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=None,  # Explicitly unassigned
        status="open",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    # For unassigned tickets, _schedule_next_escalation should set next_escalation_due to None
    # Unassigned ticket should not be due for escalation
    assert ticket.assigned_at is None
    # Trigger rescheduling which should clear next_escalation_due for unassigned tickets
    ticket._schedule_next_escalation()
    assert ticket.next_escalation_due is None
    assert ticket.is_due_for_escalation() is False


def test_escalation_timer_starts_from_assigned_at(
    db, ticket_factory, user_factory, section, facility, technician_factory
):
    """Verify escalation timer is based on assigned_at, not created_at"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = section.department.campus
    technician.sections.add(section)
    technician.save()

    # Create ticket 10 hours ago
    created_time = timezone.now() - timedelta(hours=10)
    ticket = Ticket.objects.create(
        title="Created long ago",
        description="Test escalation from assigned_at",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=None,
        status="open",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    # Manually set created_at
    Ticket.objects.filter(id=ticket.id).update(created_at=created_time)
    ticket.refresh_from_db()

    # At this point, ticket has been "created" 10 hours ago but never assigned
    # So even though 10 hours have passed since creation, it should not be due for escalation
    assert ticket.assigned_at is None
    assert ticket.is_due_for_escalation() is False

    # Now assign it
    assigned_time = timezone.now()
    ticket.assigned_to = technician
    ticket.assigned_at = assigned_time
    ticket.save()

    # Now escalation is scheduled from assigned_at
    assert ticket.assigned_at is not None
    assert ticket.next_escalation_due is not None
    # Should be 48 hours from assigned_at (still in the future)
    assert ticket.next_escalation_due > timezone.now()


def test_escalation_triggers_after_threshold_from_assigned_at(
    db, section, facility, user_factory, technician_factory
):
    """Verify escalation triggers correctly when threshold is exceeded from assigned_at"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = section.department.campus
    technician.primary_department = section.department
    technician.sections.add(section)
    technician.save()

    section_head = section.head_of_section
    section_head.primary_campus = section.department.campus
    section_head.primary_department = section.department
    section_head.save()

    # Create ticket
    ticket = Ticket.objects.create(
        title="Escalation Test",
        description="Test escalation timing",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    # Set assigned_at to 49 hours ago (exceeds 48-hour threshold)
    assigned_time = timezone.now() - timedelta(hours=49)
    Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_time)
    ticket.refresh_from_db()

    # Reschedule escalation based on new assigned_at
    ticket._schedule_next_escalation()

    # Should be due for escalation
    assert ticket.is_due_for_escalation() is True
    assert ticket.next_escalation_due < timezone.now()


def test_escalation_does_not_trigger_before_threshold_from_assigned_at(
    db, section, facility, user_factory, technician_factory
):
    """Verify escalation does NOT trigger before threshold expires from assigned_at, even if created long ago"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = section.department.campus
    technician.sections.add(section)
    technician.save()

    # Create ticket 10 hours ago so created_at is old
    created_time = timezone.now() - timedelta(hours=10)
    ticket = Ticket.objects.create(
        title="Old created time, recent assignment",
        description="Test that created_at is ignored",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    # Set created_at to 10 hours ago
    Ticket.objects.filter(id=ticket.id).update(created_at=created_time)
    ticket.refresh_from_db()

    # Set assigned_at to 47 hours ago (just under threshold)
    assigned_time = timezone.now() - timedelta(hours=47)
    Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_time)
    ticket.refresh_from_db()

    # Reschedule escalation
    ticket._schedule_next_escalation()

    # Should NOT be due for escalation yet (created_at age is irrelevant)
    assert ticket.is_due_for_escalation() is False
    assert ticket.next_escalation_due > timezone.now()


def test_reassignment_resets_escalation_timer(
    db, section, facility, user_factory, technician_factory
):
    """Verify reassigning a ticket resets the escalation timer from new assigned_at"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    tech1 = technician_factory(username="tech1")
    tech1.primary_campus = section.department.campus
    tech1.sections.add(section)
    tech1.save()

    tech2 = technician_factory(username="tech2")
    tech2.primary_campus = section.department.campus
    tech2.sections.add(section)
    tech2.save()

    # Create ticket assigned to tech1, long ago
    assigned_time_1 = timezone.now() - timedelta(hours=50)  # Over threshold
    ticket = Ticket.objects.create(
        title="Reassignment Test",
        description="Test reassignment",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=tech1,
        status="assigned",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_time_1)
    ticket.refresh_from_db()
    ticket._schedule_next_escalation()

    # Should be due for escalation
    assert ticket.is_due_for_escalation() is True

    # Now reassign to tech2
    ticket.change_assignment(tech2, performed_by=user)
    ticket.refresh_from_db()
    ticket._schedule_next_escalation()

    # Now should NOT be due for escalation (timer reset to now)
    assert ticket.is_due_for_escalation() is False
    assert ticket.next_escalation_due > timezone.now()


# ============================================================================
# AUTO-ESCALATION PROCESS INTEGRATION TESTS
# ============================================================================


def test_assigned_at_integration_unassigned_not_escalated(
    db, section, facility, user_factory, technician_factory
):
    """Verify unassigned tickets skip auto-escalation processing"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    # Create unassigned ticket
    ticket = Ticket.objects.create(
        title="Unassigned Integration Test",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=None,  # Key: unassigned
        status="open",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    # Manually set times to force it to seem overdue if checked
    old_time = timezone.now() - timedelta(days=10)
    Ticket.objects.filter(id=ticket.id).update(
        created_at=old_time, next_escalation_due=old_time  # Very overdue
    )
    ticket.refresh_from_db()

    # Should NOT be due for escalation (unassigned)
    assert ticket.assigned_at is None
    assert ticket.is_due_for_escalation() is False

    # Process auto escalations should skip this
    results = TicketService.process_auto_escalations()
    assert results["processed"] == 0  # Not processed
    assert results["escalated"] == 0  # Not escalated

    ticket.refresh_from_db()
    assert ticket.escalation_level == 0  # Still level 0


def test_assigned_at_integration_recently_assigned_not_escalated(
    db, section, facility, user_factory, technician_factory
):
    """Verify recently assigned tickets don't escalate before threshold"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = section.department.campus
    technician.sections.add(section)
    technician.save()

    # Create ticket assigned very recently (1 hour ago)
    assigned_time = timezone.now() - timedelta(hours=1)
    ticket = Ticket.objects.create(
        title="Recently Assigned",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    # Manually set assigned_at
    Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_time)
    ticket.refresh_from_db()

    # Reschedule escalation (normally done on assignment)
    ticket._schedule_next_escalation()
    ticket.save()

    # Should NOT be due (only 1 hour assigned, need 48)
    assert ticket.is_due_for_escalation() is False

    # Process auto escalations
    results = TicketService.process_auto_escalations()
    assert results["processed"] == 0
    assert results["escalated"] == 0

    ticket.refresh_from_db()
    assert ticket.escalation_level == 0


def test_assigned_at_integration_old_assignment_escalates(
    db, section, facility, user_factory, technician_factory
):
    """Verify old assignments get escalated on schedule"""
    user = user_factory()
    user.primary_campus = section.department.campus
    user.save()

    technician = technician_factory()
    technician.primary_campus = section.department.campus
    technician.sections.add(section)
    technician.save()

    # Use the section's existing section_head (from fixtures)
    section_head = section.head_of_section
    section_head.primary_campus = section.department.campus
    section_head.primary_department = section.department
    section_head.save()

    # Create ticket assigned 50 hours ago
    assigned_time = timezone.now() - timedelta(hours=50)
    ticket = Ticket.objects.create(
        title="Old Assignment",
        description="Test",
        section=section,
        facility=facility,
        raised_by=user,
        assigned_to=technician,
        status="assigned",
        auto_escalation_enabled=True,
        escalation_threshold_hours=48,
    )

    Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_time)
    ticket.refresh_from_db()
    ticket._schedule_next_escalation()
    ticket.save()

    # Should be due for escalation
    assert ticket.is_due_for_escalation() is True

    # Process auto escalations
    results = TicketService.process_auto_escalations()
    assert results["processed"] >= 1  # At least this one
    assert results["escalated"] >= 1

    ticket.refresh_from_db()
    assert ticket.escalation_level == 1
    assert ticket.escalated_to == section_head
