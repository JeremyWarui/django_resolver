"""
Index file for exporting all views.
This makes imports more convenient in other modules.

Consolidated views with organizational hierarchy awareness.
"""

# All views are now consolidated in views.py
from .views import (
    # Organization Hierarchy
    OrganizationListCreateView,
    OrganizationDetailView,
    CampusListCreateView,
    CampusDetailView,
    DepartmentListCreateView,
    DepartmentDetailView,
    # Sections
    SectionListCreateView,
    SectionDetailView,
    # Facilities
    FacilityListCreateView,
    FacilityDetailView,
    # Tickets
    TicketListCreateView,
    TicketDetailView,
    TicketEscalationView,
    TicketCloseView,
    OrganizationalTicketListView,
    EscalateTicketView,
    # Comments
    CommentListCreateView,
    # Feedback
    FeedbackListCreateView,
    # Users
    UserListCreateView,
    UserDetailView,
    TechniciansBySectionView,
    AssignableUsersView,
    # Bulk Operations
    BulkTicketStatusUpdateView,
    # Analytics
    OrganizationalAnalyticsView,
    AnalyticsTicketsView,
    AnalyticsTechniciansView,
)

__all__ = [
    # Organization Hierarchy
    'OrganizationListCreateView',
    'OrganizationDetailView',
    'CampusListCreateView',
    'CampusDetailView',
    'DepartmentListCreateView',
    'DepartmentDetailView',
    # Sections
    'SectionListCreateView',
    'SectionDetailView',
    # Facilities
    'FacilityListCreateView',
    'FacilityDetailView',
    # Tickets
    'TicketListCreateView',
    'TicketDetailView',
    'TicketEscalationView',
    'TicketCloseView',
    'OrganizationalTicketListView',
    'EscalateTicketView',
    # Comments
    'CommentListCreateView',
    # Feedback
    'FeedbackListCreateView',
    # Users
    'UserListCreateView',
    'UserDetailView',
    'TechniciansBySectionView',
    'AssignableUsersView',
    # Bulk Operations
    'BulkTicketStatusUpdateView',
    # Analytics
    'OrganizationalAnalyticsView',
    'AnalyticsTicketsView',
    'AnalyticsTechniciansView',
]
