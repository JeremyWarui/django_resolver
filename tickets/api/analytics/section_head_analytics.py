"""HOS (Head of Section) analytics — section-level metrics."""

from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDay
from django.utils import timezone

from tickets.models import Ticket, Section
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


class SectionHeadAnalytics:
    """Analytics for a Head of Section."""

    @staticmethod
    def for_section(section: Section, days: int = 30) -> dict:
        return get_cached(
            f"analytics_hos_section_{section.id}_{days}",
            lambda: SectionHeadAnalytics._compute_section(section, days),
        )

    @staticmethod
    def section_head_dashboard(user, days: int = 30) -> dict:
        """Legacy shim — aggregates all sections the user heads."""
        sections = Section.objects.filter(head_of_section=user).select_related(
            "campus_department__campus",
            "campus_department__department",
            "section_type",
        )
        if not sections.exists():
            return {}
        return get_cached(
            f"analytics_section_head_{user.id}_{days}",
            lambda: SectionHeadAnalytics._compute_multi_section(user, sections, days),
        )

    # ── Single-section ────────────────────────────────────────────────────────

    @staticmethod
    def _compute_section(section: Section, days: int) -> dict:
        since = timezone.now() - timedelta(days=days)
        base_qs = Ticket.objects.filter(section=section, created_at__gte=since)
        cd = section.campus_department

        return {
            "section": {
                "id": section.id,
                "name": section.name,
                "code": section.code,
                "section_type": section.section_type.name,
                "campus": {"code": cd.campus.code, "name": cd.campus.name},
                "department": {"code": cd.department.code, "name": cd.department.name},
                "head_of_section": (
                    {
                        "id": section.head_of_section.id,
                        "username": section.head_of_section.username,
                        "name": (
                            f"{section.head_of_section.first_name} "
                            f"{section.head_of_section.last_name}".strip()
                            or section.head_of_section.username
                        ),
                    }
                    if section.head_of_section else None
                ),
                "technician_count": section.technician_links.count(),
                "effective_sla_hours": section.effective_sla_hours,
            },
            "period_days": days,
            "overview": SectionHeadAnalytics._overview(base_qs),
            "technician_workload": SectionHeadAnalytics._technician_workload(base_qs),
            "pending_reasons": SectionHeadAnalytics._pending_reasons(base_qs),
            "ticket_inflow": SectionHeadAnalytics._daily_inflow(base_qs),
            "status_distribution": get_status_distribution(base_qs),
            "escalation_trends": get_escalation_trends(base_qs, days=min(days, 30)),
        }

    # ── Multi-section (legacy dashboard) ─────────────────────────────────────

    @staticmethod
    def _compute_multi_section(user, sections, days: int) -> dict:
        since = timezone.now() - timedelta(days=days)
        all_qs = Ticket.objects.filter(section__in=sections)
        base_qs = all_qs.filter(created_at__gte=since)

        section_ids = list(sections.values_list("id", flat=True))
        section_rows = (
            base_qs.filter(section__isnull=False)
            .values(
                "section_id",
                section_name=F("section__name"),
                section_code=F("section__code"),
                section_type_name=F("section__section_type__name"),
                campus_code=F("section__campus_department__campus__code"),
                department_name=F("section__campus_department__department__name"),
            )
            .annotate(**ticket_scope_annotations())
            .order_by("-total")
        )
        tech_counts = dict(
            Section.objects.filter(id__in=section_ids)
            .annotate(tc=Count("technician_links"))
            .values_list("id", "tc")
        )
        by_section = [
            {
                "section": {
                    "id": row["section_id"],
                    "name": row["section_name"],
                    "code": row["section_code"],
                    "section_type": row["section_type_name"],
                    "campus_code": row["campus_code"],
                    "department": row["department_name"],
                },
                "technician_count": tech_counts.get(row["section_id"], 0),
                "total": row["total"],
                "open": row["open_count"],
                "closed": row["closed_count"],
                "escalated": row["escalated_count"],
                "avg_resolution_hours": avg_hours(row["avg_resolution_duration"]),
                "sla_24h_pct": sla_pct(row["resolved_within_24h"], row["total_resolved"]),
            }
            for row in section_rows
        ]

        return {
            "head_of_section": {
                "id": user.id,
                "username": user.username,
                "sections_count": sections.count(),
            },
            "period_days": days,
            "overview": SectionHeadAnalytics._overview(all_qs),
            "by_section": by_section,
            "technician_workload": SectionHeadAnalytics._technician_workload(base_qs),
            "pending_reasons": SectionHeadAnalytics._pending_reasons(base_qs),
            "ticket_inflow": SectionHeadAnalytics._daily_inflow(base_qs),
            "status_distribution": get_status_distribution(base_qs),
            "escalation_trends": get_escalation_trends(base_qs, days=min(days, 30)),
        }

    # ── Sub-computations ──────────────────────────────────────────────────────

    @staticmethod
    def _overview(base_qs) -> dict:
        agg = base_qs.aggregate(
            total=Count("id"),
            open_count=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            closed_count=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            in_progress_count=Count("id", filter=Q(status="in_progress")),
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
        return {
            "total": agg["total"],
            "open": agg["open_count"],
            "closed": agg["closed_count"],
            "in_progress": agg["in_progress_count"],
            "pending": agg["pending_count"],
            "escalated": agg["escalated_count"],
            "avg_resolution_hours": avg_hours(agg["avg_resolution_duration"]),
            "sla_24h_pct": sla_pct(agg["resolved_within_24h"], agg["total_resolved"]),
        }

    @staticmethod
    def _technician_workload(base_qs) -> list:
        rows = (
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
        return [
            {
                "technician": {
                    "id": row["technician_id"],
                    "username": row["username"],
                    "name": f"{row['first_name']} {row['last_name']}".strip() or row["username"],
                },
                "total_assigned": row["total_assigned"],
                "open": row["open_count"],
                "resolved": row["resolved_count"],
                "escalated": row["escalated_count"],
                "avg_resolution_hours": avg_hours(row["avg_resolution_duration"]),
            }
            for row in rows
        ]

    @staticmethod
    def _pending_reasons(base_qs) -> list:
        return list(
            base_qs
            .filter(status="pending", pending_reason__isnull=False)
            .values("pending_reason")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

    @staticmethod
    def _daily_inflow(base_qs) -> list:
        return [
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
