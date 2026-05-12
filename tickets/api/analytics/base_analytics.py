"""Base analytics utilities shared across role-specific dashboards."""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import (
    Count, Avg, Q, F, ExpressionWrapper, DurationField, Prefetch,
)
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from typing import Dict, List

from tickets.models import Ticket, Section

ANALYTICS_CACHE_TTL = 300  # 5 minutes
OVERDUE_THRESHOLD_DAYS = 7
OVERDUE_STATUSES = ["open", "assigned", "in_progress", "pending", "escalated"]


def get_cached(key: str, compute_fn, ttl: int = ANALYTICS_CACHE_TTL):
    """Return cached value if present, otherwise compute, cache, and return."""
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = compute_fn()
    cache.set(key, result, ttl)
    return result


def count_overdue(tickets_qs) -> int:
    """Count tickets that have breached the overdue threshold."""
    cutoff = timezone.now() - timedelta(days=OVERDUE_THRESHOLD_DAYS)
    return tickets_qs.filter(
        created_at__lt=cutoff,
        status__in=OVERDUE_STATUSES,
    ).count()


def get_status_distribution(tickets_qs, order_by="-count") -> list:
    """Return ticket counts grouped by status."""
    return list(
        tickets_qs.values("status")
        .annotate(count=Count("id"))
        .order_by(order_by)
    )


def calculate_avg_resolution_time(tickets_queryset) -> float:
    """Calculate average resolution time in hours using resolved_at - created_at."""
    resolved_tickets = tickets_queryset.filter(status__in=["resolved", "closed"])
    if not resolved_tickets.exists():
        return 0.0
    avg_duration = resolved_tickets.annotate(
        resolution_time=ExpressionWrapper(
            F("resolved_at") - F("created_at"), output_field=DurationField()
        )
    ).aggregate(avg=Avg("resolution_time"))["avg"]
    return (avg_duration.total_seconds() / 3600) if avg_duration else 0.0


def calculate_sla_compliance(tickets_queryset) -> float:
    """Calculate SLA compliance percentage."""
    total = tickets_queryset.count()
    if total == 0:
        return 0.0
    sla_cutoff = timezone.now() - timedelta(days=OVERDUE_THRESHOLD_DAYS)
    overdue_count = tickets_queryset.filter(
        created_at__lt=sla_cutoff,
        status__in=OVERDUE_STATUSES,
    ).count()
    return round(((total - overdue_count) / total) * 100, 2)


def build_overview(tickets_qs) -> dict:
    """Standard overview block used by all role dashboards."""
    return {
        "total_tickets": tickets_qs.count(),
        "open_tickets": tickets_qs.filter(status__in=["open", "assigned"]).count(),
        "overdue_tickets": count_overdue(tickets_qs),
        "escalated_tickets": tickets_qs.filter(escalation_level__gt=0).count(),
        "avg_resolution_hours": calculate_avg_resolution_time(tickets_qs),
        "sla_compliance": calculate_sla_compliance(tickets_qs),
    }


def build_scope_stats(tickets_qs) -> dict:
    """Per-scope (section/campus) ticket stats used in breakdown lists."""
    return {
        "total_tickets": tickets_qs.count(),
        "open_tickets": tickets_qs.filter(status__in=["open", "assigned"]).count(),
        "escalated_tickets": tickets_qs.filter(escalation_level__gt=0).count(),
        "avg_resolution_hours": calculate_avg_resolution_time(tickets_qs),
        "sla_compliance": calculate_sla_compliance(tickets_qs),
    }


def get_ticket_trend_data(days=30, group_by="day") -> list:
    """Ticket creation trend over time; shared by admin org analytics and TicketAnalytics."""
    time_threshold = timezone.now() - timedelta(days=days)
    trunc_map = {
        "week": TruncWeek("created_at"),
        "month": TruncMonth("created_at"),
    }
    trunc_func = trunc_map.get(group_by, TruncDay("created_at"))
    return list(
        Ticket.objects.filter(created_at__gte=time_threshold)
        .annotate(period=trunc_func)
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    )


def build_technician_performance(
    all_tickets, technicians, section_filter=None
) -> List[Dict]:
    """Build technician performance stats using bulk aggregation (avoids N+1).

    Args:
        all_tickets: Ticket queryset already scoped to the caller's context.
        technicians: CustomUser queryset of technicians to include.
        section_filter: Optional Q object to filter which sections appear in
                        each technician's 'sections' list (e.g. Q(department=dept)).
                        If None, 'sections' is omitted from the output.
    """
    resolved_statuses = ["resolved", "closed"]
    open_statuses = ["open", "assigned", "in_progress"]

    stats = {
        row["assigned_to_id"]: row
        for row in all_tickets.filter(assigned_to__in=technicians)
        .annotate(
            resolution_time=ExpressionWrapper(
                F("resolved_at") - F("created_at"), output_field=DurationField()
            )
        )
        .values("assigned_to_id")
        .annotate(
            total_assigned=Count("id"),
            resolved=Count("id", filter=Q(status__in=resolved_statuses)),
            open=Count("id", filter=Q(status__in=open_statuses)),
            escalation_count=Count("id", filter=Q(escalation_level__gt=0)),
            avg_resolution_seconds=Avg(
                "resolution_time",
                filter=Q(status__in=resolved_statuses, resolved_at__isnull=False),
            ),
        )
    }

    if section_filter is not None:
        tech_qs = technicians.prefetch_related(
            Prefetch(
                "sections",
                queryset=Section.objects.filter(section_filter),
                to_attr="_scoped_sections",
            )
        )
    else:
        tech_qs = technicians

    result = []
    for tech in tech_qs:
        s = stats.get(tech.id, {})
        avg_secs = s.get("avg_resolution_seconds")
        entry = {
            "technician": {
                "id": tech.id,
                "name": f"{tech.first_name} {tech.last_name}".strip() or tech.username,
                "username": tech.username,
            },
            "total_assigned": s.get("total_assigned", 0),
            "resolved": s.get("resolved", 0),
            "open": s.get("open", 0),
            "avg_resolution_hours": (
                round(avg_secs.total_seconds() / 3600, 2) if avg_secs else 0.0
            ),
            "escalation_count": s.get("escalation_count", 0),
        }
        if section_filter is not None:
            entry["technician"]["sections"] = [
                sec.name for sec in tech._scoped_sections
            ]
        result.append(entry)

    return sorted(result, key=lambda x: x["total_assigned"], reverse=True)


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
