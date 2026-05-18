"""HOD dashboard — consolidated endpoint combining analytics, sections, technicians, and ticket summary."""

from django.db.models import Count, F, Q
from django.db.models.functions import Concat
from django.utils.text import slugify
from django.db.models import Value
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.hod_analytics import HODAnalytics
from tickets.models import Ticket, CustomUser, Section


class HODDashboardView(APIView):
    """GET /api/hod/me/dashboard/

    Consolidated HOD dashboard combining:
    - Analytics for the HOD's CampusDepartment
    - Sections under the CampusDepartment
    - Technicians assigned to those sections
    - Ticket summary counts by status

    Permission:
        hod     → own CampusDepartment data only
        admin   → can pass ?user_id=<pk> to inspect any HOD
        others  → 403

    Query params:
        days    — lookback window for analytics (default: 30, max: 365)
        user_id — (admin only) inspect a different HOD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_user = user

        # Admin can query any HOD via ?user_id=
        if user.role == "admin":
            user_id = request.query_params.get("user_id")
            if user_id:
                target_user = get_object_or_404(CustomUser, pk=user_id, role="hod")
        elif user.role != "hod":
            return Response({"detail": "HOD role required."}, status=403)

        # Parse days parameter
        try:
            days = int(request.query_params.get("days", 30))
            days = max(1, min(days, 365))
        except (TypeError, ValueError):
            days = 30

        # Get analytics (cached)
        analytics = HODAnalytics.hod_dashboard(target_user, days=days)

        # Get CampusDepartment
        campus_dept = target_user.primary_campus_department
        sections = []
        technicians = []
        tickets_summary = {}

        if campus_dept:
            # Get all sections under this CampusDepartment
            section_qs = Section.objects.filter(
                campus_department=campus_dept
            ).select_related("section_type")

            sections = list(
                section_qs.values(
                    "id",
                    "name",
                    "code",
                    section_type_name=F("section_type__name"),
                )
            )

            section_ids = [s["id"] for s in sections]

            # Count tickets by status
            status_counts = dict(
                Ticket.objects.filter(section__in=section_ids)
                .values_list("status")
                .annotate(count=Count("id"))
                .values_list("status", "count")
            )
            tickets_summary = status_counts

            # Get technicians assigned to these sections
            technicians = list(
                CustomUser.objects.filter(
                    sections__in=section_ids,
                    is_active=True,
                    role="technician",
                )
                .distinct()
                .values(
                    "id",
                    "username",
                    name=Concat("first_name", Value(" "), "last_name"),
                )
            )

        return Response({
            **analytics,
            "sections": sections,
            "technicians": technicians,
            "tickets_summary": tickets_summary,
        })
