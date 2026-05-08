"""Base analytics utilities shared across role-specific dashboards."""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import (
    Count, Avg, Q, F, ExpressionWrapper, DurationField, FloatField, Prefetch,
)
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from typing import Dict, List, Optional

from tickets.models import Ticket, Section

ANALYTICS_CACHE_TTL = 300  # 5 minutes
OVERDUE_THRESHOLD_DAYS = 7


def count_overdue(tickets_qs) -> int:
    """Count tickets that have breached the overdue threshold."""
    cutoff = timezone.now() - timedelta(days=OVERDUE_THRESHOLD_DAYS)
    return tickets_qs.filter(
        created_at__lt=cutoff,
        status__in=["open", "assigned", "in_progress", "pending", "escalated"],
    ).count()


def get_status_distribution(tickets_qs) -> list:
    """Return ticket counts grouped by status, ordered by count descending."""
    return list(
        tickets_qs.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )


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
    Returns:
        List of performance dicts sorted by total_assigned descending.
    """
    resolved_statuses = ["resolved", "closed"]
    open_statuses = ["open", "assigned", "in_progress"]

    # Single aggregation query — replaces 4 per-tech queries with one
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

    # Single prefetch query for scoped sections when requested
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
