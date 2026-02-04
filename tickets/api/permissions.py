from rest_framework import permissions
from tickets.models import Ticket


class IsAdminOrManager(permissions.BasePermission):
    """
    Custom permission to only allow admins and managers.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            "admin",
            "manager",
        ]


class IsAdminOrManagerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to allow:
    - Read access to authenticated users
    - Write access only to admins and managers
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True

        return request.user.role in ["admin", "manager"]


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


class IsTechnicianOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow technicians, admins, and managers.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            "technician",
            "admin",
            "manager",
        ]


class CanManageUsers(permissions.BasePermission):
    """
    Custom permission for user management:
    - Admins and managers can create/update/delete users
    - Regular users can only update their own profile
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # For user creation (registration), allow if admin/manager or if it's self-registration
        if request.method == "POST" and not hasattr(view, "get_object"):
            return True  # This will be handled by the view logic

        return True

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admins and managers have full access
        if user.role in ["admin", "manager"]:
            return True

        # Users can only access their own profile
        return obj == user
