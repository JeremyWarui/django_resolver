"""Technician service for managing technician-section assignments."""

from django.db.models import QuerySet
from tickets.models import CustomUser, Section, TechnicianSection
from .exceptions import InsufficientScopeException, InvalidAssignmentException


class TechnicianService:
    """Service for managing technician-section assignments with org scope validation."""

    @staticmethod
    def _check_can_manage(user: CustomUser, section: Section) -> None:
        """Raise InsufficientScopeException if user cannot manage technicians in section."""
        if user.role == "admin":
            return
        if user.role in ("user", "technician", "manager"):
            raise InsufficientScopeException(
                f"Role '{user.role}' cannot manage section technicians."
            )
        campus = section.campus_department.campus
        department = section.campus_department.department
        if user.role == "hod":
            if campus != user.primary_campus:
                raise InsufficientScopeException(
                    "HOD can only manage technicians within their campus."
                )
            if user.primary_department and department != user.primary_department:
                raise InsufficientScopeException(
                    "HOD can only manage technicians within their department."
                )
        elif user.role == "head_of_section":
            if campus != user.primary_campus:
                raise InsufficientScopeException(
                    "Head of Section can only manage technicians within their campus."
                )
            if section.head_of_section != user:
                raise InsufficientScopeException(
                    "Head of Section can only manage technicians in sections they head."
                )

    @staticmethod
    def add_technician_to_section(
        user: CustomUser, technician: CustomUser, section: Section
    ) -> TechnicianSection:
        """Validate scope and create a TechnicianSection link. Returns the new instance."""
        TechnicianService._check_can_manage(user, section)
        if technician.role != "technician":
            raise InvalidAssignmentException(
                f"User '{technician.username}' is not a technician."
            )
        campus = section.campus_department.campus
        if (
            user.role != "admin"
            and technician.primary_campus
            and technician.primary_campus != campus
        ):
            raise InvalidAssignmentException(
                "Technician must be on the same campus as the section."
            )
        obj, created = TechnicianSection.objects.get_or_create(
            technician=technician, section=section
        )
        if not created:
            raise InvalidAssignmentException(
                f"'{technician.username}' is already assigned to '{section.name}'."
            )
        return obj

    @staticmethod
    def remove_technician_from_section(
        user: CustomUser, technician: CustomUser, section: Section
    ) -> None:
        """Validate scope and remove the TechnicianSection link."""
        TechnicianService._check_can_manage(user, section)
        deleted, _ = TechnicianSection.objects.filter(
            technician=technician, section=section
        ).delete()
        if not deleted:
            raise InvalidAssignmentException(
                f"'{technician.username}' is not assigned to '{section.name}'."
            )

    @staticmethod
    def get_assignable_technicians(
        user: CustomUser, section: Section
    ) -> QuerySet:
        """Return technicians that can be assigned to the given section, scoped by role."""
        if user.role == "admin":
            return CustomUser.objects.filter(role="technician", is_active=True)
        if user.role == "manager":
            raise InsufficientScopeException("Manager role cannot manage technicians.")
        campus = section.campus_department.campus
        department = section.campus_department.department
        if user.role == "hod":
            return CustomUser.objects.filter(
                role="technician",
                is_active=True,
                primary_campus=campus,
                primary_department=department,
            )
        if user.role == "head_of_section":
            return CustomUser.objects.filter(
                role="technician",
                is_active=True,
                technician_section_links__section=section,
            ).distinct()
        return CustomUser.objects.none()
