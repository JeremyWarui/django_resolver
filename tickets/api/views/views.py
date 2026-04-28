"""
Consolidated API Views for Django Resolver

All endpoints with organizational hierarchy awareness. Views handle HTTP requests/responses
while delegating business logic to the TicketService layer.

Endpoint Categories:
- Organization Hierarchy: Organization, Campus, Department, Section CRUD
- Ticket Management: Ticket CRUD with org-aware filtering and escalation
- User Management: Users and technician assignment
- Comments & Feedback: Per-ticket discussions and ratings
- Analytics: Role-specific organizational dashboards

All views respect user's organizational scope based on role.
"""

from rest_framework.generics import (
    ListCreateAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView, ListAPIView
)
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db import models
from django.db.models import Prefetch
from django.utils import timezone
from datetime import timedelta

from tickets.api.permissions import (
    IsAdminOrManagerOrReadOnly, IsOwnerOrTechnicianOrAdmin,
    IsTechnicianOrAdmin, CanManageUsers, IsWithinOrganizationalScope,
    CanAssignTickets, CanEscalateTickets, CanViewAnalytics, IsAdminOrReadOnly
)
from tickets.serializers import (
    OrganizationSerializer, CampusSerializer, DepartmentSerializer,
    SectionSerializer, FacilitySerializer, TicketSerializer, TicketListSerializer,
    CommentSerializer, FeedbackSerializer, UserSerializer
)
from tickets.api.services import (
    TicketService,
    validate_status_transition,
    InsufficientScopeException,
    InvalidAssignmentException,
    InvalidEscalationException,
)
from tickets.api.analytics.analytics import TicketAnalytics, OrganizationalAnalytics
from tickets.models import (
    Organization, Campus, Department, Section, Facility, Ticket, Comment,
    Feedback, CustomUser
)
from tickets.pagination import TicketPagination


# ============================================================================
# ORGANIZATION HIERARCHY ENDPOINTS
# ============================================================================

class OrganizationListCreateView(ListCreateAPIView):
    """Organization list and create endpoint. Create is admin-only."""
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsWithinOrganizationalScope]

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            raise PermissionDenied("Only administrators can create organizations")
        return super().create(request, *args, **kwargs)


class OrganizationDetailView(RetrieveUpdateDestroyAPIView):
    """Organization retrieve/update/delete. Reads are scoped; writes are admin-only."""
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsWithinOrganizationalScope, IsAdminOrReadOnly]


class CampusListCreateView(ListCreateAPIView):
    """Campus list and create endpoint. Create is admin-only."""
    queryset = Campus.objects.all()
    serializer_class = CampusSerializer
    permission_classes = [IsWithinOrganizationalScope]

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            raise PermissionDenied("Only administrators can create campuses")
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """Filter campuses based on user's organizational scope"""
        queryset = Campus.objects.select_related('organization').all()
        user = self.request.user

        if user.role == 'admin':
            return queryset
        elif user.role == 'director' and user.primary_campus:
            return queryset.filter(organization=user.primary_campus.organization)
        elif user.role in ['hod', 'section_head', 'technician', 'user'] and user.primary_campus:
            return queryset.filter(id=user.primary_campus.id)
        return queryset.none()


class CampusDetailView(RetrieveUpdateDestroyAPIView):
    """Campus retrieve/update/delete. Reads are scoped; writes are admin-only."""
    queryset = Campus.objects.select_related('organization').all()
    serializer_class = CampusSerializer
    permission_classes = [IsWithinOrganizationalScope, IsAdminOrReadOnly]


class DepartmentListCreateView(ListCreateAPIView):
    """Department list and create endpoint. Create is admin-only."""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsWithinOrganizationalScope]

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            raise PermissionDenied("Only administrators can create departments")
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """Filter departments based on user's organizational scope"""
        queryset = Department.objects.select_related(
            'campus', 'campus__organization', 'head_of_department').all()
        user = self.request.user

        if user.role == 'admin':
            return queryset
        elif user.role == 'director' and user.primary_campus:
            return queryset.filter(campus__organization=user.primary_campus.organization)
        elif user.role == 'hod' and user.primary_campus:
            return queryset.filter(campus=user.primary_campus)
        elif user.role in ['section_head', 'technician', 'user'] and user.primary_department:
            return queryset.filter(id=user.primary_department.id)
        return queryset.none()


class DepartmentDetailView(RetrieveUpdateDestroyAPIView):
    """Department retrieve/update/delete. Reads are scoped; writes are admin-only."""
    queryset = Department.objects.select_related(
        'campus', 'campus__organization', 'head_of_department').all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsWithinOrganizationalScope, IsAdminOrReadOnly]


# ============================================================================
# SECTION API
# ============================================================================

class SectionListCreateView(ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'is_active']

    def create(self, request, *args, **kwargs):
        """Restrict section creation to admins only"""
        if request.user.role != 'admin':
            raise PermissionDenied("Only administrators can create sections")
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """Filter sections based on user's organizational scope"""
        queryset = Section.objects.select_related(
            'department__campus', 'section_head'
        ).prefetch_related(
            Prefetch('technicians', queryset=CustomUser.objects.select_related('primary_campus'))
        ).all()
        user = self.request.user

        if user.role == 'admin':
            return queryset
        elif user.role == 'director':
            # Director sees sections in their organization
            return queryset.filter(
                department__campus__organization=user.primary_campus.organization
            )
        elif user.role == 'hod':
            # HOD sees sections in their campus
            return queryset.filter(department__campus=user.primary_campus)
        elif user.role == 'section_head':
            # Section head sees sections in their department
            return queryset.filter(department=user.primary_department)
        elif user.role in ['technician', 'user']:
            # Technicians/users see their assigned sections
            return queryset.filter(pk__in=user.sections.all())

        return queryset.none()


class SectionDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsWithinOrganizationalScope]


# ============================================================================
# FACILITY API
# ============================================================================

class FacilityListCreateView(ListCreateAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['campus', 'type']

    def create(self, request, *args, **kwargs):
        """Restrict facility creation to admins only"""
        if request.user.role != 'admin':
            raise PermissionDenied("Only administrators can create facilities")
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """Filter facilities based on user's organizational scope"""
        queryset = Facility.objects.select_related('campus').all()
        user = self.request.user

        if user.role == 'admin':
            return queryset
        elif user.role == 'director':
            return queryset.filter(campus__organization=user.primary_campus.organization)
        elif user.role in ['hod', 'section_head', 'technician', 'user']:
            return queryset.filter(campus=user.primary_campus)

        return queryset.none()


class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsWithinOrganizationalScope]


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
    - Director: sees organization-wide tickets
    - HOD: sees campus-level tickets
    - Section Head: sees department-level tickets
    - Technician/User: sees accessible section-level tickets
    """
    queryset = Ticket.objects.all().order_by('-updated_at')
    pagination_class = TicketPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'section',
                        'assigned_to', 'raised_by', 'escalation_level']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-updated_at']  # Default ordering
    permission_classes = [IsWithinOrganizationalScope, IsAuthenticated]

    def get_serializer_class(self):
        """Use optimized serializer for list, full serializer for create."""
        if self.request.method == 'GET':
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
        status = self.request.query_params.get('status')
        if status:
            filters['status'] = status

        escalation_level = self.request.query_params.get('escalation_level')
        if escalation_level:
            filters['escalation_level'] = escalation_level

        # Get tickets accessible to user based on organizational scope
        queryset = TicketService.get_accessible_tickets(user, filters)

        # Handle additional custom filters
        assigned_to_isnull = self.request.query_params.get(
            'assigned_to__isnull', None)
        if assigned_to_isnull and assigned_to_isnull.lower() == 'true':
            queryset = queryset.filter(assigned_to__isnull=True)

        # Handle overdue filter
        is_overdue = self.request.query_params.get('is_overdue', None)
        if is_overdue and is_overdue.lower() == 'true':
            # Define overdue as tickets >7 days old in active states
            seven_days_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(
                created_at__lt=seven_days_ago,
                status__in=['open', 'assigned', 'in_progress']
            )

        return queryset

    def perform_create(self, serializer):
        """Create ticket using organizational service layer"""
        try:
            user = self.request.user
            # Get section and facility from validated data (which contains the deserialized objects)
            section = serializer.validated_data.get('section')
            facility = serializer.validated_data.get('facility')

            if not section or not facility:
                raise serializers.ValidationError(
                    "Section and Facility are required")

            # Use organizational service to create ticket and get the instance
            ticket = TicketService.create_ticket(
                data=serializer.validated_data,
                created_by=user,
                section=section,
                facility=facility,
                enable_auto_escalation=serializer.validated_data.get(
                    'auto_escalation_enabled', True)
            )

            # Set the created instance on the serializer so response includes it
            serializer.instance = ticket
        except InsufficientScopeException as e:
            raise serializers.ValidationError(str(e))
        except Exception as e:
            raise serializers.ValidationError(
                f"Failed to create ticket: {str(e)}")


class TicketDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, and delete tickets with escalation support"""
    queryset = Ticket.objects.select_related(
        'section', 'facility', 'raised_by', 'assigned_to', 'escalated_to'
    ).prefetch_related(
        'comments',
        'comments__author',
        'feedback',
        Prefetch(
            'section__technicians',
            queryset=CustomUser.objects.filter(role='technician').only(
                'id', 'username', 'first_name', 'last_name'
            ),
            to_attr='available_technicians_prefetch'
        )
    ).all()
    serializer_class = TicketSerializer
    permission_classes = [IsWithinOrganizationalScope, IsAuthenticated]

    def perform_update(self, serializer):
        """Handle ticket updates: assignment and status changes"""
        user = self.request.user
        ticket = self.get_object()

        # Prevent modifications to closed tickets
        if ticket.status == "closed":
            raise ValidationError("Closed tickets cannot be modified")

        updated = False

        # Check if this is an assignment operation
        if 'assigned_to' in serializer.validated_data and serializer.validated_data['assigned_to']:
            technician = serializer.validated_data['assigned_to']
            try:
                TicketService.assign_ticket(
                    ticket=ticket,
                    technician=technician,
                    assigned_by=user
                )
                # Refresh to get updated status from assignment
                ticket.refresh_from_db()
                updated = True
            except (InvalidAssignmentException, PermissionError) as e:
                raise serializers.ValidationError(str(e))

        # Check if this is a status update
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            old_status = ticket.status

            # Skip validation if status is not changing (e.g., status already "assigned" after assignment)
            if old_status != new_status:
                # Validate transition
                is_valid, error_msg = validate_status_transition(
                    old_status, new_status, user.role)
                if not is_valid:
                    raise ValidationError(error_msg)

                # Update using service
                TicketService.update_ticket_status(
                    ticket=ticket,
                    new_status=new_status,
                    updated_by=user
                )
                updated = True

        # Handle other field updates (title, description, etc)
        # Don't use serializer.save() because that doesn't call the service methods
        # Instead, manually update fields on the ticket object
        updatable_fields = ['title', 'description']
        for field in updatable_fields:
            if field in serializer.validated_data:
                setattr(ticket, field, serializer.validated_data[field])

        # Save any field updates or refresh after service updates
        if updated or any(field in serializer.validated_data for field in updatable_fields):
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
        """Handle ticket escalation"""
        try:
            ticket_id = self.kwargs.get('ticket_id')
            ticket = Ticket.objects.get(id=ticket_id)

            # Check permission on the specific ticket
            self.check_object_permissions(request, ticket)

            # Get escalation reason from request body
            reason = request.data.get('reason', '')
            if not reason:
                return Response(
                    {'error': 'Reason for escalation is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Escalate the ticket using the service layer
            escalated_ticket = TicketService.escalate_ticket(
                ticket=ticket,
                escalated_by=request.user,
                reason=reason,
                manual=True
            )

            # Return updated ticket
            serializer = TicketSerializer(escalated_ticket)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except (InvalidEscalationException, PermissionError) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TicketCloseView(CreateAPIView):
    """
    Close a resolved ticket.

    POST /api/tickets/{ticket_id}/close/
    {
        "closure_notes": "Issue resolved successfully"
    }

    Permission:
    - Ticket raiser (user who created the ticket) can close their own tickets
    - Admin/Manager roles can close any resolved ticket
    """
    permission_classes = [IsWithinOrganizationalScope]
    serializer_class = TicketSerializer

    def create(self, request, *args, **kwargs):
        """Handle ticket closure"""
        try:
            ticket_id = self.kwargs.get('ticket_id')
            ticket = Ticket.objects.get(id=ticket_id)

            # Check permission on the specific ticket
            self.check_object_permissions(request, ticket)

            # Get optional closure notes from request body
            closure_notes = request.data.get('closure_notes', None)

            # Close the ticket using the service layer
            closed_ticket = TicketService.close_ticket(
                ticket=ticket,
                closed_by=request.user,
                closure_notes=closure_notes
            )

            # Return updated ticket
            serializer = TicketSerializer(closed_ticket)
            return Response(
                serializer.data,
                status=status.HTTP_200_OK
            )

        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ============================================================================
# COMMENTS API
# ============================================================================

class CommentListCreateView(ListCreateAPIView):
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['author']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter comments by ticket_id from URL"""
        ticket_id = self.kwargs.get("ticket_id")
        return Comment.objects.filter(ticket_id=ticket_id).order_by('created_at')

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        TicketService.create_comment(serializer, self.request.user, ticket_id)


# ============================================================================
# FEEDBACK API
# ============================================================================

class FeedbackListCreateView(ListCreateAPIView):
    serializer_class = FeedbackSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['rating', 'rated_by']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter feedback by ticket_id from URL"""
        ticket_id = self.kwargs.get("ticket_id")
        return Feedback.objects.filter(ticket_id=ticket_id).order_by('-created_at')

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        TicketService.create_feedback(serializer, self.request.user, ticket_id)


# ============================================================================
# USERS API
# ============================================================================

class UserListCreateView(ListCreateAPIView):
    queryset = CustomUser.objects.select_related(
        'primary_campus__organization',
        'primary_department__campus__organization',
    ).prefetch_related('sections').order_by('username')
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'sections']
    permission_classes = [CanManageUsers]


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [CanManageUsers]


# ============================================================================
# TECHNICIANS BY SECTION API
# ============================================================================

class TechniciansBySectionView(generics.ListAPIView):
    """
    Get technicians filtered by section.
    Used when assigning tickets to show only relevant technicians.

    Query params:
    - section_id: Filter technicians by section (required for assignment)
    - campus_id: Filter technicians by campus (optional)
    """
    serializer_class = UserSerializer
    pagination_class = None  # Return unpaginated list for dropdown/assignment UI
    permission_classes = [IsTechnicianOrAdmin]

    def get_queryset(self):
        """Filter technicians by section and campus if provided."""
        queryset = CustomUser.objects.filter(role='technician')

        # Filter by section if provided
        section_id = self.request.query_params.get('section_id')
        if section_id:
            queryset = queryset.filter(sections__id=section_id)

        # Filter by campus if provided
        campus_id = self.request.query_params.get('campus_id')
        if campus_id:
            queryset = queryset.filter(primary_campus_id=campus_id)

        return queryset.distinct().order_by('first_name', 'last_name')


class AssignableUsersView(ListAPIView):
    """
    Get technicians that can be assigned tickets in a specific section.

    Query Parameters:
    - section_id: Required. ID of the section to get technicians for

    Returns:
    - List of technician users who are:
      1. Active and have 'technician' role
      2. Associated with the specified section
      3. Accessible within the user's organizational scope
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, CanAssignTickets]

    def get_queryset(self):
        """Get technicians assignable to the requested section."""
        section_id = self.request.query_params.get('section_id')

        if not section_id:
            return CustomUser.objects.none()

        try:
            section = Section.objects.select_related(
                'department',
                'department__campus',
                'department__campus__organization'
            ).get(id=section_id)
        except Section.DoesNotExist:
            return CustomUser.objects.none()

        user = self.request.user

        # Validate user can assign in this section using service layer
        try:
            if not TicketService._user_can_access_section(user, section):
                return CustomUser.objects.none()
        except (PermissionDenied, ValidationError):
            return CustomUser.objects.none()

        # Return active technicians assigned to this section
        return CustomUser.objects.filter(
            role='technician',
            sections=section,
            is_active=True
        ).order_by('first_name', 'last_name').select_related('primary_department')


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
        ticket_ids = request.data.get('ticket_ids')
        new_status = request.data.get('new_status')
        reason = request.data.get('reason')

        # Validate ticket_ids is a list
        if ticket_ids is None or not isinstance(ticket_ids, list):
            return Response(
                {'error': 'ticket_ids must be a list'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate new_status is provided
        if not new_status:
            return Response(
                {'error': 'new_status is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        results = TicketService.bulk_update_status(
            ticket_ids=ticket_ids,
            new_status=new_status,
            updated_by=request.user,
            reason=reason
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
    - Director: sees organization-wide tickets
    - HOD: sees campus-level tickets
    - Section Head: sees department-level tickets
    - Technician/User: sees section-level tickets
    """

    serializer_class = TicketListSerializer
    permission_classes = [IsAuthenticated, IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    pagination_class = TicketPagination

    filterset_fields = ['status', 'escalation_level']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-updated_at']

    def get_queryset(self):
        """
        Return tickets accessible to user based on organizational role.
        Uses service layer for consistent scope filtering.
        """
        return TicketService.get_accessible_tickets(self.request.user)

    def get_serializer_context(self):
        """Add request context for serializer"""
        context = super().get_serializer_context()
        context['skip_available_technicians'] = True
        return context


class EscalateTicketView(APIView):
    """
    Endpoint for manually escalating tickets with validation.

    POST /api/tickets/{ticket_id}/escalate-manual/
    {
        "reason": "Issue requires higher-level attention"
    }

    Escalation must follow organizational hierarchy:
    - Open/Assigned/In Progress → Escalate to Section Head
    - Section Head escalation → Escalate to HOD
    - Cannot escalate beyond HOD
    """

    permission_classes = [IsAuthenticated, CanEscalateTickets]

    def post(self, request, ticket_id):
        """Handle manual ticket escalation"""
        try:
            ticket = Ticket.objects.select_related(
                'section',
                'section__department',
                'section__department__campus',
                'escalated_to'
            ).get(id=ticket_id)

        except Ticket.DoesNotExist:
            return Response(
                {'error': 'Ticket not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Validate user can escalate this ticket
        try:
            TicketService._user_can_access_section(
                request.user, ticket.section)
        except (PermissionDenied, ValidationError) as e:
            return Response(
                {'error': f'Cannot escalate tickets outside your scope: {str(e)}'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get escalation reason
        reason = request.data.get('reason', '')
        if not reason:
            return Response(
                {'error': 'Escalation reason is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Perform escalation
        try:
            updated_ticket = TicketService.escalate_ticket(
                ticket=ticket,
                escalated_by=request.user,
                reason=reason,
                manual=True
            )

            return Response(
                {
                    'success': True,
                    'message': 'Ticket escalated successfully',
                    'ticket_no': updated_ticket.ticket_no,
                    'escalation_level': updated_ticket.escalation_level,
                    'escalated_to': (
                        f"{updated_ticket.escalated_to.first_name} "
                        f"{updated_ticket.escalated_to.last_name}"
                        if updated_ticket.escalated_to else None
                    ),
                    'next_escalation_due': updated_ticket.next_escalation_due
                },
                status=status.HTTP_200_OK
            )

        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Escalation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================================================
# ANALYTICS API - ORGANIZATIONAL
# ============================================================================

class OrganizationalAnalyticsView(APIView):
    """
    Unified analytics endpoint that returns role-specific dashboards.

    Returns different dashboard data based on user's organizational role:
    - Director: Organization-wide metrics and alerts
    - HOD: Campus-level performance and escalations
    - Section Head: Department efficiency and technician performance

    GET /api/analytics/organizational/?days=30&timeframe=month

    Query Parameters:
    - days: Number of days to include in analysis (default: 30)
    - timeframe: 'day', 'week', 'month' for grouping (default: 'month')
    """

    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request):
        """
        Return analytics dashboard data based on user's role.
        Falls back to limited data if insufficient permissions.
        """
        user = request.user
        days = int(request.query_params.get('days', 30))
        timeframe = request.query_params.get('timeframe', 'month')

        try:
            if user.role == 'director':
                data = OrganizationalAnalytics.director_dashboard(
                    user,
                    days=days
                )
            elif user.role == 'hod':
                data = OrganizationalAnalytics.hod_dashboard(
                    user,
                    days=days
                )
            elif user.role == 'section_head':
                data = OrganizationalAnalytics.section_head_dashboard(
                    user,
                    days=days
                )
            else:
                return Response(
                    {'error': 'User role does not have access to analytics dashboard'},
                    status=status.HTTP_403_FORBIDDEN
                )

            return Response(data)

        except Exception as e:
            return Response(
                {'error': f'Failed to generate analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsTicketsView(APIView):
    """
    Ticket analytics endpoint.

    GET /api/analytics/tickets/?timeframe=week&facility_id=1&group_by=day&days=30
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get ticket analytics data"""
        days = int(request.query_params.get('days', 30))
        timeframe = request.query_params.get('timeframe', 'day')
        facility_id = request.query_params.get('facility_id')
        section_id = request.query_params.get('section_id')

        try:
            data = {
                'ticket_counts': TicketAnalytics.get_ticket_counts_by_timeframe(
                    days=days,
                    facility_id=facility_id,
                    section_id=section_id
                ),
                'status_counts': TicketAnalytics.get_ticket_counts_by_status(
                    facility_id=facility_id,
                    section_id=section_id
                ),
                'trend_data': TicketAnalytics.get_ticket_trend_data(
                    days=days,
                    group_by=timeframe
                ),
                'facility_distribution': TicketAnalytics.get_tickets_by_facility(),
                'section_distribution': TicketAnalytics.get_tickets_by_section(),
            }
            return Response(data)
        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AnalyticsTechniciansView(APIView):
    """
    Technician analytics endpoint.

    GET /api/analytics/technicians/?technician_id=5
    """
    permission_classes = [IsAuthenticated, CanViewAnalytics]

    def get(self, request):
        """Get technician analytics data"""
        try:
            data = TicketAnalytics.get_technician_performance()
            return Response(data)
        except Exception as e:
            return Response(
                {'error': f'Failed to retrieve technician analytics: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
