"""
OrganizationalAnalytics

Provides role-specific analytics dashboards for organizational hierarchy.
Each dashboard shows metrics appropriate to the user's organizational level.

- Director: Organization-wide view
- HOD: Campus-wide view  
- Section Head: Department view
- Technician/Managers: Can view own analytics

Key Metrics:
- Ticket counts and distributions
- Resolution times and SLA compliance
- Escalation trends
- Technician performance
"""

from django.db.models import Count, Q, Avg, Sum, Max, Min
from django.utils import timezone
from datetime import timedelta
from tickets.models import Ticket, CustomUser, Organization, Campus, Department, Section, TicketLog
from typing import Dict, List, Optional, Tuple


class OrganizationalAnalytics:
    """Analytics service providing role-specific dashboards"""

    # SLA thresholds (hours)
    SLA_LIMITS = {
        'critical': 4,
        'urgent': 24,
        'high': 48,
        'normal': 72,
        'low': 120
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
            'priority_distribution': list(priority_dist),
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
                'pending_tickets': pending_tickets.count(),
                'avg_resolution_hours': OrganizationalAnalytics._calculate_avg_resolution_time(
                    all_tickets
                ),
                'sla_compliance': OrganizationalAnalytics._calculate_sla_compliance(all_tickets)
            },
            'sections': sorted(section_stats, key=lambda x: x['total_tickets'], reverse=True),
            'technicians': sorted(tech_performance, key=lambda x: x['total_assigned'], reverse=True),
            'status_distribution': list(status_dist),
            'escalation_trends': escalation_trends,
            'pending_reasons': list(pending_reasons),
            'period_days': days
        }

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    @staticmethod
    def _calculate_avg_resolution_time(tickets) -> float:
        """Calculate average resolution time in hours for ticket queryset"""
        resolved = tickets.filter(
            status__in=['resolved', 'closed'],
            resolved_at__isnull=False
        ).annotate(
            resolution_hours=Count('id')  # Placeholder
        )

        if not resolved.exists():
            return 0.0

        total_hours = 0
        count = 0
        for ticket in resolved:
            if ticket.resolved_at and ticket.created_at:
                hours = (ticket.resolved_at -
                         ticket.created_at).total_seconds() / 3600
                total_hours += hours
                count += 1

        return round(total_hours / count, 2) if count > 0 else 0.0

    @staticmethod
    def _calculate_sla_compliance(tickets) -> float:
        """Calculate SLA compliance percentage for ticket queryset"""
        resolved = tickets.filter(
            status__in=['resolved', 'closed'],
            resolved_at__isnull=False
        )

        if not resolved.exists():
            return 100.0

        compliant = 0
        sla_limit = 7 * 24  # 7 days in hours

        for ticket in resolved:
            if ticket.resolved_at and ticket.created_at:
                hours = (ticket.resolved_at -
                         ticket.created_at).total_seconds() / 3600
                if hours <= sla_limit:
                    compliant += 1

        total = resolved.count()
        return round((compliant / total) * 100, 1) if total > 0 else 100.0

    @staticmethod
    def _get_escalation_trends(tickets, days: int = 7) -> List[Dict]:
        """Get escalation trends over specified number of days"""
        trends = []
        now = timezone.now()

        for i in range(days, -1, -1):
            date = (now - timedelta(days=i)).date()
            date_start = timezone.make_aware(
                timezone.datetime.combine(date, timezone.datetime.min.time())
            )
            date_end = timezone.make_aware(
                timezone.datetime.combine(date, timezone.datetime.max.time())
            )

            escalated = tickets.filter(
                escalated_at__gte=date_start,
                escalated_at__lte=date_end
            ).count()

            trends.append({
                'date': str(date),
                'escalated_count': escalated
            })

        return trends

    @staticmethod
    def _get_top_technicians(tickets, limit: int = 10) -> List[Dict]:
        """Get top performing technicians by resolved tickets"""
        technicians = CustomUser.objects.filter(
            role='technician',
            assigned_tickets__in=tickets
        ).annotate(
            resolved_count=Count(
                'assigned_tickets',
                filter=Q(assigned_tickets__status__in=['resolved', 'closed'])
            ),
            total_assigned=Count('assigned_tickets')
        ).order_by('-resolved_count')[:limit]

        return [
            {
                'technician': {
                    'id': tech.id,
                    'name': f"{tech.first_name} {tech.last_name}",
                    'username': tech.username
                },
                'resolved_tickets': tech.resolved_count,
                'total_assigned': tech.total_assigned,
                'resolution_rate': round(
                    (tech.resolved_count / tech.total_assigned * 100),
                    1
                ) if tech.total_assigned > 0 else 0
            }
            for tech in technicians
        ]
