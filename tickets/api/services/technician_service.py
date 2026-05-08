"""Technician service for managing technician-section assignments."""

from django.db.models import QuerySet
from tickets.models import CustomUser, Section
from .exceptions import InsufficientScopeException, InvalidAssignmentException


class TechnicianService:
    """Service for managing technician-section assignments with org scope validation."""

    @staticmethod
    def _check_can_manage(user: CustomUser, section: Section) -> None:
        """Raise InsufficientScopeException if user cannot manage technicians in section."""
        if user.role == "admin":
            return
        if user.role in ["user", "technician", "manager"]:
            raise InsufficientScopeException(
                f"Role '{user.role}' cannot manage section technicians."
            )
        if not section.department or not section.department.campus:
            raise InsufficientScopeException(
                "Section has no valid department/campus.")
        if user.role == "hod":
            if section.department.campus != user.primary_campus:
                raise InsufficientScopeException(
                    "HoD can only manage technicians within their campus."
                )
            if user.primary_department and section.department != user.primary_department:
                raise InsufficientScopeException(
                    "HoD can only manage technicians within their department."
                )
        elif user.role == "head_of_section":
            if section.department.campus != user.primary_campus:
                raise InsufficientScopeException(
                    "Head of Section can only manage technicians within their campus."
                )
            if user.primary_department and section.department != user.primary_department:
                raise InsufficientScopeException(
                    "Head of Section can only manage technicians within their department."
                )

    @staticmethod
    def add_technician_to_section(
        user: CustomUser, technician: CustomUser, section: Section
    ) -> None:
        """Add a technician to a section. Validates scope for both the acting user and the technician."""
        TechnicianService._check_can_manage(user, section)
        if technician.role != "technician":
            raise InvalidAssignmentException(
                f"User '{technician.username}' is not a technician."
            )
        if not section.department or not section.department.campus:
            raise InvalidAssignmentException(
                "Section has no valid department/campus.")
        if (
            user.role != "admin"
            and technician.primary_campus
            and technician.primary_campus != section.department.campus
        ):
            raise InvalidAssignmentException(
                "Technician must be on the same campus as the section."
            )
        technician.sections.add(section)

    @staticmethod
    def remove_technician_from_section(
        user: CustomUser, technician: CustomUser, section: Section
    ) -> None:
        """Remove a technician from a section."""
        TechnicianService._check_can_manage(user, section)
        if not technician.sections.filter(pk=section.pk).exists():
            raise InvalidAssignmentException(
                f"Technician '{technician.username}' is not assigned to this section."
            )
        technician.sections.remove(section)

    @staticmethod
    def get_assignable_technicians(
        user: CustomUser, section: Section
    ) -> QuerySet:
        """Return technicians that can be assigned to the given section, scoped by role."""

        if user.role == "admin":
            return CustomUser.objects.filter(role="technician")
        if user.role == "manager":
            raise InsufficientScopeException(
                "Manager role cannot manage technicians.")
        if not section.department or not section.department.campus:
            return CustomUser.objects.none()
        campus = section.department.campus
        dept = section.department
        if user.role == "hod":
            return CustomUser.objects.filter(
                role="technician",
                primary_campus=campus,
                primary_department=dept,
            )
        if user.role == "head_of_section":
            # head_of_section can only manage technicians in their specific section
            return CustomUser.objects.filter(
                role="technician",
                sections__id=section.id,
            )
        return CustomUser.objects.none()
