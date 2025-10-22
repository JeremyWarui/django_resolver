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
    CommentListCreateView,
    FeedbackListCreateView,
    UserListCreateView,
    UserDetailView
)

__all__ = [
    'SectionListCreateView',
    'SectionDetailView',
    'FacilityListCreateView',
    'FacilityDetailView',
    'TicketListCreateView',
    'TicketDetailView',
    'CommentListCreateView',
    'FeedbackListCreateView',
    'UserListCreateView',
    'UserDetailView'
]
