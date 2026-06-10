from django.urls import path

from .views import (
    TicketListCreateView,
    TicketFilterOptionsView,
    TicketDetailView,
    TicketStatusView,
    TicketAssignView,
    TicketCommentListCreateView,
    TicketFeedbackView,
    TicketLogListView,
    AdminAuditLogView,
)

urlpatterns = [
    path("tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("tickets/filter-options/", TicketFilterOptionsView.as_view(), name="ticket-filter-options"),
    path("tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("tickets/<int:pk>/status/", TicketStatusView.as_view(), name="ticket-status"),
    path("tickets/<int:pk>/assign/", TicketAssignView.as_view(), name="ticket-assign"),
    path("tickets/<int:pk>/comments/", TicketCommentListCreateView.as_view(), name="ticket-comments"),
    path("tickets/<int:pk>/feedback/", TicketFeedbackView.as_view(), name="ticket-feedback"),
    path("tickets/<int:pk>/logs/", TicketLogListView.as_view(), name="ticket-logs"),
    path("admin/audit-log/", AdminAuditLogView.as_view(), name="admin-audit-log"),
]
