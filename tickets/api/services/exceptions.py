"""Custom exceptions for the services layer."""


class TicketServiceException(Exception):
    """Base exception for ticket service errors"""

    pass


class InsufficientScopeException(TicketServiceException):
    """User lacks organizational scope to perform operation"""

    pass


class InvalidAssignmentException(TicketServiceException):
    """Technician cannot be assigned for organizational or role reasons"""

    pass


class InvalidEscalationException(TicketServiceException):
    """Escalation cannot be performed for organizational or state reasons"""

    pass
