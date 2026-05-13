"""Service catalogue views — ServiceCategory, ServiceItem, SectionType."""

from rest_framework import generics
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
    ListAPIView,
)
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Prefetch
from rest_framework.filters import OrderingFilter

from tickets.api.permissions import IsAdminOrReadOnly
from tickets.serializers import (
    SectionTypeSerializer,
    ServiceCategorySerializer,
    ServiceItemSerializer,
)
from tickets.models import SectionType, ServiceCategory, ServiceItem


class SectionTypeDetailView(generics.RetrieveAPIView):
    """Retrieve a specific section type with all its service categories and items."""

    queryset = SectionType.objects.prefetch_related(
        Prefetch(
            "service_categories",
            ServiceCategory.objects.prefetch_related("service_items"),
        )
    )
    serializer_class = SectionTypeSerializer
    permission_classes = [IsAuthenticated]


class ServiceCategoryListCreateView(ListCreateAPIView):
    """GET /service-categories/ — list. POST — admin only.

    POST body: { section_type_id, name, description, icon, order, is_active }
    """

    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["section_type"]
    ordering_fields = ["order", "name"]
    ordering = ["order", "name"]

    def get_queryset(self):
        return ServiceCategory.objects.select_related("section_type").prefetch_related(
            "service_items"
        )


class ServiceCategoryDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT/DELETE /service-categories/<pk>/ — writes are admin only."""

    queryset = ServiceCategory.objects.select_related("section_type").prefetch_related(
        "service_items"
    )
    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


class ServiceItemListCreateView(ListCreateAPIView):
    """GET /service-items/ — list. POST — admin only.

    POST body: { category_id, name, description, sla_hours, requires_approval,
                 form_schema, default_priority, order, is_active }
    """

    serializer_class = ServiceItemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["category", "category__section_type", "is_active"]
    ordering_fields = ["order", "name", "sla_hours"]
    ordering = ["category", "order", "name"]

    def get_queryset(self):
        return ServiceItem.objects.select_related("category__section_type")


class ServiceItemDetailView(RetrieveUpdateDestroyAPIView):
    """GET/PATCH/PUT/DELETE /service-items/<pk>/ — writes are admin only."""

    queryset = ServiceItem.objects.select_related("category__section_type")
    serializer_class = ServiceItemSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]


class ServiceCategoriesBySectionTypeView(ListAPIView):
    """GET /section-types/<pk>/categories/ — active categories for a section type."""

    serializer_class = ServiceCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            ServiceCategory.objects.filter(
                section_type_id=self.kwargs["pk"],
                is_active=True,
            )
            .prefetch_related("service_items")
            .order_by("order", "name")
        )


class ServiceItemsByCategoryView(ListAPIView):
    """GET /categories/<pk>/items/ — active service items for a category."""

    serializer_class = ServiceItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ServiceItem.objects.filter(
            category_id=self.kwargs["pk"],
            is_active=True,
        ).order_by("order", "name")
