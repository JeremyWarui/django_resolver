# tickets/urls.py
from django.urls import path, include

urlpatterns = [
    # Include all API endpoints from the new organized structure
    path('api/', include('tickets.api.urls')),
]
