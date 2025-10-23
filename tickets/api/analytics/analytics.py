"""
Analytics services for ticket system.
Provides various statistics and metrics for dashboard and reporting.
"""
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, fields, FloatField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth

from tickets.models import Ticket, CustomUser, Feedback, Facility, Section


class TicketAnalytics:
    """
    Provides analytics for tickets in the system.
    Used for dashboard displays and reporting.
    """

    @staticmethod
    def get_ticket_counts_by_timeframe(days=1, facility_id=None, section_id=None):
        """
        Get ticket counts for a specific timeframe (default: today).
        Can be filtered by facility or section.

        Args:
            days (int): Number of days back to analyze
            facility_id (int, optional): ID of facility to filter by
            section_id (int, optional): ID of section to filter by

        Returns:
            dict: Count of tickets created in the specified timeframe
        """
        time_threshold = timezone.now() - timedelta(days=days)

        # Base queryset
        queryset = Ticket.objects.filter(created_at__gte=time_threshold)

        # Apply optional filters
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        # Get the count
        count = queryset.count()

        return {
            'period': f"Last {days} day{'s' if days > 1 else ''}",
            'count': count
        }

    @staticmethod
    def get_ticket_counts_by_status(facility_id=None, section_id=None):
        """
        Get ticket counts grouped by status.
        Can be filtered by facility or section.

        Args:
            facility_id (int, optional): ID of facility to filter by
            section_id (int, optional): ID of section to filter by

        Returns:
            list: List of dictionaries with status and count
        """
        # Base queryset
        queryset = Ticket.objects.all()

        # Apply optional filters
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        # Group by status and count
        status_counts = queryset.values('status').annotate(
            count=Count('id')).order_by('status')

        return list(status_counts)

    @staticmethod
    def get_ticket_trend_data(days=30, group_by='day'):
        """
        Get ticket creation trend data for visualization.

        Args:
            days (int): Number of days back to analyze
            group_by (str): Grouping period - 'day', 'week', or 'month'

        Returns:
            list: Trend data for charting
        """
        time_threshold = timezone.now() - timedelta(days=days)

        # Select appropriate truncation function
        if group_by == 'week':
            trunc_func = TruncWeek('created_at')
        elif group_by == 'month':
            trunc_func = TruncMonth('created_at')
        else:  # default to day
            trunc_func = TruncDay('created_at')

        # Get trend data
        trend_data = (
            Ticket.objects.filter(created_at__gte=time_threshold)
            .annotate(period=trunc_func)
            .values('period')
            .annotate(count=Count('id'))
            .order_by('period')
        )

        return list(trend_data)

    @staticmethod
    def get_tickets_by_facility():
        """
        Get distribution of tickets by facility.

        Returns:
            list: List of dictionaries with facility name and ticket count
        """
        facility_data = (
            Facility.objects.annotate(ticket_count=Count('ticket'))
            .values('name', 'ticket_count')
            .order_by('-ticket_count')
        )

        return list(facility_data)

    @staticmethod
    def get_tickets_by_section():
        """
        Get distribution of tickets by section.

        Returns:
            list: List of dictionaries with section name and ticket count
        """
        section_data = (
            Section.objects.annotate(ticket_count=Count('ticket'))
            .values('name', 'ticket_count')
            .order_by('-ticket_count')
        )

        return list(section_data)


class TechnicianAnalytics:
    """
    Provides analytics for technicians in the system.
    Used for performance evaluation and reporting.
    """

    @staticmethod
    def get_technician_performance(technician_id=None):
        """
        Get performance metrics for technicians.

        Args:
            technician_id (int, optional): ID of specific technician to analyze

        Returns:
            list: List of technician performance metrics
        """
        # Base queryset for technicians
        queryset = CustomUser.objects.filter(role='technician')

        # Filter for specific technician if requested
        if technician_id:
            queryset = queryset.filter(id=technician_id)

        # Calculate performance metrics for each technician
        performance_data = []

        for tech in queryset:
            # Tickets assigned to this technician
            assigned_tickets = Ticket.objects.filter(assigned_to=tech)

            # Resolved tickets
            resolved_tickets = assigned_tickets.filter(
                status__in=['resolved', 'closed'])

            # Pending tickets
            pending_tickets = assigned_tickets.filter(
                status__in=['assigned', 'in_progress', 'pending']
            )

            # Overdue tickets (>24 hours old and not resolved)
            overdue_threshold = timezone.now() - timedelta(hours=24)
            overdue_tickets = pending_tickets.filter(
                created_at__lt=overdue_threshold)

            # Average rating from feedback
            avg_rating = Feedback.objects.filter(
                ticket__assigned_to=tech
            ).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0

            # Calculate resolution time for resolved tickets
            resolution_times = []
            for ticket in resolved_tickets:
                # Using a simple heuristic for resolution time (created to updated time)
                # In a real system, you might track state changes precisely
                resolution_time = (
                    # hours
                    ticket.updated_at - ticket.created_at).total_seconds() / 3600
                resolution_times.append(resolution_time)

            avg_resolution_time = sum(
                resolution_times) / len(resolution_times) if resolution_times else 0

            performance_data.append({
                'id': tech.id,
                'username': tech.username,
                'full_name': f"{tech.first_name} {tech.last_name}",
                'total_tickets': assigned_tickets.count(),
                'resolved_tickets': resolved_tickets.count(),
                'pending_tickets': pending_tickets.count(),
                'overdue_tickets': overdue_tickets.count(),
                'avg_rating': round(avg_rating, 2),
                # in hours
                'avg_resolution_time': round(avg_resolution_time, 2),
                'resolution_percentage': round(
                    (resolved_tickets.count() / assigned_tickets.count() * 100)
                    if assigned_tickets.count() > 0 else 0, 2
                )
            })

        return performance_data

    @staticmethod
    def get_technician_ratings_by_section():
        """
        Get average technician ratings grouped by section.
        Useful for identifying which sections have the best performing techs.

        Returns:
            list: List of sections with average tech ratings
        """
        section_ratings = []

        for section in Section.objects.all():
            # Get technicians in this section
            techs_in_section = CustomUser.objects.filter(
                sections=section,
                role='technician'
            )

            # Get average rating across all these technicians
            avg_section_rating = Feedback.objects.filter(
                ticket__assigned_to__in=techs_in_section
            ).aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0

            section_ratings.append({
                'section_name': section.name,
                'technician_count': techs_in_section.count(),
                'avg_rating': round(avg_section_rating, 2)
            })

        return sorted(section_ratings, key=lambda x: x['avg_rating'], reverse=True)


class AdminAnalytics:
    """
    Provides system-wide analytics for administrators.
    Used for monitoring overall system health and performance.
    """

    @staticmethod
    def get_system_overview():
        """
        Get system-wide overview metrics.

        Returns:
            dict: System overview statistics
        """
        total_tickets = Ticket.objects.count()
        open_tickets = Ticket.objects.filter(status='open').count()
        resolved_tickets = Ticket.objects.filter(
            status__in=['resolved', 'closed']).count()

        # Calculate tickets by age
        now = timezone.now()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        new_tickets = Ticket.objects.filter(created_at__gte=day_ago).count()
        tickets_past_week = Ticket.objects.filter(
            created_at__gte=week_ago).count()
        tickets_past_month = Ticket.objects.filter(
            created_at__gte=month_ago).count()

        # Calculate average response time (from open to assigned)
        response_time_expr = ExpressionWrapper(
            F('updated_at') - F('created_at'),
            output_field=FloatField()
        )

        avg_response_time = (
            Ticket.objects.filter(
                status__in=['assigned', 'in_progress', 'pending', 'resolved', 'closed'])
            .annotate(response_time=response_time_expr)
            .aggregate(avg=Avg('response_time'))['avg']
        )

        # Convert to hours if not None
        avg_response_hours = None
        if avg_response_time:
            avg_response_hours = avg_response_time.total_seconds() / 3600
            print(avg_response_hours)

        return {
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'resolved_tickets': resolved_tickets,
            'resolution_rate': round((resolved_tickets / total_tickets * 100) if total_tickets else 0, 2),
            'new_tickets_24h': new_tickets,
            'tickets_past_week': tickets_past_week,
            'tickets_past_month': tickets_past_month,
            'avg_response_time_hours': round(avg_response_hours, 2) if avg_response_hours else None,
        }

    @staticmethod
    def get_overdue_tickets():
        """
        Get list of overdue tickets (>24 hours old and not resolved).

        Returns:
            list: List of overdue ticket information
        """
        overdue_threshold = timezone.now() - timedelta(hours=24)

        overdue_tickets = (
            Ticket.objects.filter(
                created_at__lt=overdue_threshold,
                status__in=['open', 'assigned', 'in_progress', 'pending']
            )
            .select_related('section', 'facility', 'assigned_to')
            .annotate(
                age_hours=ExpressionWrapper(
                    (timezone.now() - F('created_at')),
                    output_field=FloatField()
                )
            )
        )

        result = []
        for ticket in overdue_tickets:
            age_hours = ticket.age_hours.total_seconds(
            ) / 3600 if hasattr(ticket, 'age_hours') else 0

            result.append({
                'id': ticket.id,
                'ticket_no': ticket.ticket_no,
                'title': ticket.title,
                'status': ticket.status,
                'section': ticket.section.name,
                'facility': ticket.facility.name,
                'assigned_to': ticket.assigned_to.username if ticket.assigned_to else None,
                'age_hours': round(age_hours, 2),
                'created_at': ticket.created_at,
            })

        return sorted(result, key=lambda x: x['age_hours'], reverse=True)
