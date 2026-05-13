"""Pure validation functions for ticket service operations."""

from typing import Tuple
from tickets.models import Ticket


def validate_status_transition(
    old_status: str, new_status: str, user_role: str
) -> Tuple[bool, str]:
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
        "open": ["assigned", "pending", "escalated"],
        "assigned": ["in_progress", "pending", "escalated"],
        "in_progress": ["pending", "resolved", "escalated"],
        "pending": ["in_progress", "resolved", "escalated"],
        "pending_approval": ["open", "rejected"],  # HOD approval flow
        "resolved": ["closed"],
        "rejected": [],  # No transitions from rejected state
        "closed": [],  # No transitions allowed from closed state
        "escalated": ["in_progress", "pending", "resolved"],
    }

    # Define which roles can perform which transitions
    role_permissions = {
        "technician": [
            "open",
            "assigned",
            "in_progress",
            "pending",
            "resolved",
            "escalated",
        ],
        "head_of_section": ["assigned", "in_progress", "pending", "resolved", "escalated"],
        "hod": [
            "assigned",  # Can assign tickets
            "open",  # Can approve pending_approval tickets
            "rejected",  # Can reject pending_approval tickets
            "in_progress",
            "pending",
            "resolved",
            "escalated",
        ],
        "admin": [
            "open",
            "assigned",
            "in_progress",
            "pending",
            "rejected",
            "resolved",
            "closed",
            "escalated",
        ],
        "manager": [],  # Analytics-only role — cannot modify ticket status
        "user": [],  # Regular users can't change status
    }

    # Check if transition is valid
    if new_status not in valid_transitions.get(old_status, []):
        valid_options = ", ".join(valid_transitions.get(old_status, []))
        return (
            False,
            f"Invalid status transition from '{old_status}' to '{new_status}'. Valid options: {valid_options}",
        )

    # Check if user role has permission for this new status
    if new_status not in role_permissions.get(user_role, []):
        return (
            False,
            f"User with role '{user_role}' cannot set ticket status to '{new_status}'",
        )

    return True, ""


def manual_escalation_allowed(ticket: Ticket) -> bool:
    """Check if a ticket can be manually escalated based on auto-escalation cooldown"""
    from django.utils import timezone

    if not ticket.next_escalation_due:
        return True
    return timezone.now() > ticket.next_escalation_due


def validate_pending_transition(
    new_status: str, pending_reason: str, pending_comment: str
) -> Tuple[bool, str]:
    """
    Validate that PENDING status transitions include required reason and comment.

    Args:
        new_status: Proposed new status
        pending_reason: Reason for pending (if applicable)
        pending_comment: Comment for pending (if applicable)

    Returns:
        tuple: (is_valid, message)
    """
    if new_status == "pending":
        if not pending_reason:
            return False, "pending_reason is required when marking ticket as PENDING"
        if not pending_comment:
            return False, "pending_comment is required when marking ticket as PENDING"

    return True, ""
