"""Section Head dashboard — consolidated endpoint combining analytics, sections, technicians, and ticket summary."""

from django.db.models import Count, F, Q
from django.db.models.functions import Concat
from django.db.models import Value
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.section_head_analytics import SectionHeadAnalytics
from tickets.models import Ticket, CustomUser, Section


class SectionHeadDashboardView(APIView):
    """GET /api/section-head/me/dashboard/

    Consolidated Section Head dashboard combining:
    - Analytics for all sections the HOS heads
    - Sections this HOS is assigned to
    - Technicians assigned to those sections
    - Ticket summary counts by status

    Permission:
        head_of_section → own sections data only
        admin           → can pass ?user_id=<pk> to inspect any Section Head
        others          → 403

    Query params:
        days    — lookback window for analytics (default: 30, max: 365)
        user_id — (admin only) inspect a different Section Head
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_user = user

        # Admin can query any Section Head via ?user_id=
        if user.role == "admin":
            user_id = request.query_params.get("user_id")
            if user_id:
                target_user = get_object_or_404(CustomUser, pk=user_id, role="head_of_section")
        elif user.role != "head_of_section":
            return Response({"detail": "Section head role required."}, status=403)

        # Parse days parameter
        try:
            days = int(request.query_params.get("days", 30))
            days = max(1, min(days, 365))
        except (TypeError, ValueError):
            days = 30

        # Get analytics (cached)
        analytics = SectionHeadAnalytics.section_head_dashboard(target_user, days=days)

        # Get sections this HOS heads
        sections_qs = Section.objects.filter(
            head_of_section=target_user
        ).select_related(
            "section_type",
            "campus_department__campus",
        )

        sections = list(
            sections_qs.values(
                "id",
                "name",
                "code",
                campus=F("campus_department__campus__code"),
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
            "tickets_summary": status_counts,
        })
