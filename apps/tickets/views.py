from rest_framework import generics, serializers as drf_serializers, status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404

import os

from django.core.files.base import ContentFile

from apps.tickets.models import (
    Ticket,
    TicketAttachment,
    TicketLog,
    TicketComment,
    TicketFeedback,
)
from apps.tickets.serializers import (
    TicketCreateSerializer,
    TicketReadSerializer,
    TicketDetailReadSerializer,
    TicketStatusUpdateSerializer,
    TicketAssignSerializer,
    TicketCommentSerializer,
    TicketFeedbackSerializer,
    TicketAttachmentSerializer,
    _UserMinSerializer,
)
from apps.tickets.services.attachments import (
    process_upload,
    MAX_ATTACHMENTS_PER_TICKET,
    MIME_TO_EXT,
)
from apps.tickets.services.lifecycle import (
    claim_ticket,
    transition_status,
    TransitionError,
)
from apps.tickets.services.scope import scoped_ticket_qs
from apps.common.pagination import AppendOnlyFeedPagination, TicketFeedPagination
from apps.common.permissions import get_request_role
from apps.realtime.ws_utils import (
    emit_ticket_created,
    emit_ticket_assigned,
    emit_comment_added,
)

# Roles that may perform staff actions (assign, etc.) on in-scope tickets.
STAFF_ROLES = ("admin", "manager", "hod", "hos", "technician")


def get_ticket_for_request_or_403(
    request, pk, *, allow_requester=True, staff_only=False, qs=None
):
    """Fetch a ticket and verify the caller may act on it (IDOR guard).

    Mirrors TicketDetailView semantics: the requester's own ticket is always
    accessible when ``allow_requester`` (R15 universal requester); otherwise the
    ticket must fall inside the caller's role scope — fail closed with 403.

    ``staff_only`` additionally rejects non-staff roles even for in-scope
    tickets: a requester's own ticket is inside the ``user`` role scope, but
    actions like assignment are staff-only.
    """
    ticket = get_object_or_404(qs if qs is not None else Ticket, pk=pk)

    if allow_requester and ticket.raised_by_id == request.user.pk:
        return ticket

    role = get_request_role(request)
    if staff_only and role not in STAFF_ROLES:
        raise PermissionDenied("You do not have permission to perform this action.")
    if not scoped_ticket_qs(request.user, role).filter(pk=ticket.pk).exists():
        raise PermissionDenied("You do not have access to this ticket.")
    return ticket


class TicketLogSerializer(drf_serializers.ModelSerializer):
    actor = _UserMinSerializer(read_only=True, allow_null=True)
    level_user = _UserMinSerializer(read_only=True, allow_null=True)

    class Meta:
        model = TicketLog
        fields = [
            "id",
            "event_type",
            "from_value",
            "to_value",
            "reason",
            "actor",
            "level_user",
            "created_at",
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

    # Transitions the requester may drive on their own ticket: Rate & Close
    # (resolved → closed) and Reopen (resolved/closed → open). Target-status
    # legality against the current status stays with the lifecycle ALLOWED map.
    REQUESTER_TARGETS = ("closed", "open")

    def post(self, request, pk):
        ticket = get_ticket_for_request_or_403(request, pk)
        serializer = TicketStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Per-role transition gate (QA B1b). Supervisors in scope are
        # unrestricted; a technician may only act on tickets assigned to
        # *them* (section scope alone gives view-only); the requester may
        # only close or reopen their own ticket.
        role = get_request_role(request)
        is_assigned_tech = (
            role == "technician" and ticket.assigned_to_id == request.user.pk
        )
        is_supervisor = role in ("admin", "manager", "hod", "hos")
        is_requester = ticket.raised_by_id == request.user.pk
        if not (is_supervisor or is_assigned_tech):
            if not (
                is_requester
                and serializer.validated_data["status"] in self.REQUESTER_TARGETS
            ):
                raise PermissionDenied(
                    "You do not have permission to change this ticket's status."
                )

        try:
            transition_status(
                ticket,
                serializer.validated_data["status"],
                actor=request.user,
                reason=serializer.validated_data.get("reason", ""),
            )
        except TransitionError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(
            {"ticket_no": ticket.ticket_no, "status": ticket.status}, status=200
        )


class TicketAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        ticket = get_ticket_for_request_or_403(
            request,
            pk,
            allow_requester=False,
            staff_only=True,
            qs=Ticket.objects.select_related("service_item", "assigned_to"),
        )
        serializer = TicketAssignSerializer(
            data=request.data, context={"ticket": ticket}
        )
        serializer.is_valid(raise_exception=True)
        assignee = serializer.validated_data["assigned_to"]

        previous_assignee = (
            ticket.assigned_to
        )  # loaded via select_related before overwrite
        old_status = ticket.status

        ticket.assigned_to = assignee
        if old_status == "open":
            ticket.status = "assigned"
        ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        event_type = "reassigned" if previous_assignee is not None else "assigned"
        TicketLog.objects.create(
            ticket=ticket,
            actor=request.user,
            event_type=event_type,
            from_value=(
                (previous_assignee.get_full_name() or previous_assignee.username)
                if previous_assignee is not None
                else ""
            ),
            to_value=assignee.get_full_name() or assignee.username,
        )
        emit_ticket_assigned(ticket, previous_assignee=previous_assignee)

        return Response(
            {"assigned_to": assignee.pk, "status": ticket.status}, status=200
        )


class TicketClaimView(APIView):
    """POST /tickets/{pk}/claim/ — technician self-assigns an unassigned open
    ticket in one of their sections (QA B2a).

    Scope: technician role only; the IDOR guard's scoped queryset already
    restricts technicians to their SectionTechnician sections. Race-safe via
    select_for_update — of two simultaneous claims exactly one wins.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.db import transaction

        if get_request_role(request) != "technician":
            raise PermissionDenied("Only technicians may claim tickets.")

        try:
            with transaction.atomic():
                ticket = get_ticket_for_request_or_403(
                    request,
                    pk,
                    allow_requester=False,
                    qs=Ticket.objects.select_for_update(),
                )
                claim_ticket(ticket, request.user)
        except TransitionError as e:
            return Response({"detail": str(e)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {
                "ticket_no": ticket.ticket_no,
                "status": ticket.status,
                "assigned_to": request.user.pk,
            },
            status=200,
        )


class TicketCommentListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketCommentSerializer
    pagination_class = AppendOnlyFeedPagination

    def get_queryset(self):
        ticket = get_ticket_for_request_or_403(self.request, self.kwargs["pk"])
        qs = TicketComment.objects.filter(ticket=ticket).order_by("-created_at")
        if ticket.raised_by == self.request.user:
            qs = qs.filter(visibility="public")
        return qs

    def perform_create(self, serializer):
        ticket = get_ticket_for_request_or_403(self.request, self.kwargs["pk"])

        # Comment gating (QA B1): comments open only once a technician is
        # assigned and close permanently with the ticket — for every role.
        # Among technicians, only the assignee may comment (unless they are
        # the requester themselves); supervisors in scope may comment once
        # the ticket is assigned. Read access stays scope-only.
        if ticket.status == "closed":
            raise drf_serializers.ValidationError(
                {"detail": "Comments are disabled on a closed ticket."}
            )
        if ticket.assigned_to_id is None:
            raise drf_serializers.ValidationError(
                {"detail": "Comments open once a technician is assigned."}
            )
        role = get_request_role(self.request)
        is_requester = ticket.raised_by_id == self.request.user.pk
        if (
            role == "technician"
            and not is_requester
            and ticket.assigned_to_id != self.request.user.pk
        ):
            raise PermissionDenied(
                "Only the assigned technician may comment on this ticket."
            )

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
                {
                    "detail": "Feedback can only be submitted once the ticket is resolved."
                },
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
        ticket = get_ticket_for_request_or_403(self.request, self.kwargs["pk"])
        return (
            TicketLog.objects.filter(ticket=ticket)
            .select_related("actor", "level_user")
            .order_by("-created_at")
        )


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
                    "location__facility_type",
                    "location__facility",
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
                        + (
                            r["section__section_type__name"]
                            or f"Section {r['section_id']}"
                        )
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

        req_rows = (
            scoped.values(
                "raised_by_id",
                "raised_by__first_name",
                "raised_by__last_name",
                "raised_by__username",
            )
            .order_by()
            .distinct()
        )
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
    serializer_class = TicketDetailReadSerializer

    def get_object(self):
        return get_ticket_for_request_or_403(
            self.request,
            self.kwargs["pk"],
            qs=Ticket.objects.select_related(
                "section__campus_department__department",
                "section__campus_department__campus",
                "section__section_type",
                "priority",
                "service_item__category",
                "assigned_to",
                "raised_by",
                "requester_campus",
                "location__facility_type",
                "location__facility",
                "feedback",
            ),
        )


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


class TicketAttachmentView(APIView):
    """Upload, list, and delete attachments on a ticket.

    GET  /api/v1/tickets/<pk>/attachments/          — list attachments
    POST /api/v1/tickets/<pk>/attachments/          — upload file(s) (multipart)
    DELETE /api/v1/tickets/<pk>/attachments/<att>/  — delete one attachment
    """

    permission_classes = [IsAuthenticated]

    def _get_ticket(self, request, pk):
        return get_ticket_for_request_or_403(request, pk)

    def get(self, request, pk):
        ticket = self._get_ticket(request, pk)
        qs = ticket.attachments.select_related("uploaded_by")
        serializer = TicketAttachmentSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(serializer.data)

    def post(self, request, pk):
        ticket = self._get_ticket(request, pk)

        current_count = ticket.attachments.count()
        if current_count >= MAX_ATTACHMENTS_PER_TICKET:
            return Response(
                {
                    "detail": f"Maximum {MAX_ATTACHMENTS_PER_TICKET} attachments per ticket."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        files = request.FILES.getlist("files") or (
            [request.FILES["file"]] if "file" in request.FILES else []
        )
        if not files:
            return Response(
                {"detail": "No file(s) provided. Use 'files' or 'file' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        slots_left = MAX_ATTACHMENTS_PER_TICKET - current_count
        if len(files) > slots_left:
            return Response(
                {"detail": f"Only {slots_left} attachment slot(s) remaining."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.core.exceptions import ValidationError as DjangoValidationError

        created = []
        for f in files:
            content_type = f.content_type or "application/octet-stream"
            try:
                processed_bytes, final_mime = process_upload(f, content_type)
            except DjangoValidationError as exc:
                return Response(
                    {"detail": str(exc.message)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            ext = MIME_TO_EXT.get(final_mime, os.path.splitext(f.name)[1].lower())
            base_name = os.path.splitext(f.name)[0]
            stored_name = f"{base_name}{ext}"

            attachment = TicketAttachment(
                ticket=ticket,
                original_name=f.name,
                mime_type=final_mime,
                original_size=f.size,
                stored_size=len(processed_bytes),
                uploaded_by=request.user,
            )
            attachment.file.save(stored_name, ContentFile(processed_bytes), save=False)
            attachment.save()
            created.append(attachment)

        serializer = TicketAttachmentSerializer(
            created, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, att_id):
        ticket = self._get_ticket(request, pk)
        attachment = get_object_or_404(TicketAttachment, pk=att_id, ticket=ticket)

        is_uploader = attachment.uploaded_by_id == request.user.pk
        is_privileged = request.user.is_staff or get_request_role(request) in (
            "admin",
            "manager",
            "hod",
            "hos",
        )
        if not (is_uploader or is_privileged):
            raise PermissionDenied("You can only delete your own attachments.")

        attachment.file.delete(save=False)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


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

        qs = TicketLog.objects.select_related(
            "actor",
            "ticket",
            "ticket__priority",
            "ticket__section",
            "ticket__section__campus_department",
            "ticket__section__campus_department__department",
        ).order_by("-created_at")

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
