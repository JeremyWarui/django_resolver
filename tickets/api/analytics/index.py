"""
Index file for exporting all analytics views.
This makes imports more convenient in other modules.
"""

from .views import (
    TicketAnalyticsView,
    TechnicianAnalyticsView,
    AdminDashboardAnalyticsView
)

__all__ = [
    'TicketAnalyticsView',
    'TechnicianAnalyticsView',
    'AdminDashboardAnalyticsView'
]
