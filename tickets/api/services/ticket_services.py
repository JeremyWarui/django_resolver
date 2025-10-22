from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied

from tickets.models import Ticket, TicketLog


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
    new_assigned_to = serializer.validated_data.get(
        'assigned_to', old_assigned_to)
    new_status = serializer.validated_data.get('status', old_status)

    # Prevent any changes to closed tickets
    if old_status == "closed":
        raise ValidationError(
            "Cannot modify a closed ticket. Ticket is already finalized.")

    # If status is changing, validate the transition
    if new_status != old_status:
        is_valid, error_message = validate_status_transition(
            old_status, new_status, user.role)
        if not is_valid:
            raise ValidationError(error_message)

    if new_assigned_to:
        # 1. Check if the assigned user's role is 'technician'
        # Assuming your User model has a 'role' field
        if new_assigned_to.role != 'technician':
            raise ValidationError(
                f"User {new_assigned_to.username} cannot be assigned. Their role is not 'technician'."
            )

        # Check section of ticket is among the sections the technician has
        if ticket.section not in new_assigned_to.sections.all():
            raise ValidationError(
                f"Technician {new_assigned_to.username} does not belong to section {ticket.section.name}."
            )
        # 3. Prevent assignment if ticket is closed or resolved (existing logic)
        if old_status in ["resolved", "closed"] and new_status != "closed":
            raise ValidationError(
                "Cannot assign a ticket that is resolved or closed.")

        # prevent update of status by user
        user = user if user.is_authenticated else None
        if user.role not in ["technician", "admin"]:
            raise ValidationError(
                f"User {user.username} cannot update status. Their role is not 'technician' or 'admin'."
            )

    # Auto-change status if newly assigned and was open
    if old_assigned_to is None and new_assigned_to and old_status == 'open':
        new_status = 'assigned'
        serializer.validated_data['status'] = 'assigned'

    # prevent assignment if ticket is closed or resolved
    if new_assigned_to != old_assigned_to and old_status in ["resolved", "closed"]:
        raise ValidationError(
            "Cannot assign a ticket that is resolved or closed.")

    # Save updated fields
    updated_ticket = serializer.save()

    performed_by = user if user.is_authenticated else None

    # Log assignment changes
    if old_assigned_to != new_assigned_to:
        TicketLog.objects.create(
            ticket=updated_ticket,
            performed_by=performed_by,
            action=f"Assigned to {new_assigned_to or 'None'}"
        )

    # Log status changes
    if old_status != new_status:
        TicketLog.objects.create(
            ticket=updated_ticket,
            performed_by=performed_by,
            action=f"Status changed from {old_status} to {new_status}"
        )

    return updated_ticket


# Helper function to validate status transitions
def validate_status_transition(old_status, new_status, user_role):
    """
    Validate if a ticket status transition is allowed based on business rules.

    Args:
        old_status (str): Current status of the ticket
        new_status (str): Proposed new status
        user_role (str): Role of the user attempting the transition

    Returns:
        tuple: (is_valid, message) - is_valid is a boolean, message is an error message if invalid
    """
    # Define valid transitions based on current status
    valid_transitions = {
        'open': ['assigned'],
        'assigned': ['in_progress', 'pending'],
        'in_progress': ['pending', 'resolved'],
        'pending': ['in_progress', 'resolved'],
        'resolved': ['closed'],
        'closed': []  # No transitions allowed from closed state
    }

    # Define which roles can perform which transitions
    role_permissions = {
        'technician': ['open', 'assigned', 'in_progress', 'pending', 'resolved'],
        'admin': ['open', 'assigned', 'in_progress', 'pending', 'resolved', 'closed'],
        'manager': ['open', 'assigned', 'in_progress', 'pending', 'resolved', 'closed'],
        'user': []  # Regular users can't change status
    }

    # Check if transition is valid
    if new_status not in valid_transitions.get(old_status, []):
        valid_options = ", ".join(valid_transitions.get(old_status, []))
        return False, f"Invalid status transition from '{old_status}' to '{new_status}'. Valid options: {valid_options}"

    # Check if user role has permission for this new status
    if new_status not in role_permissions.get(user_role, []):
        return False, f"User with role '{user_role}' cannot set ticket status to '{new_status}'"

    return True, ""

# ---------------------------------------------
#  COMMENT SERVICES
# ---------------------------------------------


def create_comment(serializer, user, ticket_id):
    """
    Attach author and ticket to a new comment.
    Log the action under TicketLog.
    """
    ticket = get_object_or_404(Ticket, id=ticket_id)

    # Check if ticket is closed
    if ticket.status == "closed":
        raise ValidationError("Cannot add comments to a closed ticket.")

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

    # Feedback can be provided on resolved tickets, but not on closed tickets
    if ticket.status == "closed":
        raise ValidationError("Cannot provide feedback on a closed ticket.")

    if ticket.status != "resolved":
        raise ValidationError("The ticket has to be resolved to rate the job.")

    feedback = serializer.save(rated_by=user, ticket=ticket)

    TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action=f"Feedback ({serializer.validated_data.get('rating', '?')}/5) added by {user.username}"
    )

    return feedback
