from rest_framework import permissions
from tickets.models import Ticket


class CanViewAndEditTickets(permissions.BasePermission):
    """
    Permission for viewing and editing tickets with organizational scope.

    Distinguishes between VIEW and EDIT permissions:
    - VIEW (GET): Permissive - users can see tickets in their scope
    - EDIT (PATCH/PUT): Restrictive - users can only edit owned/assigned tickets
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def _manager_in_scope(self, user, obj):
        """Manager sees tickets whose department matches their own, across all campuses."""
        if not user.primary_department:
            return False
        return obj.campus_department.department == user.primary_department

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "admin":
            return True

        if request.method in permissions.SAFE_METHODS:
            if user.role == "manager":
                return self._manager_in_scope(user, obj)
            if user.role == "technician":
                return (
                    obj.section in user.sections.all()
                    or obj.assigned_to == user
                    or obj.raised_by == user
                )
            elif user.role == "user":
                return obj.raised_by == user
            elif user.role == "head_of_section":
                return obj.section and obj.section.head_of_section == user
            elif user.role == "hod":
                return obj.campus_department.campus == user.primary_campus

        if request.method in ["PATCH", "PUT", "DELETE"]:
            if user.role == "manager":
                return self._manager_in_scope(user, obj)
            if user.role == "technician":
                return obj.assigned_to == user
            elif user.role == "user":
                return obj.raised_by == user
            elif user.role == "head_of_section":
                return obj.section and obj.section.head_of_section == user
            elif user.role == "hod":
                return obj.campus_department.campus == user.primary_campus

        return False


class CanAssignTickets(permissions.BasePermission):
    """Permission for users who can assign tickets to technicians"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            "head_of_section",
            "hod",
            "manager",
            "admin",
        ]


class CanEscalateTickets(permissions.BasePermission):
    """Permission for users who can escalate tickets"""

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and
            # Managers excluded
            request.user.role in ["head_of_section", "hod", "admin"]
        )


class IsOwnerOrTechnicianOrAdmin(permissions.BasePermission):
    """
    Custom permission for tickets:
    - Users can only see/edit their own tickets
    - Technicians can see/edit tickets assigned to them or in their sections
    - Admins and managers can see/edit all tickets
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admins and managers have full access
        if user.role in ["admin", "manager"]:
            return True

        # For tickets
        if isinstance(obj, Ticket):
            # Users can only access their own tickets
            if user.role == "user":
                return obj.raised_by == user

            # Technicians can access tickets assigned to them or in their sections
            if user.role == "technician":
                return (
                    obj.assigned_to == user  # Assigned to them
                    or obj.section in user.sections.all()  # In their section
                    or obj.raised_by == user  # They created it
                )

        # For other objects, check if they're the owner
        if hasattr(obj, "raised_by") and obj.raised_by == user:
            return True

        if hasattr(obj, "user") and obj.user == user:
            return True

        return False


class CanCloseTicket(permissions.BasePermission):
    """
    Permission for closing tickets.

    Allowed for:
    - Users can close their own tickets (raised_by == user)
    - Admins can close any ticket

    Note: Ticket closure is restricted to users (customers) closing their own tickets
    and admins. Technicians, HOD, HOS, and managers should use status updates instead
    if they need to modify ticket state.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admin can close any ticket
        if user.role == "admin":
            return True

        # For tickets only
        if not isinstance(obj, Ticket):
            return False

        # User can close their own tickets (tickets they raised)
        if user.role == "user":
            return obj.raised_by == user

        # No other roles can close tickets
        return False
