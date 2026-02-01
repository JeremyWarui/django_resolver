from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import generics
from tickets.serializers import SectionSerializer, FacilitySerializer, TicketSerializer
from tickets.serializers import CommentSerializer, FeedbackSerializer, UserSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from tickets.api.services.ticket_services import (
    create_ticket, update_ticket, create_comment, create_feedback
)
from tickets.models import Section, Facility, Ticket, Comment, Feedback, CustomUser
from django.utils import timezone
from datetime import timedelta


# --------------------------------
# SECTION API
# ----------------------------------

class SectionListCreateView(ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    # permission_classes = [IsAuthenticated]


class SectionDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    # permission_classes = [IsAuthenticated]


# --------------------------------
# FACILITY API
# ----------------------------------

class FacilityListCreateView(ListCreateAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    # permission_classes = [IsAuthenticated]


class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    # permission_classes = [IsAuthenticated]


# --------------------------------
# TICKETS API
# ----------------------------------

class TicketListCreateView(ListCreateAPIView):
    queryset = Ticket.objects.all().order_by('-updated_at')
    serializer_class = TicketSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'section', 'assigned_to', 'raised_by']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-updated_at']  # Default ordering
    # permission_classes = [IsAuthenticated]  # Commented out to allow public access

    def get_queryset(self):
        """
        Optimized queryset with select_related and prefetch_related.
        Optionally filter tickets by:
        - assigned_to__isnull: for unassigned tickets
        - is_overdue: for tickets older than 7 days in active states
        """
        queryset = Ticket.objects.select_related(
            'section',
            'facility',
            'raised_by',
            'assigned_to'
        ).prefetch_related(
            'comments',
            'feedback'
        ).order_by('-updated_at')

        # Handle unassigned filter
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
    # permission_classes = [IsAuthenticated]  # Make sure user is authenticated

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
    # permission_classes = [IsAuthenticated]

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
    # permission_classes = [IsAuthenticated]

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
    # permission_classes = [IsAuthenticated]


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticated]


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
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter technicians by section if provided."""
        queryset = CustomUser.objects.filter(role='technician')

        # Filter by section if provided
        section_id = self.request.query_params.get('section_id')
        if section_id:
            queryset = queryset.filter(sections__id=section_id)

        return queryset.distinct().order_by('username')
