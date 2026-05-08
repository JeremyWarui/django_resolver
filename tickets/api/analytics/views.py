"""
API Views for analytics endpoints.
These endpoints provide various statistics for dashboards and reporting.
"""

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from tickets.api.analytics.ticket_analytics import TicketAnalytics
from tickets.api.analytics.technician_analytics import TechnicianAnalytics
from tickets.api.analytics.admin_analytics import AdminAnalytics
from tickets.api.analytics.manager_analytics import ManagerAnalytics
from tickets.api.analytics.hod_analytics import HODAnalytics
from tickets.api.analytics.section_head_analytics import SectionHeadAnalytics

# ============================================================================
# MANAGER DASHBOARD VIEW
# ============================================================================


class TicketAnalyticsView(generics.GenericAPIView):
    """
    API view for ticket analytics data.
    """

    # All authenticated users can view analytics
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Get ticket analytics based on query parameters.

        Query Parameters:
        - timeframe: day, week, month (default: day)
        - facility_id: Optional facility ID to filter by
        - section_id: Optional section ID to filter by
        - group_by: day, week, month for trend data (default: day)
        - days: Number of days for historical data (default: 30)
        """
        # Extract query parameters
        timeframe = request.query_params.get("timeframe", "day")
        facility_id = request.query_params.get("facility_id")
        section_id = request.query_params.get("section_id")
        group_by = request.query_params.get("group_by", "day")
        days = int(request.query_params.get("days", 30))

        # Map timeframe to days
        days_map = {"day": 1, "week": 7, "month": 30}

        time_days = days_map.get(timeframe, 1)

        # Get analytics data
        ticket_counts = TicketAnalytics.get_ticket_counts_by_timeframe(
            days=time_days,
            facility_id=facility_id,
            section_id=section_id,
        )

        status_counts = TicketAnalytics.get_ticket_counts_by_status(
            facility_id=facility_id,
            section_id=section_id,
        )

        trend_data = TicketAnalytics.get_ticket_trend_data(
            days=days, group_by=group_by
        )

        facility_distribution = TicketAnalytics.get_tickets_by_facility()
        section_distribution = TicketAnalytics.get_tickets_by_section()

        data = {
            "ticket_counts": ticket_counts,
            "status_counts": status_counts,
            "trend_data": trend_data,
            "facility_distribution": facility_distribution,
            "section_distribution": section_distribution,
        }

        return Response(data)


class TechnicianAnalyticsView(generics.GenericAPIView):
    """
    API view for technician performance analytics.
    """

    permission_classes = [IsAuthenticated]  # All authenticated users can view

    def get(self, request, format=None):
        """
        Get technician performance analytics.
        Technicians can only see their own stats, admins/managers see all.

        Query Parameters:
        - technician_id: Optional specific technician to analyze
        """
        technician_id = request.query_params.get("technician_id")

        # Restrict technicians to their own stats
        if request.user.role == "technician":
            technician_id = request.user.id
        # Admins and managers can specify any technician_id

        # Get analytics data
        performance_data = (
            TechnicianAnalytics.get_technician_performance(
                technician_id
            )
        )

        # Get section ratings if requesting all technicians and user is
        # admin/manager
        section_ratings = None
        if (
            not technician_id
            and request.user.role in ["admin", "manager"]
        ):
            section_ratings = (
                TechnicianAnalytics.get_technician_ratings_by_section()
            )

        response_data = {"technician_performance": performance_data}

        if section_ratings:
            response_data["section_ratings"] = section_ratings

        return Response(response_data)


class AdminDashboardAnalyticsView(generics.GenericAPIView):
    """
    API view for admin dashboard analytics.
    Now accessible to all authenticated users for viewing system stats.
    """

    permission_classes = [IsAuthenticated]  # All authenticated users can view

    def get(self, request, format=None):
        """Get system-wide analytics for dashboard."""
        # Get analytics data
        system_overview = AdminAnalytics.get_system_overview()

        # Only show overdue tickets to admins/managers/technicians
        overdue_tickets = []
        if request.user.role in ["admin", "manager", "technician"]:
            overdue_tickets = AdminAnalytics.get_overdue_tickets()

        data = {
            "system_overview": system_overview,
            "overdue_tickets": overdue_tickets,
        }

        return Response(data)


# ============================================================================
# ORGANIZATIONAL ANALYTICS VIEWS
# ============================================================================


class RoleBasedDashboardView(APIView):
    """Base class for small role-scoped organizational dashboards.

    Subclasses should set `required_roles` (list of allowed role strings)
    and `analytics_method` (callable taking `(user, days=...)`).
    """

    permission_classes = [IsAuthenticated]
    required_roles = []
    analytics_method = None

    def get(self, request):
        # basic configuration checks
        if not self.required_roles:
            return Response(
                {"error": "No roles configured"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        if not callable(self.analytics_method):
            return Response(
                {"error": "Analytics method not configured"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # permission check
        if request.user.role not in self.required_roles:
            return Response(
                {"error": "Insufficient permissions for this endpoint"},
                status=status.HTTP_403_FORBIDDEN,
            )

        days = int(request.query_params.get("days", 30))
        dashboard = self.analytics_method(request.user, days=days)
        return Response(dashboard)


class OrganizationalAnalyticsView(APIView):
    """Organisation-wide analytics for admin — campus breakdown, top items, trend."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "admin":
            return Response(
                {"error": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )
        days = int(request.query_params.get("days", 30))
        data = AdminAnalytics.get_organisation_analytics(days=days)
        return Response(data)


class ManagerDashboardView(RoleBasedDashboardView):
    required_roles = ["manager", "admin"]
    analytics_method = staticmethod(ManagerAnalytics.manager_dashboard)


class HODDashboardView(RoleBasedDashboardView):
    required_roles = ["hod", "admin"]
    analytics_method = staticmethod(HODAnalytics.hod_dashboard)


class SectionHeadDashboardView(RoleBasedDashboardView):
    required_roles = ["head_of_section", "admin"]
    analytics_method = staticmethod(SectionHeadAnalytics.section_head_dashboard)
