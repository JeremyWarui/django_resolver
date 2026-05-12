"""Manager analytics - cross-campus department metrics.

Scope: same department code across every campus in the organization.
Manager has primary_department but no primary_campus.
"""

from datetime import timedelta
from django.utils import timezone

from tickets.models import Ticket, CustomUser, Department, Section
from .base_analytics import (
    ANALYTICS_CACHE_TTL,
    get_cached,
    calculate_avg_resolution_time,
    get_escalation_trends,
    build_technician_performance,
    build_overview,
    build_scope_stats,
    get_status_distribution,
)


class ManagerAnalytics:

    @staticmethod
    def manager_dashboard(user, days=30):
        if not user.primary_department:
            return {}

        dept = user.primary_department
        org = dept.campus.organization
        dept_code = dept.code

        def compute():
            same_depts = Department.objects.filter(code=dept_code, campus__organization=org)
            time_threshold = timezone.now() - timedelta(days=days)

            all_tickets = Ticket.objects.filter(section__department__in=same_depts)
            recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

            campus_stats = []
            for dept_instance in same_depts.select_related("campus"):
                campus = dept_instance.campus
                campus_tickets = all_tickets.filter(section__department=dept_instance)
                campus_stats.append({
                    "campus": {"id": campus.id, "name": campus.name, "code": campus.code},
                    "department_id": dept_instance.id,
                    **build_scope_stats(campus_tickets),
                })

            section_stats = []
            for section in Section.objects.filter(
                department__in=same_depts, is_active=True
            ).select_related("department__campus", "head_of_section"):
                section_tickets = all_tickets.filter(section=section)
                section_stats.append({
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
                    **build_scope_stats(section_tickets),
                    "technician_count": section.technicians.count(),
                })

            technicians = CustomUser.objects.filter(
                role="technician", sections__department__in=same_depts
            ).distinct()
            tech_performance = build_technician_performance(all_tickets, technicians)

            return {
                "department": {
                    "name": dept.name,
                    "code": dept_code,
                    "campuses_count": same_depts.count(),
                },
                "overview": build_overview(all_tickets),
                "campuses": sorted(campus_stats, key=lambda x: x["total_tickets"], reverse=True),
                "sections": sorted(section_stats, key=lambda x: x["total_tickets"], reverse=True),
                "technicians": sorted(
                    tech_performance, key=lambda x: x["total_assigned"], reverse=True
                ),
                "status_distribution": get_status_distribution(recent_tickets),
                "escalation_trends": get_escalation_trends(all_tickets, days=7),
                "period_days": days,
            }

        return get_cached(f"analytics_manager_{org.id}_{dept_code}_{days}", compute)
