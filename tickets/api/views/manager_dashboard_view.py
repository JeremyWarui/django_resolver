"""Manager dashboard — consolidated endpoint combining analytics, department info, and ticket summary."""

from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.manager_analytics import ManagerAnalytics
from tickets.models import Ticket, CustomUser


class ManagerDashboardView(APIView):
    """GET /api/manager/me/dashboard/

    Consolidated Manager dashboard combining:
    - Analytics for the manager's Department (cross-campus)
    - Department information
    - Ticket summary counts by status

    Permission:
        manager → own Department data only
        admin   → can pass ?user_id=<pk> to inspect any Manager
        others  → 403

    Query params:
        days    — lookback window for analytics (default: 30, max: 365)
        user_id — (admin only) inspect a different Manager
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_user = user

        # Admin can query any Manager via ?user_id=
        if user.role == "admin":
            user_id = request.query_params.get("user_id")
            if user_id:
                target_user = get_object_or_404(CustomUser, pk=user_id, role="manager")
        elif user.role != "manager":
            return Response({"detail": "Manager role required."}, status=403)

        # Parse days parameter
        try:
            days = int(request.query_params.get("days", 30))
            days = max(1, min(days, 365))
        except (TypeError, ValueError):
            days = 30

        # Get analytics (cached)
        analytics = ManagerAnalytics.manager_dashboard(target_user, days=days)

        # Get department information
        dept = target_user.primary_department
        tickets_summary = {}

        if dept:
            # Count tickets by status across all department tickets
            status_counts = dict(
                Ticket.objects.filter(
                    section__campus_department__department=dept
                )
                .values_list("status")
                .annotate(count=Count("id"))
                .values_list("status", "count")
            )
            tickets_summary = status_counts

        return Response({
            **analytics,
            "department": {
                "id": dept.id if dept else None,
                "name": dept.name if dept else None,
            },
            "tickets_summary": tickets_summary,
        })
