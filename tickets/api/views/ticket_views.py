"""
Ticket Views

Covers: TicketListCreateView, TicketCreateView, TicketDetailView,
TicketEscalationView, TicketCloseView, ApproveTicketView, RejectTicketView,
BulkTicketStatusUpdateView, OrganizationalTicketListView.
"""

from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    CreateAPIView,
    ListAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch, Count, Q
from django.utils import timezone
from datetime import timedelta

from tickets.api.permissions import (
    IsWithinOrganizationalScope,
    CanEscalateTickets,
    CanManageUsers,
    CanViewAndEditTickets,
    CanCloseTicket,
)
from tickets.serializers import (
    TicketSerializer,
    TicketListSerializer,
    TicketCreateSerializer,
    CommentSerializer,
    FeedbackSerializer,
    format_user_info,
)
from tickets.api.services import (
    TicketService,
    validate_status_transition,
    InsufficientScopeException,
    InvalidAssignmentException,
    InvalidEscalationException,
)
from tickets.models import (
    CampusDepartment,
    Section,
    SectionType,
    Ticket,
    TicketLog,
    Comment,
    Feedback,
    CustomUser,
)
from tickets.pagination import TicketPagination

# ============================================================================
# TICKETS API - ORGANIZATIONAL
# ============================================================================


class TicketListCreateView(ListCreateAPIView):
    """
    List and create tickets with organizational scope awareness.

    Supports filtering by:
    - status: open, assigned, in_progress, pending, resolved, closed, escalated
    - section_id: specific section
    - assigned_to_id: assigned technician
    - escalation_level: 0 (none), 1 (section_head), 2 (hod)
    - is_overdue: boolean (tickets >7 days old)

    Respects organizational hierarchy:
    - Admin: sees all tickets
    - Manager: sees organization-wide tickets
    - HOD: sees campus-level tickets
    - Section Head: sees department-level tickets
    - Technician/User: sees accessible section-level tickets
    """

    queryset = Ticket.objects.all().order_by("-updated_at")
    pagination_class = TicketPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = [
        "status",
        "section",
        "assigned_to",
        "raised_by",
        "escalation_level",
    ]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-updated_at"]  # Default ordering
    permission_classes = [CanViewAndEditTickets, IsAuthenticated]

    def get_serializer_class(self):
        """Use optimized serializer for list, full serializer for create."""
        if self.request.method == "GET":
            return TicketListSerializer  # Fast list serializer
        return TicketSerializer  # Full serializer for create

    def get_queryset(self):
        """
        Filter tickets based on user's organizational scope using service layer
        """
        user = self.request.user
        if not user.is_authenticated:
            return Ticket.objects.none()

        # Use service layer for consistent scope filtering across the app
        filters = {}

        # Extract filter parameters from query string
        status = self.request.query_params.get("status")
        if status:
            filters["status"] = status

        escalation_level = self.request.query_params.get("escalation_level")
        if escalation_level:
            filters["escalation_level"] = escalation_level

        # Get tickets accessible to user based on organizational scope
        queryset = TicketService.get_accessible_tickets(user, filters)

        # Handle additional custom filters
        assigned_to_isnull = self.request.query_params.get(
            "assigned_to__isnull", None)
        if assigned_to_isnull and assigned_to_isnull.lower() == "true":
            queryset = queryset.filter(assigned_to__isnull=True)

        # Handle overdue filter
        is_overdue = self.request.query_params.get("is_overdue", None)
        if is_overdue and is_overdue.lower() == "true":
            # Define overdue as tickets >7 days old in active states
            seven_days_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(
                created_at__lt=seven_days_ago,
                status__in=["open", "assigned", "in_progress"],
            )

        return queryset

    def perform_create(self, serializer):
        """Create ticket using organizational service layer"""
        try:
            user = self.request.user
            # Get section and facility from validated data (which contains the deserialized objects)
            section = serializer.validated_data.get("section")
            facility = serializer.validated_data.get("facility")

            # Use organizational service to create ticket and get the instance.
            # `section` may be omitted by the client; service will resolve it from
            # catalogue fields (service_category/service_item) using the user's campus.
            ticket = TicketService.create_ticket(
                data=serializer.validated_data,
                created_by=user,
                section=serializer.validated_data.get("section"),
                facility=facility,
                enable_auto_escalation=serializer.validated_data.get(
                    "auto_escalation_enabled", True
                ),
            )

            # Set the created instance on the serializer so response includes it
            serializer.instance = ticket
        except InsufficientScopeException as e:
            raise serializers.ValidationError(str(e))
        except Exception as e:
            raise serializers.ValidationError(
                f"Failed to create ticket: {str(e)}")


class TicketCreateView(CreateAPIView):
    """POST /api/tickets/create/

    Dedicated ticket creation endpoint with automatic section resolution.

    Resolution flow
    ---------------
    1. CampusDepartment  ← user.primary_campus  +  department_id
    2. SectionType       ← service_item → category → section_type
    3. Section           ← CampusDepartment  +  SectionType

    Eligibility
    -----------
    Eligible assignees are technicians who satisfy ALL of:
    - linked to the resolved Section via TechnicianSection
    - primary_campus matches the user's campus
    - role == "technician" and is_active == True

    Response
    --------
    Returns the created ticket plus resolved context so the frontend can
    display the assigned HOD, HOS, section, and eligible technicians
    without additional round-trips.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TicketCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        user = request.user

        if not user.primary_campus:
            raise ValidationError(
                {"non_field_errors": ["No primary campus assigned to your account. Contact your administrator."]}
            )

        department = vd["department"]
        service_item = vd.get("service_item")

        # ── 1. Resolve CampusDepartment ──────────────────────────────────────
        campus_department = (
            CampusDepartment.objects
            .select_related("campus", "department", "head_of_department")
            .filter(campus=user.primary_campus, department=department)
            .first()
        )
        if not campus_department:
            raise ValidationError({
                "department_id": (
                    f"'{department.name}' is not available on campus "
                    f"'{user.primary_campus.name}'. Contact your administrator."
                )
            })

        # ── 2. Resolve Section via service catalogue ─────────────────────────
        section = None
        if service_item:
            section_type = service_item.category.section_type
            if section_type.department != department:
                raise ValidationError({
                    "service_item_id": (
                        f"Service item '{service_item.name}' belongs to "
                        f"'{section_type.department.name}', not '{department.name}'."
                    )
                })
            section = (
                Section.objects
                .select_related(
                    "head_of_section",
                    "section_type",
                    "campus_department__campus",
                    "campus_department__department",
                )
                .filter(
                    campus_department=campus_department,
                    section_type=section_type,
                )
                .first()
            )
            if not section:
                raise ValidationError({
                    "service_item_id": (
                        f"No '{section_type.name}' section exists under "
                        f"{campus_department}. Contact your administrator."
                    )
                })

        # ── 3. Eligible assignees ─────────────────────────────────────────────
        # Technicians must be: linked to the section, on the same campus, active.
        eligible_technicians = []
        if section:
            eligible_technicians = list(
                CustomUser.objects
                .filter(
                    technician_section_links__section=section,
                    primary_campus=user.primary_campus,
                    role="technician",
                    is_active=True,
                )
                .annotate(
                    open_tickets=Count(
                        "assigned_tickets",
                        filter=Q(assigned_tickets__status__in=("assigned", "in_progress")),
                    )
                )
                .order_by("open_tickets")
                .distinct()
            )

        # ── 4. Create ticket ──────────────────────────────────────────────────
        initial_status = (
            "pending_approval"
            if service_item and service_item.requires_approval
            else "open"
        )

        with transaction.atomic():
            ticket = Ticket.objects.create(
                title=vd["title"],
                description=vd["description"],
                raised_by=user,
                campus_department=campus_department,
                section=section,
                service_item=service_item,
                facility=vd.get("facility"),
                location_detail=vd.get("location_detail", ""),
                form_data=vd.get("form_data"),
                status=initial_status,
            )
            TicketLog.objects.create(
                ticket=ticket, action="created", performed_by=user
            )

        # ── 5. Rich response ──────────────────────────────────────────────────
        return Response(
            self._build_response(ticket, campus_department, section, eligible_technicians),
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _build_response(ticket, campus_department, section, eligible_technicians):
        return {
            "ticket": {
                "id": ticket.id,
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "due_date": ticket.due_date,
                "created_at": ticket.created_at,
                "form_data": ticket.form_data,
                "location_detail": ticket.location_detail,
            },
            "campus_department": {
                "id": campus_department.id,
                "campus": {
                    "code": campus_department.campus.code,
                    "name": campus_department.campus.name,
                },
                "department": {
                    "code": campus_department.department.code,
                    "name": campus_department.department.name,
                },
                "head_of_department": format_user_info(campus_department.head_of_department),
            },
            "section": {
                "id": section.id,
                "name": section.name,
                "code": section.code,
                "section_type": section.section_type.name,
                "effective_sla_hours": section.effective_sla_hours,
                "head_of_section": format_user_info(section.head_of_section),
            } if section else None,
            "eligible_technicians": [
                {**format_user_info(t), "open_tickets": t.open_tickets}
                for t in eligible_technicians
            ],
        }


class TicketDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete tickets with escalation support"""

    queryset = (
        Ticket.objects.select_related(
            "campus_department__campus",
            "campus_department__department",
            "section__section_type",
            "section__head_of_section",
            "facility",
            "raised_by",
            "assigned_to",
            "escalated_to",
            "service_item",
        )
        .prefetch_related(
            "comments",
            "comments__author",
            "feedback",
            Prefetch(
                "section__technician_links__technician",
                queryset=CustomUser.objects.filter(role="technician").only(
                    "id", "username", "first_name", "last_name"
                ),
                to_attr="available_technicians_prefetch",
            ),
        )
        .all()
    )
    serializer_class = TicketSerializer
    permission_classes = [CanViewAndEditTickets, IsAuthenticated]

    def perform_update(self, serializer):
        """Handle ticket updates: assignment and status changes"""
        user = self.request.user
        ticket = self.get_object()

        # Prevent modifications to closed tickets
        if ticket.status == "closed":
            raise ValidationError("Closed tickets cannot be modified")

        updated = False

        # Check if this is an assignment operation
        if (
            "assigned_to" in serializer.validated_data
            and serializer.validated_data["assigned_to"]
        ):
            technician = serializer.validated_data["assigned_to"]
            try:
                TicketService.assign_ticket(
                    ticket=ticket, technician=technician, assigned_by=user
                )
                # Refresh to get updated status from assignment
                ticket.refresh_from_db()
                updated = True
            except (InvalidAssignmentException, PermissionError) as e:
                raise serializers.ValidationError(str(e))

        # Check if this is a status update
        if "status" in serializer.validated_data:
            new_status = serializer.validated_data["status"]
            old_status = ticket.status

            # Skip validation if status is not changing (e.g., status already "assigned" after assignment)
            if old_status != new_status:
                # Validate transition
                is_valid, error_msg = validate_status_transition(
                    old_status, new_status, user.role
                )
                if not is_valid:
                    raise ValidationError(error_msg)

                # Update using service
                try:
                    TicketService.update_ticket_status(
                        ticket=ticket,
                        new_status=new_status,
                        updated_by=user,
                        pending_reason=serializer.validated_data.get(
                            "pending_reason"),
                        pending_comment=serializer.validated_data.get(
                            "pending_comment"),
                    )
                except (ValidationError, DjangoValidationError) as e:
                    raise serializers.ValidationError(str(e))
                updated = True

        # Handle other field updates (title, description, etc)
        # Don't use serializer.save() because that doesn't call the service methods
        # Instead, manually update fields on the ticket object
        updatable_fields = ["title", "description"]
        for field in updatable_fields:
            if field in serializer.validated_data:
                setattr(ticket, field, serializer.validated_data[field])

        # Save any field updates or refresh after service updates
        if updated or any(
            field in serializer.validated_data for field in updatable_fields
        ):
            ticket.save()
            ticket.refresh_from_db()
            serializer.instance = ticket


class TicketEscalationView(CreateAPIView):
    """
    Escalate a ticket to the next level in the approval chain.

    POST /api/tickets/{ticket_id}/escalate/
    {
        "reason": "Issue requires higher-level approval"
    }

    Escalation chain:
    - Level 0 (technician) → Level 1 (section_head)
    - Level 1 (section_head) → Level 2 (hod) [MAXIMUM]
    """

    permission_classes = [IsWithinOrganizationalScope, CanEscalateTickets]
    serializer_class = TicketSerializer

    def create(self, request, *args, **kwargs):
        try:
            ticket = Ticket.objects.get(id=self.kwargs.get("ticket_id"))
            self.check_object_permissions(request, ticket)
            reason = request.data.get("reason", "") or "Manual escalation"
            escalated_ticket = TicketService.escalate_ticket(
                ticket=ticket, escalated_by=request.user, reason=reason, manual=True
            )
            return Response(TicketSerializer(escalated_ticket).data, status=status.HTTP_200_OK)
        except Ticket.DoesNotExist:
            return Response({"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)
        except (InvalidEscalationException, PermissionError) as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class TicketCloseView(CreateAPIView):
    """
    Close a ticket (customer feedback endpoint).

    POST /api/tickets/{ticket_id}/close/
    {
        "closure_notes": "Issue resolved successfully"
    }

    Permission (CanCloseTicket):
    - Users (customers) can close their own tickets (raised_by == user)
    - Admins can close any ticket
    - Other roles (technician, hod, hos, manager) should use status updates via
      PATCH /api/tickets/<id>/ to change ticket state.

    This endpoint is primarily for customers to confirm ticket closure/satisfaction.
    """

    permission_classes = [IsAuthenticated, CanCloseTicket]
    serializer_class = TicketSerializer

    def create(self, request, *args, **kwargs):
        """Handle ticket closure"""
        try:
            ticket_id = self.kwargs.get("ticket_id")
            ticket = Ticket.objects.get(id=ticket_id)

            # Check permission on the specific ticket
            self.check_object_permissions(request, ticket)

            # Get optional closure notes from request body
            closure_notes = request.data.get("closure_notes", None)

            # Close the ticket using the service layer
            closed_ticket = TicketService.close_ticket(
                ticket=ticket, closed_by=request.user, closure_notes=closure_notes
            )

            # Return updated ticket
            serializer = TicketSerializer(closed_ticket)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Ticket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# APPROVAL / REJECTION API
# ============================================================================


class ApproveTicketView(APIView):
    """
    POST /api/tickets/{ticket_id}/approve/
    {
        "notes": "Looks good, proceed."   // optional
    }

    Permission: hod, manager, admin only.
    Ticket must be in pending_approval status.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        try:
            ticket = Ticket.objects.select_related(
                "section",
                "campus_department__campus",
                "campus_department__department",
            ).get(id=ticket_id)
        except Ticket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )

        notes = request.data.get("notes", "")

        try:
            updated_ticket = TicketService.approve_ticket(
                ticket=ticket, approved_by=request.user, notes=notes
            )
            serializer = TicketSerializer(updated_ticket)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except DRFPermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except DRFValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RejectTicketView(APIView):
    """
    POST /api/tickets/{ticket_id}/reject/
    {
        "reason": "Budget not available."   // required
    }

    Permission: hod, manager, admin only.
    Ticket must be in pending_approval status.
    Rejection reason is stored in TicketLog.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, ticket_id):
        try:
            ticket = Ticket.objects.select_related(
                "section",
                "campus_department__campus",
                "campus_department__department",
            ).get(id=ticket_id)
        except Ticket.DoesNotExist:
            return Response(
                {"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND
            )

        reason = request.data.get("reason", "").strip()
        if not reason:
            return Response(
                {"error": "Rejection reason is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            updated_ticket = TicketService.reject_ticket(
                ticket=ticket, rejected_by=request.user, reason=reason
            )
            serializer = TicketSerializer(updated_ticket)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except DRFPermissionDenied as e:
            return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
        except DRFValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================================
# BULK OPERATIONS API
# ============================================================================


class BulkTicketStatusUpdateView(CreateAPIView):
    """
    Bulk update ticket statuses.

    POST /api/tickets/bulk-status-update/
    {
        "ticket_ids": [1, 2, 3],
        "new_status": "pending",
        "reason": "Weekly batch processing"
    }

    Only admins and managers can perform bulk operations.
    """

    permission_classes = [IsAuthenticated, CanManageUsers]

    def create(self, request, *args, **kwargs):
        """Perform bulk status update"""
        ticket_ids = request.data.get("ticket_ids")
        new_status = request.data.get("new_status")
        reason = request.data.get("reason")

        # Validate ticket_ids is a list
        if ticket_ids is None or not isinstance(ticket_ids, list):
            return Response(
                {"error": "ticket_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate new_status is provided
        if not new_status:
            return Response(
                {"error": "new_status is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        results = TicketService.bulk_update_status(
            ticket_ids=ticket_ids,
            new_status=new_status,
            updated_by=request.user,
            reason=reason,
        )

        return Response(results, status=status.HTTP_200_OK)


class OrganizationalTicketListView(ListAPIView):
    """
    List tickets within user's organizational scope.

    Supports filtering by:
    - status: open, assigned, in_progress, pending, resolved, closed, escalated
    - section_id: specific section
    - assigned_to_id: assigned technician
    - escalation_level: 0 (none), 1 (section_head), 2 (hod)
    - is_overdue: boolean (tickets >7 days old)

    Respects organizational hierarchy:
    - Admin: sees all tickets
    - Manager: sees organization-wide tickets
    - HOD: sees campus-level tickets
    - Section Head: sees department-level tickets
    - Technician/User: sees section-level tickets
    """

    serializer_class = TicketListSerializer
    permission_classes = [IsAuthenticated, IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    pagination_class = TicketPagination

    filterset_fields = ["status", "escalation_level"]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-updated_at"]

    def get_queryset(self):
        """
        Return tickets accessible to user based on organizational role.
        Uses service layer for consistent scope filtering.
        """
        return TicketService.get_accessible_tickets(self.request.user)

    def get_serializer_context(self):
        """Add request context for serializer"""
        context = super().get_serializer_context()
        context["skip_available_technicians"] = True
        return context


class CommentListCreateView(ListCreateAPIView):
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["author"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        ticket_id = self.kwargs.get("ticket_id")
        return Comment.objects.filter(ticket_id=ticket_id).order_by("created_at")

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        TicketService.create_comment(serializer, self.request.user, ticket_id)


class FeedbackListCreateView(ListCreateAPIView):
    serializer_class = FeedbackSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["rating", "rated_by"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        ticket_id = self.kwargs.get("ticket_id")
        if ticket_id:
            return Feedback.objects.filter(ticket_id=ticket_id).order_by("-created_at")
        # For non-nested endpoint, return all feedback for the user's accessible tickets
        return Feedback.objects.all().order_by("-created_at")

    def perform_create(self, serializer):
        # Handle both nested and non-nested endpoints
        ticket_id = self.kwargs.get("ticket_id")
        if not ticket_id:
            # Non-nested endpoint — ticket_id must come from request data
            ticket_id = self.request.data.get("ticket")
        TicketService.create_feedback(serializer, self.request.user, ticket_id)
