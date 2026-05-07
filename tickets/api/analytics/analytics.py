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
from django.core.cache import cache
from django.db.models import (
    Count,
    Avg,
    Q,
    F,
    ExpressionWrapper,
    fields,
    FloatField,
    DurationField,
)
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from typing import Dict, List, Optional, Tuple

from tickets.models import (
    Ticket,
    CustomUser,
    Feedback,
    Facility,
    Section,
    Organization,
    Campus,
    Department,
    TicketLog,
)

ANALYTICS_CACHE_TTL = 300  # 5 minutes


class TicketAnalytics:
    """
    Provides analytics for tickets in the system.
    Used for dashboard displays and reporting.
    """

    @staticmethod
    def get_ticket_counts_by_timeframe(days=1, facility_id=None, section_id=None):
        cache_key = f"analytics_timeframe_{days}_{facility_id}_{section_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        time_threshold = timezone.now() - timedelta(days=days)
        queryset = Ticket.objects.filter(created_at__gte=time_threshold)
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        result = {
            "period": f"Last {days} day{'s' if days > 1 else ''}",
            "count": queryset.count(),
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_ticket_counts_by_status(facility_id=None, section_id=None):
        cache_key = f"analytics_status_{facility_id}_{section_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        queryset = Ticket.objects.all()
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        result = list(
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_ticket_trend_data(days=30, group_by="day"):
        cache_key = f"analytics_trend_{days}_{group_by}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        time_threshold = timezone.now() - timedelta(days=days)
        trunc_map = {"week": TruncWeek("created_at"), "month": TruncMonth("created_at")}
        trunc_func = trunc_map.get(group_by, TruncDay("created_at"))

        result = list(
            Ticket.objects.filter(created_at__gte=time_threshold)
            .annotate(period=trunc_func)
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_tickets_by_facility():
        cache_key = "analytics_by_facility"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = list(
            Facility.objects.annotate(ticket_count=Count("tickets"))
            .values("name", "ticket_count")
            .order_by("-ticket_count")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_tickets_by_section():
        cache_key = "analytics_by_section"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = list(
            Section.objects.annotate(ticket_count=Count("tickets"))
            .values("name", "ticket_count")
            .order_by("-ticket_count")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result


class TechnicianAnalytics:
    """
    Provides analytics for technicians in the system.
    Used for performance evaluation and reporting.
    """

    @staticmethod
    def get_technician_performance(technician_id=None):
        """
        Performance metrics for technicians via DB aggregation — single query instead
        of multiple queries per technician.
        """
        cache_key = f"analytics_tech_performance_{technician_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        overdue_threshold = timezone.now() - timedelta(hours=24)

        queryset = CustomUser.objects.filter(role="technician")
        if technician_id:
            queryset = queryset.filter(id=technician_id)

        techs = queryset.annotate(
            total_tickets=Count("assigned_tickets", distinct=True),
            resolved_tickets=Count(
                "assigned_tickets",
                filter=Q(assigned_tickets__status__in=["resolved", "closed"]),
                distinct=True,
            ),
            pending_tickets=Count(
                "assigned_tickets",
                filter=Q(
                    assigned_tickets__status__in=["assigned", "in_progress", "pending"]
                ),
                distinct=True,
            ),
            overdue_tickets=Count(
                "assigned_tickets",
                filter=Q(
                    assigned_tickets__status__in=["assigned", "in_progress", "pending"],
                    assigned_tickets__created_at__lt=overdue_threshold,
                ),
                distinct=True,
            ),
            avg_rating=Avg("assigned_tickets__feedback__rating"),
            avg_resolution_hours=Avg(
                ExpressionWrapper(
                    F("assigned_tickets__updated_at")
                    - F("assigned_tickets__created_at"),
                    output_field=DurationField(),
                ),
                filter=Q(assigned_tickets__status__in=["resolved", "closed"]),
            ),
        )

        # Fetch per-status breakdown in one query for all techs in the queryset
        tech_ids = [t.id for t in techs]
        status_rows = (
            Ticket.objects.filter(assigned_to_id__in=tech_ids)
            .values("assigned_to_id", "status")
            .annotate(count=Count("id"))
        )
        status_by_tech: Dict[int, Dict[str, int]] = {}
        for row in status_rows:
            status_by_tech.setdefault(row["assigned_to_id"], {})[row["status"]] = row["count"]

        performance_data = []
        for tech in techs:
            avg_res = (
                (tech.avg_resolution_hours.total_seconds() / 3600)
                if tech.avg_resolution_hours
                else 0
            )
            performance_data.append(
                {
                    "id": tech.id,
                    "username": tech.username,
                    "full_name": f"{tech.first_name} {tech.last_name}",
                    "total_tickets": tech.total_tickets,
                    "resolved_tickets": tech.resolved_tickets,
                    "pending_tickets": tech.pending_tickets,
                    "overdue_tickets": tech.overdue_tickets,
                    "avg_rating": round(tech.avg_rating or 0, 2),
                    "avg_resolution_time": round(avg_res, 2),
                    "resolution_percentage": round(
                        (
                            (tech.resolved_tickets / tech.total_tickets * 100)
                            if tech.total_tickets > 0
                            else 0
                        ),
                        2,
                    ),
                    "tickets_by_status": status_by_tech.get(tech.id, {}),
                }
            )

        cache.set(cache_key, performance_data, ANALYTICS_CACHE_TTL)
        return performance_data

    @staticmethod
    def get_technician_ratings_by_section():
        """Ratings grouped by section via a single aggregation query."""
        cache_key = "analytics_tech_ratings_by_section"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        rows = Section.objects.annotate(
            technician_count=Count("technicians", distinct=True),
            avg_rating=Avg("technicians__assigned_tickets__feedback__rating"),
        ).values("name", "technician_count", "avg_rating")

        result = sorted(
            [
                {
                    "section_name": r["name"],
                    "technician_count": r["technician_count"],
                    "avg_rating": round(r["avg_rating"] or 0, 2),
                }
                for r in rows
            ],
            key=lambda x: x["avg_rating"],
            reverse=True,
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result


class OrganizationalAnalytics:
    """Analytics service providing role-specific dashboards for organizational hierarchy"""

    # SLA thresholds (hours)
    SLA_LIMITS = {"critical": 4, "urgent": 24, "high": 48, "normal": 72, "low": 120}

    @staticmethod
    def _calculate_avg_resolution_time(tickets_queryset) -> float:
        """Calculate average resolution time in hours"""
        resolved_tickets = tickets_queryset.filter(status__in=["resolved", "closed"])
        if not resolved_tickets.exists():
            return 0.0

        duration_annotations = resolved_tickets.annotate(
            resolution_time=ExpressionWrapper(
                F("resolved_at") - F("created_at"), output_field=DurationField()
            )
        )
        avg_duration = duration_annotations.aggregate(avg=Avg("resolution_time"))["avg"]
        return (avg_duration.total_seconds() / 3600) if avg_duration else 0.0

    @staticmethod
    def _calculate_sla_compliance(tickets_queryset) -> float:
        """Calculate SLA compliance percentage using a DB count instead of Python iteration."""
        total = tickets_queryset.count()
        if total == 0:
            return 0.0

        sla_cutoff = timezone.now() - timedelta(days=7)
        overdue_count = tickets_queryset.filter(
            created_at__lt=sla_cutoff,
            status__in=["open", "assigned", "in_progress", "pending", "escalated"],
        ).count()
        return round(((total - overdue_count) / total) * 100, 2)

    @staticmethod
    def _get_escalation_trends(tickets_queryset, days: int = 30) -> Dict:
        """Get escalation trends over specified period"""
        time_threshold = timezone.now() - timedelta(days=days)
        recent = tickets_queryset.filter(escalated_at__gte=time_threshold)

        return {
            "total_escalations": recent.count(),
            "by_level": dict(
                recent.values("escalation_level")
                .annotate(count=Count("id"))
                .values_list("escalation_level", "count")
            ),
            "avg_levels": recent.aggregate(avg=Avg("escalation_level"))["avg"] or 0,
        }

    @staticmethod
    def manager_dashboard(user: CustomUser, days: int = 30) -> Dict:
        """
        Cross-campus department dashboard for managers.
        Shows metrics for the manager's department across ALL campuses.

        Manager scope: same department code across every campus in the organization.
        Manager has no primary_campus; scoped via primary_department.
        """
        if user.role != "manager" or not user.primary_department:
            return {}

        dept = user.primary_department
        org = dept.campus.organization
        dept_code = dept.code

        cache_key = f"analytics_manager_{org.id}_{dept_code}_{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        # All departments with the same code across every campus in the org
        same_depts = Department.objects.filter(code=dept_code, campus__organization=org)
        time_threshold = timezone.now() - timedelta(days=days)

        all_tickets = Ticket.objects.filter(section__department__in=same_depts)
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(status__in=["open", "assigned"]).count()
        overdue_count = all_tickets.filter(
            created_at__lt=timezone.now() - timedelta(days=7),
            status__in=["open", "assigned", "in_progress", "pending", "escalated"],
        ).count()
        escalated_count = all_tickets.filter(escalation_level__gt=0).count()

        # Per-campus breakdown
        campus_stats = []
        for dept_instance in same_depts.select_related("campus"):
            campus = dept_instance.campus
            campus_tickets = all_tickets.filter(section__department=dept_instance)
            campus_stats.append(
                {
                    "campus": {"id": campus.id, "name": campus.name, "code": campus.code},
                    "department_id": dept_instance.id,
                    "total_tickets": campus_tickets.count(),
                    "open_tickets": campus_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "escalated_tickets": campus_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        campus_tickets
                    ),
                    "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                        campus_tickets
                    ),
                }
            )

        # Section performance across campuses
        section_stats = []
        for section in Section.objects.filter(department__in=same_depts, is_active=True):
            section_tickets = all_tickets.filter(section=section)
            section_stats.append(
                {
                    "section": {
                        "id": section.id,
                        "name": section.name,
                        "code": section.code,
                        "campus": (
                            section.department.campus.name
                            if section.department and section.department.campus
                            else None
                        ),
                        "head_of_section": (
                            section.head_of_section.username
                            if section.head_of_section
                            else None
                        ),
                    },
                    "total_tickets": section_tickets.count(),
                    "open_tickets": section_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "escalated_tickets": section_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        section_tickets
                    ),
                    "technician_count": section.technicians.count(),
                }
            )

        # Technician performance
        technicians = CustomUser.objects.filter(
            role="technician", sections__department__in=same_depts
        ).distinct()
        tech_performance = []
        for tech in technicians:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            tech_performance.append(
                {
                    "technician": {
                        "id": tech.id,
                        "name": f"{tech.first_name} {tech.last_name}",
                        "username": tech.username,
                    },
                    "total_assigned": tech_tickets.count(),
                    "resolved": tech_tickets.filter(
                        status__in=["resolved", "closed"]
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        tech_tickets
                    ),
                }
            )

        status_dist = (
            recent_tickets.values("status").annotate(count=Count("id")).order_by("-count")
        )
        escalation_trends = OrganizationalAnalytics._get_escalation_trends(all_tickets, days=7)

        result = {
            "department": {
                "name": dept.name,
                "code": dept_code,
                "campuses_count": same_depts.count(),
            },
            "overview": {
                "total_tickets": total_tickets,
                "open_tickets": total_open,
                "overdue_tickets": overdue_count,
                "escalated_tickets": escalated_count,
                "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                    all_tickets
                ),
                "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                    all_tickets
                ),
            },
            "campuses": sorted(campus_stats, key=lambda x: x["total_tickets"], reverse=True),
            "sections": sorted(section_stats, key=lambda x: x["total_tickets"], reverse=True),
            "technicians": sorted(
                tech_performance, key=lambda x: x["total_assigned"], reverse=True
            ),
            "status_distribution": list(status_dist),
            "escalation_trends": escalation_trends,
            "period_days": days,
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

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
        if user.role != "manager" or not user.primary_campus:
            return {}

        cache_key = f"analytics_director_{user.primary_campus.organization_id}_{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        org = user.primary_campus.organization
        time_threshold = timezone.now() - timedelta(days=days)

        # Base querysets
        all_tickets = Ticket.objects.filter(
            section__department__campus__organization=org
        )
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        # Overall metrics
        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(status__in=["open", "assigned"]).count()
        total_escalated = all_tickets.filter(escalation_level__gt=0).count()
        avg_resolution_time = OrganizationalAnalytics._calculate_avg_resolution_time(
            all_tickets
        )

        # Campus breakdown
        campus_stats = []
        for campus in org.campuses.all():
            campus_tickets = all_tickets.filter(section__department__campus=campus)
            campus_stats.append(
                {
                    "campus": {
                        "id": campus.id,
                        "name": campus.name,
                        "code": campus.code,
                        "location": campus.location,
                    },
                    "total_tickets": campus_tickets.count(),
                    "open_tickets": campus_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "overdue_tickets": campus_tickets.filter(
                        created_at__lt=timezone.now() - timedelta(days=7),
                        status__in=[
                            "open",
                            "assigned",
                            "in_progress",
                            "pending",
                            "escalated",
                        ],
                    ).count(),
                    "escalated_tickets": campus_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        campus_tickets
                    ),
                    "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                        campus_tickets
                    ),
                }
            )

        # Department performance across campuses
        dept_performance = []
        for campus in org.campuses.all():
            for dept in campus.departments.filter(is_active=True):
                dept_tickets = all_tickets.filter(section__department=dept)
                dept_performance.append(
                    {
                        "department": {
                            "id": dept.id,
                            "name": dept.name,
                            "code": dept.code,
                            "campus": campus.name,
                            "hod": (
                                dept.head_of_department.username
                                if dept.head_of_department
                                else None
                            ),
                        },
                        "ticket_count": dept_tickets.count(),
                        "open_count": dept_tickets.filter(
                            status__in=["open", "assigned"]
                        ).count(),
                        "resolved_count": dept_tickets.filter(
                            status__in=["resolved", "closed"]
                        ).count(),
                        "escalation_count": dept_tickets.filter(
                            escalation_level__gt=0
                        ).count(),
                        "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                            dept_tickets
                        ),
                        "avg_escalations": dept_tickets.aggregate(
                            avg=Avg("escalation_level")
                        )["avg"]
                        or 0,
                    }
                )

        # Status distribution
        status_dist = (
            recent_tickets.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Escalation trends
        escalation_trends = OrganizationalAnalytics._get_escalation_trends(
            all_tickets, days=7
        )

        # Top technicians by resolution count
        top_technicians = []
        technicians = CustomUser.objects.filter(
            role="technician", sections__department__campus__organization=org
        ).distinct()
        for tech in technicians[:10]:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            top_technicians.append(
                {
                    "technician": {
                        "id": tech.id,
                        "name": f"{tech.first_name} {tech.last_name}",
                        "username": tech.username,
                    },
                    "total_assigned": tech_tickets.count(),
                    "resolved": tech_tickets.filter(
                        status__in=["resolved", "closed"]
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        tech_tickets
                    ),
                }
            )

        # Facility-level metrics across organization
        facility_stats = []
        org_facilities = Facility.objects.filter(campus__organization=org)
        for facility in org_facilities:
            facility_tickets = all_tickets.filter(facility=facility)
            facility_stats.append(
                {
                    "facility": {
                        "id": facility.id,
                        "name": facility.name,
                        "type": facility.type,
                        "status": facility.status,
                        "campus": facility.campus.name if facility.campus else None,
                    },
                    "total_tickets": facility_tickets.count(),
                    "open_tickets": facility_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "resolved_tickets": facility_tickets.filter(
                        status__in=["resolved", "closed"]
                    ).count(),
                    "overdue_tickets": sum(1 for t in facility_tickets if t.is_overdue),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        facility_tickets
                    ),
                }
            )

        # Organization-wide section metrics
        section_stats = []
        org_sections = Section.objects.filter(department__campus__organization=org)
        for section in org_sections:
            section_tickets = all_tickets.filter(section=section)
            section_stats.append(
                {
                    "section": {
                        "id": section.id,
                        "name": section.name,
                        "code": section.code,
                        "department": (
                            section.department.name if section.department else None
                        ),
                        "campus": (
                            section.department.campus.name
                            if section.department and section.department.campus
                            else None
                        ),
                        "head_of_section": (
                            section.head_of_section.username
                            if section.head_of_section
                            else None
                        ),
                    },
                    "total_tickets": section_tickets.count(),
                    "open_tickets": section_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "resolved_tickets": section_tickets.filter(
                        status__in=["resolved", "closed"]
                    ).count(),
                    "escalated_tickets": section_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        section_tickets
                    ),
                    "technician_count": section.technicians.count(),
                }
            )

        # Status distribution
        status_dist = (
            recent_tickets.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        result = {
            "organization": {
                "name": org.name,
                "code": org.code,
                "type": org.organization_type,
                "campuses_count": org.campuses.count(),
            },
            "overview": {
                "total_tickets": total_tickets,
                "total_open": total_open,
                "total_escalated": total_escalated,
                "avg_resolution_hours": avg_resolution_time,
                "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                    all_tickets
                ),
            },
            "campuses": campus_stats,
            "departments": sorted(
                dept_performance, key=lambda x: x["ticket_count"], reverse=True
            ),
            "facilities": sorted(
                facility_stats, key=lambda x: x["total_tickets"], reverse=True
            ),
            "sections": sorted(
                section_stats, key=lambda x: x["total_tickets"], reverse=True
            ),
            "status_distribution": list(status_dist),
            "escalation_trends": escalation_trends,
            "top_technicians": top_technicians,
            "period_days": days,
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

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
        if user.role != "hod" or not user.primary_campus:
            return {}

        cache_key = f"analytics_hod_{user.primary_campus_id}_{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        campus = user.primary_campus
        time_threshold = timezone.now() - timedelta(days=days)

        # Base querysets
        all_tickets = Ticket.objects.filter(section__department__campus=campus)
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        # Campus overview
        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(status__in=["open", "assigned"]).count()
        overdue_count = all_tickets.filter(
            created_at__lt=timezone.now() - timedelta(days=7),
            status__in=["open", "assigned", "in_progress", "pending", "escalated"],
        ).count()
        escalated_count = all_tickets.filter(escalation_level__gt=0).count()

        # Department breakdown
        dept_stats = []
        for dept in campus.departments.filter(is_active=True):
            dept_tickets = all_tickets.filter(section__department=dept)
            dept_stats.append(
                {
                    "department": {
                        "id": dept.id,
                        "name": dept.name,
                        "code": dept.code,
                        "hod": (
                            dept.head_of_department.username
                            if dept.head_of_department
                            else None
                        ),
                    },
                    "total_tickets": dept_tickets.count(),
                    "open_tickets": dept_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "escalated_tickets": dept_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        dept_tickets
                    ),
                    "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                        dept_tickets
                    ),
                }
            )

        # Section performance within departments
        section_performance = []
        for dept in campus.departments.filter(is_active=True):
            for section in dept.sections.filter(is_active=True):
                section_tickets = all_tickets.filter(section=section)
                section_performance.append(
                    {
                        "section": {
                            "id": section.id,
                            "name": section.name,
                            "code": section.code,
                            "department": dept.name,
                            "head_of_section": (
                                section.head_of_section.username
                                if section.head_of_section
                                else None
                            ),
                        },
                        "ticket_count": section_tickets.count(),
                        "open_count": section_tickets.filter(
                            status__in=["open", "assigned"]
                        ).count(),
                        "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                            section_tickets
                        ),
                        "technician_count": section.technicians.count(),
                    }
                )

        # Technician performance (across campus)
        technicians = CustomUser.objects.filter(
            role="technician", sections__department__campus=campus
        ).distinct()

        tech_performance = []
        for tech in technicians:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            tech_performance.append(
                {
                    "technician": {
                        "id": tech.id,
                        "name": f"{tech.first_name} {tech.last_name}",
                        "username": tech.username,
                        "sections": list(
                            tech.sections.filter(department__campus=campus).values_list(
                                "name", flat=True
                            )
                        ),
                    },
                    "total_assigned": tech_tickets.count(),
                    "resolved": tech_tickets.filter(
                        status__in=["resolved", "closed"]
                    ).count(),
                    "open": tech_tickets.filter(
                        status__in=["open", "assigned", "in_progress"]
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        tech_tickets
                    ),
                }
            )

        # Status distribution
        status_dist = (
            recent_tickets.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Escalation analysis
        escalation_by_level = (
            all_tickets.values("escalation_level")
            .annotate(count=Count("id"))
            .order_by("escalation_level")
        )

        result = {
            "campus": {
                "name": campus.name,
                "code": campus.code,
                "location": campus.location,
                "departments_count": campus.departments.filter(is_active=True).count(),
            },
            "overview": {
                "total_tickets": total_tickets,
                "open_tickets": total_open,
                "overdue_tickets": overdue_count,
                "escalated_tickets": escalated_count,
                "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                    all_tickets
                ),
                "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                    all_tickets
                ),
            },
            "departments": sorted(
                dept_stats, key=lambda x: x["total_tickets"], reverse=True
            ),
            "sections": sorted(
                section_performance, key=lambda x: x["ticket_count"], reverse=True
            ),
            "technicians": sorted(
                tech_performance, key=lambda x: x["total_assigned"], reverse=True
            ),
            "status_distribution": list(status_dist),
            "escalation_by_level": list(escalation_by_level),
            "period_days": days,
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def head_of_section_dashboard(user: CustomUser, days: int = 30) -> Dict:
        """
        Department-level dashboard for Section Heads.
        Shows metrics for their department and sections.

        Args:
            user: Section Head user
            days: Number of days to analyze (default: 30)

        Returns:
            Dictionary with dashboard metrics
        """
        if user.role != "head_of_section" or not user.primary_department:
            return {}

        cache_key = f"analytics_section_head_{user.primary_department_id}_{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        department = user.primary_department
        time_threshold = timezone.now() - timedelta(days=days)

        # Base querysets
        all_tickets = Ticket.objects.filter(section__department=department)
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        # Department overview
        total_tickets = all_tickets.count()
        total_open = all_tickets.filter(status__in=["open", "assigned"]).count()
        overdue_count = all_tickets.filter(
            created_at__lt=timezone.now() - timedelta(days=7),
            status__in=["open", "assigned", "in_progress", "pending", "escalated"],
        ).count()
        escalated_count = all_tickets.filter(escalation_level__gt=0).count()

        # Section breakdown
        section_stats = []
        for section in department.sections.filter(is_active=True):
            section_tickets = all_tickets.filter(section=section)
            section_stats.append(
                {
                    "section": {
                        "id": section.id,
                        "name": section.name,
                        "code": section.code,
                        "head_of_section": (
                            section.head_of_section.username
                            if section.head_of_section
                            else None
                        ),
                    },
                    "total_tickets": section_tickets.count(),
                    "open_tickets": section_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "escalated_tickets": section_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        section_tickets
                    ),
                    "technician_count": section.technicians.count(),
                }
            )

        # Technician performance
        technicians = CustomUser.objects.filter(
            role="technician", sections__department=department
        ).distinct()

        tech_performance = []
        for tech in technicians:
            tech_tickets = all_tickets.filter(assigned_to=tech)
            resolved_tickets = tech_tickets.filter(status__in=["resolved", "closed"])

            tech_performance.append(
                {
                    "technician": {
                        "id": tech.id,
                        "name": f"{tech.first_name} {tech.last_name}",
                        "username": tech.username,
                        "sections": list(
                            tech.sections.filter(department=department).values_list(
                                "name", flat=True
                            )
                        ),
                    },
                    "total_assigned": tech_tickets.count(),
                    "resolved": resolved_tickets.count(),
                    "open": tech_tickets.filter(
                        status__in=["open", "assigned", "in_progress"]
                    ).count(),
                    "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                        tech_tickets
                    ),
                    "escalation_count": tech_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                }
            )

        # Status distribution
        status_dist = (
            recent_tickets.values("status")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Escalation trends
        escalation_trends = OrganizationalAnalytics._get_escalation_trends(
            all_tickets, days=7
        )

        # Pending tickets analysis
        pending_tickets = all_tickets.filter(status="pending")
        pending_reasons = (
            pending_tickets.values("pending_reason")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        result = {
            "department": {
                "name": department.name,
                "code": department.code,
                "campus": department.campus.name if department.campus else None,
                "sections_count": department.sections.filter(is_active=True).count(),
            },
            "overview": {
                "total_tickets": total_tickets,
                "open_tickets": total_open,
                "overdue_tickets": overdue_count,
                "escalated_tickets": escalated_count,
                "avg_resolution_hours": OrganizationalAnalytics._calculate_avg_resolution_time(
                    all_tickets
                ),
                "sla_compliance": OrganizationalAnalytics._calculate_sla_compliance(
                    all_tickets
                ),
            },
            "sections": sorted(
                section_stats, key=lambda x: x["total_tickets"], reverse=True
            ),
            "technicians": sorted(
                tech_performance, key=lambda x: x["total_assigned"], reverse=True
            ),
            "pending_reasons": list(pending_reasons),
            "status_distribution": list(status_dist),
            "escalation_trends": escalation_trends,
            "period_days": days,
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result


class AdminAnalytics:
    """
    Provides system-wide analytics for administrators.
    Used for monitoring overall system health and performance.
    """

    @staticmethod
    def get_system_overview():
        cached = cache.get("analytics_admin_overview")
        if cached is not None:
            return cached

        now = timezone.now()
        resolved_qs = Ticket.objects.filter(
            status__in=["resolved", "closed"], resolved_at__isnull=False
        )

        counts = Ticket.objects.aggregate(
            total=Count("id"),
            open=Count("id", filter=Q(status="open")),
            resolved=Count(
                "id",
                filter=Q(status__in=["resolved", "closed"], resolved_at__isnull=False),
            ),
            new_24h=Count("id", filter=Q(created_at__gte=now - timedelta(days=1))),
            past_week=Count("id", filter=Q(created_at__gte=now - timedelta(days=7))),
            past_month=Count("id", filter=Q(created_at__gte=now - timedelta(days=30))),
        )

        avg_resolution_time = resolved_qs.annotate(
            resolution_time=ExpressionWrapper(
                F("resolved_at") - F("created_at"), output_field=DurationField()
            )
        ).aggregate(avg=Avg("resolution_time"))["avg"]

        avg_resolution_hours = (
            round(avg_resolution_time.total_seconds() / 3600, 2)
            if avg_resolution_time
            else None
        )
        total = counts["total"] or 0
        resolved = counts["resolved"] or 0

        result = {
            "total_tickets": total,
            "open_tickets": counts["open"] or 0,
            "resolved_tickets": resolved,
            "resolution_rate": round((resolved / total * 100) if total else 0, 2),
            "new_tickets_24h": counts["new_24h"] or 0,
            "tickets_past_week": counts["past_week"] or 0,
            "tickets_past_month": counts["past_month"] or 0,
            "avg_resolution_time_hours": avg_resolution_hours,
        }
        cache.set("analytics_admin_overview", result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_overdue_tickets():
        cached = cache.get("analytics_admin_overdue")
        if cached is not None:
            return cached

        overdue_threshold = timezone.now() - timedelta(hours=24)

        overdue_tickets = (
            Ticket.objects.filter(
                created_at__lt=overdue_threshold,
                status__in=["open", "assigned", "in_progress", "pending"],
            )
            .select_related("section", "facility", "assigned_to")
            .annotate(
                age_hours=ExpressionWrapper(
                    (timezone.now() - F("created_at")), output_field=DurationField()
                )
            )
        )

        result = sorted(
            [
                {
                    "id": t.id,
                    "ticket_no": t.ticket_no,
                    "title": t.title,
                    "status": t.status,
                    "section": t.section.name,
                    "facility": t.facility.name,
                    "assigned_to": t.assigned_to.username if t.assigned_to else None,
                    "age_hours": round(t.age_hours.total_seconds() / 3600, 2),
                    "created_at": t.created_at,
                }
                for t in overdue_tickets
            ],
            key=lambda x: x["age_hours"],
            reverse=True,
        )
        cache.set("analytics_admin_overdue", result, ANALYTICS_CACHE_TTL)
        return result
