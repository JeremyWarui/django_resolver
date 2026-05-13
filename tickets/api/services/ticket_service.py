"""Ticket service — business logic for ticket operations with organisational validation."""

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
    TicketLog,
    Comment,
    Feedback,
    CustomUser,
    CampusDepartment,
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
from .validators import validate_status_transition, validate_pending_transition

import logging
logger = logging.getLogger(__name__)


class TicketService:
    """
    Central service for ticket operations with organisational hierarchy validation.

    Enforces:
    - Role-based access (user, technician, head_of_section, hod, manager, admin)
    - Scope boundaries: section → CampusDepartment → campus
    - Status-machine transitions and pending-state requirements
    - Escalation rules: level 0→head_of_section, level 1→head_of_department (max)
    - Assignment rules: technician must be linked to ticket's section
    """

    # =========================================================================
    # TICKET CREATION
    # =========================================================================

    @staticmethod
    def create_ticket(
        data: Dict,
        created_by: CustomUser,
        section: Optional[Section] = None,
        facility: Optional[Facility] = None,
        enable_auto_escalation: bool = True,
    ) -> Ticket:
        """Create a ticket with organisational validation.

        Resolution flow when `section` is not provided:
          service_item → category → section_type → department
          + created_by.primary_campus
          → CampusDepartment
          → Section

        Raises:
            InsufficientScopeException: user lacks access to the resolved section/facility
            DRFValidationError: missing required data or no matching section found
        """
        campus_department: Optional[CampusDepartment] = None

        if section is None:
            service_item = data.get("service_item")
            if not service_item:
                raise DRFValidationError(
                    "service_item is required when section is not provided."
                )

            if not created_by.primary_campus:
                raise DRFValidationError(
                    "User has no primary campus; cannot resolve section automatically."
                )

            # Walk: service_item → category → section_type → department
            section_type = service_item.category.section_type
            department = section_type.department

            campus_department = CampusDepartment.objects.filter(
                campus=created_by.primary_campus,
                department=department,
            ).first()
            if not campus_department:
                raise DRFValidationError(
                    f"No CampusDepartment found for campus '{created_by.primary_campus.code}' "
                    f"and department '{department.code}'."
                )

            section = (
                Section.objects.filter(
                    campus_department=campus_department,
                    section_type=section_type,
                )
                .order_by("id")
                .first()
            )
            if not section:
                raise DRFValidationError(
                    f"No '{section_type.name}' section found under "
                    f"{campus_department}."
                )
        else:
            campus_department = section.campus_department

        # Scope check
        if not TicketService._user_can_access_section(created_by, section):
            raise InsufficientScopeException(
                f"User '{created_by.username}' lacks access to section '{section.name}'."
            )

        if facility and not TicketService._user_can_access_facility(created_by, facility):
            raise InsufficientScopeException(
                f"User '{created_by.username}' lacks access to facility '{facility.name}'."
            )

        service_item = data.get("service_item")
        initial_status = (
            "pending_approval"
            if service_item and service_item.requires_approval
            else "open"
        )

        with transaction.atomic():
            ticket = Ticket.objects.create(
                title=data.get("title"),
                description=data.get("description"),
                campus_department=campus_department,
                section=section,
                facility=facility,
                raised_by=created_by,
                service_item=service_item,
                form_data=data.get("form_data"),
                location_detail=data.get("location_detail", ""),
                auto_escalation_enabled=enable_auto_escalation,
                status=initial_status,
            )
            TicketLog.objects.create(
                ticket=ticket, action="created", performed_by=created_by
            )
            TicketService._notify_ticket_creation(ticket)
            if ticket.status == "pending_approval":
                EmailService.send_ticket_pending_approval(ticket)

        return ticket

    # =========================================================================
    # TICKET ASSIGNMENT
    # =========================================================================

    @staticmethod
    def assign_ticket(
        ticket: Ticket, technician: CustomUser, assigned_by: CustomUser
    ) -> Ticket:
        """Assign a ticket to a technician with organisational validation.

        Raises:
            DRFPermissionDenied: assigner role is not authorised
            InsufficientScopeException: assigner is outside the ticket's scope
            InvalidAssignmentException: technician is ineligible
        """
        ASSIGNABLE_ROLES = {"head_of_section", "hod", "manager", "admin"}
        if assigned_by.role not in ASSIGNABLE_ROLES:
            raise DRFPermissionDenied(
                f"Role '{assigned_by.role}' cannot assign tickets."
            )

        if not TicketService._user_can_access_section(assigned_by, ticket.section):
            raise InsufficientScopeException(
                f"'{assigned_by.username}' lacks access to the ticket's section."
            )

        if technician.role != "technician":
            raise InvalidAssignmentException(
                f"'{technician.username}' is not a technician (role: {technician.role})."
            )

        if not technician.is_active:
            raise InvalidAssignmentException(
                f"Technician '{technician.username}' is not active."
            )

        # Technician must be linked to the ticket's section
        if ticket.section and not technician.sections.filter(pk=ticket.section_id).exists():
            raise InvalidAssignmentException(
                f"'{technician.username}' is not assigned to section '{ticket.section.name}'."
            )

        # Technician must be on the same campus as the ticket
        ticket_campus = ticket.campus_department.campus
        if technician.primary_campus and technician.primary_campus != ticket_campus:
            raise InvalidAssignmentException(
                f"'{technician.username}' is on campus "
                f"'{technician.primary_campus.code}', but the ticket belongs to "
                f"'{ticket_campus.code}'."
            )

        if ticket.status in Ticket.TERMINAL_STATUSES:
            raise InvalidAssignmentException(
                f"Cannot assign a ticket in '{ticket.status}' status."
            )

        with transaction.atomic():
            ticket.change_assignment(technician, performed_by=assigned_by)

        EmailService.send_ticket_assigned(ticket, technician)
        return ticket

    # =========================================================================
    # TICKET ESCALATION
    # =========================================================================

    @staticmethod
    def escalate_ticket(
        ticket: Ticket, escalated_by: CustomUser, reason: str, manual: bool = True
    ) -> Ticket:
        """Escalate to the next level in the chain (max: head_of_department).

        Chain:
          level 0 → section.head_of_section
          level 1 → campus_department.head_of_department  [MAXIMUM]

        Raises:
            DRFPermissionDenied: role is not authorised to escalate
            ValidationError: ticket is terminal or already at max level
        """
        ESCALATABLE_ROLES = {"technician", "head_of_section", "hod", "admin"}
        if escalated_by.role not in ESCALATABLE_ROLES:
            raise DRFPermissionDenied(
                f"Role '{escalated_by.role}' cannot escalate tickets."
            )

        if ticket.status in Ticket.TERMINAL_STATUSES:
            raise ValidationError(
                f"Cannot escalate a '{ticket.status}' ticket ({ticket.ticket_no})."
            )

        if ticket.escalation_level >= 2:
            return ticket  # already at maximum

        with transaction.atomic():
            ticket.escalate(
                escalated_by=escalated_by,
                reason=reason,
                is_auto_escalation=not manual,
            )
            TicketService._notify_escalation(ticket)

        return ticket

    # =========================================================================
    # TICKET STATUS UPDATES
    # =========================================================================

    @staticmethod
    def update_ticket_status(
        ticket: Ticket,
        new_status: str,
        updated_by: CustomUser,
        notes: Optional[str] = None,
        pending_reason: Optional[str] = None,
        pending_comment: Optional[str] = None,
    ) -> Ticket:
        """Update ticket status with transition validation.

        Raises:
            DRFPermissionDenied: role is not authorised for this transition
            ValidationError: invalid transition or missing pending fields
        """
        old_status = ticket.status

        is_valid, error_msg = validate_status_transition(old_status, new_status, updated_by.role)
        if not is_valid:
            raise ValidationError(error_msg)

        if new_status == "pending":
            is_valid, error_msg = validate_pending_transition(
                new_status, pending_reason, pending_comment
            )
            if not is_valid:
                raise ValidationError(error_msg)

        if new_status == "closed" and updated_by.role not in ("admin", "manager", "user"):
            raise DRFPermissionDenied(
                "Only the ticket raiser, admin, or manager can close tickets."
            )

        with transaction.atomic():
            ticket.change_status(new_status, performed_by=updated_by)

            if new_status == "pending":
                ticket.pending_reason = pending_reason
                ticket.pending_comment = pending_comment
                ticket.save(update_fields=["pending_reason", "pending_comment"])

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
        """Approve a pending_approval ticket.

        Only hod, manager, or admin may approve. Uses a direct ORM update so
        that `change_status()` — which blocks managers — is bypassed for this
        privileged action.

        Raises:
            DRFPermissionDenied: approver role not authorised
            DRFValidationError: ticket is not in pending_approval
        """
        if approved_by.role not in ("hod", "manager", "admin"):
            raise DRFPermissionDenied("Only HOD, manager, or admin can approve tickets.")

        if ticket.status != "pending_approval":
            raise DRFValidationError(
                f"Only pending_approval tickets can be approved. Current: '{ticket.status}'."
            )

        action = f"approved: {notes}" if notes else "approved"
        with transaction.atomic():
            Ticket.objects.filter(pk=ticket.pk).update(
                status="open", updated_at=timezone.now()
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
        """Reject a pending_approval ticket.

        Raises:
            DRFPermissionDenied: rejector role not authorised
            DRFValidationError: ticket not in pending_approval, or reason missing
        """
        if rejected_by.role not in ("hod", "manager", "admin"):
            raise DRFPermissionDenied("Only HOD, manager, or admin can reject tickets.")

        if ticket.status != "pending_approval":
            raise DRFValidationError(
                f"Only pending_approval tickets can be rejected. Current: '{ticket.status}'."
            )

        if not reason or not reason.strip():
            raise DRFValidationError("Rejection reason is required.")

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
        """Update status for multiple tickets in two DB round-trips."""
        if not isinstance(ticket_ids, list):
            ticket_ids = [ticket_ids]

        results = {
            "success": bool(ticket_ids),
            "total": len(ticket_ids),
            "updated": 0,
            "failed": 0,
            "errors": [],
        }

        tickets = list(
            Ticket.objects.filter(id__in=ticket_ids).only("id", "ticket_no", "status")
        )
        found_ids = {t.id for t in tickets}

        for missing_id in set(ticket_ids) - found_ids:
            results["failed"] += 1
            results["success"] = False
            results["errors"].append(
                {"ticket_id": missing_id, "error": f"Ticket {missing_id} not found."}
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
                    {"ticket_id": ticket.id, "ticket_no": ticket.ticket_no, "error": error_msg}
                )

        if valid_tickets:
            now = timezone.now()
            update_kwargs = {"status": new_status, "updated_at": now}
            if new_status in Ticket.TERMINAL_STATUSES:
                update_kwargs["resolved_at"] = now
            if new_status == "closed":
                update_kwargs["closed_at"] = now

            action = f"Bulk status update to '{new_status}'"
            if reason:
                action += f": {reason}"

            with transaction.atomic():
                Ticket.objects.filter(id__in=[t.id for t in valid_tickets]).update(
                    **update_kwargs
                )
                TicketLog.objects.bulk_create(
                    [
                        TicketLog(ticket_id=t.id, action=action, performed_by=updated_by)
                        for t in valid_tickets
                    ]
                )
            results["updated"] += len(valid_tickets)

        return results

    # =========================================================================
    # TICKET CLOSURE
    # =========================================================================

    @staticmethod
    def close_ticket(
        ticket: Ticket, closed_by: CustomUser, closure_notes: Optional[str] = None
    ) -> Ticket:
        """Close a resolved ticket.

        Permitted for: ticket raiser, admin, manager.

        Raises:
            DRFPermissionDenied: caller is not authorised
            DRFValidationError: ticket is not resolved
        """
        if closed_by.role == "user":
            if ticket.raised_by != closed_by:
                raise DRFPermissionDenied(
                    "Users can only close their own tickets."
                )
        elif closed_by.role not in ("admin", "manager"):
            raise DRFPermissionDenied(
                f"Role '{closed_by.role}' cannot close tickets."
            )

        if ticket.status != "resolved":
            raise DRFValidationError(
                f"Only resolved tickets can be closed. Current: '{ticket.status}'."
            )

        with transaction.atomic():
            ticket.change_status("closed", performed_by=closed_by)
            if closure_notes:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f"closed: {closure_notes}",
                    performed_by=closed_by,
                )

        return ticket

    # =========================================================================
    # AUTO-ESCALATION
    # =========================================================================

    @staticmethod
    def process_auto_escalations() -> Dict[str, Any]:
        """Process all tickets due for automatic escalation.

        Only considers assigned tickets (assigned_at IS NOT NULL).
        Run periodically via management command or cron.
        """
        stats = {"processed": 0, "escalated": 0, "failed": 0, "errors": []}

        tickets_due = Ticket.objects.filter(
            auto_escalation_enabled=True,
            assigned_at__isnull=False,
            next_escalation_due__lte=timezone.now(),
            status__in=("open", "assigned", "in_progress", "pending"),
        ).exclude(escalation_level__gte=2)

        system_user = TicketService._get_system_user()

        for ticket in tickets_due:
            stats["processed"] += 1
            try:
                TicketService.escalate_ticket(
                    ticket=ticket,
                    escalated_by=system_user,
                    reason="Automatic escalation due to timeout.",
                    manual=False,
                )
                stats["escalated"] += 1
            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append(
                    f"Failed to escalate {ticket.ticket_no}: {e}"
                )

        return stats

    # =========================================================================
    # TICKET RETRIEVAL & FILTERING
    # =========================================================================

    @staticmethod
    def get_accessible_tickets(
        user: CustomUser, filters: Optional[Dict] = None
    ) -> List[Ticket]:
        """Return the tickets this user is permitted to see.

        Scope rules:
        - admin       → all tickets
        - manager     → all tickets whose department matches the manager's primary_department
        - hod         → all tickets on their primary_campus
        - head_of_section → tickets in sections they head
        - technician  → tickets in their assigned sections + assigned to them + raised by them
        - user        → only their own tickets
        """
        if user.role == "admin":
            queryset = Ticket.objects.all()

        elif user.role == "manager":
            # Department-wide across all campuses
            if user.primary_department:
                queryset = Ticket.objects.filter(
                    campus_department__department=user.primary_department
                )
            else:
                queryset = Ticket.objects.none()

        elif user.role == "hod":
            if user.primary_campus:
                queryset = Ticket.objects.filter(
                    campus_department__campus=user.primary_campus
                )
            else:
                queryset = Ticket.objects.none()

        elif user.role == "head_of_section":
            queryset = Ticket.objects.filter(section__head_of_section=user)

        elif user.role == "technician":
            queryset = (
                Ticket.objects.filter(section__in=user.sections.all())
                | Ticket.objects.filter(assigned_to=user)
                | Ticket.objects.filter(raised_by=user)
            )

        else:  # user
            queryset = Ticket.objects.filter(raised_by=user)

        if filters:
            if "status" in filters:
                queryset = queryset.filter(status=filters["status"])
            if "section_id" in filters:
                queryset = queryset.filter(section_id=filters["section_id"])
            if "facility_id" in filters:
                queryset = queryset.filter(facility_id=filters["facility_id"])
            if "escalation_level" in filters:
                queryset = queryset.filter(escalation_level=filters["escalation_level"])

        return (
            queryset.select_related(
                "campus_department__campus",
                "campus_department__department",
                "campus_department__head_of_department",
                "section__head_of_section",
                "section__section_type",
                "facility",
                "raised_by",
                "assigned_to",
                "escalated_to",
                "service_item",
            )
            .distinct()
            .order_by("-created_at")
        )

    # =========================================================================
    # COMMENTS
    # =========================================================================

    @staticmethod
    def create_comment(serializer, user: CustomUser, ticket_id: int) -> Comment:
        """Attach author and ticket to a new comment and log the action."""
        ticket = get_object_or_404(Ticket, id=ticket_id)
        if ticket.status == "closed":
            raise DRFValidationError("Cannot add comments to a closed ticket.")
        comment = serializer.save(author=user, ticket=ticket)
        TicketLog.objects.create(
            ticket=ticket,
            performed_by=user,
            action=f"Comment added by {user.username}",
        )
        return comment

    # =========================================================================
    # FEEDBACK
    # =========================================================================

    @staticmethod
    def create_feedback(serializer, user: CustomUser, ticket_id: int) -> Feedback:
        """Ensure only the ticket raiser can submit feedback on a resolved ticket."""
        ticket = get_object_or_404(Ticket, id=ticket_id)

        if ticket.raised_by != user:
            raise DRFPermissionDenied("Only the ticket raiser can give feedback.")
        if ticket.status == "closed":
            raise DRFValidationError("Cannot provide feedback on a closed ticket.")
        if ticket.status != "resolved":
            raise DRFValidationError("Ticket must be resolved before feedback can be given.")
        if Feedback.objects.filter(ticket=ticket).exists():
            raise DRFValidationError("Feedback has already been submitted for this ticket.")

        feedback = serializer.save(rated_by=user, ticket=ticket)
        TicketLog.objects.create(
            ticket=ticket,
            performed_by=user,
            action=f"Feedback ({serializer.validated_data.get('rating', '?')}/5) by {user.username}",
        )
        return feedback

    # =========================================================================
    # HELPERS
    # =========================================================================

    @staticmethod
    def _user_can_access_section(user: CustomUser, section: Optional[Section]) -> bool:
        """Return True if the user is permitted to act on the given section."""
        if user.role == "admin":
            return True
        if not section:
            return False

        if user.role == "manager":
            # Manager: any section whose department matches theirs
            return (
                user.primary_department is not None
                and section.campus_department.department == user.primary_department
            )
        if user.role == "hod":
            return section.campus_department.campus == user.primary_campus
        if user.role == "head_of_section":
            return section.head_of_section == user
        if user.role in ("technician", "user"):
            return section in user.sections.all()

        return False

    @staticmethod
    def _user_can_access_facility(user: CustomUser, facility: Facility) -> bool:
        """Return True if the user is permitted to act on the given facility."""
        if user.role == "admin":
            return True
        if user.role == "manager":
            return True  # managers have organisation-wide access
        if not facility.campus:
            return False
        return facility.campus == user.primary_campus

    @staticmethod
    def _get_system_user() -> CustomUser:
        """Get or create the system user used for automated operations."""
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
        """Log a notification event when a ticket is created (email handled by email_service)."""
        try:
            if ticket.section and ticket.section.head_of_section:
                TicketLog.objects.create(
                    ticket=ticket,
                    action="notification: ticket created",
                    performed_by=ticket.raised_by,
                )
        except Exception as exc:
            logger.error("Failed to notify on ticket creation %s: %s", ticket.ticket_no, exc)

    @staticmethod
    def _notify_escalation(ticket: Ticket) -> None:
        """Log a notification event when a ticket is escalated."""
        try:
            if ticket.escalated_to:
                TicketLog.objects.create(
                    ticket=ticket,
                    action=f"notification: escalated to {ticket.escalated_to.username}",
                    performed_by=ticket.raised_by,
                )
        except Exception as exc:
            logger.error("Failed to notify on ticket escalation %s: %s", ticket.ticket_no, exc)
