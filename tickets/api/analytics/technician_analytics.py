"""Technician analytics - technician performance and workload metrics."""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import (
    Count, Avg, Q, F, ExpressionWrapper, DurationField,
)

from tickets.models import Ticket, CustomUser, Section

ANALYTICS_CACHE_TTL = 300


class TechnicianAnalytics:
    """Provides analytics for technician performance and workload."""

    @staticmethod
    def get_technician_performance(technician_id=None):
        """Get performance metrics for technicians via DB aggregation."""
        cache_key = f"analytics_tech_performance_{technician_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        overdue_threshold = timezone.now() - timedelta(hours=24)

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
                    F("assigned_tickets__updated_at")
                    - F("assigned_tickets__created_at"),
                    output_field=DurationField(),
                ),
                filter=Q(assigned_tickets__status__in=["resolved", "closed"]),
            ),
        )

        # Fetch per-status breakdown in one query
        tech_ids = [t.id for t in techs]
        status_rows = (
            Ticket.objects.filter(assigned_to_id__in=tech_ids)
            .values("assigned_to_id", "status")
            .annotate(count=Count("id"))
        )
        status_by_tech = {}
        for row in status_rows:
            status_by_tech.setdefault(row["assigned_to_id"], {})[row["status"]] = row["count"]

        performance_data = []
        for tech in techs:
            avg_res = (
                (tech.avg_resolution_hours.total_seconds() / 3600)
                if tech.avg_resolution_hours
                else 0
            )
            performance_data.append(
                {
                    "id": tech.id,
                    "username": tech.username,
                    "full_name": f"{tech.first_name} {tech.last_name}",
                    "total_tickets": tech.total_tickets,
                    "resolved_tickets": tech.resolved_tickets,
                    "pending_tickets": tech.pending_tickets,
                    "overdue_tickets": tech.overdue_tickets,
                    "avg_rating": round(tech.avg_rating or 0, 2),
                    "avg_resolution_time": round(avg_res, 2),
                    "resolution_percentage": round(
                        (
                            (tech.resolved_tickets / tech.total_tickets * 100)
                            if tech.total_tickets > 0
                            else 0
                        ),
                        2,
                    ),
                    "tickets_by_status": status_by_tech.get(tech.id, {}),
                }
            )

        cache.set(cache_key, performance_data, ANALYTICS_CACHE_TTL)
        return performance_data

    @staticmethod
    def get_technician_ratings_by_section():
        """Get technician ratings grouped by section."""
        cache_key = "analytics_tech_ratings_by_section"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        rows = Section.objects.annotate(
            technician_count=Count("technicians", distinct=True),
            avg_rating=Avg("technicians__assigned_tickets__feedback__rating"),
        ).values("name", "technician_count", "avg_rating")

        result = sorted(
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
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result
