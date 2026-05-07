"""Services package for the tickets app API.

Consolidated service layer providing all ticket management operations with
organizational hierarchy validation. All operations respect role-based permissions,
organizational scope, and escalation rules.

Main classes:
- TicketService: Central service for all ticket operations
- Validators: Pure validation functions for status transitions

Legacy aliases are maintained for backwards compatibility.
"""

from .services import (
    TicketService,
    validate_status_transition,
    manual_escalation_allowed,
    # Exceptions
    TicketServiceException,
    InsufficientScopeException,
    InvalidAssignmentException,
    InvalidEscalationException,
)

# Backwards compatibility aliases
OrganizationalTicketService = TicketService
OrganizationalTicketServiceException = TicketServiceException


__all__ = [
    # Main service class
    "TicketService",
    # Validators
    "validate_status_transition",
    "manual_escalation_allowed",
    # Exceptions
    "TicketServiceException",
    "InsufficientScopeException",
    "InvalidAssignmentException",
    "InvalidEscalationException",
    # Backwards compatibility
    "OrganizationalTicketService",
    "OrganizationalTicketServiceException",
]
