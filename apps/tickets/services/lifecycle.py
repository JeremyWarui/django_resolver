from datetime import timedelta

from django.utils import timezone

from apps.sla.services.due_dates import compute_due_dates
from apps.tickets.models import TicketLog
from apps.realtime.ws_utils import (
    emit_ticket_assigned,
    emit_ticket_status_changed,
    emit_ticket_resolved,
)

# Reopen (resolved/closed → open) restarts the lifecycle: `open` is the
# unassigned state, so reopen clears the assignee and the SLA clock restarts
# (QA B2f). Keep the frontend mirror in sync:
# client/src/features/technician/StatusUpdateModal.tsx (NEXT_STATUSES).
ALLOWED = {
    "open": {"assigned"},
    "assigned": {"in_progress"},
    "in_progress": {"pending", "resolved"},
    "pending": {"in_progress", "resolved"},
    "resolved": {"closed", "open"},
    "closed": {"open"},
}


class TransitionError(Exception):
    pass


def transition_status(ticket, new_status, actor, reason=""):
    """Validate and apply a status transition, handling SLA pause/resume and logging."""

    if new_status not in ALLOWED.get(ticket.status, set()):
        raise TransitionError(
            f"Cannot transition from '{ticket.status}' to '{new_status}'."
        )

    if new_status == "pending" and not reason.strip():
        raise TransitionError("A reason is required when moving to pending.")

    old_status = ticket.status
    now = timezone.now()
    is_reopen = old_status in ("resolved", "closed") and new_status == "open"

    # SLA pause/resume
    if new_status == "pending":
        ticket.paused_at = now
    elif old_status == "pending" and new_status != "pending":
        if ticket.paused_at:
            pause = now - ticket.paused_at
            ticket.accumulated_pause += pause
            if ticket.response_due_at:
                ticket.response_due_at += pause
            if ticket.resolution_due_at:
                ticket.resolution_due_at += pause
            ticket.paused_at = None

    # Timestamps
    if new_status == "resolved":
        ticket.resolved_at = now
    elif new_status == "closed":
        ticket.closed_at = now

    if is_reopen:
        # Restart the lifecycle: unassigned, fresh SLA window, no stale
        # resolution timestamps (they'd corrupt is_breaching and resolved-time
        # analytics on a live ticket). Breach history stays in TicketLog.
        ticket.assigned_to = None
        ticket.response_due_at, ticket.resolution_due_at = compute_due_dates(
            ticket.priority, now
        )
        ticket.paused_at = None
        ticket.accumulated_pause = timedelta(0)
        ticket.resolved_at = None
        ticket.closed_at = None

    ticket.status = new_status
    ticket.save(
        update_fields=[
            "status",
            "assigned_to",
            "paused_at",
            "accumulated_pause",
            "response_due_at",
            "resolution_due_at",
            "resolved_at",
            "closed_at",
            "updated_at",
        ]
    )

    # Determine event type
    if new_status == "resolved":
        event_type = "resolved"
    elif new_status == "closed":
        event_type = "closed"
    elif is_reopen:
        event_type = "reopened"
    else:
        event_type = "status_changed"

    TicketLog.objects.create(
        ticket=ticket,
        actor=actor,
        event_type=event_type,
        from_value=old_status,
        to_value=new_status,
        reason=reason,
    )

    if new_status == "resolved":
        emit_ticket_resolved(ticket)
    else:
        emit_ticket_status_changed(ticket, old_status)

    return ticket


def claim_ticket(ticket, technician):
    """Self-assign an unassigned open ticket to `technician` (QA B2a).

    Caller must hold the row lock (select_for_update) inside an atomic block —
    the guard here is the post-lock re-check that makes a double claim lose.
    Writes the `assigned` TicketLog with the technician as actor, then drives
    open → assigned → in_progress through transition_status so both status
    logs and the existing WS events fire.
    """
    if ticket.status != "open" or ticket.assigned_to_id is not None:
        raise TransitionError("Ticket has already been claimed or assigned.")

    ticket.assigned_to = technician
    ticket.save(update_fields=["assigned_to", "updated_at"])
    TicketLog.objects.create(
        ticket=ticket,
        actor=technician,
        event_type="assigned",
        from_value="",
        to_value=technician.get_full_name() or technician.username,
    )
    emit_ticket_assigned(ticket, previous_assignee=None)

    transition_status(ticket, "assigned", technician)
    transition_status(ticket, "in_progress", technician)
    return ticket
