from rest_framework.exceptions import PermissionDenied


class AdminOnlyCreateMixin:
    """Restricts POST (create) to admin users; all other methods use the view's normal permissions."""

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != "admin":
            raise PermissionDenied("Only administrators can create this resource.")
        return super().create(request, *args, **kwargs)
