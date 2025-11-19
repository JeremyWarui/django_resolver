from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import generics
from tickets.serializers import SectionSerializer, FacilitySerializer, TicketSerializer
from tickets.serializers import CommentSerializer, FeedbackSerializer, UserSerializer
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from tickets.api.services.ticket_services import (
    create_ticket, update_ticket, create_comment, create_feedback
)
from tickets.api.pagination import StandardResultsSetPagination
from tickets.models import Section, Facility, Ticket, Comment, Feedback, CustomUser
from tickets.api.cache_utils import CacheKeyBuilder, get_or_set_cache
from django.utils import timezone
from datetime import timedelta


# --------------------------------
# SECTION API
# ----------------------------------

class SectionListCreateView(ListCreateAPIView):
    queryset = Section.objects.all()
    serializer_class = SectionSerializer
    pagination_class = StandardResultsSetPagination
    # permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """
        Override list to add caching for sections lookup.
        Cache for 1 hour since sections rarely change.
        """
        cache_key = CacheKeyBuilder.sections_list()

        def fetch_sections():
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)

            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                # Return data dict, not Response object (can't pickle Response)
                return self.get_paginated_response(serializer.data).data

            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        # Cache for 1 hour (3600 seconds)
        cached_data = get_or_set_cache(
            cache_key, fetch_sections, timeout=3600)

        return Response(cached_data)


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
    pagination_class = StandardResultsSetPagination
    # permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """
        Override list to add caching for facilities lookup.
        Cache for 1 hour since facilities rarely change.
        """
        cache_key = CacheKeyBuilder.facilities_list()

        def fetch_facilities():
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)

            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                # Return data dict, not Response object (can't pickle Response)
                return self.get_paginated_response(serializer.data).data

            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        # Cache for 1 hour (3600 seconds)
        cached_data = get_or_set_cache(
            cache_key, fetch_facilities, timeout=3600)

        return Response(cached_data)


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
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['status', 'section', 'assigned_to', 'raised_by']
    ordering_fields = ['created_at', 'updated_at', 'status']
    ordering = ['-updated_at']  # Default ordering
    # permission_classes = [IsAuthenticated]

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

    def get_serializer_context(self):
        """Add flag to skip expensive fields in list views."""
        context = super().get_serializer_context()
        # Skip available_technicians calculation in list views for performance
        context['skip_available_technicians'] = True
        return context
        return context

    def list(self, request, *args, **kwargs):
        """
        Override list to add caching for common dashboard queries.
        Cache for 2 minutes to balance freshness and performance.
        """
        # Extract filter parameters
        status = request.query_params.get('status')
        section = request.query_params.get('section')
        assigned_to = request.query_params.get('assigned_to')
        raised_by = request.query_params.get('raised_by')
        is_overdue = request.query_params.get('is_overdue')
        assigned_to_isnull = request.query_params.get('assigned_to__isnull')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 10)

        # Build cache key
        cache_key = CacheKeyBuilder.ticket_list(
            status=status,
            section=section,
            assigned_to=assigned_to,
            raised_by=raised_by,
            is_overdue=is_overdue,
            assigned_to_isnull=assigned_to_isnull,
            page=page,
            page_size=page_size
        )

        # Get cached response or compute
        def fetch_ticket_list():
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)

            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                # Return data dict, not Response object (can't pickle Response)
                return self.get_paginated_response(serializer.data).data

            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        # Cache for 2 minutes (120 seconds) for dashboard queries
        cached_data = get_or_set_cache(
            cache_key, fetch_ticket_list, timeout=120)

        return Response(cached_data)

    def perform_create(self, serializer):
        """Delegate ticket creation to service layer """
        create_ticket(serializer, self.request.user)


class TicketDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Ticket.objects.select_related(
        'section', 'facility', 'raised_by', 'assigned_to'
    ).prefetch_related('comments', 'comments__author', 'feedback').all()
    serializer_class = TicketSerializer
    # permission_classes = [IsAuthenticated]  # Make sure user is authenticated

    def get_serializer_context(self):
        """Include available_technicians in detail views."""
        context = super().get_serializer_context()
        # Do NOT skip available_technicians in detail views
        context['skip_available_technicians'] = False
        return context

    def perform_update(self, serializer):
        """ delegate ticket update ( assign, update status, etc) """
        update_ticket(
            serializer, self.request.user)  # Pass authenticated user to update_ticket


# --------------------------------
# COMMENTS API
# ----------------------------------

class CommentListCreateView(ListCreateAPIView):
    serializer_class = CommentSerializer
    pagination_class = StandardResultsSetPagination
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
    pagination_class = StandardResultsSetPagination
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
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['role', 'sections']
    # permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        """
        Override list to add caching for user queries (especially technician lists).
        Cache for 15 minutes for role-based queries.
        """
        # Extract filter parameters
        role = request.query_params.get('role')
        sections = request.query_params.get('sections')
        page = request.query_params.get('page', 1)
        page_size = request.query_params.get('page_size', 10)

        # Build cache key
        cache_key = CacheKeyBuilder.user_list(
            role=role,
            sections=sections,
            page=page,
            page_size=page_size
        )

        def fetch_user_list():
            queryset = self.filter_queryset(self.get_queryset())
            page_obj = self.paginate_queryset(queryset)

            if page_obj is not None:
                serializer = self.get_serializer(page_obj, many=True)
                # Return data dict, not Response object (can't pickle Response)
                return self.get_paginated_response(serializer.data).data

            serializer = self.get_serializer(queryset, many=True)
            return serializer.data

        # Cache for 15 minutes (900 seconds)
        cached_data = get_or_set_cache(
            cache_key, fetch_user_list, timeout=900)

        return Response(cached_data)


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
    # permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter technicians by section if provided."""
        queryset = CustomUser.objects.filter(role='technician')

        # Filter by section if provided
        section_id = self.request.query_params.get('section_id')
        if section_id:
            queryset = queryset.filter(sections__id=section_id)

        return queryset.distinct().order_by('username')
