"""
Index file for exporting all views.
This makes imports more convenient in other modules.
"""

# Resource Views
from .resource_views import (
    SectionListCreateView,
    SectionDetailView,
    FacilityListCreateView,
    FacilityDetailView,
    TicketListCreateView,
    TicketDetailView,
    TicketEscalationView,
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView,
    UserDetailView,
    TechniciansBySectionView,
    BulkTicketStatusUpdateView,
)

# Organizational Views (Phase 6)
from .organizational_views import (
    OrganizationalTicketListView,
    AssignableUsersView,
    OrganizationalAnalyticsView,
    EscalateTicketView,
)

__all__ = [
    'SectionListCreateView',
    'SectionDetailView',
    'FacilityListCreateView',
    'FacilityDetailView',
    'TicketListCreateView',
    'TicketDetailView',
    'TicketEscalationView',
    'CommentListCreateView',
    'FeedbackListCreateView',
    'UserListCreateView',
    'UserDetailView',
    'TechniciansBySectionView',
    'BulkTicketStatusUpdateView',
    'OrganizationalTicketListView',
    'AssignableUsersView',
    'OrganizationalAnalyticsView',
    'EscalateTicketView',
]
