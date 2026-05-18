# tickets/api/urls.py
from django.urls import path

# Import simple authentication views
# Magic link views commented out - uncomment when email is configured
from tickets.api.simple_auth_views import (
    check_auth_method,
    simple_auth_login,  # request_magic_link,
    # magic_link_login,
    simple_logout,
    user_profile,
    register_user,
)

# Import resource views
from tickets.api.views.index import (
    CampusListCreateView,
    CampusDetailView,
    DepartmentListCreateView,
    DepartmentDetailView,
    CampusDepartmentListCreateView,
    CampusDepartmentDetailView,
    AssignHODView,
    AssignHOSView,
    SectionListCreateView,
    SectionDetailView,
    FacilityListCreateView,
    FacilityDetailView,
    TicketListCreateView,
    TicketCreateView,
    TicketDetailView,
    TicketEscalationView,
    TicketCloseView,
    ApproveTicketView,
    RejectTicketView,
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView,
    UserDetailView,
    TechnicianListView,
    TechniciansBySectionView,
    BulkTicketStatusUpdateView,
    OrganizationalTicketListView,
    AssignableUsersView,
    SectionTypeListView,
    SectionTypeDetailView,
    ServiceCategoriesBySectionTypeView,
    ServiceItemsByCategoryView,
    ServiceCategoryListCreateView,
    ServiceCategoryDetailView,
    ServiceItemListCreateView,
    ServiceItemDetailView,
    SectionTechniciansView,
    TechnicianSectionListCreateView,
    TechnicianSectionDestroyView,
    AddTechnicianToSectionView,
    RemoveTechnicianFromSectionView,
    TechnicianDashboardView,
    HODDashboardView,
    SectionHeadDashboardView,
    ManagerDashboardView,
    UserDashboardView,
    AdminDashboardView,
)

# Import analytics views
from tickets.api.analytics.index import (
    TicketAnalyticsView,
    TechnicianAnalyticsView,
    TechnicianSelfAnalyticsView,
    AdminDashboardAnalyticsView,

    UserAnalyticsView,
    ManagerDashboardView as ManagerAnalyticsDashboardView,
    HODDashboardView as HODAnalyticsDashboardView,
    SectionHeadDashboardView as SectionHeadAnalyticsDashboardView,
    DepartmentAnalyticsView,
    HODAnalyticsView,
    HOSAnalyticsView,
)

# Import report views
from tickets.api.reports.views import GenerateReportView, ReportTypesView

urlpatterns = [
    # AUTHENTICATION ENDPOINTS
    # Simple authentication endpoints (password-based for all roles)
    path("auth/check-method/", check_auth_method, name="check_auth_method"),
    path("auth/login/", simple_auth_login, name="simple_auth_login"),
    # Magic link endpoints temporarily disabled.
    # Uncomment when email is configured:
    # path("auth/magic-link/request/", request_magic_link,
    #      name="request_magic_link"),
    # path("auth/magic-link/<str:token>/",
    #      magic_link_login, name="magic_link_login"),
    path("auth/logout/", simple_logout, name="simple_logout"),
    path("auth/profile/", user_profile, name="user_profile"),
    path("auth/register/", register_user, name="register_user"),

    # DASHBOARD ENDPOINTS (must be before generic resource routes to avoid path conflicts)
    path("admin/me/dashboard/", AdminDashboardView.as_view(), name="admin-dashboard"),
    path("technicians/me/dashboard/", TechnicianDashboardView.as_view(), name="technician-dashboard"),
    path("hod/me/dashboard/", HODDashboardView.as_view(), name="hod-dashboard"),
    path("section-head/me/dashboard/", SectionHeadDashboardView.as_view(), name="section-head-dashboard"),
    path("manager/me/dashboard/", ManagerDashboardView.as_view(), name="manager-dashboard"),
    path("user/me/dashboard/", UserDashboardView.as_view(), name="user-dashboard"),
    # ORGANIZATION HIERARCHY
    path("campuses/",                    CampusListCreateView.as_view(),           name="campus-list"),
    path("campuses/<int:pk>/",           CampusDetailView.as_view(),               name="campus-detail"),
    path("departments/",                 DepartmentListCreateView.as_view(),        name="department-list"),
    path("departments/<int:pk>/",        DepartmentDetailView.as_view(),            name="department-detail"),
    path("campus-departments/",          CampusDepartmentListCreateView.as_view(), name="campus-department-list"),
    path("campus-departments/<int:pk>/", CampusDepartmentDetailView.as_view(),     name="campus-department-detail"),
    path("campus-departments/<int:pk>/assign-hod/", AssignHODView.as_view(),       name="campus-department-assign-hod"),
    # SECTION
    path("sections/",                    SectionListCreateView.as_view(),          name="section-list"),
    path("sections/<int:pk>/",           SectionDetailView.as_view(),              name="section-detail"),
    path("sections/<int:pk>/assign-hos/", AssignHOSView.as_view(),                 name="section-assign-hos"),
    # FACILITY
    path(
        "facilities/",
        FacilityListCreateView.as_view(),
        name="facility-list",
    ),
    path(
        "facilities/<int:pk>/",
        FacilityDetailView.as_view(),
        name="facility-detail",
    ),
    # TICKET
    path(
        "tickets/",
        TicketListCreateView.as_view(),
        name="ticket-list",
    ),
    path(
        "tickets/create/",
        TicketCreateView.as_view(),
        name="ticket-create",
    ),
    path(
        "tickets/<int:pk>/",
        TicketDetailView.as_view(),
        name="ticket-detail",
    ),
    # TICKET ESCALATION
    path(
        "tickets/<int:ticket_id>/escalate/",
        TicketEscalationView.as_view(),
        name="ticket-escalate",
    ),
    # TICKET CLOSURE
    path(
        "tickets/<int:ticket_id>/close/",
        TicketCloseView.as_view(),
        name="ticket-close",
    ),
    # APPROVAL WORKFLOW
    path(
        "tickets/<int:ticket_id>/approve/",
        ApproveTicketView.as_view(),
        name="ticket-approve",
    ),
    path(
        "tickets/<int:ticket_id>/reject/",
        RejectTicketView.as_view(),
        name="ticket-reject",
    ),
    # BULK OPERATIONS
    path(
        "tickets/bulk-status-update/",
        BulkTicketStatusUpdateView.as_view(),
        name="bulk-status-update",
    ),
    # ORGANIZATIONAL ENDPOINTS (Phase 6)
    path(
        "tickets/organizational/list/",
        OrganizationalTicketListView.as_view(),
        name="organizational-ticket-list",
    ),
    path(
        "assignable-users/",
        AssignableUsersView.as_view(),
        name="assignable-users",
    ),

    # COMMENT
    path(
        "comments/",
        CommentListCreateView.as_view(),
        name="comment-list",
    ),
    # FEEDBACK
    path(
        "feedback/",
        FeedbackListCreateView.as_view(),
        name="feedback-list",
    ),
    # TECHNICIANS
    path("technicians/", TechnicianListView.as_view(), name="technician-list"),

    # USER
    path(
        "users/me/",
        user_profile,
        name="user-me",
    ),
    path(
        "users/",
        UserListCreateView.as_view(),
        name="user-list",
    ),
    path(
        "users/<int:pk>/",
        UserDetailView.as_view(),
        name="user-detail",
    ),
    # TECHNICIANS BY SECTION
    path(
        "technicians/",
        TechniciansBySectionView.as_view(),
        name="technicians-by-section",
    ),
    # NESTED TICKET RESOURCES
    path(
        "tickets/<int:ticket_id>/comments/",
        CommentListCreateView.as_view(),
        name="ticket-comments",
    ),
    path(
        "tickets/<int:ticket_id>/feedback/",
        FeedbackListCreateView.as_view(),
        name="ticket-feedback",
    ),
    # ANALYTICS ENDPOINTS
    path("analytics/tickets/",                          TicketAnalyticsView.as_view(),             name="analytics-tickets"),
    path("analytics/admin-dashboard/",                  AdminDashboardAnalyticsView.as_view(),      name="analytics-admin"),
    path("analytics/user/",                             UserAnalyticsView.as_view(),                name="analytics-user"),
    path("analytics/technicians/",                      TechnicianAnalyticsView.as_view(),          name="analytics-technicians"),
    path("analytics/technicians/me/",                   TechnicianSelfAnalyticsView.as_view(),      name="analytics-technician-self"),
    # ORGANIZATIONAL ANALYTICS ENDPOINTS
    path("analytics/manager/",                              ManagerAnalyticsDashboardView.as_view(),     name="analytics-manager"),
    path("analytics/hod/",                                 HODAnalyticsDashboardView.as_view(),          name="analytics-hod"),
    path("analytics/section-head/",                        SectionHeadAnalyticsDashboardView.as_view(),  name="analytics-section-head"),
    path("analytics/departments/<int:pk>/",                DepartmentAnalyticsView.as_view(),   name="analytics-department"),
    path("analytics/campus-departments/<int:pk>/",         HODAnalyticsView.as_view(),          name="analytics-campus-department"),
    path("analytics/sections/<int:pk>/",                   HOSAnalyticsView.as_view(),          name="analytics-section"),
    # REPORT ENDPOINTS
    path(
        "reports/generate/",
        GenerateReportView.as_view(),
        name="report-generate",
    ),
    path(
        "reports/types/",
        ReportTypesView.as_view(),
        name="report-types",
    ),
    # SERVICE CATALOGUE
    path("service-catalogue/section-types/",           SectionTypeListView.as_view(),             name="section-type-list"),
    path("service-catalogue/section-types/<int:pk>/",  SectionTypeDetailView.as_view(),           name="section-type-detail"),
    path("service-catalogue/service-categories/",      ServiceCategoryListCreateView.as_view(),   name="service-category-list"),
    path("service-catalogue/service-categories/<int:pk>/", ServiceCategoryDetailView.as_view(),   name="service-category-detail"),
    path("service-catalogue/service-items/",           ServiceItemListCreateView.as_view(),        name="service-item-list"),
    path("service-catalogue/service-items/<int:pk>/",  ServiceItemDetailView.as_view(),            name="service-item-detail"),
    # Nested catalogue routes for the frontend wizard
    path("section-types/<int:pk>/categories/",         ServiceCategoriesBySectionTypeView.as_view(), name="section-type-categories"),
    path("categories/<int:pk>/items/",                 ServiceItemsByCategoryView.as_view(),          name="category-items"),
    # TECHNICIAN MANAGEMENT
    path("sections/<int:pk>/technicians/",             SectionTechniciansView.as_view(),              name="section-technicians"),
    path("sections/<int:pk>/add-technician/",          AddTechnicianToSectionView.as_view(),          name="section-add-technician"),
    path("sections/<int:pk>/technician-sections/<int:ts_pk>/", RemoveTechnicianFromSectionView.as_view(), name="section-remove-technician"),
    path("technician-sections/",                       TechnicianSectionListCreateView.as_view(),     name="technician-section-list"),
    path("technician-sections/<int:pk>/",              TechnicianSectionDestroyView.as_view(),        name="technician-section-destroy"),
]
