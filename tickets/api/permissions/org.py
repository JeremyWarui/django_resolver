from rest_framework import permissions
from tickets.models import Ticket, Campus, Department


class IsWithinOrganizationalScope(permissions.BasePermission):
    """
    Ensures users can only access data within their organizational scope.

    Scope access:
    - user/technician: section-level
    - head_of_section: department-level
    - hod: campus-level
    - manager: organization-level
    - admin: system-level (all access)
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # System admins have access to everything
        if request.user.role == "admin":
            return True

        # All other authenticated roles have scoped access
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user

        # System admin access - full access to everything
        if user.role == "admin":
            return True

        # Object-specific scope checking based on object type
        if isinstance(obj, Ticket):
            return self._check_ticket_access(user, obj)

        if isinstance(obj, Campus):
            return self._check_campus_access(user, obj)
        if isinstance(obj, Department):
            return self._check_department_access(user, obj)

        # Check if object has organizational context (FK relationships)
        if hasattr(obj, "section"):
            return self._check_section_access(user, obj.section)
        elif hasattr(obj, "department"):
            return self._check_department_access(user, obj.department)
        elif hasattr(obj, "campus"):
            return self._check_campus_access(user, obj.campus)

        return False

    @staticmethod
    def _check_ticket_access(user, ticket):
        """Check if user can access a specific ticket."""
        # Always allow the raiser to see their own ticket regardless of section state.
        if user.role == "user":
            return ticket.raised_by == user

        if not ticket.section or not ticket.section.campus_department:
            return False

        if user.role == "manager":
            return True  # managers have organisation-wide read access
        elif user.role == "hod":
            # HOD can see all tickets in their campus
            return ticket.section.campus_department.campus == user.primary_campus
        elif user.role == "head_of_section":
            # Section head can see all tickets in their department (by CampusDepartment)
            pd = user.primary_campus_department
            return pd and ticket.section.campus_department == pd
        elif user.role == "technician":
            # Technician can see tickets in their sections or assigned to them
            return (
                ticket.section in user.sections.all()
                or ticket.assigned_to == user
                or ticket.raised_by == user
            )
        elif user.role == "user":
            # Users can only see their own tickets
            return ticket.raised_by == user

        return False

    @staticmethod
    def _check_section_access(user, section):
        """Check if user has access to specific section"""
        if not section.campus_department or not section.campus_department.campus:
            return False

        if user.role == "manager":
            return True
        elif user.role == "hod":
            return section.campus_department.campus == user.primary_campus
        elif user.role == "head_of_section":
            pd = user.primary_campus_department
            return pd and section.campus_department == pd
        elif user.role in ["technician", "user"]:
            pd = user.primary_campus_department
            return pd and section.campus_department == pd

        return False

    @staticmethod
    def _check_department_access(user, department):
        """Check if user has access to a Department."""
        if user.role == "manager":
            return True
        if user.role == "hod":
            # HOD can access any department present on their campus
            return department.campus_departments.filter(
                campus=user.primary_campus
            ).exists()
        if user.role in ("head_of_section", "technician", "user"):
            return department == user.primary_department

        return False

    @staticmethod
    def _check_campus_access(user, campus):
        """Check if user has access to a specific campus."""
        if user.role == "manager":
            return True
        return user.primary_campus == campus


class CanManageSectionTechnicians(permissions.BasePermission):
    """Permission for adding/removing technicians from sections."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            "head_of_section",
            "hod",
            "admin",
        ]
