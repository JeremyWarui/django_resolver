from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from tickets.api.permissions import (
    IsAdminOrManagerOrReadOnly, IsOwnerOrTechnicianOrAdmin,
    IsTechnicianOrAdmin, CanManageUsers
)
from tickets.serializers import SectionSerializer, FacilitySerializer, TicketSerializer, TicketListSerializer
from tickets.serializers import CommentSerializer, FeedbackSerializer, UserSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from django.db import models
from tickets.api.services.ticket_services import (
    create_ticket, update_ticket, create_comment, create_feedback
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
    permission_classes = [IsAdminOrManagerOrReadOnly]


class SectionDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


# --------------------------------
# FACILITY API
# ----------------------------------

class FacilityListCreateView(ListCreateAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsAdminOrManagerOrReadOnly]


# --------------------------------
# TICKETS API
# ----------------------------------

class TicketListCreateView(ListCreateAPIView):
    queryset = Ticket.objects.all().order_by('-updated_at')
    # Use custom pagination for flexible page sizes
    pagination_class = TicketPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'section', 'assigned_to', 'raised_by']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-updated_at']  # Default ordering
    permission_classes = [IsOwnerOrTechnicianOrAdmin]  # Role-based access

    def get_serializer_class(self):
        """Use optimized serializer for list, full serializer for create."""
        if self.request.method == 'GET':
            return TicketListSerializer  # Fast list serializer
        return TicketSerializer  # Full serializer for create

    def get_queryset(self):
        """
        Filter tickets based on user role:
        - Users: Only their own tickets
        - Technicians: Tickets assigned to them or in their sections + their own
        - Admins/Managers: All tickets
        """
        queryset = Ticket.objects.select_related(
            'section',
            'facility',
            'raised_by',
            'assigned_to'  # Only fields needed for list view
        ).order_by('-updated_at')

        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()

        # Filter based on user role
        if user.role == 'user':
            queryset = queryset.filter(raised_by=user)
        elif user.role == 'technician':
            queryset = queryset.filter(
                models.Q(raised_by=user) |  # Their own tickets
                models.Q(assigned_to=user) |  # Assigned to them
                models.Q(section__in=user.sections.all())  # In their sections
            )
        # Admins and managers see all tickets (no additional filtering)

        # Handle additional filters
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
        """Delegate ticket creation to service layer """
        create_ticket(serializer, self.request.user)


class TicketDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Ticket.objects.select_related(
        'section', 'facility', 'raised_by', 'assigned_to'
    ).prefetch_related('comments', 'comments__author', 'feedback').all()
    serializer_class = TicketSerializer
    permission_classes = [IsOwnerOrTechnicianOrAdmin]

    def perform_update(self, serializer):
        """ delegate ticket update ( assign, update status, etc) """
        update_ticket(
            serializer, self.request.user)  # Pass authenticated user to update_ticket


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
