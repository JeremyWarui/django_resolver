from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied

from .models import Ticket, TicketLog

# ---------------------
# TICKET SERVICES
# ---------------------

def create_ticket(serializer, user):
    """Logic for creating a ticket."""
    ticket = serializer.save(raised_by=user)

    TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action=f"Ticket created by {user.username}"
    )
    return ticket


def update_ticket(serializer, user):
    """Logic for updating a ticket (assignments, status, etc.)"""
    ticket = serializer.instance
    old_assigned_to = ticket.assigned_to
    old_status = ticket.status

    # Get new data from serializer (not saved yet)
    new_assigned_to = serializer.validated_data.get('assigned_to', old_assigned_to)
    new_status = serializer.validated_data.get('status', old_status)

    # Check section consistency
    if new_assigned_to and ticket.section != new_assigned_to.section:
        raise ValidationError(
            f"Technician {new_assigned_to.username} does not belong to section {ticket.section.name}."
        )

    # Auto-change status if newly assigned and was open
    if old_assigned_to is None and new_assigned_to and old_status == 'open':
        new_status = 'assigned'
        serializer.validated_data['status'] = 'assigned'

    #prevent assignment if ticket is closed or resolved
    if new_assigned_to and old_status in ["resolved", "closed"]:
        raise ValidationError("Cannot assign a ticket that is resolved or closed.")

    # Save updated fields
    updated_ticket = serializer.save()

    # Log assignment changes
    if old_assigned_to != new_assigned_to:
        TicketLog.objects.create(
            ticket=updated_ticket,
            performed_by=user,
            action=f"Assigned to {new_assigned_to or 'None'}"
        )

    # Log status changes
    if old_status != new_status:
        TicketLog.objects.create(
            ticket=updated_ticket,
            performed_by=user,
            action=f"Status changed from {old_status} to {new_status}"
        )

    return updated_ticket
# ---------------------------------------------
#  COMMENT SERVICES
# ---------------------------------------------
def create_comment(serializer, user, ticket_id):
    """
    Attach author and ticket to a new comment.
    Log the action under TicketLog.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)
    comment = serializer.save(author=user, ticket=ticket)

    TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action=f"Comment added by {user.username}"
    )

    return comment


# ---------------------------------------------
#  FEEDBACK SERVICES
# ---------------------------------------------
def create_feedback(serializer, user, ticket_id):
    """
    Ensure only the ticket raiser can provide feedback.
    Attach user and ticket, log the action.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.raised_by != user:
        raise PermissionDenied("Only the ticket raiser can give feedback.")

    feedback = serializer.save(rated_by=user, ticket=ticket)

    TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action=f"Feedback ({serializer.validated_data.get('rating', '?')}/5) added by {user.username}"
    )

    return feedback