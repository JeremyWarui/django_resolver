"""Section Head analytics - section-level metrics for Section Heads.

Scope: all sections where user is head_of_section (a Section Head may oversee
more than one section, but typically just one).
"""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count, Q

from tickets.models import Ticket, CustomUser, Section
from .base_analytics import (
    calculate_avg_resolution_time,
    calculate_sla_compliance,
    get_escalation_trends,
    build_technician_performance,
    count_overdue,
    get_status_distribution,
)

ANALYTICS_CACHE_TTL = 300


class SectionHeadAnalytics:

    @staticmethod
    def section_head_dashboard(user, days=30):
        if user.role != "head_of_section":
            return {}

        sections = Section.objects.filter(head_of_section=user)
        if not sections.exists():
            return {}

        cache_key = f"analytics_section_head_{user.id}_{days}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        time_threshold = timezone.now() - timedelta(days=days)

        all_tickets = Ticket.objects.filter(section__in=sections)
        recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

        overdue_count = count_overdue(all_tickets)

        section_stats = []
        for section in sections.filter(is_active=True).select_related("department"):
            section_tickets = all_tickets.filter(section=section)
            section_stats.append(
                {
                    "section": {
                        "id": section.id,
                        "name": section.name,
                        "code": section.code,
                        "department": section.department.name if section.department else None,
                    },
                    "total_tickets": section_tickets.count(),
                    "open_tickets": section_tickets.filter(
                        status__in=["open", "assigned"]
                    ).count(),
                    "escalated_tickets": section_tickets.filter(
                        escalation_level__gt=0
                    ).count(),
                    "avg_resolution_hours": calculate_avg_resolution_time(section_tickets),
                    "sla_compliance": calculate_sla_compliance(section_tickets),
                    "technician_count": section.technicians.count(),
                }
            )

        technicians = CustomUser.objects.filter(
            role="technician", sections__in=sections
        ).distinct()

        tech_performance = build_technician_performance(
            all_tickets, technicians, section_filter=Q(id__in=sections)
        )

        pending_reasons = list(
            all_tickets.filter(status="pending")
            .values("pending_reason")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        result = {
            "sections": sorted(section_stats, key=lambda x: x["total_tickets"], reverse=True),
            "overview": {
                "total_tickets": all_tickets.count(),
                "open_tickets": all_tickets.filter(status__in=["open", "assigned"]).count(),
                "overdue_tickets": overdue_count,
                "escalated_tickets": all_tickets.filter(escalation_level__gt=0).count(),
                "avg_resolution_hours": calculate_avg_resolution_time(all_tickets),
                "sla_compliance": calculate_sla_compliance(all_tickets),
            },
            "technicians": sorted(
                tech_performance, key=lambda x: x["total_assigned"], reverse=True
            ),
            "pending_reasons": pending_reasons,
            "status_distribution": get_status_distribution(recent_tickets),
            "escalation_trends": get_escalation_trends(all_tickets, days=7),
            "period_days": days,
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result
