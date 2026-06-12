from rest_framework import generics, serializers as drf_serializers, status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404

from apps.tickets.models import Ticket, TicketLog, TicketComment, TicketFeedback
from apps.tickets.serializers import (
    TicketCreateSerializer,
    TicketReadSerializer,
    TicketStatusUpdateSerializer,
    TicketAssignSerializer,
    TicketCommentSerializer,
    TicketFeedbackSerializer,
)
from apps.tickets.services.lifecycle import transition_status, TransitionError
from apps.tickets.services.scope import scoped_ticket_qs
from apps.common.pagination import AppendOnlyFeedPagination, TicketFeedPagination
from apps.common.permissions import get_request_role
from apps.realtime.ws_utils import (
    emit_ticket_created,
    emit_ticket_assigned,
    emit_comment_added,
)


class TicketLogSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = TicketLog
        fields = [
            "id", "event_type", "from_value", "to_value",
            "reason", "actor", "level_user", "created_at",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Phase 3 — kept intact
# ---------------------------------------------------------------------------

class TicketCreateView(CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        emit_ticket_created(ticket)
        return Response(
            {"id": ticket.id, "ticket_no": ticket.ticket_no},
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Phase 4 — lifecycle & interaction views
# ---------------------------------------------------------------------------

class TicketStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            transition_status(
                ticket,
                serializer.validated_data["status"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )
        except TransitionError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"ticket_no": ticket.ticket_no, "status": ticket.status}, status=200)


class TicketAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        serializer = TicketAssignSerializer(data=request.data, context={"ticket": ticket})
        serializer.is_valid(raise_exception=True)
        assignee = serializer.validated_data["assigned_to"]

        was_assigned = ticket.assigned_to_id is not None
        old_status = ticket.status

        ticket.assigned_to = assignee
        if old_status == "open":
            ticket.status = "assigned"
        ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        event_type = "reassigned" if was_assigned else "assigned"
        TicketLog.objects.create(
            ticket=ticket,
            actor=request.user,
            event_type=event_type,
            from_value=old_status if old_status == "open" else "",
            to_value=str(assignee.pk),
        )
        emit_ticket_assigned(ticket)

        return Response({"assigned_to": assignee.pk, "status": ticket.status}, status=200)


class TicketCommentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketCommentSerializer
    pagination_class = AppendOnlyFeedPagination

    def get_queryset(self):
        ticket = get_object_or_404(Ticket, pk=self.kwargs["pk"])
        qs = TicketComment.objects.filter(ticket=ticket).order_by("-created_at")
        if ticket.raised_by == self.request.user:
            qs = qs.filter(visibility="public")
        return qs

    def perform_create(self, serializer):
        ticket = get_object_or_404(Ticket, pk=self.kwargs["pk"])
        serializer.save(ticket=ticket, author=self.request.user)
        TicketLog.objects.create(
            ticket=ticket,
            actor=self.request.user,
            event_type="comment_added",
            to_value=str(serializer.instance.pk),
        )
        emit_comment_added(ticket, serializer.instance)


class TicketFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)

        if ticket.raised_by != request.user:
            raise PermissionDenied("Only the requester can submit feedback.")

        if ticket.status not in ("resolved", "closed"):
            return Response(
                {"detail": "Feedback can only be submitted once the ticket is resolved."},
                status=400,
            )

        if TicketFeedback.objects.filter(ticket=ticket).exists():
            return Response(
                {"detail": "Feedback has already been submitted."},
                status=409,
            )

        serializer = TicketFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save(ticket=ticket)

        TicketLog.objects.create(
            ticket=ticket,
            actor=request.user,
            event_type="rated",
            to_value=str(feedback.rating),
        )

        return Response(serializer.data, status=201)


class TicketLogListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketLogSerializer
    pagination_class = AppendOnlyFeedPagination

    def get_queryset(self):
        return TicketLog.objects.filter(ticket_id=self.kwargs["pk"]).order_by("-created_at")


# ---------------------------------------------------------------------------
# Phase 6 — scoped list + detail (§3.5, R15)
# ---------------------------------------------------------------------------

class TicketListCreateView(generics.ListCreateAPIView):
    """Role-scoped ticket list.

    GET  ?mine=1  → raised_by == user (any authenticated user, R15 universal requester).
    GET  (no ?mine) → role-scoped queryset; users with no role get an empty result.
    POST → create a new ticket (same as TicketCreateView).
    Filters: status, priority (id), section (id), current_level.
    Pagination: PageNumber ordered -updated_at (D6 / §3.7).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = TicketFeedPagination

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TicketCreateSerializer
        return TicketReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = serializer.save()
        emit_ticket_created(ticket)
        return Response(
            {"id": ticket.id, "ticket_no": ticket.ticket_no},
            status=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        user = self.request.user
        params = self.request.query_params

        if params.get("mine") == "1":
            qs = (
                Ticket.objects.filter(raised_by=user)
                .select_related(
                    "section__campus_department__department",
                    "section__campus_department__campus",
                    "section__section_type",
                    "section__hos",
                    "priority",
                    "service_item__category",
                    "assigned_to",
                    "raised_by",
                    "requester_campus",
                )
                .order_by("-updated_at")
            )
        else:
            role = get_request_role(self.request)
            qs = scoped_ticket_qs(user, role)

        # Apply optional filters. These narrow the already role-scoped queryset
        # (scope is never widened — out-of-scope ids simply match nothing).
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("priority"):
            qs = qs.filter(priority_id=params["priority"])
        if params.get("section"):
            qs = qs.filter(section_id=params["section"])
        if params.get("assigned_to"):
            qs = qs.filter(assigned_to_id=params["assigned_to"])
        if params.get("raised_by"):
            qs = qs.filter(raised_by_id=params["raised_by"])
        if params.get("current_level"):
            qs = qs.filter(current_level=params["current_level"])

        return qs


class TicketFilterOptionsView(APIView):
    """Scoped option lists for the tickets-table filters.

    Returns the sections, technicians (assignees) and requesters that actually
    appear in the caller's role-scoped tickets, so the filter dropdowns only
    offer values that can return results. Scope is derived server-side from the
    JWT role (never from client params) via ``scoped_ticket_qs`` — fail-closed.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _full_name(first, last, username):
        name = f"{first or ''} {last or ''}".strip()
        return name or username

    def get(self, request):
        role = get_request_role(request)
        scoped = scoped_ticket_qs(request.user, role)

        section_rows = (
            scoped.exclude(section__isnull=True)
            .values(
                "section_id",
                "section__section_type__name",
                "section__campus_department__campus__code",
            )
            .order_by()
            .distinct()
        )
        sections = sorted(
            (
                {
                    "id": r["section_id"],
                    "name": (
                        r["section__campus_department__campus__code"]
                        + " - "
                        + (r["section__section_type__name"] or f"Section {r['section_id']}")
                    ),
                }
                for r in section_rows
            ),
            key=lambda s: s["name"].lower(),
        )

        tech_rows = (
            scoped.exclude(assigned_to__isnull=True)
            .values(
                "assigned_to_id",
                "assigned_to__first_name",
                "assigned_to__last_name",
                "assigned_to__username",
            )
            .order_by()
            .distinct()
        )
        technicians = sorted(
            (
                {
                    "id": r["assigned_to_id"],
                    "name": self._full_name(
                        r["assigned_to__first_name"],
                        r["assigned_to__last_name"],
                        r["assigned_to__username"],
                    ),
                }
                for r in tech_rows
            ),
            key=lambda t: t["name"].lower(),
        )

        req_rows = scoped.values(
            "raised_by_id",
            "raised_by__first_name",
            "raised_by__last_name",
            "raised_by__username",
        ).order_by().distinct()
        requesters = sorted(
            (
                {
                    "id": r["raised_by_id"],
                    "name": self._full_name(
                        r["raised_by__first_name"],
                        r["raised_by__last_name"],
                        r["raised_by__username"],
                    ),
                }
                for r in req_rows
            ),
            key=lambda u: u["name"].lower(),
        )

        return Response(
            {"sections": sections, "technicians": technicians, "requesters": requesters}
        )


class TicketDetailView(generics.RetrieveAPIView):
    """Role-scoped ticket detail.

    Own ticket (raised_by == user) is always accessible — R15 universal requester.
    Staff can access tickets within their operational scope.
    Out-of-scope tickets return 403.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TicketReadSerializer

    def get_object(self):
        ticket = get_object_or_404(Ticket, pk=self.kwargs["pk"])
        user = self.request.user

        # Universal requester — own ticket always visible (R15).
        if ticket.raised_by_id == user.pk:
            return ticket

        # Staff — verify ticket is within their role scope.
        role = get_request_role(self.request)
        scoped = scoped_ticket_qs(user, role)
        if not scoped.filter(pk=ticket.pk).exists():
            raise PermissionDenied("You do not have access to this ticket.")

        return ticket


class AuditLogSerializer(drf_serializers.Serializer):
    id = drf_serializers.IntegerField(read_only=True)
    actor = drf_serializers.SerializerMethodField()
    action = drf_serializers.SerializerMethodField()
    target_type = drf_serializers.SerializerMethodField()
    ticket_no = drf_serializers.SerializerMethodField()
    priority = drf_serializers.SerializerMethodField()
    department = drf_serializers.SerializerMethodField()
    detail = drf_serializers.SerializerMethodField()
    reason = drf_serializers.SerializerMethodField()
    created_at = drf_serializers.DateTimeField(read_only=True)

    def get_actor(self, obj):
        return obj.actor.username if obj.actor else None

    def get_action(self, obj):
        return obj.event_type

    def get_target_type(self, obj):
        return "ticket"

    def get_ticket_no(self, obj):
        return obj.ticket.ticket_no if obj.ticket else None

    def get_priority(self, obj):
        return obj.ticket.priority.name if obj.ticket and obj.ticket.priority else None

    def get_department(self, obj):
        if obj.ticket and obj.ticket.section:
            return obj.ticket.section.campus_department.department.name
        return None

    def get_detail(self, obj):
        parts = []
        if obj.from_value:
            parts.append(f"from: {obj.from_value}")
        if obj.to_value:
            parts.append(f"to: {obj.to_value}")
        return " | ".join(parts) if parts else ""

    def get_reason(self, obj):
        return obj.reason or ""


class AdminAuditLogView(generics.ListAPIView):
    """Admin-only system audit log (all TicketLog entries).

    GET /api/v1/admin/audit-log/?page=1&page_size=20
    Optional filters: actor, action, target_type, date_from, date_to
    """

    permission_classes = [IsAuthenticated]
    serializer_class = AuditLogSerializer
    pagination_class = TicketFeedPagination

    def get_queryset(self):
        user = self.request.user
        if not user.is_staff:
            return TicketLog.objects.none()

        qs = (
            TicketLog.objects.select_related(
                "actor",
                "ticket",
                "ticket__priority",
                "ticket__section",
                "ticket__section__campus_department",
                "ticket__section__campus_department__department",
            )
            .order_by("-created_at")
        )

        params = self.request.query_params
        if actor := params.get("actor"):
            qs = qs.filter(actor__username__icontains=actor)
        if action := params.get("action"):
            qs = qs.filter(event_type=action)
        if target_type := params.get("target_type"):
            if target_type != "ticket":
                return TicketLog.objects.none()
        if date_from := params.get("date_from"):
            qs = qs.filter(created_at__gte=date_from)
        if date_to := params.get("date_to"):
            qs = qs.filter(created_at__lte=date_to)

        return qs
