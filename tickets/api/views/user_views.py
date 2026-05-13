"""User and technician-listing views."""

from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
)
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend

from tickets.api.permissions import (
    CanManageUsers,
    CanAssignTickets,
    IsTechnicianOrAdmin,
)
from tickets.api.services import TicketService
from tickets.serializers import UserSerializer
from tickets.models import CustomUser, Section


class UserListCreateView(ListCreateAPIView):
    queryset = (
        CustomUser.objects.select_related("primary_campus", "primary_department")
        .prefetch_related("sections")
        .order_by("username")
    )
    serializer_class = UserSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["role", "sections"]
    permission_classes = [CanManageUsers]


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [CanManageUsers]


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
        queryset = CustomUser.objects.filter(role="technician")

        section_id = self.request.query_params.get("section_id")
        if section_id:
            queryset = queryset.filter(sections__id=section_id)

        campus_id = self.request.query_params.get("campus_id")
        if campus_id:
            queryset = queryset.filter(primary_campus_id=campus_id)

        return queryset.distinct().order_by("first_name", "last_name")


class AssignableUsersView(ListAPIView):
    """
    Get technicians that can be assigned tickets in a specific section.

    Query Parameters:
    - section_id: Required. ID of the section to get technicians for
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, CanAssignTickets]

    def get_queryset(self):
        section_id = self.request.query_params.get("section_id")

        if not section_id:
            return CustomUser.objects.none()

        try:
            section = Section.objects.select_related(
                "campus_department__campus",
                "campus_department__department",
            ).get(id=section_id)
        except Section.DoesNotExist:
            return CustomUser.objects.none()

        user = self.request.user

        try:
            if not TicketService._user_can_access_section(user, section):
                return CustomUser.objects.none()
        except Exception:
            return CustomUser.objects.none()

        return (
            CustomUser.objects.filter(
                role="technician", sections=section, is_active=True
            )
            .order_by("first_name", "last_name")
            .select_related("primary_department")
        )
