"""Admin analytics - system-wide metrics for administrators."""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Avg, Count, ExpressionWrapper, F, Q, DurationField

from tickets.models import Ticket, CustomUser

ANALYTICS_CACHE_TTL = 300


class AdminAnalytics:

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
            "summary": {
                "total_tickets": total,
                "open_tickets": counts["open"] or 0,
                "resolved_tickets": resolved,
                "new_24h": counts["new_24h"] or 0,
                "past_7_days": counts["past_week"] or 0,
                "past_30_days": counts["past_month"] or 0,
                "avg_resolution_time_hours": avg_resolution_hours,
            },
            "users": {
                "total_users": CustomUser.objects.filter(is_active=True).count(),
                "technicians": CustomUser.objects.filter(
                    role="technician", is_active=True
                ).count(),
                "managers": CustomUser.objects.filter(
                    role="manager", is_active=True
                ).count(),
                "admins": CustomUser.objects.filter(
                    role="admin", is_active=True
                ).count(),
            },
            "resolution_rate": round(
                (resolved / total * 100) if total > 0 else 0, 2
            ),
        }
        cache.set("analytics_admin_overview", result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_overdue_tickets():
        cached = cache.get("analytics_admin_overdue")
        if cached is not None:
            return cached

        threshold = timezone.now() - timedelta(days=7)
        overdue = (
            Ticket.objects.filter(
                created_at__lt=threshold,
                status__in=["open", "assigned", "in_progress", "pending"],
            )
            .select_related("section", "facility", "assigned_to")
            .annotate(
                age_hours=ExpressionWrapper(
                    timezone.now() - F("created_at"), output_field=DurationField()
                )
            )
            .order_by("created_at")
        )

        result = {
            "count": overdue.count(),
            "tickets": [
                {
                    "id": t.id,
                    "ticket_no": t.ticket_no,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "section": t.section.name,
                    "facility": t.facility.name if t.facility else None,
                    "assigned_to": t.assigned_to.username if t.assigned_to else None,
                    "age_hours": round(t.age_hours.total_seconds() / 3600, 2),
                    "days_old": (timezone.now() - t.created_at).days,
                    "created_at": t.created_at.isoformat(),
                }
                for t in overdue[:50]
            ],
        }
        cache.set("analytics_admin_overdue", result, ANALYTICS_CACHE_TTL)
        return result
