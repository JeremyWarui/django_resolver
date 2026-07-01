"""
URL configuration for resolver project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # Legacy /api/auth/* routes — provided by apps.accounts for backward compatibility
    path("api/", include("apps.accounts.urls")),
    # Main API at /api/v1/
    path("api/v1/", include("resolver.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
