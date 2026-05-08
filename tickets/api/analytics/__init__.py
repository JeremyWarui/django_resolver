"""Analytics module - role-scoped analytics and dashboards.

Each class is responsible for one level of the org hierarchy:

  AdminAnalytics       — system-wide (admin only)
  ManagerAnalytics     — own department across all campuses
  HODAnalytics         — own department within own campus
  SectionHeadAnalytics — own section(s) only
  TechnicianAnalytics  — personal performance metrics
  TicketAnalytics      — raw ticket counts and trends (shared utility)
"""

from .ticket_analytics import TicketAnalytics
from .technician_analytics import TechnicianAnalytics
from .admin_analytics import AdminAnalytics
from .manager_analytics import ManagerAnalytics
from .hod_analytics import HODAnalytics
from .section_head_analytics import SectionHeadAnalytics

__all__ = [
    "TicketAnalytics",
    "TechnicianAnalytics",
    "AdminAnalytics",
    "ManagerAnalytics",
    "HODAnalytics",
    "SectionHeadAnalytics",
]
