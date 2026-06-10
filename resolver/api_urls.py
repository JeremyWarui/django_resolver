"""Central URL router for all /api/v1/ endpoints."""
from django.urls import include, path

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("", include("apps.org.urls")),
    path("", include("apps.sla.urls")),
    path("", include("apps.facilities.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.tickets.urls")),
    path("", include("apps.analytics.urls")),
]
