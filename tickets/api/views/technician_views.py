"""Technician-section assignment views."""

from rest_framework.generics import (
    ListCreateAPIView,
    DestroyAPIView,
    CreateAPIView,
    ListAPIView,
)
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError

from django_filters.rest_framework import DjangoFilterBackend

from tickets.api.permissions import CanManageSectionTechnicians
from tickets.api.services import (
    TechnicianService,
    InsufficientScopeException,
    InvalidAssignmentException,
)
from tickets.serializers import TechnicianSectionSerializer, UserSerializer
from tickets.models import Section, TechnicianSection


class SectionTechniciansView(ListAPIView):
    """GET /sections/<pk>/technicians/ — assignable technicians for a section."""

    serializer_class = UserSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated, CanManageSectionTechnicians]

    def get_queryset(self):
        section = generics.get_object_or_404(Section, pk=self.kwargs["pk"])
        return TechnicianService.get_assignable_technicians(self.request.user, section)


class TechnicianSectionListCreateView(ListCreateAPIView):
    """GET /technician-sections/ — list assignments. POST — assign technician to section.

    POST body: { "technician": <user_pk>, "section": <section_pk> }
    """

    serializer_class = TechnicianSectionSerializer
    permission_classes = [IsAuthenticated, CanManageSectionTechnicians]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["section", "technician"]

    def get_queryset(self):
        user = self.request.user
        qs = TechnicianSection.objects.select_related(
            "technician", "section__campus_department__campus"
        )
        if user.role == "admin":
            return qs
        if user.role == "hod" and user.primary_campus:
            return qs.filter(section__campus_department__campus=user.primary_campus)
        if user.role == "head_of_section":
            return qs.filter(section__head_of_section=user)
        return qs.none()

    def perform_create(self, serializer):
        technician = serializer.validated_data["technician"]
        section = serializer.validated_data["section"]
        try:
            TechnicianService.add_technician_to_section(
                self.request.user, technician, section
            )
        except (InsufficientScopeException, InvalidAssignmentException) as e:
            raise ValidationError({"non_field_errors": [str(e)]})


class TechnicianSectionDestroyView(DestroyAPIView):
    """DELETE /technician-sections/<pk>/ — remove a technician-section link."""

    serializer_class = TechnicianSectionSerializer
    permission_classes = [IsAuthenticated, CanManageSectionTechnicians]

    def get_queryset(self):
        user = self.request.user
        qs = TechnicianSection.objects.select_related(
            "technician", "section__campus_department__campus"
        )
        if user.role == "admin":
            return qs
        if user.role == "hod" and user.primary_campus:
            return qs.filter(section__campus_department__campus=user.primary_campus)
        if user.role == "head_of_section":
            return qs.filter(section__head_of_section=user)
        return qs.none()

    def perform_destroy(self, instance):
        try:
            TechnicianService._check_can_manage(self.request.user, instance.section)
        except InsufficientScopeException as e:
            raise ValidationError({"non_field_errors": [str(e)]})
        instance.delete()


class AddTechnicianToSectionView(CreateAPIView):
    """POST /sections/<pk>/add-technician/ — legacy endpoint, prefer /technician-sections/."""

    serializer_class = TechnicianSectionSerializer
    permission_classes = [IsAuthenticated, CanManageSectionTechnicians]

    def get_serializer(self, *args, **kwargs):
        if "data" in kwargs:
            data = kwargs["data"]
            # QueryDict (multipart) needs .dict(); JSON arrives as a plain dict
            if hasattr(data, "dict"):
                data = data.dict()
            section = generics.get_object_or_404(Section, pk=self.kwargs["pk"])
            kwargs["data"] = {**data, "section": section.id}
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        section = generics.get_object_or_404(Section, pk=self.kwargs["pk"])
        technician = serializer.validated_data["technician"]
        try:
            ts = TechnicianService.add_technician_to_section(
                self.request.user, technician, section
            )
            serializer.instance = ts
        except (InsufficientScopeException, InvalidAssignmentException) as e:
            raise ValidationError({"non_field_errors": [str(e)]})


class RemoveTechnicianFromSectionView(DestroyAPIView):
    """DELETE /sections/<pk>/technician-sections/<ts_pk>/ — legacy endpoint."""

    serializer_class = TechnicianSectionSerializer
    permission_classes = [IsAuthenticated, CanManageSectionTechnicians]

    def get_object(self):
        return generics.get_object_or_404(
            TechnicianSection,
            pk=self.kwargs["ts_pk"],
            section_id=self.kwargs["pk"],
        )

    def perform_destroy(self, instance):
        try:
            TechnicianService._check_can_manage(self.request.user, instance.section)
        except InsufficientScopeException as e:
            raise ValidationError({"non_field_errors": [str(e)]})
        instance.delete()
