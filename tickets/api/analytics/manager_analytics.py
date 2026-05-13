"""Manager / Department analytics — cross-campus metrics for a single Department."""

from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone

from tickets.models import Ticket, CustomUser, Department, CampusDepartment, Section
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
    build_technician_performance,
)


class ManagerAnalytics:
    """Cross-campus analytics for a single global Department."""

    @staticmethod
    def for_department(department: Department, days: int = 30, campus=None) -> dict:
        cache_key = (
            f"analytics_dept_{department.id}_{days}"
            f"{'_campus_' + str(campus.id) if campus else ''}"
        )
        return get_cached(
            cache_key,
            lambda: ManagerAnalytics._compute(department, days, campus),
        )

    @staticmethod
    def manager_dashboard(user, days: int = 30) -> dict:
        """Legacy shim used by RoleBasedDashboardView."""
        if not user.primary_department:
            return {}
        return ManagerAnalytics.for_department(user.primary_department, days=days)

    @staticmethod
    def _compute(department: Department, days: int, campus) -> dict:
        since = timezone.now() - timedelta(days=days)
        base_qs = Ticket.objects.filter(
            campus_department__department=department,
            created_at__gte=since,
        )
        if campus:
            base_qs = base_qs.filter(campus_department__campus=campus)

        # ── 1. Overview ───────────────────────────────────────────────────────
        agg = base_qs.aggregate(
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

        # ── 2. Campus breakdown ───────────────────────────────────────────────
        campus_rows = (
            base_qs
            .values(
                campus_id=F("campus_department__campus__id"),
                campus_code=F("campus_department__campus__code"),
                campus_name=F("campus_department__campus__name"),
                cd_id=F("campus_department__id"),
            )
            .annotate(**annotations)
            .order_by("-total")
        )
        cd_hod_map = {
            cd.id: cd.head_of_department
            for cd in CampusDepartment.objects.filter(
                department=department,
                **({} if not campus else {"campus": campus}),
            ).select_related("head_of_department")
        }
        by_campus = []
        for row in campus_rows:
            hod = cd_hod_map.get(row["cd_id"])
            by_campus.append({
                "campus": {
                    "id": row["campus_id"],
                    "code": row["campus_code"],
                    "name": row["campus_name"],
                },
                "campus_department_id": row["cd_id"],
                "head_of_department": (
                    {
                        "id": hod.id,
                        "name": f"{hod.first_name} {hod.last_name}".strip() or hod.username,
                        "username": hod.username,
                    }
                    if hod else None
                ),
                "total": row["total"],
                "open": row["open_count"],
                "closed": row["closed_count"],
                "escalated": row["escalated_count"],
                "avg_resolution_hours": avg_hours(row["avg_resolution_duration"]),
                "sla_24h_pct": sla_pct(row["resolved_within_24h"], row["total_resolved"]),
            })

        # ── 3. Section breakdown ──────────────────────────────────────────────
        section_rows = (
            base_qs.filter(section__isnull=False)
            .values(
                "section_id",
                section_name=F("section__name"),
                section_code=F("section__code"),
                section_type_name=F("section__section_type__name"),
                campus_code=F("campus_department__campus__code"),
                campus_name=F("campus_department__campus__name"),
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
                "campus": {"code": row["campus_code"], "name": row["campus_name"]},
                "head_of_section": (
                    {"id": hos.id, "username": hos.username,
                     "name": f"{hos.first_name} {hos.last_name}".strip() or hos.username}
                    if hos else None
                ),
                "technician_count": tech_counts.get(row["section_id"], 0),
                "total": row["total"],
                "open": row["open_count"],
                "closed": row["closed_count"],
                "escalated": row["escalated_count"],
                "avg_resolution_hours": avg_hours(row["avg_resolution_duration"]),
                "sla_24h_pct": sla_pct(row["resolved_within_24h"], row["total_resolved"]),
            })

        # ── 4. Technician performance ─────────────────────────────────────────
        technicians = CustomUser.objects.filter(
            role="technician",
            is_active=True,
            technician_section_links__section__campus_department__department=department,
            **({} if not campus else {
                "technician_section_links__section__campus_department__campus": campus
            }),
        ).distinct()

        return {
            "department": {
                "id": department.id,
                "code": department.code,
                "name": department.name,
            },
            "period_days": days,
            "overview": overview,
            "by_campus": by_campus,
            "by_section": by_section,
            "technicians": build_technician_performance(base_qs, technicians),
            "status_distribution": get_status_distribution(base_qs),
            "escalation_trends": get_escalation_trends(base_qs, days=min(days, 30)),
        }
