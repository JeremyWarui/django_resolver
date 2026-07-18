from django.urls import path

from .views import (
    TicketListCreateView,
    TicketFilterOptionsView,
    TicketDetailView,
    TicketStatusView,
    TicketAssignView,
    TicketClaimView,
    TicketCommentListCreateView,
    TicketFeedbackView,
    TicketLogListView,
    TicketAttachmentView,
    AdminAuditLogView,
)

urlpatterns = [
    path("tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path(
        "tickets/filter-options/",
        TicketFilterOptionsView.as_view(),
        name="ticket-filter-options",
    ),
    path("tickets/<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("tickets/<int:pk>/status/", TicketStatusView.as_view(), name="ticket-status"),
    path("tickets/<int:pk>/assign/", TicketAssignView.as_view(), name="ticket-assign"),
    path("tickets/<int:pk>/claim/", TicketClaimView.as_view(), name="ticket-claim"),
    path(
        "tickets/<int:pk>/comments/",
        TicketCommentListCreateView.as_view(),
        name="ticket-comments",
    ),
    path(
        "tickets/<int:pk>/feedback/",
        TicketFeedbackView.as_view(),
        name="ticket-feedback",
    ),
    path("tickets/<int:pk>/logs/", TicketLogListView.as_view(), name="ticket-logs"),
    path(
        "tickets/<int:pk>/attachments/",
        TicketAttachmentView.as_view(),
        name="ticket-attachments",
    ),
    path(
        "tickets/<int:pk>/attachments/<int:att_id>/",
        TicketAttachmentView.as_view(),
        name="ticket-attachment-detail",
    ),
    path("admin/audit-log/", AdminAuditLogView.as_view(), name="admin-audit-log"),
]
