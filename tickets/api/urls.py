# tickets/api/urls.py
from django.urls import path

# Import resource views
from tickets.api.views.index import (
    SectionListCreateView, SectionDetailView,
    FacilityListCreateView, FacilityDetailView,
    TicketListCreateView, TicketDetailView,
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView, UserDetailView,
)

# Import analytics views
from tickets.api.analytics.index import (
    TicketAnalyticsView,
    TechnicianAnalyticsView,
    AdminDashboardAnalyticsView
)

# Import report views
from tickets.api.reports.views import (
    GenerateReportView,
    ReportTypesView
)

urlpatterns = [
    # SECTION
    path('sections/', SectionListCreateView.as_view(), name='section-list'),
    path('sections/<int:pk>/', SectionDetailView.as_view(), name='section-detail'),

    # FACILITY
    path('facilities/', FacilityListCreateView.as_view(), name='facility-list'),
    path('facilities/<int:pk>/', FacilityDetailView.as_view(),
         name='facility-detail'),

    # TICKET
    path('tickets/', TicketListCreateView.as_view(), name='ticket-list'),
    path('tickets/<int:pk>/', TicketDetailView.as_view(), name='ticket-detail'),

    # COMMENT
    path('comments/', CommentListCreateView.as_view(), name='comment-list'),

    # FEEDBACK
    path('feedback/', FeedbackListCreateView.as_view(), name='feedback-list'),

    # USER
    path('users/', UserListCreateView.as_view(), name='user-list'),
    path('users/<int:pk>/', UserDetailView.as_view(), name='user-detail'),

    # NESTED TICKET RESOURCES
    path('tickets/<int:ticket_id>/comments/',
         CommentListCreateView.as_view(), name='ticket-comments'),
    path('tickets/<int:ticket_id>/feedback/',
         FeedbackListCreateView.as_view(), name='ticket-feedback'),

    # ANALYTICS ENDPOINTS
    path('analytics/tickets/',
         TicketAnalyticsView.as_view(), name='analytics-tickets'),
    path('analytics/technicians/',
         TechnicianAnalyticsView.as_view(), name='analytics-technicians'),
    path('analytics/admin-dashboard/',
         AdminDashboardAnalyticsView.as_view(), name='analytics-admin'),
    
    # REPORT ENDPOINTS
    path('reports/generate/',
         GenerateReportView.as_view(), name='report-generate'),
    path('reports/types/',
         ReportTypesView.as_view(), name='report-types'),
]
