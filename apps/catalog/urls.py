from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.catalog.views import CatalogTreeView, ServiceCategoryViewSet, ServiceItemViewSet

router = DefaultRouter()
router.register("service-categories", ServiceCategoryViewSet, basename="servicecategory")
router.register("service-items", ServiceItemViewSet, basename="serviceitem")

urlpatterns = [
    path("catalog/", CatalogTreeView.as_view(), name="catalog-tree"),
] + router.urls
