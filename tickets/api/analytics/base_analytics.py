"""Base analytics utilities shared across role-specific dashboards."""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import (
    Count, Avg, Q, F, ExpressionWrapper, DurationField, FloatField,
)
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from typing import Dict

from tickets.models import Ticket

ANALYTICS_CACHE_TTL = 300  # 5 minutes


def calculate_avg_resolution_time(tickets_queryset) -> float:
    """Calculate average resolution time in hours."""
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


def calculate_sla_compliance(tickets_queryset) -> float:
    """Calculate SLA compliance percentage."""
    total = tickets_queryset.count()
    if total == 0:
        return 0.0
    sla_cutoff = timezone.now() - timedelta(days=7)
    overdue_count = tickets_queryset.filter(
        created_at__lt=sla_cutoff,
        status__in=["open", "assigned", "in_progress", "pending", "escalated"],
    ).count()
    return round(((total - overdue_count) / total) * 100, 2)


def get_escalation_trends(tickets_queryset, days: int = 30) -> Dict:
    """Get escalation trends over specified period."""
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
