"""Services package for the tickets app API.

Consolidated service layer providing all ticket management operations with
organizational hierarchy validation. All operations respect role-based permissions,
organizational scope, and escalation rules.

Main classes:
- TicketService: Central service for all ticket operations
- TechnicianService: Service for managing technician assignments
- Validators: Pure validation functions for status transitions
- Exceptions: Custom exceptions for service errors
"""

from .ticket_service import TicketService
from .technician_service import TechnicianService

from .validators import (
    validate_status_transition,
    manual_escalation_allowed,
    validate_pending_transition,
)

from .exceptions import (
    TicketServiceException,
    InsufficientScopeException,
    InvalidAssignmentException,
    InvalidEscalationException,
)

__all__ = [
    "TicketService",
    "TechnicianService",
    "validate_status_transition",
    "manual_escalation_allowed",
    "validate_pending_transition",
    "TicketServiceException",
    "InsufficientScopeException",
    "InvalidAssignmentException",
    "InvalidEscalationException",
]
