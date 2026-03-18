from rest_framework import permissions
from tickets.models import Ticket


# ORGANIZATIONAL HIERARCHY PERMISSIONS

class IsWithinOrganizationalScope(permissions.BasePermission):
    """
    Ensures users can only access data within their organizational scope.

    Scope access:
    - user/technician: section-level
    - section_head: department-level
    - hod: campus-level
    - director: organization-level
    - admin: system-level (all access)
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # System admins have access to everything
        if request.user.role == 'admin':
            return True

        # All other authenticated roles have scoped access
        return True

    def has_object_permission(self, request, view, obj):
        user = request.user

        # System admin access - full access to everything
        if user.role == 'admin':
            return True

        # Object-specific scope checking based on object type
        if isinstance(obj, Ticket):
            return self._check_ticket_access(user, obj)

        # Check if object has organizational context
        if hasattr(obj, 'section'):
            return self._check_section_access(user, obj.section)
        elif hasattr(obj, 'department'):
            return self._check_department_access(user, obj.department)
        elif hasattr(obj, 'campus'):
            return self._check_campus_access(user, obj.campus)

        return False

    @staticmethod
    def _check_ticket_access(user, ticket):
        """Check if user can access a specific ticket"""
        if not ticket.section or not ticket.section.department:
            return False

        if user.role == 'director':
            # Director can see all tickets in their organization
            return (ticket.section.department.campus.organization ==
                    user.primary_campus.organization)
        elif user.role == 'hod':
            # HOD can see all tickets in their campus
            return ticket.section.department.campus == user.primary_campus
        elif user.role == 'section_head':
            # Section head can see all tickets in their department
            return ticket.section.department == user.primary_department
        elif user.role == 'technician':
            # Technician can see tickets in their sections or assigned to them
            return (ticket.section in user.sections.all() or
                    ticket.assigned_to == user or
                    ticket.raised_by == user)
        elif user.role == 'user':
            # Users can only see their own tickets
            return ticket.raised_by == user

        return False

    @staticmethod
    def _check_section_access(user, section):
        """Check if user has access to specific section"""
        if not section.department or not section.department.campus:
            return False

        if user.role == 'director':
            return section.department.campus.organization == user.primary_campus.organization
        elif user.role == 'hod':
            return section.department.campus == user.primary_campus
        elif user.role == 'section_head':
            return section.department == user.primary_department
        elif user.role in ['technician', 'user']:
            return section.department == user.primary_department

        return False

    @staticmethod
    def _check_department_access(user, department):
        """Check if user has access to specific department"""
        if not department.campus:
            return False

        if user.role == 'director':
            return department.campus.organization == user.primary_campus.organization
        elif user.role == 'hod':
            return department.campus == user.primary_campus
        elif user.role in ['section_head', 'technician', 'user']:
            return department == user.primary_department

        return False

    @staticmethod
    def _check_campus_access(user, campus):
        """Check if user has access to specific campus"""
        if user.role == 'director':
            return campus.organization == user.primary_campus.organization
        elif user.role in ['hod', 'section_head', 'technician', 'user']:
            return campus == user.primary_campus

        return False


class CanAssignTickets(permissions.BasePermission):
    """Permission for users who can assign tickets to technicians"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                request.user.role in ['section_head', 'hod', 'director', 'admin'])


class CanEscalateTickets(permissions.BasePermission):
    """Permission for users who can escalate tickets"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                # Directors excluded
                request.user.role in ['section_head', 'hod', 'admin'])


class CanViewAnalytics(permissions.BasePermission):
    """Permission for accessing analytics endpoints"""

    def has_permission(self, request, view):
        return (request.user.is_authenticated and
                (request.user.can_view_analytics or
                 request.user.role in ['section_head', 'hod', 'director', 'admin']))


# LEGACY PERMISSIONS (kept for backward compatibility)

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
    Custom permission for user management and bulk operations:
    - Admins and managers can create/update/delete users and perform bulk operations
    - Regular users can only update their own profile
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # For bulk operations, only allow admins and managers
        if isinstance(view, type) and view.__name__ == 'BulkTicketStatusUpdateView':
            return request.user.role in ['admin', 'manager']

        # For bulk update endpoint (by checking view name contains 'bulk')
        view_name = view.__class__.__name__ if hasattr(
            view, '__class__') else ''
        if 'bulk' in view_name.lower():
            return request.user.role in ['admin', 'manager']

        # For user creation (registration), allow if admin/manager
        if request.method == "POST" and not hasattr(view, "get_object"):
            # Registration is handled by view logic
            return request.user.role in ['admin', 'manager'] or True

        return request.user.role in ['admin', 'manager']

    def has_object_permission(self, request, view, obj):
        user = request.user

        # Admins and managers have full access
        if user.role in ["admin", "manager"]:
            return True

        # Users can only access their own profile
        return obj == user
