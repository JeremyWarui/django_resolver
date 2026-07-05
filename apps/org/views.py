from rest_framework import serializers as drf_serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count

from apps.common.pagination import ConfigListPagination
from apps.common.permissions import IsAdminGroup, IsAdminOrReadOnly, get_request_role
from apps.tickets.services.scope import scoped_section_qs
from apps.org.models import (
    Campus,
    CampusDepartment,
    Department,
    Section,
    SectionTechnician,
    SectionType,
)
from apps.org.serializers import (
    CampusDepartmentSerializer,
    CampusSerializer,
    DepartmentSerializer,
    SectionSerializer,
    SectionTechnicianSerializer,
    SectionTypeSerializer,
    SectionTypeWithCategoriesSerializer,
)


class CampusViewSet(viewsets.ModelViewSet):
    queryset = Campus.objects.all().order_by("name")
    serializer_class = CampusSerializer
    permission_classes = [IsAdminGroup]
    pagination_class = ConfigListPagination


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related("manager_user").prefetch_related(
        "campus_departments__campus",
        "campus_departments__head_of_department",
    ).order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = ConfigListPagination

    def get_queryset(self):
        qs = super().get_queryset()
        campus_id = self.request.query_params.get("campus")
        if campus_id:
            qs = qs.filter(campus_departments__campus_id=campus_id)
        return qs


class SectionTypeViewSet(viewsets.ModelViewSet):
    """Admin CRUD for section types.
    List/retrieve return the richer SectionTypeWithCategoriesSerializer so the
    requester QuickActions widget can render the service catalogue grouped by
    department without a second round-trip."""

    queryset = (
        SectionType.objects.select_related("department")
        .prefetch_related("service_categories")
        .order_by("department", "name")
    )
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = ConfigListPagination

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return SectionTypeWithCategoriesSerializer
        return SectionTypeSerializer


class CampusDepartmentViewSet(viewsets.ModelViewSet):
    queryset = CampusDepartment.objects.select_related(
        "campus", "department", "head_of_department"
    ).order_by("campus", "department")
    serializer_class = CampusDepartmentSerializer
    permission_classes = [IsAdminGroup]
    pagination_class = ConfigListPagination

    @action(detail=True, methods=["get"], url_path="hod-candidates")
    def hod_candidates(self, request, pk=None):
        """Users who have an active HOD role assignment for this campus-department."""
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment

        cd = self.get_object()
        User = get_user_model()
        users = User.objects.filter(
            role_assignments__role="hod",
            role_assignments__campus_department=cd,
        ).distinct().order_by("last_name", "first_name")

        data = [
            {
                "id": u.id,
                "name": f"{u.first_name} {u.last_name}".strip() or u.username,
                "username": u.username,
            }
            for u in users
        ]
        return Response(data)

    @action(detail=True, methods=["patch"], url_path="assign-hod")
    def assign_hod(self, request, pk=None):
        """Set or clear the head_of_department for this campus-department."""
        from django.contrib.auth import get_user_model

        cd = self.get_object()
        hod_id = request.data.get("hod_id")

        if hod_id is None:
            cd.head_of_department = None
        else:
            User = get_user_model()
            try:
                cd.head_of_department = User.objects.get(pk=hod_id)
            except User.DoesNotExist:
                raise drf_serializers.ValidationError({"hod_id": "User not found."})

        cd.save(update_fields=["head_of_department"])
        return Response(CampusDepartmentSerializer(cd).data)


class SectionViewSet(viewsets.ModelViewSet):
    queryset = (
        Section.objects.select_related(
            "campus_department__campus",
            "campus_department__department",
            "section_type",
            "hos",
        )
        .annotate(technician_count=Count("technician_links", distinct=True))
        .order_by(
            "campus_department__campus__name",
            "campus_department__department__name",
            "section_type__name",
        )
    )
    serializer_class = SectionSerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = ConfigListPagination

    def get_queryset(self):
        qs = super().get_queryset()
        department_id = self.request.query_params.get("department")
        if department_id:
            qs = qs.filter(campus_department__department_id=department_id)
        return qs


class SectionTechnicianViewSet(viewsets.ModelViewSet):
    """Nested under /sections/<section_pk>/technicians/."""

    serializer_class = SectionTechnicianSerializer
    permission_classes = [IsAdminGroup]
    pagination_class = ConfigListPagination

    def get_queryset(self):
        qs = SectionTechnician.objects.select_related("user", "section")
        section_pk = self.kwargs.get("section_pk")
        if section_pk:
            qs = qs.filter(section_id=section_pk)
        return qs.order_by("section", "user")

    def perform_create(self, serializer):
        section_pk = self.kwargs.get("section_pk")
        if section_pk:
            serializer.save(section_id=section_pk)
        else:
            serializer.save()


class ScopedTechnicianRosterView(APIView):
    """Technician roster for the caller's scope.

    Returns the technicians assigned (via ``SectionTechnician``) to the sections
    the caller manages — admin = all, manager = department, hod = campus
    department, hos = their section(s), technician = own sections. Unlike the
    ticket-derived analytics list, this includes idle technicians. Scope is
    derived server-side from the JWT role via ``scoped_section_qs`` (fail-closed).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_request_role(request)
        sections = scoped_section_qs(request.user, role)
        links = (
            SectionTechnician.objects.filter(section__in=sections)
            .select_related(
                "user",
                "section__section_type",
                "section__campus_department__campus",
                "section__campus_department__department",
            )
            .order_by("user__first_name", "user__last_name")
        )

        techs = {}
        for link in links:
            u = link.user
            entry = techs.get(u.id)
            if entry is None:
                full = f"{u.first_name} {u.last_name}".strip() or u.username
                entry = techs[u.id] = {
                    "id": u.id,
                    "username": u.username,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "name": full,
                    "email": u.email,
                    "role": "technician",
                    "sections": [],
                    "section_names": [],
                    "campus_name": None,
                    "primary_campus_id": None,
                    "primary_campus_display": None,
                    "primary_department_id": None,
                    "primary_department_display": None,
                    "primary_department_name": None,
                }
            sec = link.section
            entry["sections"].append(sec.id)
            stype = sec.section_type.name if sec.section_type_id else None
            if stype and stype not in entry["section_names"]:
                entry["section_names"].append(stype)
            # First section establishes the technician's primary campus/department.
            if entry["campus_name"] is None:
                cd = sec.campus_department
                campus = cd.campus
                dept = cd.department
                entry["campus_name"] = campus.name
                entry["primary_campus_id"] = campus.id
                entry["primary_campus_display"] = str(campus)
                entry["primary_department_id"] = dept.id
                entry["primary_department_display"] = str(dept)
                entry["primary_department_name"] = dept.name

        return Response(sorted(techs.values(), key=lambda t: t["name"].lower()))


class SectionAssignableTechniciansView(APIView):
    """Lightweight read-only list of users assignable to tickets in a section.

    Returns User objects keyed by user.id — not SectionTechnician link records.
    Accessible to any authenticated user so HOS/technician roles can use the
    assignment modal.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, section_pk):
        links = (
            SectionTechnician.objects.filter(section_id=section_pk)
            .select_related("user")
            .order_by("user__first_name", "user__last_name", "user__username")
        )
        data = [
            {
                "id": link.user.id,
                "username": link.user.username,
                "first_name": link.user.first_name,
                "last_name": link.user.last_name,
            }
            for link in links
        ]
        return Response(data)
