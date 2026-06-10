from rest_framework import generics, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import ServiceCategory, ServiceItem
from apps.catalog.serializers import ServiceCategorySerializer, ServiceItemSerializer
from apps.catalog.services.visibility import get_visible_categories
from apps.common.pagination import ConfigListPagination
from apps.common.permissions import IsAdminGroup


class CatalogTreeView(generics.ListAPIView):
    """GET /catalog/?campus=<id>
    Returns R5-filtered categories + nested items for the given campus.
    Any authenticated user may call this (used in the ticket create wizard).
    campus param is required — returns 400 when missing.
    """

    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ConfigListPagination

    def get_queryset(self):
        campus_id = self.request.query_params.get("campus")
        if not campus_id:
            return ServiceCategory.objects.none()
        return get_visible_categories(campus_id)

    def list(self, request, *args, **kwargs):
        if not request.query_params.get("campus"):
            return Response(
                {"detail": "campus query parameter is required."},
                status=400,
            )
        return super().list(request, *args, **kwargs)


class ServiceCategoryViewSet(viewsets.ModelViewSet):
    """Admin CRUD for service categories.

    Supports ?section_type=<id> filter to scope results to one section type.
    """

    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAdminGroup]
    pagination_class = None  # return plain list so frontend doesn't need to unwrap

    def get_queryset(self):
        qs = (
            ServiceCategory.objects.select_related(
                "section_type__department", "default_priority"
            )
            .prefetch_related("service_items__default_priority")
            .order_by("section_type", "name")
        )
        section_type_id = self.request.query_params.get("section_type")
        if section_type_id:
            qs = qs.filter(section_type_id=section_type_id)
        return qs


class ServiceItemViewSet(viewsets.ModelViewSet):
    """Admin CRUD for service items."""

    queryset = ServiceItem.objects.select_related(
        "category__section_type", "default_priority"
    ).order_by("category", "name")
    serializer_class = ServiceItemSerializer
    permission_classes = [IsAdminGroup]
    pagination_class = ConfigListPagination
