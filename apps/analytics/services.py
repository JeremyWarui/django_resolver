"""Analytics aggregation service — one core, role presets on top (SoT §5.4).

Single entry point: aggregate(scoped_qs, date_range, group_by).
Every role endpoint supplies (a) a scoped queryset from Phase 6 and
(b) a group_by dimension. Dashboard preset (overview) and deep-dive
endpoints call the SAME core — same scope+window yields identical numbers.
"""

from datetime import timedelta, datetime
from typing import Optional

from django.db.models import (
    Avg,
    Count,
    Exists,
    F,
    OuterRef,
    Q,
    Subquery,
)
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth, TruncQuarter
from django.utils import timezone

from apps.tickets.models import Ticket, TicketLog, TicketFeedback, TicketLocation

ACTIVE_STATUSES = ("open", "assigned", "in_progress", "pending")
TERMINAL_STATUSES = ("resolved", "closed")
AT_RISK_WINDOW = timedelta(hours=4)


# ── Date range ─────────────────────────────────────────────────────────────────


def resolve_date_range(params: dict) -> dict:
    """Parse date_from/date_to/days from query params.

    Returns {date_from, date_to, prior_from, prior_to} as timezone-aware datetimes.
    Default window = last 30 days.
    """
    now = timezone.now()
    date_from_param = params.get("date_from")
    date_to_param = params.get("date_to")
    days_param = params.get("days")

    if date_from_param and date_to_param:
        date_from = datetime.fromisoformat(str(date_from_param))
        date_to = datetime.fromisoformat(str(date_to_param))
        if not timezone.is_aware(date_from):
            date_from = timezone.make_aware(date_from)
        if not timezone.is_aware(date_to):
            date_to = timezone.make_aware(date_to)
    else:
        days = int(days_param) if days_param else 30
        date_to = now
        date_from = now - timedelta(days=days)

    window = date_to - date_from
    prior_to = date_from
    prior_from = prior_to - window

    return {
        "date_from": date_from,
        "date_to": date_to,
        "prior_from": prior_from,
        "prior_to": prior_to,
    }


# ── Percentile (Python-side, DB-agnostic) ─────────────────────────────────────


def _percentile(values: list, p: float) -> Optional[float]:
    """Linear interpolation p-th percentile. None if list is empty."""
    if not values:
        return None
    sorted_vals = sorted(v for v in values if v is not None)
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _delta(current, prior):
    """Trend delta vs prior window. None if either value is None."""
    if current is None or prior is None:
        return None
    return round(current - prior, 2)


# ── Group-by breakdowns ────────────────────────────────────────────────────────


def _group_by_section(window_qs):
    return list(
        window_qs.annotate(
            section_type_name=F("section__section_type__name"),
            campus_name=F("section__campus_department__campus__name"),
            campus_code=F("section__campus_department__campus__code"),
        )
        .values(
            "section_id",
            "section_type_name",
            "campus_name",
            "campus_code",
        )
        .annotate(
            total=Count("id"),
            open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            resolved_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            escalated_count=Count("id", filter=Q(current_level__in=["hos", "hod"])),
            resolution_sla_met=Count(
                "id",
                filter=Q(
                    status__in=TERMINAL_STATUSES,
                    resolved_at__isnull=False,
                    resolution_due_at__isnull=False,
                    resolved_at__lte=F("resolution_due_at"),
                ),
            ),
            total_resolved_with_due=Count(
                "id",
                filter=Q(status__in=TERMINAL_STATUSES, resolution_due_at__isnull=False),
            ),
        )
        .order_by("-total")
    )


def _group_by_campus(window_qs):
    return list(
        window_qs.values(
            campus_id=F("section__campus_department__campus__id"),
            campus_name=F("section__campus_department__campus__name"),
            campus_code=F("section__campus_department__campus__code"),
        )
        .annotate(
            total=Count("id"),
            open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            resolved_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            escalated_count=Count("id", filter=Q(current_level__in=["hos", "hod"])),
            resolution_sla_met=Count(
                "id",
                filter=Q(
                    status__in=TERMINAL_STATUSES,
                    resolved_at__isnull=False,
                    resolution_due_at__isnull=False,
                    resolved_at__lte=F("resolution_due_at"),
                ),
            ),
            total_resolved_with_due=Count(
                "id",
                filter=Q(status__in=TERMINAL_STATUSES, resolution_due_at__isnull=False),
            ),
        )
        .order_by("-total")
    )


def _group_by_campus_department(window_qs):
    return list(
        window_qs.values(
            cd_id=F("section__campus_department__id"),
            campus_name=F("section__campus_department__campus__name"),
            dept_name=F("section__campus_department__department__name"),
        )
        .annotate(
            total=Count("id"),
            open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            resolved_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            escalated_count=Count("id", filter=Q(current_level__in=["hos", "hod"])),
            resolution_sla_met=Count(
                "id",
                filter=Q(
                    status__in=TERMINAL_STATUSES,
                    resolved_at__isnull=False,
                    resolution_due_at__isnull=False,
                    resolved_at__lte=F("resolution_due_at"),
                ),
            ),
            total_resolved_with_due=Count(
                "id",
                filter=Q(status__in=TERMINAL_STATUSES, resolution_due_at__isnull=False),
            ),
        )
        .order_by("-total")
    )


def _group_by_technician(window_qs):
    return list(
        window_qs.filter(assigned_to__isnull=False)
        .values(
            technician_id=F("assigned_to__id"),
            username=F("assigned_to__username"),
            first_name=F("assigned_to__first_name"),
            last_name=F("assigned_to__last_name"),
        )
        .annotate(
            total_assigned=Count("id"),
            open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            resolved_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            escalated_count=Count("id", filter=Q(current_level__in=["hos", "hod"])),
        )
        .order_by("-open_count")
    )


def technician_load(scoped_qs):
    """Live open-ticket load per technician (no date window). One query.

    Standalone so the Performance endpoint can fetch it without running the full
    aggregate(); aggregate() reuses it for its headline `technician_load`.
    """
    return list(
        scoped_qs.filter(status__in=ACTIVE_STATUSES, assigned_to__isnull=False)
        .values(
            technician_id=F("assigned_to__id"),
            username=F("assigned_to__username"),
            first_name=F("assigned_to__first_name"),
            last_name=F("assigned_to__last_name"),
        )
        .annotate(open_count=Count("id"))
        .order_by("-open_count")
    )


# Generic group-by for the remaining dimensions — one helper, a field map, no
# per-dimension duplication. Each row: {key, label, + standard metric set}.
_GENERIC_GROUP_BY = {
    "department": (
        F("section__campus_department__department__id"),
        F("section__campus_department__department__name"),
    ),
    "section_type": (F("section__section_type__id"), F("section__section_type__name")),
    "service_category": (
        F("service_item__category__id"),
        F("service_item__category__name"),
    ),
    "service_item": (F("service_item__id"), F("service_item__name")),
    "priority": (F("priority__id"), F("priority__name")),
    "facility_type": (
        F("location__facility_type__id"),
        F("location__facility_type__name"),
    ),
    "facility": (F("location__facility__id"), F("location__facility__name")),
    "status": (F("status"), F("status")),
}


def _standard_breakdown_metrics():
    """The metric set shared by every breakdown dimension (SLA-aware)."""
    return dict(
        total=Count("id"),
        open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
        resolved_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
        escalated_count=Count("id", filter=Q(current_level__in=["hos", "hod"])),
        resolution_sla_met=Count(
            "id",
            filter=Q(
                status__in=TERMINAL_STATUSES,
                resolved_at__isnull=False,
                resolution_due_at__isnull=False,
                resolved_at__lte=F("resolution_due_at"),
            ),
        ),
        total_resolved_with_due=Count(
            "id",
            filter=Q(status__in=TERMINAL_STATUSES, resolution_due_at__isnull=False),
        ),
    )


def _group_by_generic(window_qs, dim):
    key_expr, label_expr = _GENERIC_GROUP_BY[dim]
    qs = window_qs
    if dim in ("facility_type", "facility"):
        qs = qs.filter(location__isnull=False)
    return list(
        qs.values(key=key_expr, label=label_expr)
        .annotate(**_standard_breakdown_metrics())
        .order_by("-total")
    )


def breakdown(scoped_qs, date_range: dict, group_by: str) -> list:
    """Compute ONLY the group-by breakdown, skipping the full headline metric set.

    Lightweight counterpart to aggregate() for endpoints that return just a
    breakdown (the Performance* views). aggregate() fires ~40 extra queries for
    the headline KPIs; against a remote DB that is the difference between one
    round-trip and dozens. The breakdown uses the same created_at window as
    aggregate(), so numbers match the full path exactly.
    """
    window_qs = scoped_qs.filter(
        created_at__gte=date_range["date_from"],
        created_at__lte=date_range["date_to"],
    )
    if group_by == "section":
        return _group_by_section(window_qs)
    if group_by == "campus":
        return _group_by_campus(window_qs)
    if group_by == "campus_department":
        return _group_by_campus_department(window_qs)
    if group_by == "technician":
        return _group_by_technician(window_qs)
    if group_by in _GENERIC_GROUP_BY:
        return _group_by_generic(window_qs, group_by)
    # 'time' (and anything unrecognised) needs the full path; rare for breakdown-only callers.
    return (
        aggregate(scoped_qs, date_range, group_by=group_by).get("breakdown", []) or []
    )


# ── Core aggregation ───────────────────────────────────────────────────────────

_TRUNC_FN = {
    "day": TruncDay,
    "week": TruncWeek,
    "month": TruncMonth,
    "quarter": TruncQuarter,
}


def aggregate(
    scoped_qs,
    date_range: dict,
    group_by: Optional[str] = None,
    granularity: str = "day",
) -> dict:
    """Core analytics aggregation.

    Args:
        scoped_qs:  Role-scoped Ticket queryset from Phase 6 resolver.
                    Never re-filters scope here.
        date_range: Dict from resolve_date_range().
        group_by:   Optional breakdown dimension. Bespoke shapes:
                    'section' | 'campus' | 'campus_department' | 'technician'.
                    Generic {key,label,+metrics} shapes: 'department' |
                    'section_type' | 'service_category' | 'service_item' |
                    'priority' | 'facility_type' | 'facility' | 'status'.
                    'time' returns the per-day flow_trend.

    Returns:
        Full metrics dict. Role endpoints slice what they expose to the client.
        The same scope+window yields identical numbers regardless of which
        endpoint calls this function (acceptance criterion §7 step 2).
    """
    date_from = date_range["date_from"]
    date_to = date_range["date_to"]
    prior_from = date_range["prior_from"]
    prior_to = date_range["prior_to"]
    now = timezone.now()

    # ── Window querysets ──────────────────────────────────────────────────────
    window_qs = scoped_qs.filter(created_at__gte=date_from, created_at__lte=date_to)
    prior_qs = scoped_qs.filter(created_at__gte=prior_from, created_at__lte=prior_to)

    # Resolved: resolved_at in window (independent of created_at window)
    resolved_qs = scoped_qs.filter(
        resolved_at__gte=date_from,
        resolved_at__lte=date_to,
        status__in=TERMINAL_STATUSES,
    )
    prior_resolved_qs = scoped_qs.filter(
        resolved_at__gte=prior_from,
        resolved_at__lte=prior_to,
        status__in=TERMINAL_STATUSES,
    )

    # ── Combined scalar counts ────────────────────────────────────────────────
    # One pass over scoped_qs with conditional FILTER aggregates replaces ~19
    # separate COUNT round-trips. Every predicate is on a direct Ticket column
    # (status, created_at, resolved_at, resolution_due_at, current_level,
    # assigned_to) — no fan-out joins — so the counts are independent and exact.
    _q_window = Q(created_at__gte=date_from, created_at__lte=date_to)
    _q_prior = Q(created_at__gte=prior_from, created_at__lte=prior_to)
    _q_resolved = Q(
        resolved_at__gte=date_from,
        resolved_at__lte=date_to,
        status__in=TERMINAL_STATUSES,
    )
    _q_prior_resolved = Q(
        resolved_at__gte=prior_from,
        resolved_at__lte=prior_to,
        status__in=TERMINAL_STATUSES,
    )
    _q_active = Q(status__in=ACTIVE_STATUSES)
    _q_resolved_due = _q_resolved & Q(resolution_due_at__isnull=False)
    _q_prior_resolved_due = _q_prior_resolved & Q(resolution_due_at__isnull=False)
    _q_met = Q(resolved_at__lte=F("resolution_due_at"))
    _q_escalated = Q(current_level__in=["hos", "hod"])
    counts = scoped_qs.aggregate(
        open_backlog=Count("id", filter=_q_active),
        created=Count("id", filter=_q_window),
        prior_created=Count("id", filter=_q_prior),
        resolved=Count("id", filter=_q_resolved),
        prior_resolved=Count("id", filter=_q_prior_resolved),
        resolution_sla_total=Count("id", filter=_q_resolved_due),
        resolution_sla_met=Count("id", filter=_q_resolved_due & _q_met),
        prior_resolution_sla_total=Count("id", filter=_q_prior_resolved_due),
        prior_resolution_sla_met=Count("id", filter=_q_prior_resolved_due & _q_met),
        at_risk=Count(
            "id",
            filter=_q_active
            & Q(
                resolution_due_at__isnull=False,
                resolution_due_at__gt=now,
                resolution_due_at__lte=now + AT_RISK_WINDOW,
            ),
        ),
        breached=Count(
            "id",
            filter=_q_active
            & Q(
                resolution_due_at__isnull=False,
                resolution_due_at__lt=now,
            ),
        ),
        escalated_window=Count("id", filter=_q_window & _q_escalated),
        escalated_live=Count("id", filter=_q_escalated),
        unassigned=Count("id", filter=_q_active & Q(assigned_to__isnull=True)),
        currently_paused=Count("id", filter=Q(status="pending")),
        age_lt_1d=Count(
            "id", filter=_q_active & Q(created_at__gt=now - timedelta(days=1))
        ),
        age_d1_3d=Count(
            "id",
            filter=_q_active
            & Q(
                created_at__lte=now - timedelta(days=1),
                created_at__gt=now - timedelta(days=3),
            ),
        ),
        age_d3_7d=Count(
            "id",
            filter=_q_active
            & Q(
                created_at__lte=now - timedelta(days=3),
                created_at__gt=now - timedelta(days=7),
            ),
        ),
        age_gt_7d=Count(
            "id", filter=_q_active & Q(created_at__lte=now - timedelta(days=7))
        ),
    )

    # ── Volume/flow ───────────────────────────────────────────────────────────
    open_backlog = counts["open_backlog"]
    created = counts["created"]
    prior_created = counts["prior_created"]
    resolved = counts["resolved"]
    prior_resolved = counts["prior_resolved"]
    net_flow = created - resolved

    status_dist = list(
        window_qs.values("status").annotate(count=Count("id")).order_by("-count")
    )
    priority_dist = list(
        window_qs.values(name=F("priority__name"))
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Flow trend — created vs resolved bucketed by granularity (day/week/month)
    trunc_fn = _TRUNC_FN.get(granularity, TruncDay)
    created_by_period = {
        row["period"].date().isoformat(): row["count"]
        for row in window_qs.annotate(period=trunc_fn("created_at"))
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    }
    resolved_by_period = {
        row["period"].date().isoformat(): row["count"]
        for row in scoped_qs.filter(
            resolved_at__gte=date_from,
            resolved_at__lte=date_to,
            status__in=TERMINAL_STATUSES,
        )
        .annotate(period=trunc_fn("resolved_at"))
        .values("period")
        .annotate(count=Count("id"))
        .order_by("period")
    }
    all_periods = sorted(
        set(list(created_by_period.keys()) + list(resolved_by_period.keys()))
    )
    flow_trend = [
        {
            "date": d,
            "created": created_by_period.get(d, 0),
            "resolved": resolved_by_period.get(d, 0),
            "net": created_by_period.get(d, 0) - resolved_by_period.get(d, 0),
        }
        for d in all_periods
    ]

    # ── SLA timeliness ────────────────────────────────────────────────────────

    # Resolution SLA: use shifted resolution_due_at (R9 — already accounts for pause)
    resolution_sla_total = counts["resolution_sla_total"]
    resolution_sla_met = counts["resolution_sla_met"]
    resolution_sla_pct = (
        round(resolution_sla_met / resolution_sla_total * 100, 1)
        if resolution_sla_total
        else None
    )

    prior_resolution_sla_total = counts["prior_resolution_sla_total"]
    prior_resolution_sla_met = counts["prior_resolution_sla_met"]
    prior_resolution_sla_pct = (
        round(prior_resolution_sla_met / prior_resolution_sla_total * 100, 1)
        if prior_resolution_sla_total
        else None
    )

    # Response SLA: first TicketLog action (assigned / status_changed / resolved /
    # closed / escalated / priority_changed) vs response_due_at.
    # Subquery fetches the earliest matching log's created_at.
    first_response_sq = (
        TicketLog.objects.filter(
            ticket=OuterRef("pk"),
            event_type__in=[
                "assigned",
                "status_changed",
                "resolved",
                "closed",
                "escalated",
                "priority_changed",
            ],
        )
        .order_by("created_at")
        .values("created_at")[:1]
    )

    # total + met in one pass (FILTER over the Subquery-annotated first_response_at).
    _q_has_response = Q(first_response_at__isnull=False, response_due_at__isnull=False)
    annotated_window = window_qs.annotate(first_response_at=Subquery(first_response_sq))
    _resp = annotated_window.aggregate(
        total=Count("id", filter=_q_has_response),
        met=Count(
            "id",
            filter=_q_has_response & Q(first_response_at__lte=F("response_due_at")),
        ),
    )
    response_sla_total = _resp["total"]
    response_sla_met = _resp["met"]
    response_sla_pct = (
        round(response_sla_met / response_sla_total * 100, 1)
        if response_sla_total
        else None
    )

    prior_window_qs = scoped_qs.filter(
        created_at__gte=prior_from, created_at__lte=prior_to
    )
    prior_annotated = prior_window_qs.annotate(
        first_response_at=Subquery(first_response_sq)
    )
    _prior_resp = prior_annotated.aggregate(
        total=Count("id", filter=_q_has_response),
        met=Count(
            "id",
            filter=_q_has_response & Q(first_response_at__lte=F("response_due_at")),
        ),
    )
    prior_response_sla_total = _prior_resp["total"]
    prior_response_sla_met = _prior_resp["met"]
    prior_response_sla_pct = (
        round(prior_response_sla_met / prior_response_sla_total * 100, 1)
        if prior_response_sla_total
        else None
    )

    # p50/p90 resolution time: resolved_at − created_at − accumulated_pause
    resolution_time_rows = list(
        resolved_qs.filter(resolved_at__isnull=False).values_list(
            "resolved_at", "created_at", "accumulated_pause"
        )
    )
    resolution_seconds = [
        (
            (resolved_at - created_at) - (accumulated_pause or timedelta())
        ).total_seconds()
        for resolved_at, created_at, accumulated_pause in resolution_time_rows
        if resolved_at and created_at
    ]
    resolution_p50 = _percentile(resolution_seconds, 50)
    resolution_p90 = _percentile(resolution_seconds, 90)

    # p50/p90 first-response time
    first_response_pairs = list(
        annotated_window.filter(first_response_at__isnull=False).values_list(
            "first_response_at", "created_at"
        )
    )
    first_response_seconds = [
        (fr - ca).total_seconds() for fr, ca in first_response_pairs if fr and ca
    ]
    first_response_p50 = _percentile(first_response_seconds, 50)
    first_response_p90 = _percentile(first_response_seconds, 90)

    # At-risk and breached (live — no date filter, from scoped_qs)
    at_risk = counts["at_risk"]
    breached = counts["breached"]

    # ── Workload / escalation ─────────────────────────────────────────────────
    escalated_count = counts["escalated_window"]
    escalation_rate = round(escalated_count / created * 100, 1) if created else None

    reassigned_qs = window_qs.annotate(
        has_reassignment=Exists(
            TicketLog.objects.filter(ticket=OuterRef("pk"), event_type="reassigned")
        )
    )
    reassigned_tickets = reassigned_qs.filter(has_reassignment=True).count()
    reassignment_rate = (
        round(reassigned_tickets / created * 100, 1) if created else None
    )

    # Open load per technician (no date filter — live snapshot)
    tech_load = technician_load(scoped_qs)

    # ── Quality ───────────────────────────────────────────────────────────────
    csat_agg = TicketFeedback.objects.filter(ticket__in=resolved_qs).aggregate(
        avg=Avg("rating"),
        count=Count("id"),
        satisfied=Count("id", filter=Q(rating__gte=4)),
    )
    csat = round(float(csat_agg["avg"]), 2) if csat_agg["avg"] else None
    feedback_count = csat_agg["count"] or 0
    feedback_response_rate = (
        round(feedback_count / resolved * 100, 1) if resolved else None
    )

    reopen_sq = TicketLog.objects.filter(ticket=OuterRef("pk"), event_type="reopened")
    reopen_count = (
        resolved_qs.annotate(was_reopened=Exists(reopen_sq))
        .filter(was_reopened=True)
        .count()
    )
    reopen_rate = round(reopen_count / resolved * 100, 1) if resolved else None

    # Prior quality
    prior_csat_agg = TicketFeedback.objects.filter(
        ticket__in=prior_resolved_qs
    ).aggregate(avg=Avg("rating"), count=Count("id"))
    prior_csat = (
        round(float(prior_csat_agg["avg"]), 2) if prior_csat_agg["avg"] else None
    )
    prior_reopen_count = (
        prior_resolved_qs.annotate(
            was_reopened=Exists(
                TicketLog.objects.filter(ticket=OuterRef("pk"), event_type="reopened")
            )
        )
        .filter(was_reopened=True)
        .count()
    )
    prior_reopen_rate = (
        round(prior_reopen_count / prior_resolved * 100, 1) if prior_resolved else None
    )

    # ── Demand shape ──────────────────────────────────────────────────────────
    demand_by_category = list(
        window_qs.values(
            category_id=F("service_item__category__id"),
            category_name=F("service_item__category__name"),
        )
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    demand_by_section_type = list(
        window_qs.values(
            section_type_id=F("section__section_type__id"),
            section_type_name=F("section__section_type__name"),
        )
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    demand_by_campus = list(
        window_qs.values(
            campus_id=F("section__campus_department__campus__id"),
            campus_name=F("section__campus_department__campus__name"),
            campus_code=F("section__campus_department__campus__code"),
        )
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    demand_by_facility_type = list(
        window_qs.filter(location__isnull=False)
        .values(
            facility_type_id=F("location__facility_type__id"),
            facility_type_name=F("location__facility_type__name"),
        )
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Live status distribution — ALL scoped tickets by current status (not windowed).
    # Used by stat cards that need current state counts, not just the selected window.
    live_status_dist = list(
        scoped_qs.values("status").annotate(count=Count("id")).order_by("-count")
    )

    # ── Capacity / triage signals (live snapshot) ─────────────────────────────
    unassigned = counts["unassigned"]

    # Aging buckets for currently-open tickets (decision: what's getting stale).
    aging_buckets = {
        "lt_1d": counts["age_lt_1d"],
        "d1_3d": counts["age_d1_3d"],
        "d3_7d": counts["age_d3_7d"],
        "gt_7d": counts["age_gt_7d"],
    }

    # ── Pause burden (the "stuck waiting" signal) ─────────────────────────────
    # Duration reduced in Python for SQLite/Postgres portability (DurationField).
    pause_secs = [
        (p.total_seconds() if p else 0)
        for p in window_qs.values_list("accumulated_pause", flat=True)
    ]
    pause_total_seconds = sum(pause_secs)
    ever_paused_count = sum(1 for s in pause_secs if s > 0)
    pause_avg_seconds = (
        round(pause_total_seconds / ever_paused_count, 1) if ever_paused_count else None
    )
    currently_paused = counts["currently_paused"]

    # ── CSAT distribution (mean alone hides the shape) ────────────────────────
    feedback_qs = TicketFeedback.objects.filter(ticket__in=resolved_qs)
    rating_histogram = list(
        feedback_qs.values("rating").annotate(count=Count("id")).order_by("rating")
    )
    satisfied_count = csat_agg["satisfied"] or 0
    csat_satisfied_pct = (
        round(satisfied_count / feedback_count * 100, 1) if feedback_count else None
    )

    # ── Ticket flow by status variant (drives the stacked HOD/HOS chart) ──────
    _flow_counts = {row["status"]: row["count"] for row in live_status_dist}
    ticket_flow = {
        "total": sum(_flow_counts.values()),
        "open": _flow_counts.get("open", 0),
        "assigned": _flow_counts.get("assigned", 0),
        "in_progress": _flow_counts.get("in_progress", 0),
        "pending": _flow_counts.get("pending", 0),
        "resolved": _flow_counts.get("resolved", 0),
        "closed": _flow_counts.get("closed", 0),
        "escalated": counts["escalated_live"],
    }

    # ── Optional group-by breakdown ───────────────────────────────────────────
    breakdown = None
    if group_by == "section":
        breakdown = _group_by_section(window_qs)
    elif group_by == "campus":
        breakdown = _group_by_campus(window_qs)
    elif group_by == "campus_department":
        breakdown = _group_by_campus_department(window_qs)
    elif group_by == "technician":
        breakdown = _group_by_technician(window_qs)
    elif group_by == "time":
        breakdown = flow_trend
    elif group_by in _GENERIC_GROUP_BY:
        breakdown = _group_by_generic(window_qs, group_by)

    result = {
        # Volume & flow
        "open_backlog": open_backlog,
        "created": created,
        "resolved": resolved,
        "net_flow": net_flow,
        "flow_trend": flow_trend,
        "status_distribution": status_dist,
        "priority_distribution": priority_dist,
        "live_status_distribution": live_status_dist,
        # Timeliness
        "resolution_sla_pct": resolution_sla_pct,
        "response_sla_pct": response_sla_pct,
        "resolution_time_p50_seconds": resolution_p50,
        "resolution_time_p90_seconds": resolution_p90,
        "first_response_p50_seconds": first_response_p50,
        "first_response_p90_seconds": first_response_p90,
        "at_risk": at_risk,
        "breached": breached,
        # Workload / capacity
        "escalation_rate": escalation_rate,
        "escalated_count": escalated_count,
        "reassignment_rate": reassignment_rate,
        "technician_load": tech_load,
        "unassigned": unassigned,
        "aging_buckets": aging_buckets,
        # Pause burden
        "pause_total_seconds": pause_total_seconds,
        "pause_avg_seconds": pause_avg_seconds,
        "ever_paused_count": ever_paused_count,
        "currently_paused": currently_paused,
        # Ticket flow (status variants — stacked chart)
        "ticket_flow": ticket_flow,
        # Quality
        "csat": csat,
        "feedback_response_rate": feedback_response_rate,
        "reopen_rate": reopen_rate,
        "csat_satisfied_pct": csat_satisfied_pct,
        "rating_histogram": rating_histogram,
        # Demand
        "demand": {
            "by_category": demand_by_category,
            "by_section_type": demand_by_section_type,
            "by_campus": demand_by_campus,
            "by_facility_type": demand_by_facility_type,
        },
        # Deltas vs prior window
        "delta": {
            "created": _delta(created, prior_created),
            "resolved": _delta(resolved, prior_resolved),
            "resolution_sla_pct": _delta(resolution_sla_pct, prior_resolution_sla_pct),
            "response_sla_pct": _delta(response_sla_pct, prior_response_sla_pct),
            "csat": _delta(csat, prior_csat),
            "reopen_rate": _delta(reopen_rate, prior_reopen_rate),
        },
    }

    if breakdown is not None:
        result["breakdown"] = breakdown

    return result


# ── Admin config-health signals ───────────────────────────────────────────────


def config_health() -> dict:
    """Org-wide config-health signals for the admin overview (SoT §5.4).

    Returns counts and lists of misconfigured objects that need attention.
    Only called when role == 'admin'.
    """
    from apps.org.models import Section
    from apps.sla.models import Priority
    from apps.facilities.models import FacilityType
    from django.db.models import Count

    sections_without_hos = list(
        Section.objects.filter(hos__isnull=True, is_active=True).values(
            "id",
            campus_name=F("campus_department__campus__name"),
            dept_name=F("campus_department__department__name"),
            section_type_name=F("section_type__name"),
        )
    )

    priorities_without_rules = list(
        Priority.objects.annotate(rule_count=Count("escalation_rules"))
        .filter(rule_count=0)
        .values("id", "name", "rank")
    )

    used_ft_ids = TicketLocation.objects.values_list(
        "facility_type_id", flat=True
    ).distinct()
    unused_facility_types = list(
        FacilityType.objects.exclude(id__in=used_ft_ids).values("id", "name", "code")
    )

    return {
        "sections_without_hos": sections_without_hos,
        "sections_without_hos_count": len(sections_without_hos),
        "priorities_without_escalation_rules": priorities_without_rules,
        "priorities_without_escalation_rules_count": len(priorities_without_rules),
        "unused_facility_types": unused_facility_types,
        "unused_facility_types_count": len(unused_facility_types),
    }
