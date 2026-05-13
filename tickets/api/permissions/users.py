from rest_framework import permissions


class CanManageUsers(permissions.BasePermission):
    """
    Custom permission for user management and bulk operations:
    - Admins and managers can create/update/delete users and perform bulk operations
    - All authenticated users can view users (read-only)
    - Regular users can only edit their own profile
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # For bulk operations, only allow admins and managers
        view_name = view.__class__.__name__ if hasattr(
            view, "__class__") else ""
        if "bulk" in view_name.lower():
            return request.user.role in ["admin", "manager"]

        # For all GET requests, allow all authenticated users (read-only)
        if request.method in permissions.SAFE_METHODS:
            return True

        # For POST/PUT/PATCH/DELETE, only allow admin/manager
        return request.user.role in ["admin", "manager"]

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admins and managers have full access
        if user.role in ["admin", "manager"]:
            return True

        # All authenticated users can view any user (read-only)
        if request.method in permissions.SAFE_METHODS:
            return True

        # Users can only edit their own profile
        return obj == user


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


class CanViewAnalytics(permissions.BasePermission):
    """Permission for accessing analytics endpoints"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.can_view_analytics
            or request.user.role
            in ["user", "technician", "head_of_section", "hod", "manager", "admin"]
        )
