"""Ticket analytics - basic ticket metrics and trends."""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache
from django.db.models import Count
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth

from tickets.models import Ticket, Facility, Section

ANALYTICS_CACHE_TTL = 300


class TicketAnalytics:
    """Provides analytics for tickets in the system."""

    @staticmethod
    def get_ticket_counts_by_timeframe(days=1, facility_id=None, section_id=None):
        """Get ticket count for a specific timeframe."""
        cache_key = f"analytics_timeframe_{days}_{facility_id}_{section_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        time_threshold = timezone.now() - timedelta(days=days)
        queryset = Ticket.objects.filter(created_at__gte=time_threshold)
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        result = {
            "period": f"Last {days} day{'s' if days > 1 else ''}",
            "count": queryset.count(),
        }
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_ticket_counts_by_status(facility_id=None, section_id=None):
        """Get ticket count breakdown by status."""
        cache_key = f"analytics_status_{facility_id}_{section_id}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        queryset = Ticket.objects.all()
        if facility_id:
            queryset = queryset.filter(facility_id=facility_id)
        if section_id:
            queryset = queryset.filter(section_id=section_id)

        result = list(
            queryset.values("status").annotate(count=Count("id")).order_by("status")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_ticket_trend_data(days=30, group_by="day"):
        """Get ticket trend data over time."""
        cache_key = f"analytics_trend_{days}_{group_by}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        time_threshold = timezone.now() - timedelta(days=days)
        trunc_map = {
            "week": TruncWeek("created_at"),
            "month": TruncMonth("created_at"),
        }
        trunc_func = trunc_map.get(group_by, TruncDay("created_at"))

        result = list(
            Ticket.objects.filter(created_at__gte=time_threshold)
            .annotate(period=trunc_func)
            .values("period")
            .annotate(count=Count("id"))
            .order_by("period")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_tickets_by_facility():
        """Get ticket counts grouped by facility."""
        cache_key = "analytics_by_facility"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = list(
            Facility.objects.annotate(ticket_count=Count("tickets"))
            .values("name", "ticket_count")
            .order_by("-ticket_count")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result

    @staticmethod
    def get_tickets_by_section():
        """Get ticket counts grouped by section."""
        cache_key = "analytics_by_section"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        result = list(
            Section.objects.annotate(ticket_count=Count("tickets"))
            .values("name", "ticket_count")
            .order_by("-ticket_count")
        )
        cache.set(cache_key, result, ANALYTICS_CACHE_TTL)
        return result
