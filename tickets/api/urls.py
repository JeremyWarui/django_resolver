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
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView,
    UserDetailView,
    TechniciansBySectionView,
    BulkTicketStatusUpdateView,
    OrganizationalTicketListView,
    AssignableUsersView,
    OrganizationalAnalyticsView,
    EscalateTicketView,
)

# Import analytics views
from tickets.api.analytics.index import (
    TicketAnalyticsView,
    TechnicianAnalyticsView,
    AdminDashboardAnalyticsView,
    DirectorDashboardView,
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
    # Magic link endpoints temporarily disabled - uncomment when email is configured
    # path("auth/magic-link/request/", request_magic_link, name="request_magic_link"),
    # path("auth/magic-link/<str:token>/",
    #      magic_link_login, name="magic_link_login"),
    path("auth/logout/", simple_logout, name="simple_logout"),
    path("auth/profile/", user_profile, name="user_profile"),
    path("auth/register/", register_user, name="register_user"),
    # ORGANIZATION HIERARCHY
    path(
        "organizations/", OrganizationListCreateView.as_view(), name="organization-list"
    ),
    path(
        "organizations/<int:pk>/",
        OrganizationDetailView.as_view(),
        name="organization-detail",
    ),
    path("campuses/", CampusListCreateView.as_view(), name="campus-list"),
    path("campuses/<int:pk>/", CampusDetailView.as_view(), name="campus-detail"),
    path("departments/", DepartmentListCreateView.as_view(), name="department-list"),
    path(
        "departments/<int:pk>/",
        DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    # SECTION
    path("sections/", SectionListCreateView.as_view(), name="section-list"),
    path("sections/<int:pk>/", SectionDetailView.as_view(), name="section-detail"),
    # FACILITY
    path("facilities/", FacilityListCreateView.as_view(), name="facility-list"),
    path("facilities/<int:pk>/", FacilityDetailView.as_view(), name="facility-detail"),
    # TICKET
    path("tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    # TICKET ESCALATION
    path(
        "tickets/<int:ticket_id>/escalate/",
        TicketEscalationView.as_view(),
        name="ticket-escalate",
    ),
    # TICKET CLOSURE
    path(
        "tickets/<int:ticket_id>/close/", TicketCloseView.as_view(), name="ticket-close"
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
        "tickets/<int:ticket_id>/escalate-manual/",
        EscalateTicketView.as_view(),
        name="escalate-ticket-manual",
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
    path("comments/", CommentListCreateView.as_view(), name="comment-list"),
    # FEEDBACK
    path("feedback/", FeedbackListCreateView.as_view(), name="feedback-list"),
    # USER
    path("users/me/", user_profile, name="user-me"),
    path("users/", UserListCreateView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
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
    path("analytics/tickets/", TicketAnalyticsView.as_view(), name="analytics-tickets"),
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
        "analytics/director/",
        DirectorDashboardView.as_view(),
        name="analytics-director",
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
    path("reports/generate/", GenerateReportView.as_view(), name="report-generate"),
    path("reports/types/", ReportTypesView.as_view(), name="report-types"),
]
