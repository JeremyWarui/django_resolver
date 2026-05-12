"""HOD analytics - single-campus department metrics for Heads of Department.

Scope: own department within own campus only.
HOD must have both primary_campus and primary_department set.
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Q

from tickets.models import Ticket, CustomUser
from .base_analytics import (
    ANALYTICS_CACHE_TTL,
    get_cached,
    calculate_avg_resolution_time,
    calculate_sla_compliance,
    get_escalation_trends,
    build_technician_performance,
    build_overview,
    get_status_distribution,
)


class HODAnalytics:

    @staticmethod
    def hod_dashboard(user, days=30):
        if not user.primary_campus or not user.primary_department:
            return {}

        department = user.primary_department
        campus = user.primary_campus

        def compute():
            time_threshold = timezone.now() - timedelta(days=days)

            all_tickets = Ticket.objects.filter(section__department=department)
            recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

            section_performance = []
            for section in department.sections.filter(is_active=True).select_related(
                "head_of_section"
            ):
                section_tickets = all_tickets.filter(section=section)
                section_performance.append({
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
                    "ticket_count": section_tickets.count(),
                    "open_count": section_tickets.filter(status__in=["open", "assigned"]).count(),
                    "avg_resolution_hours": calculate_avg_resolution_time(section_tickets),
                    "sla_compliance": calculate_sla_compliance(section_tickets),
                    "technician_count": section.technicians.count(),
                })

            technicians = CustomUser.objects.filter(
                role="technician", sections__department=department
            ).distinct()
            tech_performance = build_technician_performance(
                all_tickets, technicians, section_filter=Q(department=department)
            )

            return {
                "campus": {
                    "id": campus.id,
                    "name": campus.name,
                    "code": campus.code,
                    "location": getattr(campus, "location", ""),
                },
                "department": {
                    "id": department.id,
                    "name": department.name,
                    "code": department.code,
                    "campus": campus.name,
                },
                "overview": build_overview(all_tickets),
                "sections": sorted(
                    section_performance, key=lambda x: x["ticket_count"], reverse=True
                ),
                "technicians": tech_performance,
                "status_distribution": get_status_distribution(recent_tickets),
                "escalation_trends": get_escalation_trends(all_tickets, days=7),
                "period_days": days,
            }

        return get_cached(f"analytics_hod_{department.id}_{days}", compute)
