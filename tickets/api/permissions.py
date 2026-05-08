from rest_framework import permissions
from tickets.models import Ticket, Campus, Department, Organization

# ORGANIZATIONAL HIERARCHY PERMISSIONS


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

        # Direct organizational model checks (object IS the organizational unit)
        if isinstance(obj, Organization):
            return self._check_organization_access(user, obj)
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
        """Check if user can access a specific ticket"""
        if not ticket.section or not ticket.section.department:
            return False

        if user.role == "manager":
            # Manager can see all tickets in their organization
            return (
                ticket.section.department.campus.organization
                == user.primary_campus.organization
            )
        elif user.role == "hod":
            # HOD can see all tickets in their campus
            return ticket.section.department.campus == user.primary_campus
        elif user.role == "head_of_section":
            # Section head can see all tickets in their department
            return ticket.section.department == user.primary_department
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
        if not section.department or not section.department.campus:
            return False

        if user.role == "manager":
            return (
                section.department.campus.organization
                == user.primary_campus.organization
            )
        elif user.role == "hod":
            return section.department.campus == user.primary_campus
        elif user.role == "head_of_section":
            return section.department == user.primary_department
        elif user.role in ["technician", "user"]:
            return section.department == user.primary_department

        return False

    @staticmethod
    def _check_department_access(user, department):
        """Check if user has access to specific department"""
        if not department.campus:
            return False

        if user.role == "manager":
            return department.campus.organization == user.primary_campus.organization
        elif user.role == "hod":
            return department.campus == user.primary_campus
        elif user.role in ["head_of_section", "technician", "user"]:
            return department == user.primary_department

        return False

    @staticmethod
    def _check_campus_access(user, campus):
        """Check if user has access to specific campus"""
        if not user.primary_campus:
            return False
        if user.role == "manager":
            return campus.organization == user.primary_campus.organization
        elif user.role in ["hod", "head_of_section", "technician", "user"]:
            return campus == user.primary_campus

        return False

    @staticmethod
    def _check_organization_access(user, organization):
        """Check if user has access to specific organization"""
        if not user.primary_campus:
            return False
        return user.primary_campus.organization == organization


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Allow read (GET/HEAD/OPTIONS) access to any authenticated user within
    organizational scope; restrict write (POST/PUT/PATCH/DELETE) to admin only.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.role == "admin"


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
        if not user.primary_department:
            return False
        dept_code = user.primary_department.code
        ticket_dept = obj.section.department if obj.section else None
        if not ticket_dept:
            return False
        org = user.primary_department.campus.organization
        return (
            ticket_dept.code == dept_code
            and ticket_dept.campus.organization == org
        )

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
                user_campus = user.primary_campus
                ticket_campus = (
                    obj.section.department.campus
                    if obj.section and obj.section.department
                    else None
                )
                return ticket_campus == user_campus
            elif user.role == "head_of_section":
                return obj.section.head_of_section == user
            elif user.role == "hod":
                return obj.section.department.campus == user.primary_campus

        if request.method in ["PATCH", "PUT", "DELETE"]:
            if user.role == "manager":
                return self._manager_in_scope(user, obj)
            if user.role == "technician":
                return obj.assigned_to == user
            elif user.role == "user":
                return obj.raised_by == user
            elif user.role == "head_of_section":
                return obj.section.head_of_section == user
            elif user.role == "hod":
                return obj.section.department.campus == user.primary_campus

        return False


class CanManageSectionTechnicians(permissions.BasePermission):
    """Permission for adding/removing technicians from sections."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            "head_of_section",
            "hod",
            "admin",
        ]


class CanViewAnalytics(permissions.BasePermission):
    """Permission for accessing analytics endpoints"""

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.can_view_analytics
            or request.user.role
            in ["user", "technician", "head_of_section", "hod", "manager", "admin"]
        )


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
    - All authenticated users can view users (read-only)
    - Regular users can only edit their own profile
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # For bulk operations, only allow admins and managers
        view_name = view.__class__.__name__ if hasattr(view, "__class__") else ""
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
