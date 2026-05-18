"""Technician dashboard — consolidated endpoint combining profile, KPIs, sections, and ticket queues."""

from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.technician_analytics import TechnicianAnalytics
from tickets.models import Ticket, CustomUser
from tickets.api.analytics.base_analytics import ACTIVE_STATUSES


def _serialize_ticket(ticket):
    """Serialize ticket for dashboard display."""
    escalation_status_map = {
        0: {"code": "none", "label": "None"},
        1: {"code": "section_head", "label": "Section Head"},
        2: {"code": "hod", "label": "Head of Department"},
        3: {"code": "manager", "label": "Manager"},
    }

    return {
        "id": ticket.id,
        "ticket_no": ticket.ticket_no,
        "title": ticket.title,
        "status": ticket.status,
        "priority": ticket.priority,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
        "due_date": ticket.due_date.isoformat() if ticket.due_date else None,
        "campus": ticket.campus_department.campus.code if ticket.campus_department else None,
        "section_name": ticket.section.name if ticket.section else None,
        "raised_by": ticket.raised_by.username if ticket.raised_by else None,
        "pending_reason": ticket.pending_reason,
        "pending_comment": ticket.pending_comment,
        "escalation_level": ticket.escalation_level or 0,
        "escalation_status": escalation_status_map.get(ticket.escalation_level or 0, {"code": "none", "label": "None"}),
        "is_due_for_escalation": ticket.is_due_for_escalation(),
        "service_item": {
            "id": ticket.service_item.id,
            "name": ticket.service_item.name,
            "requires_approval": ticket.service_item.requires_approval,
        } if ticket.service_item else None,
    }


class TechnicianDashboardView(APIView):
    """GET /api/technicians/me/dashboard/

    Consolidated technician dashboard combining:
    - Technician profile and KPIs
    - Assigned sections
    - Assigned tickets
    - Section queue stats

    Permission:
        technician  → own data only
        head_of_section → can query own data
        admin       → can pass ?user_id=<pk> to inspect any technician
        others      → 403
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        target_user = user

        # Admin can query any technician via ?user_id=
        if user.role == "admin":
            user_id = request.query_params.get("user_id")
            if user_id:
                target_user = get_object_or_404(CustomUser, pk=user_id, role="technician")
        elif user.role not in ("technician", "head_of_section"):
            return Response({"detail": "Insufficient permissions."}, status=403)

        # Get analytics (cached)
        analytics = TechnicianAnalytics.for_technician(target_user)

        # Get assigned tickets (active status only)
        assigned_qs = (
            Ticket.objects
            .filter(assigned_to=target_user, status__in=ACTIVE_STATUSES)
            .select_related(
                "campus_department__campus",
                "section",
                "raised_by",
                "service_item",
            )
            .order_by("-updated_at")
        )

        # Get section IDs for this technician
        section_ids = list(target_user.sections.values_list("id", flat=True))

        # Count tickets by status across all sections
        status_counts = dict(
            Ticket.objects.filter(section__in=section_ids)
            .values_list("status")
            .annotate(count=Count("id"))
            .values_list("status", "count")
        )

        # Count unassigned tickets in sections
        unassigned_count = Ticket.objects.filter(
            section__in=section_ids, assigned_to__isnull=True, status__in=ACTIVE_STATUSES
        ).count()

        return Response({
            "technician": analytics.get("technician", {}),
            "kpis": analytics.get("kpis", {}),
            "sections": analytics.get("sections", []),
            "assigned_tickets": [_serialize_ticket(t) for t in assigned_qs],
            "section_queue": {
                "unassigned_count": unassigned_count,
                "tickets_by_status": status_counts,
            },
        })
