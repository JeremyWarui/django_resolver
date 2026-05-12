"""Section Head analytics - section-level metrics for Section Heads.

Scope: all sections where user is head_of_section (a Section Head may oversee
more than one section, but typically just one).
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q

from tickets.models import Ticket, CustomUser, Section
from .base_analytics import (
    ANALYTICS_CACHE_TTL,
    get_cached,
    get_escalation_trends,
    build_technician_performance,
    build_overview,
    build_scope_stats,
    get_status_distribution,
)


class SectionHeadAnalytics:

    @staticmethod
    def section_head_dashboard(user, days=30):
        sections = Section.objects.filter(head_of_section=user)
        if not sections.exists():
            return {}

        def compute():
            time_threshold = timezone.now() - timedelta(days=days)

            all_tickets = Ticket.objects.filter(section__in=sections)
            recent_tickets = all_tickets.filter(created_at__gte=time_threshold)

            section_stats = []
            for section in sections.filter(is_active=True).select_related("department__campus"):
                section_tickets = all_tickets.filter(section=section)
                section_stats.append({
                    "section": {
                        "id": section.id,
                        "name": section.name,
                        "code": section.code,
                        "department": section.department.name if section.department else None,
                        "section_head": user.username,
                    },
                    **build_scope_stats(section_tickets),
                    "technician_count": section.technicians.count(),
                })

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

            first_section = sections.select_related("department__campus").first()
            department_data = None
            if first_section and first_section.department:
                dept = first_section.department
                department_data = {
                    "name": dept.name,
                    "code": dept.code,
                    "campus": dept.campus.name if dept.campus else None,
                    "sections_count": sections.count(),
                }

            return {
                "department": department_data,
                "overview": build_overview(all_tickets),
                "sections": sorted(
                    section_stats, key=lambda x: x["total_tickets"], reverse=True
                ),
                "technicians": tech_performance,
                "pending_reasons": pending_reasons,
                "status_distribution": get_status_distribution(recent_tickets),
                "escalation_trends": get_escalation_trends(all_tickets, days=7),
                "period_days": days,
            }

        return get_cached(f"analytics_section_head_{user.id}_{days}", compute)
