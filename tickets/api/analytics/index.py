"""
Index file for exporting all analytics views.
This makes imports more convenient in other modules.
"""

from .views import (
    TicketAnalyticsView,
    TechnicianAnalyticsView,
    TechnicianSelfAnalyticsView,
    AdminDashboardAnalyticsView,
    UserAnalyticsView,
    ManagerDashboardView,
    HODDashboardView,
    SectionHeadDashboardView,
    DepartmentAnalyticsView,
    HODAnalyticsView,
    HOSAnalyticsView,
)

__all__ = [
    "TicketAnalyticsView",
    "TechnicianAnalyticsView",
    "TechnicianSelfAnalyticsView",
    "AdminDashboardAnalyticsView",
    "UserAnalyticsView",
    "ManagerDashboardView",
    "HODDashboardView",
    "SectionHeadDashboardView",
    "DepartmentAnalyticsView",
    "HODAnalyticsView",
    "HOSAnalyticsView",
]
