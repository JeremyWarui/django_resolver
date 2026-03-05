"""Services package for the tickets app API."""

from .ticket_services import (
    validate_status_transition,
    update_ticket,
    create_ticket,
    create_comment,
    create_feedback,
)
from .organizational_ticket_service import (
    OrganizationalTicketService,
    OrganizationalTicketServiceException,
    InsufficientScopeException,
    InvalidAssignmentException,
    InvalidEscalationException,
    manual_escalation_allowed,
)

__all__ = [
    # Legacy services
    'validate_status_transition',
    'update_ticket',
    'create_ticket',
    'create_comment',
    'create_feedback',
    # Organizational services
    'OrganizationalTicketService',
    'OrganizationalTicketServiceException',
    'InsufficientScopeException',
    'InvalidAssignmentException',
    'InvalidEscalationException',
    'manual_escalation_allowed',
]
