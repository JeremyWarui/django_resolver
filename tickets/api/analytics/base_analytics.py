"""Base analytics utilities shared across all role-specific dashboards.

Exports used by every analytics module
──────────────────────────────────────
Constants:
    ACTIVE_STATUSES      tuple of non-terminal status values
    TERMINAL_STATUSES    tuple of resolved/closed statuses
    SLA_WINDOW_HOURS     default SLA target in hours (24)
    OVERDUE_THRESHOLD_DAYS  legacy overdue threshold (7 days)
    OVERDUE_STATUSES     alias for ACTIVE_STATUSES (kept for compat)

Helpers:
    sla_pct(within, total_resolved) -> float
    avg_hours(avg_duration)         -> float
    ticket_scope_annotations()      -> dict  (standard GROUP BY annotation set)

Queries:
    get_cached(key, fn, ttl)
    get_status_distribution(qs)
    get_ticket_trend_data(days, group_by)
    get_escalation_trends(qs, days)
    build_technician_performance(tickets_qs, technicians, section_filter)
    count_overdue(qs)
"""

from datetime import timedelta
from typing import Dict, List

from django.core.cache import cache
from django.db.models import (
    Avg, Count, DurationField, ExpressionWrapper, F, Prefetch, Q,
)
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.utils import timezone

from tickets.models import Ticket, Section

# ── Status groups ──────────────────────────────────────────────────────────────

ACTIVE_STATUSES = ("open", "assigned", "in_progress", "pending", "escalated")
TERMINAL_STATUSES = ("resolved", "closed")
SLA_WINDOW_HOURS = 24

# Legacy aliases (kept so existing callers don't break)
OVERDUE_THRESHOLD_DAYS = 7
OVERDUE_STATUSES = list(ACTIVE_STATUSES)
ANALYTICS_CACHE_TTL = 300  # 5 minutes — used as default in get_cached


# ── Scalar helpers ─────────────────────────────────────────────────────────────

def sla_pct(within: int, total_resolved: int) -> float:
    """Percentage of resolved tickets that met the SLA window. Zero-safe."""
    if not total_resolved:
        return 0.0
    return round(within / total_resolved * 100, 1)


def avg_hours(avg_duration) -> float:
    """Convert a Django Avg(DurationField) result to float hours. None-safe."""
    if not avg_duration:
        return 0.0
    return round(avg_duration.total_seconds() / 3600, 2)


# ── Shared annotation factory ──────────────────────────────────────────────────

def ticket_scope_annotations() -> dict:
    """
    Standard ORM annotation set for GROUP BY breakdowns used by all roles.

    Returns a dict suitable for `.annotate(**ticket_scope_annotations())`.

    Computes in one database pass:
      total, open_count, closed_count, pending_count, escalated_count,
      resolved_within_24h, total_resolved, avg_resolution_duration.

    Callers extract scalars with `sla_pct()` and `avg_hours()`:
        row["sla_24h_pct"] = sla_pct(row["resolved_within_24h"], row["total_resolved"])
        row["avg_resolution_hours"] = avg_hours(row["avg_resolution_duration"])
    """
    return dict(
        total=Count("id"),
        open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
        closed_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
        pending_count=Count("id", filter=Q(status="pending")),
        escalated_count=Count("id", filter=Q(escalation_level__gt=0)),
        resolved_within_24h=Count(
            "id",
            filter=Q(
                status__in=TERMINAL_STATUSES,
                resolved_at__isnull=False,
                # Database-level arithmetic: resolved_at ≤ created_at + 24 h
                resolved_at__lte=F("created_at") + timedelta(hours=SLA_WINDOW_HOURS),
            ),
        ),
        total_resolved=Count(
            "id",
            filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
        ),
        avg_resolution_duration=Avg(
            ExpressionWrapper(
                F("resolved_at") - F("created_at"),
                output_field=DurationField(),
            ),
            filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
        ),
    )


# ── Cache ──────────────────────────────────────────────────────────────────────

def get_cached(key: str, compute_fn, ttl: int = ANALYTICS_CACHE_TTL):
    """Return cached value if present; otherwise compute, cache, and return."""
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = compute_fn()
    cache.set(key, result, ttl)
    return result


# ── Status distribution ────────────────────────────────────────────────────────

def get_status_distribution(tickets_qs, order_by: str = "-count") -> list:
    """Ticket counts grouped by status value, ordered by `order_by`."""
    return list(
        tickets_qs.values("status")
        .annotate(count=Count("id"))
        .order_by(order_by)
    )


# ── Overdue count ──────────────────────────────────────────────────────────────

def count_overdue(tickets_qs) -> int:
    """Count active tickets older than OVERDUE_THRESHOLD_DAYS."""
    cutoff = timezone.now() - timedelta(days=OVERDUE_THRESHOLD_DAYS)
    return tickets_qs.filter(
        created_at__lt=cutoff,
        status__in=OVERDUE_STATUSES,
    ).count()


# ── Trend data ─────────────────────────────────────────────────────────────────

def get_ticket_trend_data(days: int = 30, group_by: str = "day") -> list:
    """Ticket creation counts grouped by day/week/month over the last `days` days."""
    since = timezone.now() - timedelta(days=days)
    trunc_map = {
        "week": TruncWeek("created_at"),
        "month": TruncMonth("created_at"),
    }
    trunc_func = trunc_map.get(group_by, TruncDay("created_at"))
    cache_key = f"analytics_trend_{days}_{group_by}"
    return get_cached(
        cache_key,
        lambda: list(
            Ticket.objects.filter(created_at__gte=since)
            .annotate(period=trunc_func)
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        ),
    )


# ── Escalation trends ──────────────────────────────────────────────────────────

def get_escalation_trends(tickets_qs, days: int = 30) -> Dict:
    """Escalation counts over the last `days` days from `tickets_qs`."""
    since = timezone.now() - timedelta(days=days)
    recent = tickets_qs.filter(escalated_at__gte=since)
    return {
        "total_escalations": recent.count(),
        "by_level": dict(
            recent.values("escalation_level")
            .annotate(count=Count("id"))
            .values_list("escalation_level", "count")
        ),
        "avg_level": recent.aggregate(avg=Avg("escalation_level"))["avg"] or 0,
    }


# ── Technician performance (bulk, no N+1) ─────────────────────────────────────

def build_technician_performance(
    all_tickets,
    technicians,
    section_filter=None,
) -> List[Dict]:
    """
    Build technician performance stats using one GROUP BY query.

    Args:
        all_tickets:    Ticket queryset scoped to the caller's context.
        technicians:    CustomUser queryset of technicians to include.
        section_filter: Optional Q object to narrow which sections appear
                        in each technician's output (e.g. Q(campus_department=cd)).
                        If None, 'sections' is omitted from the output.

    Returns a list sorted by total_assigned descending.
    """
    stats = {
        row["assigned_to_id"]: row
        for row in (
            all_tickets.filter(assigned_to__in=technicians)
            .values("assigned_to_id")
            .annotate(
                total_assigned=Count("id"),
                resolved=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
                open=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
                escalation_count=Count("id", filter=Q(escalation_level__gt=0)),
                avg_resolution_duration=Avg(
                    ExpressionWrapper(
                        F("resolved_at") - F("created_at"),
                        output_field=DurationField(),
                    ),
                    filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
                ),
            )
        )
    }

    tech_qs = (
        technicians.prefetch_related(
            Prefetch(
                "sections",
                queryset=Section.objects.filter(section_filter),
                to_attr="_scoped_sections",
            )
        )
        if section_filter is not None
        else technicians
    )

    result = []
    for tech in tech_qs:
        s = stats.get(tech.id, {})
        entry = {
            "technician": {
                "id": tech.id,
                "username": tech.username,
                "name": f"{tech.first_name} {tech.last_name}".strip() or tech.username,
            },
            "total_assigned": s.get("total_assigned", 0),
            "resolved": s.get("resolved", 0),
            "open": s.get("open", 0),
            "escalation_count": s.get("escalation_count", 0),
            "avg_resolution_hours": avg_hours(s.get("avg_resolution_duration")),
        }
        if section_filter is not None:
            entry["technician"]["sections"] = [
                sec.name for sec in tech._scoped_sections
            ]
        result.append(entry)

    return sorted(result, key=lambda x: x["total_assigned"], reverse=True)
