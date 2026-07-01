from django.utils import timezone

from apps.tickets.models import TicketLog
from apps.realtime.ws_utils import emit_ticket_status_changed, emit_ticket_resolved

ALLOWED = {
    "open": {"assigned"},
    "assigned": {"in_progress"},
    "in_progress": {"pending", "resolved"},
    "pending": {"in_progress"},
    "resolved": {"closed", "in_progress"},
    "closed": {"in_progress"},
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

    ticket.status = new_status
    ticket.save(
        update_fields=[
            "status",
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
    elif old_status in ("resolved", "closed") and new_status == "in_progress":
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
