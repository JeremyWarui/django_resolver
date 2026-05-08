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
    OrganizationListCreateView,
    OrganizationDetailView,
    CampusListCreateView,
    CampusDetailView,
    DepartmentListCreateView,
    DepartmentDetailView,
    SectionListCreateView,
    SectionDetailView,
    FacilityListCreateView,
    FacilityDetailView,
    TicketListCreateView,
    TicketDetailView,
    TicketEscalationView,
    TicketCloseView,
    ApproveTicketView,
    RejectTicketView,
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView,
    UserDetailView,
    TechniciansBySectionView,
    BulkTicketStatusUpdateView,
    OrganizationalTicketListView,
    AssignableUsersView,
    DepartmentTypeListView,
    ServiceCategoryListView,
    ServiceItemListView,
    SectionTypeDetailView,
    ServiceCategoriesBySectionTypeView,
    ServiceItemsByCategoryView,
    ServiceItemDetailView,
    SectionTechniciansView,
    AddTechnicianToSectionView,
    RemoveTechnicianFromSectionView,
)

# Import analytics views
from tickets.api.analytics.index import (
    TicketAnalyticsView,
    TechnicianAnalyticsView,
    AdminDashboardAnalyticsView,
    OrganizationalAnalyticsView,
    ManagerDashboardView,
    HODDashboardView,
    SectionHeadDashboardView,
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
    # ORGANIZATION HIERARCHY
    path(
        "organizations/",
        OrganizationListCreateView.as_view(),
        name="organization-list",
    ),
    path(
        "organizations/<int:pk>/",
        OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path(
        "campuses/",
        CampusListCreateView.as_view(),
        name="campus-list",
    ),
    path(
        "campuses/<int:pk>/",
        CampusDetailView.as_view(),
        name="campus-detail",
    ),
    path(
        "departments/",
        DepartmentListCreateView.as_view(),
        name="department-list",
    ),
    path(
        "departments/<int:pk>/",
        DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    # SECTION
    path(
        "sections/",
        SectionListCreateView.as_view(),
        name="section-list",
    ),
    path(
        "sections/<int:pk>/",
        SectionDetailView.as_view(),
        name="section-detail",
    ),
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
    path(
        "analytics/organizational/",
        OrganizationalAnalyticsView.as_view(),
        name="analytics-organizational",
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
    path(
        "analytics/tickets/",
        TicketAnalyticsView.as_view(),
        name="analytics-tickets",
    ),
    path(
        "analytics/technicians/",
        TechnicianAnalyticsView.as_view(),
        name="analytics-technicians",
    ),
    path(
        "analytics/admin-dashboard/",
        AdminDashboardAnalyticsView.as_view(),
        name="analytics-admin",
    ),
    # ORGANIZATIONAL ANALYTICS ENDPOINTS
    path(
        "analytics/manager/",
        ManagerDashboardView.as_view(),
        name="analytics-manager",
    ),
    path(
        "analytics/hod/",
        HODDashboardView.as_view(),
        name="analytics-hod",
    ),
    path(
        "analytics/section-head/",
        SectionHeadDashboardView.as_view(),
        name="analytics-section-head",
    ),
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
    # SECTION TECHNICIAN MANAGEMENT
    path(
        "sections/<int:pk>/technicians/",
        SectionTechniciansView.as_view(),
        name="section-technicians",
    ),
    path(
        "sections/<int:pk>/add-technician/",
        AddTechnicianToSectionView.as_view(),
        name="section-add-technician",
    ),
    path(
        "sections/<int:pk>/remove-technician/",
        RemoveTechnicianFromSectionView.as_view(),
        name="section-remove-technician",
    ),
    # PHASE 4: SERVICE CATALOGUE ENDPOINTS
    path(
        "service-catalogue/department-types/",
        DepartmentTypeListView.as_view(),
        name="department-types-list",
    ),
    path(
        "service-catalogue/section-types/<int:pk>/",
        SectionTypeDetailView.as_view(),
        name="section-type-detail",
    ),
    path(
        "service-catalogue/service-categories/",
        ServiceCategoryListView.as_view(),
        name="service-categories-list",
    ),
    path(
        "service-catalogue/service-items/",
        ServiceItemListView.as_view(),
        name="service-items-list",
    ),
    # Nested catalogue routes consumed by the frontend wizard
    path(
        "section-types/<int:pk>/categories/",
        ServiceCategoriesBySectionTypeView.as_view(),
        name="section-type-categories",
    ),
    path(
        "categories/<int:pk>/items/",
        ServiceItemsByCategoryView.as_view(),
        name="category-items",
    ),
    path(
        "service-items/<int:pk>/",
        ServiceItemDetailView.as_view(),
        name="service-item-detail",
    ),
]
