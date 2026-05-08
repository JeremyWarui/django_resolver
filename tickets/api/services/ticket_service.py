"""Ticket service for managing tickets with organizational validation."""

from typing import Dict, List, Optional, Any
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import (
    ValidationError as DRFValidationError,
    PermissionDenied as DRFPermissionDenied,
)

from tickets.models import (
    Ticket,
    CustomUser,
    TicketLog,
    Comment,
    Feedback,
    Section,
    Facility,
)
from tickets.email_service import EmailService
from .exceptions import (
    TicketServiceException,
    InsufficientScopeException,
    InvalidAssignmentException,
    InvalidEscalationException,
)
from .validators import (
    validate_status_transition,
    validate_pending_transition,
)


class TicketService:
    """
    Central service for ticket operations with organizational hierarchy validation.

    Enforces:
    - Role-based access control (user, technician, head_of_section, hod, manager, admin)
    - Organizational scope boundaries (section → department → campus → organization)
    - Escalation rules (configurable threshold hours to head_of_section, then to hod max)
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
        facility: Optional[Facility] = None,
        enable_auto_escalation: bool = True,
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

        # Check user has access to facility when one is provided
        if facility and facility.campus_id:
            if not TicketService._user_can_access_facility(created_by, facility):
                raise InsufficientScopeException(
                    f"User {created_by.username} lacks access to facility {facility.name}"
                )

        service_item = data.get("service_item")
        initial_status = "open"
        if service_item and getattr(service_item, "requires_approval", False):
            initial_status = "pending_approval"

        with transaction.atomic():
            ticket = Ticket.objects.create(
                title=data.get("title"),
                description=data.get("description"),
                section=section,
                facility=facility,
                raised_by=created_by,
                auto_escalation_enabled=enable_auto_escalation,
                status=initial_status,
                service_item=service_item,
                form_data=data.get("form_data"),
            )

            TicketLog.objects.create(
                ticket=ticket, action="created", performed_by=created_by
            )

            TicketService._notify_ticket_creation(ticket)

            if ticket.status == "pending_approval":
                EmailService.send_ticket_pending_approval(ticket)

            return ticket

    # ========================================================================
    # TICKET ASSIGNMENT
    # ========================================================================

    @staticmethod
    def assign_ticket(
        ticket: Ticket, technician: CustomUser, assigned_by: CustomUser
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
        if assigned_by.role not in [
            "head_of_section",
            "hod",
            "manager",
            "admin",
            "technician",
        ]:
            raise DRFPermissionDenied(
                f"User {assigned_by.username} (role: {assigned_by.role}) cannot assign tickets"
            )

        # Check scope - assigner must have access to ticket's section/department
        if not TicketService._user_can_access_section(assigned_by, ticket.section):
            raise InsufficientScopeException(
                f"User {assigned_by.username} lacks access to ticket's section"
            )

        # Validate technician
        if technician.role != "technician":
            raise InvalidAssignmentException(
                f"User {technician.username} is not a technician (role: {technician.role})"
            )

        # Check technician belongs to ticket's section
        if not technician.sections.filter(pk=ticket.section_id).exists():
            raise InvalidAssignmentException(
                f"Technician {technician.username} is not part of section {ticket.section.name}"
            )

        # Check technician's campus matches ticket's campus (handle None department)
        ticket_campus = (
            ticket.section.department.campus if ticket.section.department else None
        )
        if ticket_campus and technician.primary_campus != ticket_campus:
            raise InvalidAssignmentException(
                f"Technician {technician.username} is not assigned to this campus"
            )

        # Check ticket can be assigned (not resolved/closed)
        if ticket.status in ["resolved", "closed"]:
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

        EmailService.send_ticket_assigned(ticket, technician)
        return ticket

    # ========================================================================
    # TICKET ESCALATION
    # ========================================================================

    @staticmethod
    def escalate_ticket(
        ticket: Ticket, escalated_by: CustomUser, reason: str, manual: bool = True
    ) -> Ticket:
        """
        Escalate a ticket to the next level in approval chain.

        Escalation chain:
        - Level 0 (technician) → Level 1 (head_of_section)
        - Level 1 (head_of_section) → Level 2 (hod) [MAXIMUM]
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
            DRFValidationError: Ticket cannot be escalated
        """
        # Check permission to escalate - allow technician, section_head, hod, admin
        if escalated_by.role not in ["technician", "head_of_section", "hod", "admin"]:
            raise DRFPermissionDenied(
                f"User {escalated_by.username} (role: {escalated_by.role}) cannot escalate tickets"
            )

        # Check ticket status allows escalation
        if ticket.status in ["resolved", "closed"]:
            raise ValidationError(
                f"Cannot escalate resolved or closed ticket {ticket.ticket_no}"
            )

        # Check max escalation level not exceeded
        if ticket.escalation_level >= 2:
            # Return ticket unchanged if already at maximum escalation level
            return ticket

        with transaction.atomic():
            # Use model's atomic helper
            ticket.escalate(
                escalated_by=escalated_by, reason=reason, is_auto_escalation=not manual
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
        notes: Optional[str] = None,
        pending_reason: Optional[str] = None,
        pending_comment: Optional[str] = None,
    ) -> Ticket:
        """
        Update ticket status with proper validation and logging.

        Validates status transitions and ensures user has permission.

        Args:
            ticket: Ticket to update
            new_status: New status value
            updated_by: User performing the update
            notes: Optional notes about the status change
            pending_reason: Reason if marking as PENDING (required for PENDING status)
            pending_comment: Comment if marking as PENDING (required for PENDING status)

        Returns:
            Updated Ticket object

        Raises:
            DRFPermissionDenied: User lacks permission to change status
            ValidationError: Invalid status transition or missing PENDING fields
        """
        old_status = ticket.status

        # Validate status transition
        is_valid, error_msg = validate_status_transition(
            old_status, new_status, updated_by.role
        )
        if not is_valid:
            raise ValidationError(error_msg)

        # Validate pending fields if marking as PENDING
        if new_status == "pending":
            is_valid, error_msg = validate_pending_transition(
                new_status, pending_reason, pending_comment
            )
            if not is_valid:
                raise ValidationError(error_msg)

        # Check permission for this specific transition
        if new_status == "closed" and updated_by.role not in [
            "admin",
            "manager",
            "user",
        ]:
            raise DRFPermissionDenied(
                "Only admins/managers or ticket raiser can close tickets"
            )

        # Perform status change
        with transaction.atomic():
            ticket.change_status(new_status, performed_by=updated_by)

            # Set pending fields if applicable
            if new_status == "pending":
                ticket.pending_reason = pending_reason
                ticket.pending_comment = pending_comment
                ticket.save()

            # Log additional context if provided
            if notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f"{old_status} → {new_status}: {notes}",
                    performed_by=updated_by,
                )

        if new_status == "resolved":
            EmailService.send_ticket_resolved(ticket)

        return ticket

    @staticmethod
    def approve_ticket(
        ticket: Ticket,
        approved_by: CustomUser,
        notes: Optional[str] = None,
    ) -> Ticket:
        """
        Approve a ticket that is in pending_approval status.

        Only hod, manager, or admin may approve. Manager bypass is intentional:
        change_status() blocks managers for regular workflow transitions, but
        approval is a distinct privileged action, so we update the DB directly.

        Raises:
            DRFPermissionDenied: approver role is not authorised
            DRFValidationError: ticket is not in pending_approval status
        """
        if approved_by.role not in ["hod", "manager", "admin"]:
            raise DRFPermissionDenied(
                "Only HOD, manager, or admin can approve tickets"
            )
        if ticket.status != "pending_approval":
            raise DRFValidationError(
                f"Only pending_approval tickets can be approved. "
                f"Current status: '{ticket.status}'"
            )

        action = f"approved: {notes}" if notes else "approved"

        with transaction.atomic():
            Ticket.objects.filter(pk=ticket.pk).update(
                status="approved", updated_at=timezone.now()
            )
            TicketLog.objects.create(
                ticket=ticket, action=action, performed_by=approved_by
            )

        ticket.refresh_from_db()
        return ticket

    @staticmethod
    def reject_ticket(
        ticket: Ticket,
        rejected_by: CustomUser,
        reason: str,
    ) -> Ticket:
        """
        Reject a ticket that is in pending_approval status.

        Only hod, manager, or admin may reject. Reason is required and stored
        in TicketLog so the requester can see why their request was declined.

        Raises:
            DRFPermissionDenied: rejector role is not authorised
            DRFValidationError: ticket is not in pending_approval, or reason missing
        """
        if rejected_by.role not in ["hod", "manager", "admin"]:
            raise DRFPermissionDenied(
                "Only HOD, manager, or admin can reject tickets"
            )
        if ticket.status != "pending_approval":
            raise DRFValidationError(
                f"Only pending_approval tickets can be rejected. "
                f"Current status: '{ticket.status}'"
            )
        if not reason or not reason.strip():
            raise DRFValidationError("Rejection reason is required")

        with transaction.atomic():
            Ticket.objects.filter(pk=ticket.pk).update(
                status="rejected", updated_at=timezone.now()
            )
            TicketLog.objects.create(
                ticket=ticket,
                action=f"rejected: {reason.strip()}",
                performed_by=rejected_by,
            )

        ticket.refresh_from_db()
        EmailService.send_ticket_rejected(ticket, reason.strip())
        return ticket

    @staticmethod
    def bulk_update_status(
        ticket_ids: list,
        new_status: str,
        updated_by: CustomUser,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update status for multiple tickets in two DB round-trips: one bulk UPDATE
        and one bulk INSERT for logs, instead of one transaction per ticket.
        """
        if not isinstance(ticket_ids, list):
            ticket_ids = [ticket_ids]

        results = {
            "success": len(ticket_ids) > 0,
            "total": len(ticket_ids),
            "updated": 0,
            "failed": 0,
            "errors": [],
        }

        tickets = list(
            Ticket.objects.filter(id__in=ticket_ids).only(
                "id", "ticket_no", "status")
        )

        found_ids = {t.id for t in tickets}
        for missing_id in set(ticket_ids) - found_ids:
            results["failed"] += 1
            results["success"] = False
            results["errors"].append(
                {
                    "ticket_id": missing_id,
                    "error": f"Ticket with ID {missing_id} not found",
                }
            )

        valid_tickets = []
        for ticket in tickets:
            if ticket.status == new_status:
                results["updated"] += 1
                continue
            is_valid, error_msg = validate_status_transition(
                ticket.status, new_status, updated_by.role
            )
            if is_valid:
                valid_tickets.append(ticket)
            else:
                results["failed"] += 1
                results["success"] = False
                results["errors"].append(
                    {
                        "ticket_id": ticket.id,
                        "ticket_no": ticket.ticket_no,
                        "error": error_msg,
                    }
                )

        if valid_tickets:
            valid_ids = [t.id for t in valid_tickets]
            now = timezone.now()

            update_kwargs = {"status": new_status, "updated_at": now}
            if new_status in ["resolved", "closed"]:
                update_kwargs["resolved_at"] = now
            if new_status == "closed":
                update_kwargs["closed_at"] = now

            action = f"Bulk status update to '{new_status}'"
            if reason:
                action += f": {reason}"

            with transaction.atomic():
                Ticket.objects.filter(id__in=valid_ids).update(**update_kwargs)
                TicketLog.objects.bulk_create(
                    [
                        TicketLog(
                            ticket_id=t.id, action=action, performed_by=updated_by
                        )
                        for t in valid_tickets
                    ]
                )

            results["updated"] += len(valid_tickets)

        return results

    # ========================================================================
    # TICKET CLOSURE
    # ========================================================================

    @staticmethod
    def close_ticket(
        ticket: Ticket, closed_by: CustomUser, closure_notes: Optional[str] = None
    ) -> Ticket:
        """
        Close a resolved ticket.

        Allowed for:
        - Ticket raiser (user who created the ticket)
        - Admin or manager roles

        Args:
            ticket: Ticket to close
            closed_by: User closing the ticket
            closure_notes: Optional notes about closure

        Returns:
            Updated Ticket object

        Raises:
            DRFPermissionDenied: User is not authorized to close
            DRFValidationError: Ticket is not resolved
        """
        # Check permission - allow requester OR admin/manager
        if closed_by.role == "user":
            # User can only close their own tickets
            if ticket.raised_by != closed_by:
                raise DRFPermissionDenied(
                    "Only the ticket creator or administrators can close this ticket"
                )
        elif closed_by.role not in ["admin", "manager"]:
            raise DRFPermissionDenied(
                f"Only ticket raiser, admins, or managers can close tickets, not {closed_by.role}"
            )

        # Check ticket is resolved
        if ticket.status != "resolved":
            raise DRFValidationError(
                f"Only resolved tickets can be closed. Ticket {ticket.ticket_no} is '{ticket.status}'"
            )

        with transaction.atomic():
            # Use model's atomic helper
            ticket.change_status("closed", performed_by=closed_by)

            # Log closure details
            if closure_notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f"closed - {closure_notes}",
                    performed_by=closed_by,
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

        Only considers tickets that have been assigned (assigned_at IS NOT NULL).
        Unassigned tickets are excluded from escalation processing.

        Returns:
            Dictionary with escalation statistics:
            {
                'processed': count,
                'escalated': count,
                'failed': count,
                'errors': [list of error messages]
            }
        """
        stats = {"processed": 0, "escalated": 0, "failed": 0, "errors": []}

        # Find all tickets due for auto-escalation
        # Must be assigned (assigned_at IS NOT NULL) to be considered for escalation
        tickets_due = Ticket.objects.filter(
            auto_escalation_enabled=True,
            assigned_at__isnull=False,  # Only assigned tickets
            next_escalation_due__lte=timezone.now(),
            status__in=["open", "assigned", "in_progress", "pending"],
        ).exclude(
            escalation_level=2
        )  # Don't escalate beyond HOD

        for ticket in tickets_due:
            stats["processed"] += 1
            try:
                # Get system user for auto-escalation
                system_user = TicketService._get_system_user()

                # Escalate ticket
                TicketService.escalate_ticket(
                    ticket=ticket,
                    escalated_by=system_user,
                    reason="Automatic escalation due to timeout",
                    manual=False,
                )

                stats["escalated"] += 1

                # Log auto-escalation event
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f"auto_escalated to level {ticket.escalation_level}",
                    performed_by=system_user,
                )

            except Exception as e:
                stats["failed"] += 1
                error_msg = f"Failed to escalate ticket {ticket.ticket_no}: {str(e)}"
                stats["errors"].append(error_msg)

        return stats

    # ========================================================================
    # TICKET RETRIEVAL & FILTERING
    # ========================================================================

    @staticmethod
    def get_accessible_tickets(
        user: CustomUser, filters: Optional[Dict] = None
    ) -> List[Ticket]:
        """
        Get all tickets user can access based on organizational scope.

        Args:
            user: User requesting tickets
            filters: Optional additional filters (status, priority, etc.)

        Returns:
            Queryset of accessible Ticket objects
        """
        if user.role == "admin":
            # Admin can see all tickets
            queryset = Ticket.objects.all()
        elif user.role == "manager":
            # Manager sees their department's tickets across all campuses in the org
            if user.primary_department:
                dept_code = user.primary_department.code
                org = user.primary_department.campus.organization
                queryset = Ticket.objects.filter(
                    section__department__code=dept_code,
                    section__department__campus__organization=org,
                )
            else:
                queryset = Ticket.objects.none()
        elif user.role == "hod":
            # HOD can see all tickets in their department
            if user.primary_department:
                queryset = Ticket.objects.filter(
                    section__department=user.primary_department
                )
            else:
                queryset = Ticket.objects.none()
        elif user.role == "head_of_section":
            # Section head can see all tickets in sections they manage
            # They manage sections via Section.head_of_section FK
            queryset = Ticket.objects.filter(section__head_of_section=user)
        elif user.role == "technician":
            # Technician can see tickets in their sections or assigned to them
            queryset = (
                Ticket.objects.filter(section__in=user.sections.all())
                | Ticket.objects.filter(assigned_to=user)
                | Ticket.objects.filter(raised_by=user)
            )
        else:  # user role
            # Users can only see their own tickets
            queryset = Ticket.objects.filter(raised_by=user)

        # Apply additional filters if provided
        if filters:
            if "status" in filters:
                queryset = queryset.filter(status=filters["status"])
            if "section_id" in filters:
                queryset = queryset.filter(section_id=filters["section_id"])
            if "facility_id" in filters:
                queryset = queryset.filter(facility_id=filters["facility_id"])
            if "escalation_level" in filters:
                queryset = queryset.filter(
                    escalation_level=filters["escalation_level"])

        return (
            queryset.select_related(
                "section", "facility", "raised_by", "assigned_to", "escalated_to"
            )
            .distinct()
            .order_by("-created_at")
        )

    # ========================================================================
    # COMMENTS
    # ========================================================================

    @staticmethod
    def create_comment(serializer, user: CustomUser, ticket_id: int) -> Comment:
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
            ticket=ticket, performed_by=user, action=f"Comment added by {user.username}"
        )

        return comment

    # ========================================================================
    # FEEDBACK
    # ========================================================================

    @staticmethod
    def create_feedback(serializer, user: CustomUser, ticket_id: int) -> Feedback:
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
                "The ticket has to be resolved to rate the job.")

        # Prevent duplicate feedback for the same ticket
        if Feedback.objects.filter(ticket=ticket).exists():
            raise DRFValidationError(
                "Feedback has already been submitted for this ticket."
            )

        feedback = serializer.save(rated_by=user, ticket=ticket)

        TicketLog.objects.create(
            ticket=ticket,
            performed_by=user,
            action=f"Feedback ({serializer.validated_data.get('rating', '?')}/5) added by {user.username}",
        )

        return feedback

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    @staticmethod
    def _user_can_access_section(user: CustomUser, section: Section) -> bool:
        """Check if user has access to section based on role and organizational scope"""
        if user.role == "admin":
            return True

        if not section or not section.department or not section.department.campus:
            return False

        if user.role == "manager":
            return (
                section.department.campus.organization
                == user.primary_campus.organization
            )
        elif user.role == "hod":
            return section.department.campus == user.primary_campus
        elif user.role == "head_of_section":
            return section.department == user.primary_department
        elif user.role in ["technician", "user"]:
            return section in user.sections.all()

        return False

    @staticmethod
    def _user_can_access_facility(user: CustomUser, facility: Facility) -> bool:
        """Check if user has access to facility based on role and organizational scope"""
        if user.role == "admin":
            return True

        if not facility.campus:
            return False

        if user.role == "manager":
            return facility.campus.organization == user.primary_campus.organization
        elif user.role in ["hod", "head_of_section"]:
            return facility.campus == user.primary_campus
        elif user.role in ["technician", "user"]:
            return facility.campus == user.primary_campus

        return False

    @staticmethod
    def _get_system_user() -> CustomUser:
        """Get or create system user for automated operations"""
        user, _ = CustomUser.objects.get_or_create(
            username="system",
            defaults={
                "first_name": "System",
                "last_name": "User",
                "email": "system@example.com",
                "role": "admin",
                "is_staff": True,
            },
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
            if ticket.section and ticket.section.head_of_section:
                # Log notification event (actual email sending handled elsewhere)
                TicketLog.objects.create(
                    ticket=ticket,
                    action="notification: ticket created",
                    performed_by=ticket.raised_by,
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
                    action=f"notification: escalated to {ticket.escalated_to.username}",
                    performed_by=ticket.raised_by,
                )
        except Exception as e:
            # Log notification error but don't fail the escalation
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to notify on ticket escalation {ticket.ticket_no}: {str(e)}"
            )
