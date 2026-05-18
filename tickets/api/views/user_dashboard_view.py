"""User dashboard — consolidated endpoint for end-user ticket summary and recent tickets."""

from django.db.models import Count, F
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.user_analytics import UserAnalytics
from tickets.models import Ticket


class UserDashboardView(APIView):
    """GET /api/user/me/dashboard/

    Consolidated User dashboard combining:
    - User analytics (ticket counts, resolution rates)
    - Recent tickets (last 10 raised by user)
    - Ticket summary counts by status

    Permission:
        All authenticated users (scoped to request.user)

    No query params.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get analytics (cached)
        analytics = UserAnalytics.for_user(user)

        # Get recent tickets raised by this user
        recent_tickets = list(
            Ticket.objects.filter(raised_by=user)
            .select_related(
                "campus_department__campus",
                "section",
            )
            .order_by("-created_at")[:10]
            .values(
                "id",
                "ticket_no",
                "title",
                "status",
                "priority",
                "created_at",
                campus=F("campus_department__campus__code"),
                section_name=F("section__name"),
            )
        )

        # Count tickets by status
        status_counts = dict(
            Ticket.objects.filter(raised_by=user)
            .values_list("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        return Response({
            **analytics,
            "recent_tickets": recent_tickets,
            "tickets_summary": status_counts,
        })
