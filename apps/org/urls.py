from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.org.views import (
    CampusDepartmentViewSet,
    CampusViewSet,
    DepartmentViewSet,
    ScopedTechnicianRosterView,
    SectionAssignableTechniciansView,
    SectionTechnicianViewSet,
    SectionTypeViewSet,
    SectionViewSet,
)

router = DefaultRouter()
router.register("campuses", CampusViewSet, basename="campus")
router.register("departments", DepartmentViewSet, basename="department")
router.register("section-types", SectionTypeViewSet, basename="sectiontype")
router.register("campus-departments", CampusDepartmentViewSet, basename="campusdepartment")
router.register("sections", SectionViewSet, basename="section")

urlpatterns = router.urls + [
    path(
        "technicians/",
        ScopedTechnicianRosterView.as_view(),
        name="scoped-technician-roster",
    ),
    path(
        "sections/<int:section_pk>/assignable-technicians/",
        SectionAssignableTechniciansView.as_view(),
        name="section-assignable-technicians",
    ),
    path(
        "sections/<int:section_pk>/technicians/",
        SectionTechnicianViewSet.as_view({"get": "list", "post": "create"}),
        name="section-technicians-list",
    ),
    path(
        "sections/<int:section_pk>/technicians/<int:pk>/",
        SectionTechnicianViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="section-technicians-detail",
    ),
]
