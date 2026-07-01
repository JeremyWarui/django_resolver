from django.urls import path

from .views import (
    MeView,
    SwitchRoleView,
    UserRoleAssignmentListCreateView,
    UserRoleAssignmentDetailView,
    UserListCreateView,
    UserDetailView,
    jwt_login,
    jwt_register,
    jwt_refresh,
    jwt_logout,
)

urlpatterns = [
    # Auth endpoints
    path("auth/login/", jwt_login, name="auth-login"),
    path("auth/register/", jwt_register, name="auth-register"),
    path("auth/refresh/", jwt_refresh, name="auth-refresh"),
    path("auth/logout/", jwt_logout, name="auth-logout"),
    path("auth/me/", MeView.as_view(), name="auth-me"),
    path("auth/switch-role/", SwitchRoleView.as_view(), name="auth-switch-role"),
    # User management (admin only)
    path("users/", UserListCreateView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    # Role assignment management
    path(
        "users/<int:user_pk>/role-assignments/",
        UserRoleAssignmentListCreateView.as_view(),
        name="user-role-assignments",
    ),
    path(
        "users/<int:user_pk>/role-assignments/<int:ra_pk>/",
        UserRoleAssignmentDetailView.as_view(),
        name="user-role-assignment-detail",
    ),
]
