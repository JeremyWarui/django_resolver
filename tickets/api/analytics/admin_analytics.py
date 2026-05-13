"""Admin analytics — system-wide metrics for administrators."""

from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone

from tickets.models import Ticket, CustomUser
from .base_analytics import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    OVERDUE_STATUSES,
    OVERDUE_THRESHOLD_DAYS,
    SLA_WINDOW_HOURS,
    avg_hours,
    sla_pct,
    ticket_scope_annotations,
    get_cached,
    get_ticket_trend_data,
    build_technician_performance,
)


class AdminAnalytics:

    @staticmethod
    def get_system_overview() -> dict:
        """One aggregate query for all top-line counters."""
        def compute():
            now = timezone.now()
            counts = Ticket.objects.aggregate(
                total=Count("id"),
                open=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
                closed=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
                pending=Count("id", filter=Q(status="pending")),
                pending_approval=Count("id", filter=Q(status="pending_approval")),
                escalated=Count("id", filter=Q(escalation_level__gt=0)),
                new_24h=Count("id", filter=Q(created_at__gte=now - timedelta(days=1))),
                new_7d=Count("id", filter=Q(created_at__gte=now - timedelta(days=7))),
                new_30d=Count("id", filter=Q(created_at__gte=now - timedelta(days=30))),
                resolved_within_24h=Count(
                    "id",
                    filter=Q(
                        status__in=TERMINAL_STATUSES,
                        resolved_at__isnull=False,
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

            total = counts["total"] or 0
            closed = counts["closed"] or 0

            users_agg = CustomUser.objects.filter(is_active=True).aggregate(
                total=Count("id"),
                technicians=Count("id", filter=Q(role="technician")),
                managers=Count("id", filter=Q(role="manager")),
                hods=Count("id", filter=Q(role="hod")),
                head_of_sections=Count("id", filter=Q(role="head_of_section")),
                admins=Count("id", filter=Q(role="admin")),
            )

            return {
                "total": total,
                "open": counts["open"] or 0,
                "closed": closed,
                "pending": counts["pending"] or 0,
                "pending_approval": counts["pending_approval"] or 0,
                "escalated": counts["escalated"] or 0,
                "new_24h": counts["new_24h"] or 0,
                "new_7d": counts["new_7d"] or 0,
                "new_30d": counts["new_30d"] or 0,
                "resolution_rate_pct": round(closed / total * 100, 1) if total else 0.0,
                "avg_resolution_hours": avg_hours(counts["avg_resolution_duration"]),
                "sla_24h_pct": sla_pct(counts["resolved_within_24h"] or 0, counts["total_resolved"] or 0),
                "users": {
                    "total": users_agg["total"],
                    "technicians": users_agg["technicians"],
                    "managers": users_agg["managers"],
                    "hods": users_agg["hods"],
                    "head_of_sections": users_agg["head_of_sections"],
                    "admins": users_agg["admins"],
                },
            }

        return get_cached("analytics_admin_overview", compute)

    @staticmethod
    def get_overdue_tickets() -> list:
        """Tickets that have breached the overdue threshold and are still active."""
        def compute():
            threshold = timezone.now() - timedelta(days=OVERDUE_THRESHOLD_DAYS)
            overdue = (
                Ticket.objects.filter(
                    created_at__lt=threshold,
                    status__in=OVERDUE_STATUSES,
                )
                .select_related(
                    "campus_department__campus",
                    "campus_department__department",
                    "section",
                    "facility",
                    "assigned_to",
                )
                .annotate(
                    age_seconds=ExpressionWrapper(
                        timezone.now() - F("created_at"),
                        output_field=DurationField(),
                    )
                )
                .order_by("created_at")
            )
            return [
                {
                    "id": t.id,
                    "ticket_no": t.ticket_no,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                    "campus": t.campus_department.campus.code,
                    "department": t.campus_department.department.code,
                    "section": t.section.name if t.section else None,
                    "facility": t.facility.name if t.facility else None,
                    "assigned_to": t.assigned_to.username if t.assigned_to else None,
                    "age_hours": round(t.age_seconds.total_seconds() / 3600, 1),
                    "days_old": (timezone.now() - t.created_at).days,
                    "created_at": t.created_at.isoformat(),
                }
                for t in overdue[:50]
            ]

        return get_cached("analytics_admin_overdue", compute)

    @staticmethod
    def get_organisation_analytics(days: int = 30) -> dict:
        """Full org-wide analytics: campus + department + section + technician breakdowns."""
        def compute():
            since = timezone.now() - timedelta(days=days)
            base_qs = Ticket.objects.filter(created_at__gte=since)
            annotations = ticket_scope_annotations()

            # ── Campus breakdown ───────────────────────────────────────────────
            campus_rows = (
                base_qs
                .values(
                    campus_id=F("campus_department__campus__id"),
                    campus_code=F("campus_department__campus__code"),
                    campus_name=F("campus_department__campus__name"),
                )
                .annotate(**annotations)
                .order_by("-total")
            )
            campus_breakdown = [
                {
                    "campus": {"id": r["campus_id"], "code": r["campus_code"], "name": r["campus_name"]},
                    "total": r["total"],
                    "open": r["open_count"],
                    "closed": r["closed_count"],
                    "pending": r["pending_count"],
                    "escalated": r["escalated_count"],
                    "avg_resolution_hours": avg_hours(r["avg_resolution_duration"]),
                    "sla_24h_pct": sla_pct(r["resolved_within_24h"], r["total_resolved"]),
                }
                for r in campus_rows
            ]

            # ── Department breakdown ───────────────────────────────────────────
            dept_rows = (
                base_qs
                .values(
                    dept_id=F("campus_department__department__id"),
                    dept_code=F("campus_department__department__code"),
                    dept_name=F("campus_department__department__name"),
                )
                .annotate(**annotations)
                .order_by("-total")
            )
            department_breakdown = [
                {
                    "department": {"id": r["dept_id"], "code": r["dept_code"], "name": r["dept_name"]},
                    "total": r["total"],
                    "open": r["open_count"],
                    "closed": r["closed_count"],
                    "pending": r["pending_count"],
                    "escalated": r["escalated_count"],
                    "avg_resolution_hours": avg_hours(r["avg_resolution_duration"]),
                    "sla_24h_pct": sla_pct(r["resolved_within_24h"], r["total_resolved"]),
                }
                for r in dept_rows
            ]

            # ── Busiest sections ───────────────────────────────────────────────
            section_rows = (
                base_qs.filter(section__isnull=False)
                .values(
                    "section_id",
                    section_name=F("section__name"),
                    section_code=F("section__code"),
                    campus_code=F("campus_department__campus__code"),
                    dept_name=F("campus_department__department__name"),
                )
                .annotate(total=Count("id"))
                .order_by("-total")[:10]
            )
            busiest_sections = [
                {
                    "section": {
                        "id": r["section_id"],
                        "name": r["section_name"],
                        "display_name": f"{r['campus_code']}-{r['section_name']}",
                    },
                    "campus_code": r["campus_code"],
                    "department": r["dept_name"],
                    "total": r["total"],
                }
                for r in section_rows
            ]

            # ── Top service items ──────────────────────────────────────────────
            top_service_items = [
                {
                    "id": r["item_id"],
                    "name": r["item_name"],
                    "category": r["category_name"] or "",
                    "ticket_count": r["ticket_count"],
                }
                for r in (
                    base_qs.filter(service_item__isnull=False)
                    .values(
                        item_id=F("service_item__id"),
                        item_name=F("service_item__name"),
                        category_name=F("service_item__category__name"),
                    )
                    .annotate(ticket_count=Count("id"))
                    .order_by("-ticket_count")[:10]
                )
            ]

            # ── Technician performance ─────────────────────────────────────────
            technicians = CustomUser.objects.filter(role="technician", is_active=True)

            # ── Trend ──────────────────────────────────────────────────────────
            trend = [
                {
                    "date": (
                        row["period"].strftime("%Y-%m-%d")
                        if hasattr(row["period"], "strftime")
                        else str(row["period"])[:10]
                    ),
                    "count": row["count"],
                }
                for row in get_ticket_trend_data(days=days, group_by="day")
            ]

            return {
                "summary": AdminAnalytics.get_system_overview(),
                "period_days": days,
                "campus_breakdown": campus_breakdown,
                "department_breakdown": department_breakdown,
                "busiest_sections": busiest_sections,
                "top_service_items": top_service_items,
                "technician_performance": build_technician_performance(base_qs, technicians),
                "trend": trend,
            }

        return get_cached(f"analytics_org_{days}", compute)
