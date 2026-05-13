"""Ticket analytics — filterable drill-down metrics for admin/manager use.

Distinct from role-scoped dashboards: this module provides facility/section
filtering that the role dashboards don't expose.
"""

from datetime import timedelta

from django.db import models
from django.db.models import Count
from django.utils import timezone

from tickets.models import Ticket, Facility, Section
from .base_analytics import (
    get_cached,
    get_status_distribution,
    get_ticket_trend_data,
)


class TicketAnalytics:
    """Filterable ticket metrics — admin and manager drill-down tool."""

    @staticmethod
    def get_ticket_counts_by_timeframe(days=1, facility_id=None, section_id=None):
        """Count tickets created in the last `days` days, optionally filtered."""
        def compute():
            since = timezone.now() - timedelta(days=days)
            qs = Ticket.objects.filter(created_at__gte=since)
            if facility_id:
                qs = qs.filter(facility_id=facility_id)
            if section_id:
                qs = qs.filter(section_id=section_id)
            return {
                "period": f"Last {days} day{'s' if days > 1 else ''}",
                "count": qs.count(),
            }

        return get_cached(
            f"analytics_timeframe_{days}_{facility_id}_{section_id}", compute
        )

    @staticmethod
    def get_ticket_counts_by_status(facility_id=None, section_id=None):
        """Status distribution with optional facility/section filter."""
        def compute():
            qs = Ticket.objects.all()
            if facility_id:
                qs = qs.filter(facility_id=facility_id)
            if section_id:
                qs = qs.filter(section_id=section_id)
            rows = get_status_distribution(qs, order_by="status")
            return {row["status"]: row["count"] for row in rows}

        return get_cached(f"analytics_status_{facility_id}_{section_id}", compute)

    @staticmethod
    def get_tickets_by_facility():
        """Ticket count per facility, ordered by descending count."""
        def compute():
            return list(
                Facility.objects.annotate(ticket_count=Count("tickets"))
                .values("id", "name", "ticket_count")
                .order_by("-ticket_count")
            )

        return get_cached("analytics_by_facility", compute)

    @staticmethod
    def get_tickets_by_section():
        """Ticket count per section with campus-prefixed display name."""
        def compute():
            rows = list(
                Section.objects
                .select_related("campus_department__campus")
                .annotate(ticket_count=Count("tickets"))
                .values(
                    "id",
                    "name",
                    "ticket_count",
                    campus_code=models.F("campus_department__campus__code"),
                )
                .order_by("-ticket_count")
            )
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "ticket_count": r["ticket_count"],
                    "display_name": (
                        f"{r['campus_code']}-{r['name']}"
                        if r.get("campus_code") else r["name"]
                    ),
                }
                for r in rows
            ]

        return get_cached("analytics_by_section", compute)
