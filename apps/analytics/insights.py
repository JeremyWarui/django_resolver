"""Insights layer — turns the scoped analytics data into decisions (SoT §5.4).

Heavier, prescriptive computations kept separate from the headline `aggregate()`
core. Fed the SAME role-scoped queryset, so insights never widen scope. Each
function is defensive: it returns [] when there isn't enough data to say
something useful (low-scope roles legitimately produce few/no insights).

All computations are DB-agnostic (no Postgres-only SQL; DurationField math is
reduced in Python) so SQLite tests and Postgres prod agree.
"""

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, F
from django.utils import timezone

from apps.analytics.services import ACTIVE_STATUSES, TERMINAL_STATUSES, _percentile
from apps.tickets.models import TicketFeedback

# Tuning knobs (kept here so they're easy to find / adjust).
RECURRING_FAULT_MIN = 3          # occurrences of (facility, service_item) to flag
BOTTLENECK_MULTIPLE = 2.0        # outlier = >= N× the peer median
CSAT_DRIVER_MIN_SAMPLE = 6       # need at least this many rated tickets
CSAT_DRIVER_GAP = 1.0            # rating points drop to flag speed as a driver


def compute_insights(scoped_qs, date_range, enabled_types=None):
    """Return a list of insight dicts. `enabled_types` (from ROLE_VIEWS) filters
    which insight families run; None = run all."""
    enabled = set(enabled_types) if enabled_types is not None else None

    def want(t):
        return enabled is None or t in enabled

    insights = []
    if want("recurring_fault"):
        insights += _recurring_fault(scoped_qs, date_range)
    if want("bottleneck"):
        insights += _bottleneck(scoped_qs, date_range)
    if want("sla_leak"):
        insights += _sla_leak(scoped_qs)
    if want("capacity"):
        insights += _capacity(scoped_qs, date_range)
    if want("csat_driver"):
        insights += _csat_driver(scoped_qs, date_range)
    return insights


def _recurring_fault(scoped_qs, date_range):
    """Repeat (facility, service_item) issues — the permanent-fix backlog."""
    rows = (
        scoped_qs.filter(
            created_at__gte=date_range["date_from"],
            created_at__lte=date_range["date_to"],
            location__facility__isnull=False,
        )
        .values(
            facility_id=F("location__facility__id"),
            facility_name=F("location__facility__name"),
            item_id=F("service_item__id"),
            item_name=F("service_item__name"),
        )
        .annotate(occurrences=Count("id"))
        .filter(occurrences__gte=RECURRING_FAULT_MIN)
        .order_by("-occurrences")
    )
    out = []
    for r in rows[:10]:
        out.append({
            "type": "recurring_fault",
            "severity": "high" if r["occurrences"] >= 5 else "med",
            "facility_id": r["facility_id"],
            "facility": r["facility_name"],
            "service_item": r["item_name"],
            "occurrences": r["occurrences"],
            "message": (
                f"{r['item_name']} at {r['facility_name']} was raised "
                f"{r['occurrences']}× in the selected period — candidate for a "
                f"permanent fix rather than repeated patching."
            ),
        })
    return out


def _bottleneck(scoped_qs, date_range):
    """Sections whose tickets sit paused far longer than their peers."""
    window = scoped_qs.filter(
        created_at__gte=date_range["date_from"],
        created_at__lte=date_range["date_to"],
    )
    sec_pause = defaultdict(float)
    sec_name = {}
    for sid, sname, pause in window.values_list(
        "section_id", "section__section_type__name", "accumulated_pause"
    ):
        sec_pause[sid] += pause.total_seconds() if pause else 0.0
        sec_name[sid] = sname

    if len(sec_pause) < 2:
        return []
    ordered = sorted(sec_pause.values())
    median = ordered[len(ordered) // 2]
    if median <= 0:
        return []

    out = []
    for sid, total in sec_pause.items():
        if total >= BOTTLENECK_MULTIPLE * median:
            out.append({
                "type": "bottleneck",
                "severity": "med",
                "dimension": "section",
                "key": sid,
                "label": sec_name.get(sid),
                "metric": "pause_total_seconds",
                "value": round(total),
                "vs_peer_median": round(median),
                "message": (
                    f"Section '{sec_name.get(sid)}' tickets sit paused far longer "
                    f"than peer sections ({round(total / 3600, 1)}h vs median "
                    f"{round(median / 3600, 1)}h) — a workflow/dependency bottleneck."
                ),
            })
    return out


def _sla_leak(scoped_qs):
    """Classify currently-breached tickets by cause — each points to a different fix."""
    now = timezone.now()
    breached = scoped_qs.filter(
        status__in=ACTIVE_STATUSES,
        resolution_due_at__isnull=False,
        resolution_due_at__lt=now,
    )
    total = breached.count()
    if total == 0:
        return []

    # Mutually exclusive causes.
    unassigned = breached.filter(assigned_to__isnull=True).count()
    assigned = breached.filter(assigned_to__isnull=False)
    paused = assigned.filter(status="pending").count()
    slow = assigned.exclude(status="pending").count()

    causes = {
        "unassigned_too_long": unassigned,
        "paused_too_long": paused,
        "slow_resolution": slow,
    }
    labels = {
        "unassigned_too_long": "tickets left unassigned (a triage gap)",
        "paused_too_long": "tickets stuck paused on a dependency",
        "slow_resolution": "slow active resolution (a capacity/skill gap)",
    }
    dominant = max(causes, key=causes.get)
    return [{
        "type": "sla_leak",
        "severity": "high" if total >= 10 else "med",
        "breached_total": total,
        "causes": causes,
        "dominant_cause": dominant,
        "message": (
            f"{total} ticket(s) are past their resolution SLA; the largest driver "
            f"is {labels[dominant]} ({causes[dominant]})."
        ),
    }]


def _capacity(scoped_qs, date_range):
    """Persistent positive net flow — backlog compounding, a staffing signal."""
    window = scoped_qs.filter(
        created_at__gte=date_range["date_from"],
        created_at__lte=date_range["date_to"],
    )
    created = window.count()
    resolved = scoped_qs.filter(
        resolved_at__gte=date_range["date_from"],
        resolved_at__lte=date_range["date_to"],
        status__in=TERMINAL_STATUSES,
    ).count()
    net = created - resolved
    if created < 5 or net < max(5, 0.2 * created):
        return []
    return [{
        "type": "capacity",
        "severity": "high" if net >= 0.5 * created else "med",
        "created": created,
        "resolved": resolved,
        "net_flow": net,
        "message": (
            f"Backlog is growing: {created} created vs {resolved} resolved "
            f"(net +{net}) — capacity may be insufficient for current demand."
        ),
    }]


def _csat_driver(scoped_qs, date_range):
    """Does slowness drive dissatisfaction? Compare CSAT for slowest 10% vs rest."""
    resolved_qs = scoped_qs.filter(
        resolved_at__gte=date_range["date_from"],
        resolved_at__lte=date_range["date_to"],
        status__in=TERMINAL_STATUSES,
    )
    rows = TicketFeedback.objects.filter(ticket__in=resolved_qs).values_list(
        "rating", "ticket__resolved_at", "ticket__created_at",
        "ticket__accumulated_pause",
    )
    enriched = []
    for rating, res, cre, pause in rows:
        if res and cre:
            secs = (res - cre - (pause or timedelta())).total_seconds()
            enriched.append((rating, max(secs, 0.0)))
    if len(enriched) < CSAT_DRIVER_MIN_SAMPLE:
        return []

    p90 = _percentile([s for _, s in enriched], 90)
    slow = [r for r, s in enriched if s >= p90]
    fast = [r for r, s in enriched if s < p90]
    if not slow or not fast:
        return []

    avg_slow = sum(slow) / len(slow)
    avg_fast = sum(fast) / len(fast)
    if avg_fast - avg_slow < CSAT_DRIVER_GAP:
        return []
    return [{
        "type": "csat_driver",
        "severity": "med",
        "avg_rating_slow": round(avg_slow, 2),
        "avg_rating_fast": round(avg_fast, 2),
        "message": (
            f"Satisfaction drops on slow tickets: avg rating {round(avg_slow, 2)} "
            f"for the slowest 10% vs {round(avg_fast, 2)} for the rest — resolution "
            f"speed is a CSAT driver."
        ),
    }]
