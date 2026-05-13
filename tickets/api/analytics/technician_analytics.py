"""Technician analytics — KPIs for individual technicians and admin-wide views."""

from datetime import timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.utils import timezone

from tickets.models import Ticket, CustomUser, Section
from .base_analytics import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    avg_hours,
    get_cached,
)


class TechnicianAnalytics:

    @staticmethod
    def for_technician(user: CustomUser) -> dict:
        """Self-service KPIs for a single technician."""
        return get_cached(
            f"analytics_tech_self_{user.id}",
            lambda: TechnicianAnalytics._compute_for_technician(user),
        )

    @staticmethod
    def _compute_for_technician(user: CustomUser) -> dict:
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=now.weekday())
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        base_qs = Ticket.objects.filter(assigned_to=user)

        agg = base_qs.aggregate(
            open_total=Count("id", filter=Q(status__in=ACTIVE_STATUSES)),
            resolved_today=Count(
                "id", filter=Q(status__in=TERMINAL_STATUSES, resolved_at__gte=today_start)
            ),
            resolved_week=Count(
                "id", filter=Q(status__in=TERMINAL_STATUSES, resolved_at__gte=week_start)
            ),
            resolved_month=Count(
                "id", filter=Q(status__in=TERMINAL_STATUSES, resolved_at__gte=month_start)
            ),
            total_assigned=Count("id"),
            total_resolved=Count("id", filter=Q(status__in=TERMINAL_STATUSES)),
            escalated=Count("id", filter=Q(escalation_level__gt=0)),
            avg_resolution_duration=Avg(
                ExpressionWrapper(
                    F("resolved_at") - F("created_at"), output_field=DurationField()
                ),
                filter=Q(status__in=TERMINAL_STATUSES, resolved_at__isnull=False),
            ),
            avg_rating=Avg("feedback__rating", filter=Q(status__in=TERMINAL_STATUSES)),
        )

        open_tickets = list(
            base_qs.filter(status__in=ACTIVE_STATUSES)
            .select_related("campus_department__campus", "section")
            .values(
                "id", "ticket_no", "title", "status", "priority", "created_at", "due_date",
                campus=F("campus_department__campus__code"),
                section_name=F("section__name"),
            )
            .order_by("priority", "created_at")
        )

        sections = list(
            user.sections.select_related(
                "campus_department__campus",
                "campus_department__department",
                "section_type",
            ).values(
                "id", "name", "code",
                campus=F("campus_department__campus__code"),
                department=F("campus_department__department__name"),
                section_type_name=F("section_type__name"),
            )
        )

        total = agg["total_assigned"] or 0
        total_resolved = agg["total_resolved"] or 0
        return {
            "technician": {
                "id": user.id,
                "username": user.username,
                "name": f"{user.first_name} {user.last_name}".strip() or user.username,
                "email": user.email,
            },
            "kpis": {
                "resolved_today": agg["resolved_today"],
                "resolved_this_week": agg["resolved_week"],
                "resolved_this_month": agg["resolved_month"],
                "open_assignments": agg["open_total"],
                "total_assigned": total,
                "total_resolved": total_resolved,
                "escalated": agg["escalated"],
                "resolution_rate_pct": round(total_resolved / total * 100, 1) if total else 0.0,
                "avg_resolution_hours": avg_hours(agg["avg_resolution_duration"]),
                "avg_rating": round(agg["avg_rating"] or 0.0, 2),
            },
            "open_tickets": open_tickets,
            "sections": sections,
        }

    @staticmethod
    def get_technician_performance(technician_id=None) -> list:
        """Admin-facing list: aggregated performance for all (or one) technicians."""
        def compute():
            now = timezone.now()
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = now - timedelta(days=now.weekday())
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            qs = CustomUser.objects.filter(role="technician", is_active=True)
            if technician_id:
                qs = qs.filter(id=technician_id)

            techs = qs.annotate(
                total_assigned=Count("assigned_tickets", distinct=True),
                total_resolved=Count(
                    "assigned_tickets",
                    filter=Q(assigned_tickets__status__in=TERMINAL_STATUSES),
                    distinct=True,
                ),
                open_count=Count(
                    "assigned_tickets",
                    filter=Q(assigned_tickets__status__in=ACTIVE_STATUSES),
                    distinct=True,
                ),
                resolved_today=Count(
                    "assigned_tickets",
                    filter=Q(
                        assigned_tickets__status__in=TERMINAL_STATUSES,
                        assigned_tickets__resolved_at__gte=today_start,
                    ),
                    distinct=True,
                ),
                resolved_week=Count(
                    "assigned_tickets",
                    filter=Q(
                        assigned_tickets__status__in=TERMINAL_STATUSES,
                        assigned_tickets__resolved_at__gte=week_start,
                    ),
                    distinct=True,
                ),
                resolved_month=Count(
                    "assigned_tickets",
                    filter=Q(
                        assigned_tickets__status__in=TERMINAL_STATUSES,
                        assigned_tickets__resolved_at__gte=month_start,
                    ),
                    distinct=True,
                ),
                escalated_count=Count(
                    "assigned_tickets",
                    filter=Q(assigned_tickets__escalation_level__gt=0),
                    distinct=True,
                ),
                avg_rating=Avg("assigned_tickets__feedback__rating"),
                avg_resolution_duration=Avg(
                    ExpressionWrapper(
                        F("assigned_tickets__resolved_at") - F("assigned_tickets__created_at"),
                        output_field=DurationField(),
                    ),
                    filter=Q(
                        assigned_tickets__status__in=TERMINAL_STATUSES,
                        assigned_tickets__resolved_at__isnull=False,
                    ),
                ),
            )

            tech_ids = [t.id for t in techs]
            status_map: dict = {}
            for row in (
                Ticket.objects.filter(assigned_to_id__in=tech_ids)
                .values("assigned_to_id", "status")
                .annotate(count=Count("id"))
            ):
                status_map.setdefault(row["assigned_to_id"], {})[row["status"]] = row["count"]

            result = []
            for tech in techs:
                total = tech.total_assigned or 0
                resolved = tech.total_resolved or 0
                result.append({
                    "technician": {
                        "id": tech.id,
                        "username": tech.username,
                        "name": f"{tech.first_name} {tech.last_name}".strip() or tech.username,
                        "email": tech.email,
                    },
                    "total_assigned": total,
                    "open": tech.open_count,
                    "resolved": resolved,
                    "escalated": tech.escalated_count,
                    "resolved_today": tech.resolved_today,
                    "resolved_this_week": tech.resolved_week,
                    "resolved_this_month": tech.resolved_month,
                    "resolution_rate_pct": round(resolved / total * 100, 1) if total else 0.0,
                    "avg_resolution_hours": avg_hours(tech.avg_resolution_duration),
                    "avg_rating": round(tech.avg_rating or 0.0, 2),
                    "tickets_by_status": status_map.get(tech.id, {}),
                })

            return sorted(result, key=lambda x: x["open"], reverse=True)

        return get_cached(f"analytics_tech_performance_{technician_id or 'all'}", compute)

    @staticmethod
    def get_technician_ratings_by_section() -> list:
        """Average feedback rating per section."""
        def compute():
            rows = (
                Section.objects
                .select_related("campus_department__campus", "campus_department__department")
                .annotate(
                    technician_count=Count("technician_links", distinct=True),
                    avg_rating=Avg(
                        "technician_links__technician__assigned_tickets__feedback__rating"
                    ),
                )
                .values(
                    "id", "name", "technician_count", "avg_rating",
                    campus_code=F("campus_department__campus__code"),
                    dept_code=F("campus_department__department__code"),
                )
                .order_by("-avg_rating")
            )
            return [
                {
                    "section": {
                        "id": r["id"],
                        "name": r["name"],
                        "display_name": f"{r['campus_code']}-{r['name']}",
                        "department": r["dept_code"],
                    },
                    "technician_count": r["technician_count"],
                    "avg_rating": round(r["avg_rating"] or 0.0, 2),
                }
                for r in rows
            ]

        return get_cached("analytics_tech_ratings_by_section", compute)
