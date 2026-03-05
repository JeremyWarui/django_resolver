from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from tickets.api.permissions import (
    IsAdminOrManagerOrReadOnly, IsOwnerOrTechnicianOrAdmin,
    IsTechnicianOrAdmin, CanManageUsers, IsWithinOrganizationalScope,
    CanAssignTickets, CanEscalateTickets, CanViewAnalytics
)
from tickets.serializers import SectionSerializer, FacilitySerializer, TicketSerializer, TicketListSerializer
from tickets.serializers import CommentSerializer, FeedbackSerializer, UserSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db import models
from tickets.api.services.ticket_services import (
    create_ticket, update_ticket, create_comment, create_feedback
)
from tickets.api.services import (
    OrganizationalTicketService, InsufficientScopeException,
    InvalidAssignmentException, InvalidEscalationException
)
from tickets.models import Section, Facility, Ticket, Comment, Feedback, CustomUser
from django.utils import timezone
from datetime import timedelta
from tickets.pagination import TicketPagination


# --------------------------------
# SECTION API
# ----------------------------------

class SectionListCreateView(ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['department', 'is_active']

    def get_queryset(self):
        """Filter sections based on user's organizational scope"""
        queryset = Section.objects.select_related(
            'department', 'section_head').all()
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


# --------------------------------
# FACILITY API
# ----------------------------------

class FacilityListCreateView(ListCreateAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['campus', 'department', 'facility_type']

    def get_queryset(self):
        """Filter facilities based on user's organizational scope"""
        queryset = Facility.objects.select_related(
            'campus', 'department').all()
        user = self.request.user

        if user.role == 'admin':
            return queryset
        elif user.role == 'director':
            # Director sees facilities in their organization
            return queryset.filter(campus__organization=user.primary_campus.organization)
        elif user.role == 'hod':
            # HOD sees facilities in their campus
            return queryset.filter(campus=user.primary_campus)
        elif user.role == 'section_head':
            # Section head sees facilities in their department
            return queryset.filter(department=user.primary_department)
        elif user.role in ['technician', 'user']:
            # Technicians/users see facilities in their primary campus/department
            return queryset.filter(campus=user.primary_campus)

        return queryset.none()


class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsWithinOrganizationalScope]


# --------------------------------
# TICKETS API
# ----------------------------------

class TicketListCreateView(ListCreateAPIView):
    queryset = Ticket.objects.all().order_by('-updated_at')
    # Use custom pagination for flexible page sizes
    pagination_class = TicketPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'section',
                        'assigned_to', 'raised_by', 'priority']
    ordering_fields = ['created_at', 'updated_at', 'status', 'priority']
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

        priority = self.request.query_params.get('priority')
        if priority:
            filters['priority'] = priority

        # Get tickets accessible to user based on organizational scope
        queryset = OrganizationalTicketService.get_accessible_tickets(
            user, filters)

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
            section_id = self.request.data.get('section')
            facility_id = self.request.data.get('facility')

            section = Section.objects.get(
                id=section_id) if section_id else None
            facility = Facility.objects.get(
                id=facility_id) if facility_id else None

            if not section or not facility:
                raise ValueError("Section and Facility are required")

            # Use organizational service to ensure scope checking
            OrganizationalTicketService.create_ticket(
                data=serializer.validated_data,
                created_by=user,
                section=section,
                facility=facility,
                priority=serializer.validated_data.get('priority', 'medium'),
                enable_auto_escalation=serializer.validated_data.get(
                    'auto_escalation_enabled', True)
            )
        except InsufficientScopeException as e:
            raise serializers.ValidationError(str(e))
        except Exception as e:
            # Fall back to legacy service for backward compatibility
            create_ticket(serializer, self.request.user)


class TicketDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Ticket.objects.select_related(
        'section', 'facility', 'raised_by', 'assigned_to', 'escalated_to'
    ).prefetch_related('comments', 'comments__author', 'feedback').all()
    serializer_class = TicketSerializer
    permission_classes = [IsWithinOrganizationalScope, IsAuthenticated]

    def perform_update(self, serializer):
        """Handle ticket updates: assignment, status changes, escalation"""
        user = self.request.user
        ticket = self.get_object()

        # Check if this is an assignment operation
        if 'assigned_to' in serializer.validated_data and serializer.validated_data['assigned_to']:
            technician = serializer.validated_data['assigned_to']
            try:
                OrganizationalTicketService.assign_ticket(
                    ticket=ticket,
                    technician=technician,
                    assigned_by=user
                )
            except (InvalidAssignmentException, PermissionError) as e:
                from rest_framework.serializers import ValidationError as SerializerValidationError
                raise SerializerValidationError(str(e))

        # Check if this is a status update that requires escalation validation
        if 'status' in serializer.validated_data:
            new_status = serializer.validated_data['status']
            # Let the legacy service handle status transitions for now
            # Phase 4 will fully integrate OrganizationalTicketService into status flows
            update_ticket(serializer, user)
        else:
            update_ticket(serializer, user)


# --------------------------------
# TICKET ESCALATION API
# ----------------------------------

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
            escalated_ticket = OrganizationalTicketService.escalate_ticket(
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


# --------------------------------
# COMMENTS API
# ----------------------------------

class CommentListCreateView(ListCreateAPIView):
    serializer_class = CommentSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['author']  # Removed 'ticket' since we filter by URL
    # Users must be authenticated to comment
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter comments by ticket_id from URL"""
        ticket_id = self.kwargs.get("ticket_id")
        return Comment.objects.filter(ticket_id=ticket_id).order_by('created_at')

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        create_comment(serializer, self.request.user, ticket_id)


# --------------------------------
# FEEDBACK API
# ----------------------------------

class FeedbackListCreateView(ListCreateAPIView):
    serializer_class = FeedbackSerializer
    filter_backends = [DjangoFilterBackend]
    # Removed 'ticket' since we filter by URL
    filterset_fields = ['rating', 'rated_by']
    # Users must be authenticated to provide feedback
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter feedback by ticket_id from URL"""
        ticket_id = self.kwargs.get("ticket_id")
        return Feedback.objects.filter(ticket_id=ticket_id).order_by('-created_at')

    def perform_create(self, serializer):
        ticket_id = self.kwargs.get("ticket_id")
        create_feedback(serializer, self.request.user, ticket_id)


# --------------------------------
# USERS API
# ----------------------------------

class UserListCreateView(ListCreateAPIView):
    queryset = CustomUser.objects.all().order_by('username')
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'sections']
    permission_classes = [CanManageUsers]  # Role-based user management


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [CanManageUsers]  # Role-based user management


# --------------------------------
# TECHNICIANS BY SECTION API
# ----------------------------------

class TechniciansBySectionView(generics.ListAPIView):
    """
    Get technicians filtered by section.
    Used when assigning tickets to show only relevant technicians.

    Query params:
    - section_id: Filter technicians by section (required for assignment)
    """
    serializer_class = UserSerializer
    pagination_class = None  # Return unpaginated list for dropdown/assignment UI
    # Only technicians and above can assign
    permission_classes = [IsTechnicianOrAdmin]

    def get_queryset(self):
        """Filter technicians by section if provided."""
        queryset = CustomUser.objects.filter(role='technician')

        # Filter by section if provided
        section_id = self.request.query_params.get('section_id')
        if section_id:
            queryset = queryset.filter(sections__id=section_id)

        return queryset.distinct().order_by('username')
