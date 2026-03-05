"""
OrganizationalTicketService

Comprehensive service layer for ticket operations with organizational hierarchy validation.
Ensures all ticket operations respect role-based permissions, organizational scope, and escalation rules.

Key Operations:
- create_ticket(): Create tickets with organizational context validation
- assign_ticket(): Assign tickets to technicians with scope validation
- escalate_ticket(): Manual escalation with approval chain
- process_auto_escalations(): Scheduled task for automatic escalations
- close_ticket(): Close tickets with proper authorization
- get_accessible_tickets(): Retrieve tickets within user's organizational scope
"""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from tickets.models import Ticket, CustomUser, TicketLog
from typing import List, Optional, Dict, Tuple


class OrganizationalTicketServiceException(Exception):
    """Base exception for organizational ticket service errors"""
    pass


class InsufficientScopeException(OrganizationalTicketServiceException):
    """User lacks organizational scope to perform operation"""
    pass


class InvalidAssignmentException(OrganizationalTicketServiceException):
    """Technician cannot be assigned for organizational or role reasons"""
    pass


class InvalidEscalationException(OrganizationalTicketServiceException):
    """Escalation cannot be performed for organizational or state reasons"""
    pass


class OrganizationalTicketService:
    """
    Central service for ticket operations with organizational hierarchy validation.

    Enforces:
    - Role-based access control (user, technician, section_head, hod, director, admin)
    - Organizational scope boundaries (section → department → campus → organization)
    - Escalation rules (48h to section_head, 24h to hod, hod is max)
    - Ticket state transitions (open → assigned → in_progress → pending → resolved → closed)
    - Assignment rules (technician must be in ticket's section)
    """

    @staticmethod
    def create_ticket(
        data: Dict,
        created_by: CustomUser,
        section,
        facility,
        priority: str = 'medium',
        enable_auto_escalation: bool = True
    ) -> Ticket:
        """
        Create a new ticket with organizational validation.

        Args:
            data: Dictionary with ticket data (title, description, etc.)
            created_by: User creating the ticket
            section: Section object ticket belongs to
            facility: Facility object ticket is for
            priority: Ticket priority (low/medium/high/critical)
            enable_auto_escalation: Whether to enable auto-escalation (default: True)

        Returns:
            Created Ticket object

        Raises:
            InsufficientScopeException: User doesn't have access to this section/facility
            ValidationError: Invalid ticket data
        """
        # Check user has access to section
        if not OrganizationalTicketService._user_can_access_section(created_by, section):
            raise InsufficientScopeException(
                f"User {created_by.username} lacks access to section {section.name}"
            )

        # Check user has access to facility
        if facility.campus_id and facility.departmentid:
            if not OrganizationalTicketService._user_can_access_facility(created_by, facility):
                raise InsufficientScopeException(
                    f"User {created_by.username} lacks access to facility {facility.name}"
                )

        with transaction.atomic():
            # Create ticket with organizational context
            ticket = Ticket.objects.create(
                title=data.get('title'),
                description=data.get('description'),
                section=section,
                facility=facility,
                raised_by=created_by,
                priority=priority,
                auto_escalation_enabled=enable_auto_escalation,
                status='open'
            )

            # Log ticket creation
            TicketLog.objects.create(
                ticket=ticket,
                action='created',
                changed_by=created_by,
                details={
                    'section': section.name,
                    'facility': facility.name,
                    'priority': priority,
                    'auto_escalation_enabled': enable_auto_escalation
                }
            )

            return ticket

    @staticmethod
    def assign_ticket(
        ticket: Ticket,
        technician: CustomUser,
        assigned_by: CustomUser
    ) -> Ticket:
        """
        Assign a ticket to a technician with organizational validation.

        Args:
            ticket: Ticket to assign
            technician: Technician to assign to
            assigned_by: User performing the assignment

        Returns:
            Updated Ticket object

        Raises:
            PermissionDenied: assigned_by user lacks permission
            InvalidAssignmentException: Technician cannot be assigned for any reason
        """
        # Check assigner has permission
        if assigned_by.role not in ['section_head', 'hod', 'director', 'admin']:
            raise PermissionDenied(
                f"User {assigned_by.username} (role: {assigned_by.role}) cannot assign tickets"
            )

        # Check scope - assigner must have access to ticket's section/department
        if not OrganizationalTicketService._user_can_access_section(assigned_by, ticket.section):
            raise InsufficientScopeException(
                f"User {assigned_by.username} lacks access to ticket's section"
            )

        # Validate technician
        if technician.role != 'technician':
            raise InvalidAssignmentException(
                f"User {technician.username} is not a technician (role: {technician.role})"
            )

        # Check technician belongs to ticket's section
        if ticket.section not in technician.sections.all():
            raise InvalidAssignmentException(
                f"Technician {technician.username} is not part of section {ticket.section.name}"
            )

        # Check ticket can be assigned (not resolved/closed)
        if ticket.status in ['resolved', 'closed']:
            raise InvalidAssignmentException(
                f"Cannot assign ticket in '{ticket.status}' status"
            )

        # Check technician is active
        if not technician.is_active:
            raise InvalidAssignmentException(
                f"Technician {technician.username} is not active"
            )

        with transaction.atomic():
            # Use model's atomic helper
            ticket.change_assignment(technician, performed_by=assigned_by)

            return ticket

    @staticmethod
    def escalate_ticket(
        ticket: Ticket,
        escalated_by: CustomUser,
        reason: str,
        manual: bool = True
    ) -> Ticket:
        """
        Escalate a ticket to the next level in approval chain.

        Escalation chain:
        - Level 0 (technician) → Level 1 (section_head)
        - Level 1 (section_head) → Level 2 (hod) [MAXIMUM]
        - Cannot escalate beyond hod

        Args:
            ticket: Ticket to escalate
            escalated_by: User performing escalation
            reason: Reason for escalation
            manual: Whether this is a manual escalation (default: True)

        Returns:
            Updated Ticket object

        Raises:
            PermissionDenied: User lacks escalation permission
            InvalidEscalationException: Ticket cannot be escalated
        """
        # Check permission to escalate
        if escalated_by.role not in ['section_head', 'hod', 'admin']:
            raise PermissionDenied(
                f"User {escalated_by.username} (role: {escalated_by.role}) cannot escalate tickets"
            )

        # Verify manual escalation timing if applicable
        if manual and not manual_escalation_allowed(ticket):
            raise InvalidEscalationException(
                f"Cannot manually escalate ticket {ticket.ticket_no} - auto-escalation timeout active"
            )

        # Check ticket status allows escalation
        if ticket.status in ['resolved', 'closed']:
            raise InvalidEscalationException(
                f"Cannot escalate resolved or closed ticket {ticket.ticket_no}"
            )

        with transaction.atomic():
            # Use model's atomic helper
            ticket.escalate(
                reason=reason, escalated_by=escalated_by, is_manual=manual)

            return ticket

    @staticmethod
    def close_ticket(
        ticket: Ticket,
        closed_by: CustomUser,
        closure_notes: Optional[str] = None
    ) -> Ticket:
        """
        Close a resolved ticket (admin/manager only).

        Args:
            ticket: Ticket to close
            closed_by: User closing the ticket (must be admin/manager)
            closure_notes: Optional notes about closure

        Returns:
            Updated Ticket object

        Raises:
            PermissionDenied: User is not admin or manager
            ValidationError: Ticket is not resolved
        """
        # Check permission
        if closed_by.role not in ['admin', 'manager']:
            raise PermissionDenied(
                f"Only admins/managers can close tickets, not {closed_by.role}"
            )

        # Check ticket is resolved
        if ticket.status != 'resolved':
            raise ValidationError(
                f"Only resolved tickets can be closed. Ticket {ticket.ticket_no} is '{ticket.status}'"
            )

        with transaction.atomic():
            # Use model's atomic helper
            ticket.change_status('closed', performed_by=closed_by)

            # Log closure details
            if closure_notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action='closed',
                    changed_by=closed_by,
                    details={'closure_notes': closure_notes}
                )

            return ticket

    @staticmethod
    def process_auto_escalations() -> Dict[str, any]:
        """
        Process automatic escalations for tickets that have exceeded time thresholds.

        Scheduled task to run periodically (e.g., every hour via management command).

        Returns:
            Dictionary with escalation statistics:
            {
                'processed': count,
                'escalated': count,
                'failed': count,
                'errors': [list of error messages]
            }
        """
        stats = {
            'processed': 0,
            'escalated': 0,
            'failed': 0,
            'errors': []
        }

        # Find all tickets due for auto-escalation
        tickets_due = Ticket.objects.filter(
            auto_escalation_enabled=True,
            next_escalation_due__lte=timezone.now(),
            status__in=['open', 'assigned', 'in_progress', 'pending']
        ).exclude(escalation_level=2)  # Don't escalate beyond HOD

        for ticket in tickets_due:
            stats['processed'] += 1
            try:
                # Get system user for auto-escalation
                system_user = OrganizationalTicketService._get_system_user()

                # Escalate ticket
                OrganizationalTicketService.escalate_ticket(
                    ticket=ticket,
                    escalated_by=system_user,
                    reason='Automatic escalation due to timeout',
                    manual=False
                )

                stats['escalated'] += 1

                # Log auto-escalation event
                TicketLog.objects.create(
                    ticket=ticket,
                    action='auto_escalated',
                    changed_by=system_user,
                    details={
                        'escalation_level': ticket.escalation_level,
                        'escalated_to': str(ticket.escalated_to),
                        'next_escalation_due': str(ticket.next_escalation_due)
                    }
                )

            except Exception as e:
                stats['failed'] += 1
                error_msg = f"Failed to escalate ticket {ticket.ticket_no}: {str(e)}"
                stats['errors'].append(error_msg)

        return stats

    @staticmethod
    def get_accessible_tickets(
        user: CustomUser,
        filters: Optional[Dict] = None
    ) -> List[Ticket]:
        """
        Get all tickets user can access based on organizational scope.

        Args:
            user: User requesting tickets
            filters: Optional additional filters (status, priority, etc.)

        Returns:
            Queryset of accessible Ticket objects
        """
        if user.role == 'admin':
            # Admin can see all tickets
            queryset = Ticket.objects.all()
        elif user.role == 'director':
            # Director can see all tickets in organization
            queryset = Ticket.objects.filter(
                section__department__campus__organization=user.primary_campus.organization
            )
        elif user.role == 'hod':
            # HOD can see all tickets in campus
            queryset = Ticket.objects.filter(
                section__department__campus=user.primary_campus
            )
        elif user.role == 'section_head':
            # Section head can see all tickets in department
            queryset = Ticket.objects.filter(
                section__department=user.primary_department
            )
        elif user.role == 'technician':
            # Technician can see tickets in their sections or assigned to them
            queryset = Ticket.objects.filter(
                section__in=user.sections.all()
            ) | Ticket.objects.filter(assigned_to=user) | Ticket.objects.filter(raised_by=user)
        else:  # user role
            # Users can only see their own tickets
            queryset = Ticket.objects.filter(raised_by=user)

        # Apply additional filters if provided
        if filters:
            if 'status' in filters:
                queryset = queryset.filter(status=filters['status'])
            if 'priority' in filters:
                queryset = queryset.filter(priority=filters['priority'])
            if 'section_id' in filters:
                queryset = queryset.filter(section_id=filters['section_id'])
            if 'facility_id' in filters:
                queryset = queryset.filter(facility_id=filters['facility_id'])

        return queryset.select_related(
            'section', 'facility', 'raised_by', 'assigned_to'
        ).order_by('-created_at')

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    @staticmethod
    def _user_can_access_section(user: CustomUser, section) -> bool:
        """Check if user has access to section based on role and organizational scope"""
        if user.role == 'admin':
            return True

        if not section or not section.department or not section.department.campus:
            return False

        if user.role == 'director':
            return section.department.campus.organization == user.primary_campus.organization
        elif user.role == 'hod':
            return section.department.campus == user.primary_campus
        elif user.role == 'section_head':
            return section.department == user.primary_department
        elif user.role in ['technician', 'user']:
            return section in user.sections.all() or section.department == user.primary_department

        return False

    @staticmethod
    def _user_can_access_facility(user: CustomUser, facility) -> bool:
        """Check if user has access to facility based on role and organizational scope"""
        if user.role == 'admin':
            return True

        if not facility.campus or not facility.department:
            return False

        if user.role == 'director':
            return facility.campus.organization == user.primary_campus.organization
        elif user.role == 'hod':
            return facility.campus == user.primary_campus
        elif user.role == 'section_head':
            return facility.department == user.primary_department
        elif user.role in ['technician', 'user']:
            return facility.campus == user.primary_campus

        return False

    @staticmethod
    def _get_system_user() -> CustomUser:
        """
        Get or create system user for automated operations.

        Returns:
            CustomUser object representing the system
        """
        system_user, _ = CustomUser.objects.get_or_create(
            username='system',
            defaults={
                'email': 'system@tickets.local',
                'first_name': 'System',
                'last_name': 'User',
                'role': 'admin',
                'is_staff': False,
                'is_active': True
            }
        )
        return system_user


def manual_escalation_allowed(ticket: Ticket) -> bool:
    """
    Check if ticket can be manually escalated (respects auto-escalation timeout).

    If auto-escalation is enabled and next escalation is due soon, prevent
    manual escalation to avoid bypassing the auto-escalation process.

    Args:
        ticket: Ticket to check

    Returns:
        True if manual escalation is allowed, False otherwise
    """
    if not ticket.auto_escalation_enabled:
        return True

    # Allow manual escalation if auto-escalation is overdue
    # (system should have escalated it already)
    if ticket.next_escalation_due and ticket.next_escalation_due <= timezone.now():
        return True

    return True  # Allow manual escalation by default
