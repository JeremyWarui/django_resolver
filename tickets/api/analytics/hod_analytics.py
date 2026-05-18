"""HOD analytics — single-campus, single-department metrics."""

from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDay
from django.utils import timezone

from tickets.models import Ticket, CustomUser, Section, TechnicianSection
from .base_analytics import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    SLA_WINDOW_HOURS,
    avg_hours,
    sla_pct,
    ticket_scope_annotations,
    get_cached,
    get_escalation_trends,
    get_status_distribution,
)


class HODAnalytics:
    """Analytics for a Head of Department scoped to one CampusDepartment."""

    @staticmethod
    def for_campus_department(campus_department, days: int = 30) -> dict:
        return get_cached(
            f"analytics_hod_cd_{campus_department.id}_{days}",
            lambda: HODAnalytics._compute(campus_department, days),
        )

    @staticmethod
    def hod_dashboard(user, days: int = 30) -> dict:
        """Legacy shim used by RoleBasedDashboardView."""
        cd = user.primary_campus_department
        if not cd:
            return {}
        return HODAnalytics.for_campus_department(cd, days=days)

    @staticmethod
    def _compute(campus_department, days: int) -> dict:
        since = timezone.now() - timedelta(days=days)
        campus = campus_department.campus
        department = campus_department.department

        # All tickets for this campus department (no date window) — used for
        # live status counts that must match the ticket table.
        all_qs = Ticket.objects.filter(campus_department=campus_department)

        # Time-windowed subset — used for trend, SLA, and section/technician analytics.
        base_qs = all_qs.filter(created_at__gte=since)

        # ── 1. Overview (all-time counts so stat cards match the ticket table) ─
        agg = all_qs.aggregate(
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
                    resolved_at__lte=F("created_at") + timedelta(hours=SLA_WINDOW_HOURS),
                ),
            ),
            total_resolved=Count(
                "id", filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False)
            ),
            avg_resolution_duration=Avg(
                ExpressionWrapper(
                    F("resolved_at") - F("created_at"), output_field=DurationField()
                ),
                filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
            ),
        )
        overview = {
            "total": agg["total"],
            "open": agg["open_count"],
            "closed": agg["closed_count"],
            "pending": agg["pending_count"],
            "escalated": agg["escalated_count"],
            "avg_resolution_hours": avg_hours(agg["avg_resolution_duration"]),
            "sla_24h_pct": sla_pct(agg["resolved_within_24h"], agg["total_resolved"]),
        }

        annotations = ticket_scope_annotations()

        # ── 2. Section breakdown ──────────────────────────────────────────────
        section_rows = (
            base_qs.filter(section__isnull=False)
            .values(
                "section_id",
                section_name=F("section__name"),
                section_code=F("section__code"),
                section_type_name=F("section__section_type__name"),
            )
            .annotate(**annotations)
            .order_by("-total")
        )
        section_ids = [r["section_id"] for r in section_rows]
        sections_meta = {
            s.id: s
            for s in Section.objects.filter(id__in=section_ids).select_related("head_of_section")
        }
        tech_counts = dict(
            Section.objects.filter(id__in=section_ids)
            .annotate(tc=Count("technician_links"))
            .values_list("id", "tc")
        )
        by_section = []
        for row in section_rows:
            sec = sections_meta.get(row["section_id"])
            hos = sec.head_of_section if sec else None
            by_section.append({
                "section": {
                    "id": row["section_id"],
                    "name": row["section_name"],
                    "code": row["section_code"],
                    "section_type": row["section_type_name"],
                },
                "head_of_section": (
                    {"id": hos.id, "username": hos.username,
                     "name": f"{hos.first_name} {hos.last_name}".strip() or hos.username}
                    if hos else None
                ),
                "technician_count": tech_counts.get(row["section_id"], 0),
                "total": row["total"],
                "open": row["open_count"],
                "closed": row["closed_count"],
                "pending": row["pending_count"],
                "escalated": row["escalated_count"],
                "avg_resolution_hours": avg_hours(row["avg_resolution_duration"]),
                "sla_24h_pct": sla_pct(row["resolved_within_24h"], row["total_resolved"]),
            })

        # ── 3. Technician workload ────────────────────────────────────────────
        workload_rows = (
            base_qs.filter(assigned_to__isnull=False)
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
                escalated_count=Count("id", filter=Q(escalation_level__gt=0)),
                avg_resolution_duration=Avg(
                    ExpressionWrapper(
                        F("resolved_at") - F("created_at"), output_field=DurationField()
                    ),
                    filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
                ),
            )
            .order_by("-open_count", "-total_assigned")
        )
        tech_ids = [row["technician_id"] for row in workload_rows]
        tech_sections: dict[int, list[dict]] = {}
        for ts in TechnicianSection.objects.filter(
            technician_id__in=tech_ids,
            section__campus_department=campus_department,
        ).values("technician_id", "section__id", "section__name", "section__code"):
            tech_sections.setdefault(ts["technician_id"], []).append({
                "id": ts["section__id"],
                "name": ts["section__name"],
                "code": ts["section__code"],
            })

        technician_workload = [
            {
                "technician": {
                    "id": row["technician_id"],
                    "username": row["username"],
                    "name": f"{row['first_name']} {row['last_name']}".strip() or row["username"],
                },
                "sections": tech_sections.get(row["technician_id"], []),
                "total_assigned": row["total_assigned"],
                "open": row["open_count"],
                "resolved": row["resolved_count"],
                "escalated": row["escalated_count"],
                "avg_resolution_hours": avg_hours(row["avg_resolution_duration"]),
            }
            for row in workload_rows
        ]

        # ── 4. Daily inflow ───────────────────────────────────────────────────
        ticket_inflow = [
            {"date": day.date().isoformat(), "count": count}
            for day, count in (
                base_qs
                .annotate(day=TruncDay("created_at"))
                .values("day")
                .annotate(count=Count("id"))
                .order_by("day")
                .values_list("day", "count")
            )
        ]

        return {
            "campus_department": {
                "id": campus_department.id,
                "campus": {"id": campus.id, "code": campus.code, "name": campus.name},
                "department": {"id": department.id, "code": department.code, "name": department.name},
                "head_of_department": (
                    {
                        "id": campus_department.head_of_department.id,
                        "username": campus_department.head_of_department.username,
                        "name": (
                            f"{campus_department.head_of_department.first_name} "
                            f"{campus_department.head_of_department.last_name}".strip()
                            or campus_department.head_of_department.username
                        ),
                    }
                    if campus_department.head_of_department else None
                ),
            },
            "period_days": days,
            "overview": overview,
            "by_section": by_section,
            "technician_workload": technician_workload,
            "ticket_inflow": ticket_inflow,
            "status_distribution": get_status_distribution(base_qs),
            "escalation_trends": get_escalation_trends(base_qs, days=min(days, 30)),
        }
