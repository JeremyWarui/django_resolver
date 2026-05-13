from rest_framework import permissions


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
