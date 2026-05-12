"""Admin analytics - system-wide metrics for administrators."""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, ExpressionWrapper, F, Q, DurationField

from tickets.models import Ticket, CustomUser, Campus
from .base_analytics import (
    ANALYTICS_CACHE_TTL,
    OVERDUE_STATUSES,
    OVERDUE_THRESHOLD_DAYS,
    calculate_avg_resolution_time,
    calculate_sla_compliance,
    get_cached,
    get_ticket_trend_data,
)


class AdminAnalytics:

    @staticmethod
    def get_system_overview():
        def compute():
            now = timezone.now()
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

            total = counts["total"] or 0
            resolved = counts["resolved"] or 0

            return {
                "summary": {
                    "total_tickets": total,
                    "open_tickets": counts["open"] or 0,
                    "resolved_tickets": resolved,
                    "new_24h": counts["new_24h"] or 0,
                    "past_7_days": counts["past_week"] or 0,
                    "past_30_days": counts["past_month"] or 0,
                    "avg_resolution_time_hours": calculate_avg_resolution_time(Ticket.objects.all()) or None,
                },
                "users": {
                    "total_users": CustomUser.objects.filter(is_active=True).count(),
                    "technicians": CustomUser.objects.filter(role="technician", is_active=True).count(),
                    "managers": CustomUser.objects.filter(role="manager", is_active=True).count(),
                    "admins": CustomUser.objects.filter(role="admin", is_active=True).count(),
                },
                "resolution_rate": round((resolved / total * 100) if total > 0 else 0, 2),
            }

        return get_cached("analytics_admin_overview", compute)

    @staticmethod
    def get_overdue_tickets():
        def compute():
            threshold = timezone.now() - timedelta(days=OVERDUE_THRESHOLD_DAYS)
            overdue = (
                Ticket.objects.filter(
                    created_at__lt=threshold,
                    status__in=OVERDUE_STATUSES,
                )
                .select_related("section", "section__department__campus", "facility", "assigned_to")
                .annotate(
                    age_hours=ExpressionWrapper(
                        timezone.now() - F("created_at"), output_field=DurationField()
                    )
                )
                .order_by("created_at")
            )

            return {
                "count": overdue.count(),
                "tickets": [
                    {
                        "id": t.id,
                        "ticket_no": t.ticket_no,
                        "title": t.title,
                        "status": t.status,
                        "priority": t.priority,
                        "section": (
                            f"{t.section.department.campus.code}-{t.section.name}"
                            if t.section.department_id and t.section.department.campus_id
                            else t.section.name
                        ),
                        "facility": t.facility.name if t.facility else None,
                        "assigned_to": t.assigned_to.username if t.assigned_to else None,
                        "age_hours": round(t.age_hours.total_seconds() / 3600, 2),
                        "days_old": (timezone.now() - t.created_at).days,
                        "created_at": t.created_at.isoformat(),
                    }
                    for t in overdue[:50]
                ],
            }

        return get_cached("analytics_admin_overdue", compute)

    @staticmethod
    def get_organisation_analytics(days=30):
        def compute():
            campus_breakdown = []
            for campus in Campus.objects.all():
                campus_tickets = Ticket.objects.filter(section__department__campus=campus)
                total = campus_tickets.count()
                resolved = campus_tickets.filter(status__in=["resolved", "closed"]).count()
                campus_breakdown.append({
                    "campus": {"id": campus.id, "name": campus.name, "code": campus.code},
                    "total_tickets": total,
                    "open_tickets": campus_tickets.filter(status="open").count(),
                    "resolved_tickets": resolved,
                    "resolution_rate": round((resolved / total * 100) if total > 0 else 0, 1),
                    "avg_resolution_hours": calculate_avg_resolution_time(campus_tickets),
                    "sla_compliance": calculate_sla_compliance(campus_tickets),
                })
            campus_breakdown.sort(key=lambda x: x["total_tickets"], reverse=True)

            try:
                top_items = list(
                    Ticket.objects.filter(service_item__isnull=False)
                    .values(
                        "service_item__id",
                        "service_item__name",
                        "service_item__category__name",
                    )
                    .annotate(ticket_count=Count("id"))
                    .order_by("-ticket_count")[:10]
                )
                top_service_items = [
                    {
                        "id": row["service_item__id"],
                        "name": row["service_item__name"],
                        "category": row["service_item__category__name"] or "",
                        "ticket_count": row["ticket_count"],
                    }
                    for row in top_items
                ]
            except Exception:
                top_service_items = []

            busiest_sections = list(
                Ticket.objects.values(
                    "section__id",
                    "section__name",
                    "section__department__name",
                    "section__department__campus__code",
                    "section__department__campus__name",
                )
                .annotate(ticket_count=Count("id"))
                .order_by("-ticket_count")[:10]
            )
            sections_list = [
                {
                    "section": {
                        "id": s["section__id"],
                        "name": s["section__name"],
                        "campus_code": s["section__department__campus__code"] or "",
                        "display_name": (
                            f"{s['section__department__campus__code']}-{s['section__name']}"
                            if s["section__department__campus__code"]
                            else s["section__name"]
                        ),
                    },
                    "department": s["section__department__name"] or "",
                    "campus": s["section__department__campus__name"] or "",
                    "ticket_count": s["ticket_count"],
                }
                for s in busiest_sections
            ]

            raw_trend = get_ticket_trend_data(days=days, group_by="day")
            trend = [
                {
                    "date": (
                        row["period"].strftime("%Y-%m-%d")
                        if hasattr(row["period"], "strftime")
                        else str(row["period"])[:10]
                    ),
                    "count": row["count"],
                }
                for row in raw_trend
            ]

            return {
                "summary": AdminAnalytics.get_system_overview()["summary"],
                "campus_breakdown": campus_breakdown,
                "top_service_items": top_service_items,
                "busiest_sections": sections_list,
                "trend": trend,
            }

        return get_cached(f"analytics_org_{days}", compute)
