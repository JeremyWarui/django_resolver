"""
URL configuration for resolver project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # Legacy /api/auth/* routes — provided by apps.accounts for backward compatibility
    path("api/", include("apps.accounts.urls")),
    # Main API at /api/v1/
    path("api/v1/", include("resolver.api_urls")),
]
