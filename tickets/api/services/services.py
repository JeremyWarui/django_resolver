"""
Consolidated Services Layer for Django Resolver

This module provides all ticket management services with organizational hierarchy validation.
All operations respect role-based permissions, organizational scope, and escalation rules.

Key Operations:
- create_ticket(): Create tickets with organizational context validation
- assign_ticket(): Assign tickets with scope validation
- escalate_ticket(): Manual escalation with approval chain
- process_auto_escalations(): Scheduled task for automatic escalations
- close_ticket(): Close tickets with proper authorization
- get_accessible_tickets(): Retrieve tickets within user's organizational scope
- create_comment(): Add comments to tickets
- create_feedback(): Add feedback/ratings to tickets

Organizational Hierarchy:
- Admin: Full system access
- Director: Organization-wide view
- HOD: Campus-level access
- Section Head: Department level
- Technician: Section level
- User: Own tickets only
"""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError as DRFValidationError, PermissionDenied as DRFPermissionDenied
from tickets.models import Ticket, CustomUser, TicketLog, Comment, Feedback, Section, Facility
from typing import List, Optional, Dict, Tuple, Any
from datetime import timedelta


# ============================================================================
# EXCEPTIONS
# ============================================================================

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


# ============================================================================
# VALIDATORS - Pure validation functions
# ============================================================================

def validate_status_transition(old_status: str, new_status: str, user_role: str) -> Tuple[bool, str]:
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
        'open': ['assigned', 'escalated'],
        'assigned': ['in_progress', 'pending', 'escalated'],
        'in_progress': ['pending', 'resolved', 'escalated'],
        'pending': ['in_progress', 'resolved', 'escalated'],
        'resolved': ['closed'],
        'closed': [],  # No transitions allowed from closed state
        'escalated': ['in_progress', 'pending', 'resolved']
    }

    # Define which roles can perform which transitions
    role_permissions = {
        'technician': ['open', 'assigned', 'in_progress', 'pending', 'resolved', 'escalated'],
        'section_head': ['in_progress', 'pending', 'resolved', 'escalated'],
        'hod': ['in_progress', 'pending', 'resolved', 'escalated'],
        'admin': ['open', 'assigned', 'in_progress', 'pending', 'resolved', 'closed', 'escalated'],
        'manager': ['open', 'assigned', 'in_progress', 'pending', 'resolved', 'closed', 'escalated'],
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


def manual_escalation_allowed(ticket: Ticket) -> bool:
    """Check if a ticket can be manually escalated based on auto-escalation cooldown"""
    if not ticket.next_escalation_due:
        return True
    return timezone.now() > ticket.next_escalation_due


# ============================================================================
# TICKET SERVICE - Organizational-focused
# ============================================================================

class TicketService:
    """
    Central service for ticket operations with organizational hierarchy validation.

    Enforces:
    - Role-based access control (user, technician, section_head, hod, director, admin)
    - Organizational scope boundaries (section → department → campus → organization)
    - Escalation rules (configurable threshold hours to section_head, then to hod max)
    - Ticket state transitions (open → assigned → in_progress → pending → resolved → closed)
    - Assignment rules (technician must be in ticket's section and accessible campus)
    """

    # ========================================================================
    # TICKET CREATION
    # ========================================================================

    @staticmethod
    def create_ticket(
        data: Dict,
        created_by: CustomUser,
        section: Section,
        facility: Facility,
        enable_auto_escalation: bool = True
    ) -> Ticket:
        """
        Create a new ticket with organizational validation.

        Args:
            data: Dictionary with ticket data (title, description, etc.)
            created_by: User creating the ticket
            section: Section object ticket belongs to
            facility: Facility object ticket is for
            enable_auto_escalation: Whether to enable auto-escalation (default: True)

        Returns:
            Created Ticket object

        Raises:
            InsufficientScopeException: User doesn't have access to this section/facility
            DRFValidationError: Invalid ticket data
        """
        # Check user has access to section
        if not TicketService._user_can_access_section(created_by, section):
            raise InsufficientScopeException(
                f"User {created_by.username} lacks access to section {section.name}"
            )

        # Check user has access to facility
        if facility.campus_id:
            if not TicketService._user_can_access_facility(created_by, facility):
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
                auto_escalation_enabled=enable_auto_escalation,
                status='open'
            )

            # Log ticket creation
            TicketLog.objects.create(
                ticket=ticket,
                action='created',
                performed_by=created_by
            )

            # Notify relevant users
            TicketService._notify_ticket_creation(ticket)

            return ticket

    # ========================================================================
    # TICKET ASSIGNMENT
    # ========================================================================

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
            DRFPermissionDenied: assigned_by user lacks permission
            InvalidAssignmentException: Technician cannot be assigned for any reason
        """
        # Check assigner has permission
        if assigned_by.role not in ['section_head', 'hod', 'director', 'admin', 'technician']:
            raise DRFPermissionDenied(
                f"User {assigned_by.username} (role: {assigned_by.role}) cannot assign tickets"
            )

        # Check scope - assigner must have access to ticket's section/department
        if not TicketService._user_can_access_section(assigned_by, ticket.section):
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

        # Check technician's campus matches ticket's campus (handle None department)
        ticket_campus = ticket.section.department.campus if ticket.section.department else None
        if ticket_campus and technician.primary_campus != ticket_campus:
            raise InvalidAssignmentException(
                f"Technician {technician.username} is not assigned to this campus"
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

    # ========================================================================
    # TICKET ESCALATION
    # ========================================================================

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
            DRFPermissionDenied: User lacks escalation permission
            InvalidEscalationException: Ticket cannot be escalated
        """
        # Check permission to escalate - allow technician, section_head, hod, admin
        if escalated_by.role not in ['technician', 'section_head', 'hod', 'admin']:
            raise DRFPermissionDenied(
                f"User {escalated_by.username} (role: {escalated_by.role}) cannot escalate tickets"
            )

        # Check ticket status allows escalation
        if ticket.status in ['resolved', 'closed']:
            raise InvalidEscalationException(
                f"Cannot escalate resolved or closed ticket {ticket.ticket_no}"
            )

        # Check max escalation level not exceeded
        if ticket.escalation_level >= 2:
            raise InvalidEscalationException(
                f"Ticket {ticket.ticket_no} is already at maximum escalation level"
            )

        with transaction.atomic():
            # Use model's atomic helper
            ticket.escalate(
                escalated_by=escalated_by,
                reason=reason,
                is_auto_escalation=not manual
            )

            # Notify escalation recipient
            TicketService._notify_escalation(ticket)

            return ticket

    # ========================================================================
    # TICKET STATUS UPDATES
    # ========================================================================

    @staticmethod
    def update_ticket_status(
        ticket: Ticket,
        new_status: str,
        updated_by: CustomUser,
        notes: Optional[str] = None
    ) -> Ticket:
        """
        Update ticket status with proper validation and logging.

        Validates status transitions and ensures user has permission.

        Args:
            ticket: Ticket to update
            new_status: New status value
            updated_by: User performing the update
            notes: Optional notes about the status change

        Returns:
            Updated Ticket object

        Raises:
            DRFPermissionDenied: User lacks permission to change status
            DRFValidationError: Invalid status transition
        """
        old_status = ticket.status

        # Validate status transition
        is_valid, error_msg = validate_status_transition(
            old_status, new_status, updated_by.role)
        if not is_valid:
            raise DRFValidationError(error_msg)

        # Check permission for this specific transition
        if new_status == 'closed' and updated_by.role not in ['admin', 'manager']:
            raise DRFPermissionDenied("Only admins/managers can close tickets")

        # Perform status change
        with transaction.atomic():
            ticket.change_status(new_status, performed_by=updated_by)

            # Log additional context if provided
            if notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f'{old_status} → {new_status}: {notes}',
                    performed_by=updated_by
                )

        return ticket

    @staticmethod
    def bulk_update_status(
        ticket_ids: list,
        new_status: str,
        updated_by: CustomUser,
        reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update status for multiple tickets in a single operation.

        Args:
            ticket_ids: List of ticket IDs to update
            new_status: New status for all tickets
            updated_by: User making the bulk update
            reason: Optional reason for bulk update

        Returns:
            Dictionary with success/failure counts and details
        """
        # Ensure ticket_ids is a list
        if not isinstance(ticket_ids, list):
            ticket_ids = [ticket_ids]

        results = {
            'success': len(ticket_ids) > 0,
            'total': len(ticket_ids),
            'updated': 0,
            'failed': 0,
            'errors': []
        }

        # Get all tickets
        tickets = Ticket.objects.filter(id__in=ticket_ids)
        
        # Track which ticket IDs were found
        found_ids = set(tickets.values_list('id', flat=True))
        missing_ids = set(ticket_ids) - found_ids
        
        # Add errors for missing tickets
        for missing_id in missing_ids:
            results['failed'] += 1
            results['success'] = False
            results['errors'].append({
                'ticket_id': missing_id,
                'error': f'Ticket with ID {missing_id} not found'
            })

        for ticket in tickets:
            try:
                # Validate and update status
                is_valid, error_msg = validate_status_transition(
                    ticket.status, new_status, updated_by.role)
                if not is_valid:
                    results['failed'] += 1
                    results['success'] = False
                    results['errors'].append({
                        'ticket_id': ticket.id,
                        'ticket_no': ticket.ticket_no,
                        'error': error_msg
                    })
                    continue

                # Perform status change
                TicketService.update_ticket_status(
                    ticket=ticket,
                    new_status=new_status,
                    updated_by=updated_by,
                    notes=reason
                )
                results['updated'] += 1

            except Exception as e:
                results['failed'] += 1
                results['success'] = False
                results['errors'].append({
                    'ticket_id': ticket.id,
                    'ticket_no': ticket.ticket_no,
                    'error': str(e)
                })

        return results

    # ========================================================================
    # TICKET CLOSURE
    # ========================================================================

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
            DRFPermissionDenied: User is not admin or manager
            DRFValidationError: Ticket is not resolved
        """
        # Check permission
        if closed_by.role not in ['admin', 'manager']:
            raise DRFPermissionDenied(
                f"Only admins/managers can close tickets, not {closed_by.role}"
            )

        # Check ticket is resolved
        if ticket.status != 'resolved':
            raise DRFValidationError(
                f"Only resolved tickets can be closed. Ticket {ticket.ticket_no} is '{ticket.status}'"
            )

        with transaction.atomic():
            # Use model's atomic helper
            ticket.change_status('closed', performed_by=closed_by)

            # Log closure details
            if closure_notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f'closed - {closure_notes}',
                    performed_by=closed_by
                )

        return ticket

    # ========================================================================
    # AUTO-ESCALATIONS
    # ========================================================================

    @staticmethod
    def process_auto_escalations() -> Dict[str, Any]:
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
                system_user = TicketService._get_system_user()

                # Escalate ticket
                TicketService.escalate_ticket(
                    ticket=ticket,
                    escalated_by=system_user,
                    reason='Automatic escalation due to timeout',
                    manual=False
                )

                stats['escalated'] += 1

                # Log auto-escalation event
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f'auto_escalated to level {ticket.escalation_level}',
                    performed_by=system_user
                )

            except Exception as e:
                stats['failed'] += 1
                error_msg = f"Failed to escalate ticket {ticket.ticket_no}: {str(e)}"
                stats['errors'].append(error_msg)

        return stats

    # ========================================================================
    # TICKET RETRIEVAL & FILTERING
    # ========================================================================

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
            if user.primary_campus:
                queryset = Ticket.objects.filter(
                    section__department__campus__organization=user.primary_campus.organization
                )
            else:
                queryset = Ticket.objects.none()
        elif user.role == 'hod':
            # HOD can see all tickets in their department
            if user.primary_department:
                queryset = Ticket.objects.filter(
                    section__department=user.primary_department
                )
            else:
                queryset = Ticket.objects.none()
        elif user.role == 'section_head':
            # Section head can see all tickets in sections they manage
            # They manage sections via Section.section_head FK
            queryset = Ticket.objects.filter(
                section__section_head=user
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
            if 'section_id' in filters:
                queryset = queryset.filter(section_id=filters['section_id'])
            if 'facility_id' in filters:
                queryset = queryset.filter(facility_id=filters['facility_id'])
            if 'escalation_level' in filters:
                queryset = queryset.filter(
                    escalation_level=filters['escalation_level'])

        return queryset.select_related(
            'section', 'facility', 'raised_by', 'assigned_to', 'escalated_to'
        ).order_by('-created_at')

    # ========================================================================
    # COMMENTS
    # ========================================================================

    @staticmethod
    def create_comment(
        serializer,
        user: CustomUser,
        ticket_id: int
    ) -> Comment:
        """
        Attach author and ticket to a new comment.
        Log the action under TicketLog.
        """
        ticket = get_object_or_404(Ticket, id=ticket_id)

        # Check if ticket is closed
        if ticket.status == "closed":
            raise DRFValidationError("Cannot add comments to a closed ticket.")

        comment = serializer.save(author=user, ticket=ticket)

        TicketLog.objects.create(
            ticket=ticket,
            performed_by=user,
            action=f"Comment added by {user.username}"
        )

        return comment

    # ========================================================================
    # FEEDBACK
    # ========================================================================

    @staticmethod
    def create_feedback(
        serializer,
        user: CustomUser,
        ticket_id: int
    ) -> Feedback:
        """
        Ensure only the ticket raiser can provide feedback.
        Attach user and ticket, log the action.
        """
        ticket = get_object_or_404(Ticket, id=ticket_id)

        if ticket.raised_by != user:
            raise DRFPermissionDenied(
                "Only the ticket raiser can give feedback.")

        # Feedback can be provided on resolved tickets, but not on closed tickets
        if ticket.status == "closed":
            raise DRFValidationError(
                "Cannot provide feedback on a closed ticket.")

        if ticket.status != "resolved":
            raise DRFValidationError(
                "The ticket has to be resolved to rate the job."
            )

        # Prevent duplicate feedback for the same ticket
        if Feedback.objects.filter(ticket=ticket).exists():
            raise DRFValidationError(
                "Feedback has already been submitted for this ticket."
            )

        feedback = serializer.save(rated_by=user, ticket=ticket)

        TicketLog.objects.create(
            ticket=ticket,
            performed_by=user,
            action=f"Feedback ({serializer.validated_data.get('rating', '?')}/5) added by {user.username}"
        )

        return feedback

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @staticmethod
    def _user_can_access_section(user: CustomUser, section: Section) -> bool:
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
            return section in user.sections.all()

        return False

    @staticmethod
    def _user_can_access_facility(user: CustomUser, facility: Facility) -> bool:
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
        """Get or create system user for automated operations"""
        user, _ = CustomUser.objects.get_or_create(
            username='system',
            defaults={
                'first_name': 'System',
                'last_name': 'User',
                'email': 'system@example.com',
                'role': 'admin',
                'is_staff': True,
            }
        )
        return user

    @staticmethod
    def _notify_ticket_creation(ticket: Ticket) -> None:
        """
        Send notification when ticket is created.

        Notifies:
        - Section head (if exists)
        - HOD (if exists)

        Args:
            ticket: Newly created ticket
        """
        try:
            if ticket.section and ticket.section.section_head:
                # Log notification event (actual email sending handled elsewhere)
                TicketLog.objects.create(
                    ticket=ticket,
                    action='notification: ticket created',
                    performed_by=ticket.raised_by
                )
        except Exception as e:
            # Log notification error but don't fail the ticket creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to notify on ticket creation {ticket.ticket_no}: {str(e)}"
            )

    @staticmethod
    def _notify_escalation(ticket: Ticket) -> None:
        """
        Send notification when ticket is escalated.

        Notifies escalation recipient with escalation details.

        Args:
            ticket: Escalated ticket
        """
        try:
            if ticket.escalated_to:
                # Log escalation notification
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f'notification: escalated to {ticket.escalated_to.username}',
                    performed_by=ticket.raised_by
                )
        except Exception as e:
            # Log notification error but don't fail the escalation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to notify on ticket escalation {ticket.ticket_no}: {str(e)}"
            )


# ============================================================================
# CONVENIENCE ALIASES FOR BACKWARDS COMPATIBILITY
# ============================================================================

# Legacy function names that now call the unified TicketService
create_ticket_legacy = TicketService.create_ticket
update_ticket_legacy = TicketService.update_ticket_status
create_comment_legacy = TicketService.create_comment
create_feedback_legacy = TicketService.create_feedback
