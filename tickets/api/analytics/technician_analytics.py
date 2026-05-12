"""Technician analytics - technician performance and workload metrics."""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, DurationField

from tickets.models import Ticket, CustomUser, Section
from .base_analytics import ANALYTICS_CACHE_TTL, get_cached

TECHNICIAN_OVERDUE_HOURS = 24


class TechnicianAnalytics:
    """Provides analytics for technician performance and workload."""

    @staticmethod
    def get_technician_performance(technician_id=None):
        def compute():
            overdue_threshold = timezone.now() - timedelta(hours=TECHNICIAN_OVERDUE_HOURS)
            queryset = CustomUser.objects.filter(role="technician")
            if technician_id:
                queryset = queryset.filter(id=technician_id)

            techs = queryset.annotate(
                total_tickets=Count("assigned_tickets", distinct=True),
                resolved_tickets=Count(
                    "assigned_tickets",
                    filter=Q(assigned_tickets__status__in=["resolved", "closed"]),
                    distinct=True,
                ),
                pending_tickets=Count(
                    "assigned_tickets",
                    filter=Q(
                        assigned_tickets__status__in=["assigned", "in_progress", "pending"]
                    ),
                    distinct=True,
                ),
                overdue_tickets=Count(
                    "assigned_tickets",
                    filter=Q(
                        assigned_tickets__status__in=["assigned", "in_progress", "pending"],
                        assigned_tickets__created_at__lt=overdue_threshold,
                    ),
                    distinct=True,
                ),
                avg_rating=Avg("assigned_tickets__feedback__rating"),
                avg_resolution_hours=Avg(
                    ExpressionWrapper(
                        F("assigned_tickets__resolved_at") - F("assigned_tickets__created_at"),
                        output_field=DurationField(),
                    ),
                    filter=Q(
                        assigned_tickets__status__in=["resolved", "closed"],
                        assigned_tickets__resolved_at__isnull=False,
                    ),
                ),
            )

            tech_ids = [t.id for t in techs]
            status_rows = (
                Ticket.objects.filter(assigned_to_id__in=tech_ids)
                .values("assigned_to_id", "status")
                .annotate(count=Count("id"))
            )
            status_by_tech: dict = {}
            for row in status_rows:
                status_by_tech.setdefault(row["assigned_to_id"], {})[row["status"]] = row["count"]

            performance_data = []
            for tech in techs:
                avg_res = (
                    (tech.avg_resolution_hours.total_seconds() / 3600)
                    if tech.avg_resolution_hours
                    else 0
                )
                performance_data.append({
                    "id": tech.id,
                    "username": tech.username,
                    "email": tech.email,
                    "full_name": f"{tech.first_name} {tech.last_name}",
                    "total_tickets": tech.total_tickets,
                    "resolved_tickets": tech.resolved_tickets,
                    "pending_tickets": tech.pending_tickets,
                    "overdue_tickets": tech.overdue_tickets,
                    "avg_rating": round(tech.avg_rating or 0, 2),
                    "avg_resolution_time": round(avg_res, 2),
                    "resolution_percentage": round(
                        (tech.resolved_tickets / tech.total_tickets * 100)
                        if tech.total_tickets > 0
                        else 0,
                        2,
                    ),
                    "tickets_by_status": status_by_tech.get(tech.id, {}),
                })
            return performance_data

        return get_cached(f"analytics_tech_performance_{technician_id}", compute)

    @staticmethod
    def get_technician_ratings_by_section():
        def compute():
            rows = Section.objects.annotate(
                technician_count=Count("technicians", distinct=True),
                avg_rating=Avg("technicians__assigned_tickets__feedback__rating"),
            ).values("name", "technician_count", "avg_rating")

            return sorted(
                [
                    {
                        "section_name": r["name"],
                        "technician_count": r["technician_count"],
                        "avg_rating": round(r["avg_rating"] or 0, 2),
                    }
                    for r in rows
                ],
                key=lambda x: x["avg_rating"],
                reverse=True,
            )

        return get_cached("analytics_tech_ratings_by_section", compute)
