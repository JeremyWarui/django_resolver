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
    pagination_class = None


class UserDetailView(RetrieveUpdateDestroyAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [CanManageUsers]


class TechnicianListView(generics.ListAPIView):
    """GET /api/technicians/

    Returns active technicians with their sections, campus, and department.
    Unpaginated — intended for dropdowns, admin tables, and dashboard contexts.

    Optional query params for scoping:
        campus_department_id — only technicians in sections under this CampusDepartment
        section_id           — only technicians assigned to this specific section
        campus_id            — only technicians whose primary campus matches
    """

    serializer_class = UserSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = (
            CustomUser.objects.filter(role="technician", is_active=True)
            .select_related("primary_campus", "primary_department")
            .prefetch_related("sections__campus_department__campus")
            .order_by("primary_campus__name", "username")
        )

        campus_department_id = self.request.query_params.get("campus_department_id")
        section_id = self.request.query_params.get("section_id")
        section_ids = self.request.query_params.get("section_ids")  # comma-separated
        campus_id = self.request.query_params.get("campus_id")

        if campus_department_id:
            qs = qs.filter(sections__campus_department_id=campus_department_id).distinct()
        elif section_ids:
            ids = [i.strip() for i in section_ids.split(",") if i.strip().isdigit()]
            qs = qs.filter(sections__id__in=ids).distinct()
        elif section_id:
            qs = qs.filter(sections__id=section_id).distinct()
        elif campus_id:
            qs = qs.filter(primary_campus_id=campus_id).distinct()

        return qs


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
