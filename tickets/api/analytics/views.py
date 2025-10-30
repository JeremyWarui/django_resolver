"""
API Views for analytics endpoints.
These endpoints provide various statistics for dashboards and reporting.
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from tickets.models import Ticket, CustomUser, Feedback, Section, Facility
from tickets.api.analytics.analytics import TicketAnalytics, TechnicianAnalytics, AdminAnalytics


class TicketAnalyticsView(generics.GenericAPIView):
    """
    API view for ticket analytics data.
    """
    # permission_classes = [IsAuthenticated]

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
        timeframe = request.query_params.get('timeframe', 'day')
        facility_id = request.query_params.get('facility_id')
        section_id = request.query_params.get('section_id')
        group_by = request.query_params.get('group_by', 'day')
        days = int(request.query_params.get('days', 30))

        # Map timeframe to days
        days_map = {
            'day': 1,
            'week': 7,
            'month': 30
        }

        time_days = days_map.get(timeframe, 1)

        # Get analytics data
        ticket_counts = TicketAnalytics.get_ticket_counts_by_timeframe(
            days=time_days,
            facility_id=facility_id,
            section_id=section_id
        )

        status_counts = TicketAnalytics.get_ticket_counts_by_status(
            facility_id=facility_id,
            section_id=section_id
        )

        trend_data = TicketAnalytics.get_ticket_trend_data(
            days=days, group_by=group_by)

        facility_distribution = TicketAnalytics.get_tickets_by_facility()
        section_distribution = TicketAnalytics.get_tickets_by_section()

        return Response({
            'ticket_counts': ticket_counts,
            'status_counts': status_counts,
            'trend_data': trend_data,
            'facility_distribution': facility_distribution,
            'section_distribution': section_distribution
        })


class TechnicianAnalyticsView(generics.GenericAPIView):
    """
    API view for technician performance analytics.
    """
    # permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """
        Get technician performance analytics.

        Query Parameters:
        - technician_id: Optional specific technician to analyze
        """
        # Extract query parameters
        technician_id = request.query_params.get('technician_id')

        # Check if user has permission to see all technicians or just themselves
        if not request.user.is_staff and request.user.role not in ['admin', 'manager']:
            # Regular users and technicians can only see their own stats
            if request.user.role == 'technician':
                technician_id = request.user.id
            else:
                return Response(
                    {"detail": "You do not have permission to view technician analytics"},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Get analytics data
        performance_data = TechnicianAnalytics.get_technician_performance(
            technician_id)

        # Get section ratings if requesting all technicians
        section_ratings = None
        if not technician_id:
            section_ratings = TechnicianAnalytics.get_technician_ratings_by_section()

        response_data = {
            'technician_performance': performance_data
        }

        if section_ratings:
            response_data['section_ratings'] = section_ratings

        return Response(response_data)


class AdminDashboardAnalyticsView(generics.GenericAPIView):
    """
    API view for admin dashboard analytics.
    Restricted to admin and manager roles.
    """
    # permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        """Get system-wide analytics for admin dashboard."""
        # Check if user has admin permissions
        # if not request.user.is_staff and request.user.role not in ['admin', 'manager']:
        #     return Response(
        #         {"detail": "You do not have permission to view admin analytics"},
        #         status=status.HTTP_403_FORBIDDEN
        #     )

        # Get analytics data
        system_overview = AdminAnalytics.get_system_overview()
        print(system_overview)
        overdue_tickets = AdminAnalytics.get_overdue_tickets()
        print(overdue_tickets)

        return Response({
            'system_overview': system_overview,
            'overdue_tickets': overdue_tickets
        })
