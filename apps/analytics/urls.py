from django.urls import path

from . import views
from . import report_views

app_name = "analytics"

urlpatterns = [
    path("reports/types/", report_views.ReportTypesView.as_view(), name="report-types"),
    path("reports/generate/", report_views.GenerateReportView.as_view(), name="report-generate"),

    # Unified endpoint — one view, full envelope, every role. The role-specific
    # endpoints below are kept as backward-compatible shims until the frontend
    # cutover, then removed.
    path("analytics/", views.AnalyticsView.as_view(), name="analytics"),

    path("analytics/overview/", views.OverviewView.as_view(), name="overview"),
    path("analytics/sla-compliance/", views.SLAComplianceView.as_view(), name="sla-compliance"),
    path("analytics/resolution-times/", views.ResolutionTimesView.as_view(), name="resolution-times"),
    path("analytics/flow/", views.FlowView.as_view(), name="flow"),
    path("analytics/quality/", views.QualityView.as_view(), name="quality"),
    path("analytics/demand/", views.DemandView.as_view(), name="demand"),
    path(
        "analytics/performance/technicians/",
        views.PerformanceTechniciansView.as_view(),
        name="performance-technicians",
    ),
    path(
        "analytics/performance/sections/",
        views.PerformanceSectionsView.as_view(),
        name="performance-sections",
    ),
    path(
        "analytics/performance/campus-departments/",
        views.PerformanceCampusDepartmentsView.as_view(),
        name="performance-campus-departments",
    ),
]
