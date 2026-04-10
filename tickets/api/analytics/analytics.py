"""
Analytics Services

Provides role-specific dashboards and ticket/technician analytics across organizational hierarchy.

Key Features:
- Director: Organization-wide metrics across all campuses/departments
- HOD: Campus-level analytics with department/section breakdown
- Section Head: Department-level metrics with technician performance
- Basic analytics: Ticket trends, status distribution, technician performance

Metrics Provided:
- Ticket counts and distributions
- Resolution times and SLA compliance
- Escalation trends
- Technician performance and workload
"""

from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, fields, FloatField, DurationField
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from typing import Dict, List, Optional, Tuple

from tickets.models import Ticket, CustomUser, Feedback, Facility, Section, Organization, Campus, Department, TicketLog


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
            Facility.objects.annotate(ticket_count=Count('tickets'))
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
            Section.objects.annotate(ticket_count=Count('tickets'))
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

            # Get tickets by status breakdown
            tickets_by_status = assigned_tickets.values('status').annotate(
                count=Count('id')
            ).values_list('status', 'count')
            tickets_by_status_dict = {
                status: count for status, count in tickets_by_status}

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
                ),
                'tickets_by_status': tickets_by_status_dict
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


class OrganizationalAnalytics:
    """Analytics service providing role-specific dashboards for organizational hierarchy"""

    # SLA thresholds (hours)
    SLA_LIMITS = {
        'critical': 4,
        'urgent': 24,
        'high': 48,
        'normal': 72,
        'low': 120
    }

    @staticmethod
    def _calculate_avg_resolution_time(tickets_queryset) -> float:
        """Calculate average resolution time in hours"""
        resolved_tickets = tickets_queryset.filter(
            status__in=['resolved', 'closed'])
        if not resolved_tickets.exists():
            return 0.0

        duration_annotations = resolved_tickets.annotate(
            resolution_time=ExpressionWrapper(
                F('resolved_at') - F('created_at'),
                output_field=DurationField()
            )
        )
        avg_duration = duration_annotations.aggregate(
            avg=Avg('resolution_time'))['avg']
        return (avg_duration.total_seconds() / 3600) if avg_duration else 0.0

    @staticmethod
    def _calculate_sla_compliance(tickets_queryset) -> float:
        """Calculate SLA compliance percentage"""
        total = tickets_queryset.count()
        if total == 0:
            return 0.0

        # For now, count tickets that are not overdue as SLA-compliant
        compliant = sum(1 for t in tickets_queryset if not t.is_overdue)
        return (compliant / total * 100) if total > 0 else 0.0

    @staticmethod
    def _get_escalation_trends(tickets_queryset, days: int = 30) -> Dict:
        """Get escalation trends over specified period"""
        time_threshold = timezone.now() - timedelta(days=days)
        recent = tickets_queryset.filter(escalated_at__gte=time_threshold)

        return {
            'total_escalations': recent.count(),
            'by_level': dict(
                recent.values('escalation_level').annotate(
                    count=Count('id')).values_list('escalation_level', 'count')
            ),
            'avg_levels': recent.aggregate(avg=Avg('escalation_level'))['avg'] or 0
        }

    @staticmethod
    def director_dashboard(user: CustomUser, days: int = 30) -> Dict:
        """
        Organization-wide dashboard for directors.
        Shows enterprise-level metrics across all campuses and departments.

        Args:
            user: Director user
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with dashboard metrics
        """
        if user.role != 'director' or not user.primary_campus:
            return {}

        org = user.primary_campus.organization
        time_threshold = timezone.now() - timedelta(days=days)

        # Base querysets
        all_tickets = Ticket.objects.filter(
            section__department__campus__organization=org
        )
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        # Overall metrics
        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(
            status__in=['open', 'assigned']).count()
        total_escalated = all_tickets.filter(escalation_level__gt=0).count()
        avg_resolution_time = OrganizationalAnalytics._calculate_avg_resolution_time(
            all_tickets
        )

        # Campus breakdown
        campus_stats = []
        for campus in org.campuses.all():
            campus_tickets = all_tickets.filter(
                section__department__campus=campus)
            campus_stats.append({
                'campus': {
                    'id': campus.id,
                    'name': campus.name,
                    'code': campus.code,
                    'location': campus.location
                },
                'total_tickets': campus_tickets.count(),
                'open_tickets': campus_tickets.filter(status__in=['open', 'assigned']).count(),
                'overdue_tickets': sum(
                    1 for t in campus_tickets if t.is_overdue
                ),
                'escalated_tickets': campus_tickets.filter(escalation_level__gt=0).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    campus_tickets
                ),
                'sla_compliance': OrganizationalAnalytics._calculate_sla_compliance(
                    campus_tickets
                )
            })

        # Department performance across campuses
        dept_performance = []
        for campus in org.campuses.all():
            for dept in campus.departments.filter(is_active=True):
                dept_tickets = all_tickets.filter(section__department=dept)
                dept_performance.append({
                    'department': {
                        'id': dept.id,
                        'name': dept.name,
                        'code': dept.code,
                        'campus': campus.name,
                        'hod': dept.head_of_department.username if dept.head_of_department else None
                    },
                    'ticket_count': dept_tickets.count(),
                    'open_count': dept_tickets.filter(status__in=['open', 'assigned']).count(),
                    'resolved_count': dept_tickets.filter(status__in=['resolved', 'closed']).count(),
                    'escalation_count': dept_tickets.filter(escalation_level__gt=0).count(),
                    'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                        dept_tickets
                    ),
                    'avg_escalations': dept_tickets.aggregate(
                        avg=Avg('escalation_level')
                    )['avg'] or 0
                })

        # Status distribution
        status_dist = recent_tickets.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Escalation trends
        escalation_trends = OrganizationalAnalytics._get_escalation_trends(
            all_tickets, days=7
        )

        # Top technicians by resolution count
        top_technicians = []
        technicians = CustomUser.objects.filter(
            role='technician',
            sections__department__campus__organization=org
        ).distinct()
        for tech in technicians[:10]:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            top_technicians.append({
                'technician': {
                    'id': tech.id,
                    'name': f"{tech.first_name} {tech.last_name}",
                    'username': tech.username
                },
                'total_assigned': tech_tickets.count(),
                'resolved': tech_tickets.filter(status__in=['resolved', 'closed']).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    tech_tickets
                )
            })

        # Facility-level metrics across organization
        facility_stats = []
        org_facilities = Facility.objects.filter(
            campus__organization=org
        )
        for facility in org_facilities:
            facility_tickets = all_tickets.filter(facility=facility)
            facility_stats.append({
                'facility': {
                    'id': facility.id,
                    'name': facility.name,
                    'type': facility.type,
                    'status': facility.status,
                    'campus': facility.campus.name if facility.campus else None,
                    'department': facility.department.name if facility.department else None
                },
                'total_tickets': facility_tickets.count(),
                'open_tickets': facility_tickets.filter(status__in=['open', 'assigned']).count(),
                'resolved_tickets': facility_tickets.filter(status__in=['resolved', 'closed']).count(),
                'overdue_tickets': sum(1 for t in facility_tickets if t.is_overdue),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    facility_tickets
                )
            })

        # Organization-wide section metrics
        section_stats = []
        org_sections = Section.objects.filter(
            department__campus__organization=org
        )
        for section in org_sections:
            section_tickets = all_tickets.filter(section=section)
            section_stats.append({
                'section': {
                    'id': section.id,
                    'name': section.name,
                    'code': section.code,
                    'department': section.department.name if section.department else None,
                    'campus': section.department.campus.name if section.department and section.department.campus else None,
                    'section_head': section.section_head.username if section.section_head else None
                },
                'total_tickets': section_tickets.count(),
                'open_tickets': section_tickets.filter(status__in=['open', 'assigned']).count(),
                'resolved_tickets': section_tickets.filter(status__in=['resolved', 'closed']).count(),
                'escalated_tickets': section_tickets.filter(escalation_level__gt=0).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    section_tickets
                ),
                'technician_count': section.technicians.count()
            })

        # Status distribution
        status_dist = recent_tickets.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        return {
            'organization': {
                'name': org.name,
                'code': org.code,
                'type': org.organization_type,
                'campuses_count': org.campuses.count()
            },
            'overview': {
                'total_tickets': total_tickets,
                'total_open': total_open,
                'total_escalated': total_escalated,
                'avg_resolution_hours': avg_resolution_time,
                'sla_compliance': OrganizationalAnalytics._calculate_sla_compliance(all_tickets)
            },
            'campuses': campus_stats,
            'departments': sorted(dept_performance, key=lambda x: x['ticket_count'], reverse=True),
            'facilities': sorted(facility_stats, key=lambda x: x['total_tickets'], reverse=True),
            'sections': sorted(section_stats, key=lambda x: x['total_tickets'], reverse=True),
            'status_distribution': list(status_dist),
            'escalation_trends': escalation_trends,
            'top_technicians': top_technicians,
            'period_days': days
        }

    @staticmethod
    def hod_dashboard(user: CustomUser, days: int = 30) -> Dict:
        """
        Campus-level dashboard for Heads of Department.
        Shows metrics for their campus across all departments and sections.

        Args:
            user: HOD user
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with dashboard metrics
        """
        if user.role != 'hod' or not user.primary_campus:
            return {}

        campus = user.primary_campus
        time_threshold = timezone.now() - timedelta(days=days)

        # Base querysets
        all_tickets = Ticket.objects.filter(section__department__campus=campus)
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        # Campus overview
        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(
            status__in=['open', 'assigned']).count()
        overdue_count = sum(1 for t in all_tickets if t.is_overdue)
        escalated_count = all_tickets.filter(escalation_level__gt=0).count()

        # Department breakdown
        dept_stats = []
        for dept in campus.departments.filter(is_active=True):
            dept_tickets = all_tickets.filter(section__department=dept)
            dept_stats.append({
                'department': {
                    'id': dept.id,
                    'name': dept.name,
                    'code': dept.code,
                    'hod': dept.head_of_department.username if dept.head_of_department else None
                },
                'total_tickets': dept_tickets.count(),
                'open_tickets': dept_tickets.filter(status__in=['open', 'assigned']).count(),
                'escalated_tickets': dept_tickets.filter(escalation_level__gt=0).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    dept_tickets
                ),
                'sla_compliance': OrganizationalAnalytics._calculate_sla_compliance(
                    dept_tickets
                )
            })

        # Section performance within departments
        section_performance = []
        for dept in campus.departments.filter(is_active=True):
            for section in dept.sections.filter(is_active=True):
                section_tickets = all_tickets.filter(section=section)
                section_performance.append({
                    'section': {
                        'id': section.id,
                        'name': section.name,
                        'code': section.code,
                        'department': dept.name,
                        'section_head': section.section_head.username if section.section_head else None
                    },
                    'ticket_count': section_tickets.count(),
                    'open_count': section_tickets.filter(status__in=['open', 'assigned']).count(),
                    'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                        section_tickets
                    ),
                    'technician_count': section.technicians.count()
                })

        # Technician performance (across campus)
        technicians = CustomUser.objects.filter(
            role='technician',
            sections__department__campus=campus
        ).distinct()

        tech_performance = []
        for tech in technicians:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            tech_performance.append({
                'technician': {
                    'id': tech.id,
                    'name': f"{tech.first_name} {tech.last_name}",
                    'username': tech.username,
                    'sections': list(
                        tech.sections.filter(
                            department__campus=campus
                        ).values_list('name', flat=True)
                    )
                },
                'total_assigned': tech_tickets.count(),
                'resolved': tech_tickets.filter(
                    status__in=['resolved', 'closed']
                ).count(),
                'open': tech_tickets.filter(
                    status__in=['open', 'assigned', 'in_progress']
                ).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    tech_tickets
                )
            })

        # Status distribution
        status_dist = recent_tickets.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Escalation analysis
        escalation_by_level = all_tickets.values('escalation_level').annotate(
            count=Count('id')
        ).order_by('escalation_level')

        return {
            'campus': {
                'name': campus.name,
                'code': campus.code,
                'location': campus.location,
                'departments_count': campus.departments.filter(is_active=True).count()
            },
            'overview': {
                'total_tickets': total_tickets,
                'open_tickets': total_open,
                'overdue_tickets': overdue_count,
                'escalated_tickets': escalated_count,
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    all_tickets
                ),
                'sla_compliance': OrganizationalAnalytics._calculate_sla_compliance(all_tickets)
            },
            'departments': sorted(dept_stats, key=lambda x: x['total_tickets'], reverse=True),
            'sections': sorted(section_performance, key=lambda x: x['ticket_count'], reverse=True),
            'technicians': sorted(tech_performance, key=lambda x: x['total_assigned'], reverse=True),
            'status_distribution': list(status_dist),
            'escalation_by_level': list(escalation_by_level),
            'period_days': days
        }

    @staticmethod
    def section_head_dashboard(user: CustomUser, days: int = 30) -> Dict:
        """
        Department-level dashboard for Section Heads.
        Shows metrics for their department and sections.

        Args:
            user: Section Head user
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with dashboard metrics
        """
        if user.role != 'section_head' or not user.primary_department:
            return {}

        department = user.primary_department
        time_threshold = timezone.now() - timedelta(days=days)

        # Base querysets
        all_tickets = Ticket.objects.filter(section__department=department)
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        # Department overview
        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(
            status__in=['open', 'assigned']).count()
        overdue_count = sum(1 for t in all_tickets if t.is_overdue)
        escalated_count = all_tickets.filter(escalation_level__gt=0).count()

        # Section breakdown
        section_stats = []
        for section in department.sections.filter(is_active=True):
            section_tickets = all_tickets.filter(section=section)
            section_stats.append({
                'section': {
                    'id': section.id,
                    'name': section.name,
                    'code': section.code,
                    'section_head': section.section_head.username if section.section_head else None
                },
                'total_tickets': section_tickets.count(),
                'open_tickets': section_tickets.filter(status__in=['open', 'assigned']).count(),
                'escalated_tickets': section_tickets.filter(escalation_level__gt=0).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    section_tickets
                ),
                'technician_count': section.technicians.count()
            })

        # Technician performance
        technicians = CustomUser.objects.filter(
            role='technician',
            sections__department=department
        ).distinct()

        tech_performance = []
        for tech in technicians:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            resolved_tickets = tech_tickets.filter(
                status__in=['resolved', 'closed']
            )

            tech_performance.append({
                'technician': {
                    'id': tech.id,
                    'name': f"{tech.first_name} {tech.last_name}",
                    'username': tech.username,
                    'sections': list(
                        tech.sections.filter(department=department).values_list(
                            'name', flat=True
                        )
                    )
                },
                'total_assigned': tech_tickets.count(),
                'resolved': resolved_tickets.count(),
                'open': tech_tickets.filter(
                    status__in=['open', 'assigned', 'in_progress']
                ).count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    tech_tickets
                ),
                'escalation_count': tech_tickets.filter(escalation_level__gt=0).count()
            })

        # Status distribution
        status_dist = recent_tickets.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Escalation trends
        escalation_trends = OrganizationalAnalytics._get_escalation_trends(
            all_tickets, days=7
        )

        # Pending tickets analysis
        pending_tickets = all_tickets.filter(status='pending')
        pending_reasons = pending_tickets.values('pending_reason').annotate(
            count=Count('id')
        ).order_by('-count')

        return {
            'department': {
                'name': department.name,
                'code': department.code,
                'campus': department.campus.name if department.campus else None,
                'sections_count': department.sections.filter(is_active=True).count()
            },
            'overview': {
                'total_tickets': total_tickets,
                'open_tickets': total_open,
                'overdue_tickets': overdue_count,
                'escalated_tickets': escalated_count,
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    all_tickets
                ),
                'sla_compliance': OrganizationalAnalytics._calculate_sla_compliance(all_tickets)
            },
            'sections': sorted(section_stats, key=lambda x: x['total_tickets'], reverse=True),
            'technicians': sorted(tech_performance, key=lambda x: x['total_assigned'], reverse=True),
            'pending_reasons': list(pending_reasons),
            'status_distribution': list(status_dist),
            'escalation_trends': escalation_trends,
            'period_days': days
        }


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
        # Use only 'resolved' and 'closed' tickets with a valid resolved_at timestamp
        resolved_tickets = Ticket.objects.filter(
            status__in=['resolved', 'closed'],
            resolved_at__isnull=False
        ).count()
        # print(Ticket.objects.filter(status__in=["closed", "resolved"],))
        print(resolved_tickets)
        # resolved_tickets = Ticket.objects.filter(
        #     status__in=['resolved', 'closed']).count()

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

        # -----------------------------------------------------------
        # Calculate average resolution time (created_at to resolved_at)
        # -----------------------------------------------------------
        resolution_time_expr = ExpressionWrapper(
            F('resolved_at') - F('created_at'),
            output_field=DurationField()
        )

        avg_resolution_time = (
            Ticket.objects.filter(
                status__in=['resolved', 'closed'],
                resolved_at__isnull=False  # Only include tickets that have been truly resolved
            )
            .annotate(resolution_time=resolution_time_expr)
            .aggregate(avg=Avg('resolution_time'))['avg']
        )

        # print(avg_resolution_time)

        # Convert to hours if not None
        avg_resolution_hours = None
        if avg_resolution_time:
            avg_resolution_hours = avg_resolution_time.total_seconds() / 3600
            # print(avg_resolution_hours)

        return {
            'total_tickets': total_tickets,
            'open_tickets': open_tickets,
            'resolved_tickets': resolved_tickets,
            'resolution_rate': round((resolved_tickets / total_tickets * 100) if total_tickets else 0, 2),
            'new_tickets_24h': new_tickets,
            'tickets_past_week': tickets_past_week,
            'tickets_past_month': tickets_past_month,
            'avg_resolution_time_hours': round(avg_resolution_hours, 2) if avg_resolution_hours else None,
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
                    output_field=DurationField()
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
