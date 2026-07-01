from django.db.models import Count, IntegerField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.common.pagination import ConfigListPagination
from apps.common.permissions import IsAdminGroup
from apps.facilities.models import Facility, FacilityType
from apps.facilities.serializers import FacilitySerializer, FacilityTypeSerializer

_OPEN_STATUSES = ["open", "assigned", "in_progress", "pending"]


def _ticket_count_subq(status_filter: Q):
    """Subquery counting TicketLocation rows for a given ticket status filter.

    Uses a subquery rather than a reverse annotation because
    TicketLocation.facility uses related_name="+".
    """
    from apps.tickets.models import TicketLocation

    return Coalesce(
        Subquery(
            TicketLocation.objects.filter(facility=OuterRef("pk"))
            .filter(status_filter)
            .values("facility")
            .annotate(c=Count("id"))
            .values("c"),
            output_field=IntegerField(),
        ),
        0,
    )


class FacilityTypeViewSet(ReadOnlyModelViewSet):
    """FacilityType is a fixed seeded set (D9) — read-only via API.
    Any authenticated user can read (needed for location form setup)."""

    queryset = FacilityType.objects.all().order_by("name")
    serializer_class = FacilityTypeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigListPagination


class FacilityViewSet(viewsets.ModelViewSet):
    """Admin CRUD for the Facility registry (buildings per campus).
    GET /facilities/?campus=&facility_type= is open to any authenticated user
    for the ticket creation location dropdown (§5.3)."""

    serializer_class = FacilitySerializer
    pagination_class = ConfigListPagination

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAdminGroup()]

    def get_queryset(self):
        qs = (
            Facility.objects.select_related("campus", "facility_type")
            .annotate(
                open_ticket_count=_ticket_count_subq(
                    Q(ticket__status__in=_OPEN_STATUSES)
                ),
                resolved_ticket_count=_ticket_count_subq(Q(ticket__status="resolved")),
                closed_ticket_count=_ticket_count_subq(Q(ticket__status="closed")),
            )
            .order_by("campus", "name")
        )
        campus = self.request.query_params.get("campus")
        facility_type = self.request.query_params.get("facility_type")
        if campus:
            qs = qs.filter(campus_id=campus)
        if facility_type:
            qs = qs.filter(facility_type__code=facility_type)
        return qs
