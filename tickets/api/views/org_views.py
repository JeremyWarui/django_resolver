"""
Organization Hierarchy Views

Covers: Campus, Department, CampusDepartment, Section, Facility CRUD endpoints
plus the AssignHOD and AssignHOS actions.
"""

from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    UpdateAPIView,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from django_filters.rest_framework import DjangoFilterBackend

from tickets.api.permissions import (
    IsAdminOrReadOnly,
    IsWithinOrganizationalScope,
)
from tickets.serializers import (
    CampusSerializer,
    DepartmentSerializer,
    CampusDepartmentSerializer,
    AssignHODSerializer,
    AssignHOSSerializer,
    SectionSerializer,
    FacilitySerializer,
)
from tickets.models import (
    Campus,
    Department,
    CampusDepartment,
    Section,
    Facility,
)
from .view_mixins import AdminOnlyCreateMixin

# ============================================================================
# ORGANIZATION HIERARCHY ENDPOINTS
# ============================================================================


class CampusListCreateView(AdminOnlyCreateMixin, ListCreateAPIView):
    """GET /campuses/ — scoped list. POST — admin only."""

    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ("admin", "manager"):
            return Campus.objects.all()
        if user.primary_campus:
            return Campus.objects.filter(id=user.primary_campus.id)
        return Campus.objects.none()


class CampusDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT/DELETE /campuses/<pk>/ — writes are admin only."""

    queryset = Campus.objects.all()
    serializer_class = CampusSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


# ──────────────────────────────────────────────────────────────────────────────


class DepartmentListCreateView(AdminOnlyCreateMixin, ListCreateAPIView):
    """GET /departments/ — scoped list. POST — admin only.

    Departments are global; scoping means showing only those present on the
    user's campus (via CampusDepartment) for non-admin/non-manager roles.
    """

    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ("admin", "manager"):
            return Department.objects.select_related("manager_user").all()
        if user.primary_campus:
            return Department.objects.filter(
                campus_departments__campus=user.primary_campus
            ).distinct()
        return Department.objects.none()


class DepartmentDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT/DELETE /departments/<pk>/ — writes are admin only."""

    queryset = Department.objects.select_related("manager_user").all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


# ──────────────────────────────────────────────────────────────────────────────


class CampusDepartmentListCreateView(AdminOnlyCreateMixin, ListCreateAPIView):
    """GET /campus-departments/ — list mappings in scope. POST — admin only.

    POST body: { campus_id, department_id, head_of_department_id (optional) }
    """

    serializer_class = CampusDepartmentSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["campus", "department"]

    def get_queryset(self):
        user = self.request.user
        qs = CampusDepartment.objects.select_related(
            "campus", "department", "head_of_department"
        )
        if user.role in ("admin", "manager"):
            return qs
        if user.primary_campus:
            return qs.filter(campus=user.primary_campus)
        return qs.none()


class CampusDepartmentDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT/DELETE /campus-departments/<pk>/

    PATCH this endpoint with { head_of_department_id } to assign an HOD
    without going through the dedicated assign-hod endpoint.
    """

    queryset = CampusDepartment.objects.select_related(
        "campus", "department", "head_of_department"
    )
    serializer_class = CampusDepartmentSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


class AssignHODView(UpdateAPIView):
    """PATCH /campus-departments/<pk>/assign-hod/

    Body: { "head_of_department_id": <user_pk> | null }
    Restricted to admin users. Managers and HODs read-only.
    """

    queryset = CampusDepartment.objects.select_related("head_of_department")
    serializer_class = AssignHODSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    http_method_names = ["patch"]

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────


class SectionListCreateView(AdminOnlyCreateMixin, ListCreateAPIView):
    """GET /sections/ — scoped list. POST — admin only.

    POST body: { campus_department_id, section_type_id, name, code, description,
                 sla_hours (optional) }
    """

    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["campus_department"]

    def get_queryset(self):
        user = self.request.user
        qs = Section.objects.select_related(
            "campus_department__campus",
            "campus_department__department",
            "section_type",
            "head_of_section",
        )
        if user.role == "admin":
            return qs
        if user.role == "manager":
            return qs.filter(
                campus_department__campus__in=user.get_accessible_campuses()
            )
        if user.role == "hod" and user.primary_campus:
            return qs.filter(campus_department__campus=user.primary_campus)
        if user.role == "head_of_section":
            return qs.filter(head_of_section=user)
        if user.role in ("technician", "user"):
            return qs.filter(pk__in=user.sections.all())
        return qs.none()


class SectionDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT/DELETE /sections/<pk>/"""

    queryset = Section.objects.select_related(
        "campus_department__campus",
        "campus_department__department",
        "section_type",
        "head_of_section",
    )
    serializer_class = SectionSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


class AssignHOSView(UpdateAPIView):
    """PATCH /sections/<pk>/assign-hos/

    Body: { "head_of_section_id": <user_pk> | null }
    Admin or HOD of the section's campus may assign. Others read-only.
    """

    queryset = Section.objects.select_related("head_of_section")
    serializer_class = AssignHOSSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    http_method_names = ["patch"]

    def update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)


# ============================================================================
# FACILITY API
# ============================================================================


class FacilityListCreateView(AdminOnlyCreateMixin, ListCreateAPIView):
    resource_name = "facilities"
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsWithinOrganizationalScope]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["campus", "type"]

    def create(self, request, *args, **kwargs):
        """Restrict facility creation to admins only"""
        if request.user.role != "admin":
            raise PermissionDenied("Only administrators can create facilities")
        return super().create(request, *args, **kwargs)

    def get_queryset(self):
        """Filter facilities based on user's organizational scope"""
        queryset = Facility.objects.select_related("campus").all()
        user = self.request.user

        if user.role == "admin":
            return queryset
        elif user.role in ("admin", "manager"):
            return queryset
        elif user.role in ["hod", "head_of_section", "technician", "user"]:
            return queryset.filter(campus=user.primary_campus)

        return queryset.none()


class FacilityDetailView(RetrieveUpdateDestroyAPIView):
    queryset = Facility.objects.all()
    serializer_class = FacilitySerializer
    permission_classes = [IsWithinOrganizationalScope]
