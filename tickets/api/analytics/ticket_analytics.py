"""Ticket analytics - basic ticket metrics and trends."""

from django.db import models
from django.db.models import Count

from tickets.models import Ticket, Facility, Section
from .base_analytics import (
    ANALYTICS_CACHE_TTL,
    get_cached,
    get_status_distribution,
    get_ticket_trend_data as _get_ticket_trend_data,
)


class TicketAnalytics:
    """Provides analytics for tickets in the system."""

    @staticmethod
    def get_ticket_counts_by_timeframe(days=1, facility_id=None, section_id=None):
        from datetime import timedelta
        from django.utils import timezone

        def compute():
            time_threshold = timezone.now() - timedelta(days=days)
            queryset = Ticket.objects.filter(created_at__gte=time_threshold)
            if facility_id:
                queryset = queryset.filter(facility_id=facility_id)
            if section_id:
                queryset = queryset.filter(section_id=section_id)
            return {
                "period": f"Last {days} day{'s' if days > 1 else ''}",
                "count": queryset.count(),
            }

        return get_cached(f"analytics_timeframe_{days}_{facility_id}_{section_id}", compute)

    @staticmethod
    def get_ticket_counts_by_status(facility_id=None, section_id=None):
        def compute():
            queryset = Ticket.objects.all()
            if facility_id:
                queryset = queryset.filter(facility_id=facility_id)
            if section_id:
                queryset = queryset.filter(section_id=section_id)
            return get_status_distribution(queryset, order_by="status")

        return get_cached(f"analytics_status_{facility_id}_{section_id}", compute)

    @staticmethod
    def get_ticket_trend_data(days=30, group_by="day"):
        return get_cached(
            f"analytics_trend_{days}_{group_by}",
            lambda: _get_ticket_trend_data(days=days, group_by=group_by),
        )

    @staticmethod
    def get_tickets_by_facility():
        def compute():
            return list(
                Facility.objects.annotate(ticket_count=Count("tickets"))
                .values("name", "ticket_count")
                .order_by("-ticket_count")
            )

        return get_cached("analytics_by_facility", compute)

    @staticmethod
    def get_tickets_by_section():
        def compute():
            rows = list(
                Section.objects.select_related("department__campus")
                .annotate(ticket_count=Count("tickets"))
                .values("name", "ticket_count", campus_code=models.F("department__campus__code"))
                .order_by("-ticket_count")
            )
            return [
                {
                    "name": r["name"],
                    "ticket_count": r["ticket_count"],
                    "display_name": (
                        f"{r['campus_code']}-{r['name']}" if r.get("campus_code") else r["name"]
                    ),
                }
                for r in rows
            ]

        return get_cached("analytics_by_section", compute)
