"""Analytics module - centralized analytics, dashboards, and reporting.

Exports:
- TicketAnalytics: Basic ticket metrics (counts, trends, distributions)
- TechnicianAnalytics: Technician performance and workload metrics
- OrganizationalAnalytics: Role-specific dashboards (Director, HOD, Section Head)

Backwards compatibility:
- OrganizationalAnalyticsService alias for module consistency
"""

from .analytics import (
    TicketAnalytics,
    TechnicianAnalytics,
    OrganizationalAnalytics,
)

# Backwards compatibility
OrganizationalAnalyticsService = OrganizationalAnalytics

__all__ = [
    'TicketAnalytics',
    'TechnicianAnalytics',
    'OrganizationalAnalytics',
    'OrganizationalAnalyticsService',
]
