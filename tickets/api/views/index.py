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
    ApproveTicketView,
    RejectTicketView,
    OrganizationalTicketListView,
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
    # Phase 4: Service Catalogue
    DepartmentTypeListView,
    SectionTypeDetailView,
    ServiceCategoryListView,
    ServiceItemListView,
    ServiceCategoriesBySectionTypeView,
    ServiceItemsByCategoryView,
    ServiceItemDetailView,
    # Section Technician Management
    SectionTechniciansView,
    AddTechnicianToSectionView,
    RemoveTechnicianFromSectionView,
)

__all__ = [
    # Organization Hierarchy
    "OrganizationListCreateView",
    "OrganizationDetailView",
    "CampusListCreateView",
    "CampusDetailView",
    "DepartmentListCreateView",
    "DepartmentDetailView",
    # Sections
    "SectionListCreateView",
    "SectionDetailView",
    # Facilities
    "FacilityListCreateView",
    "FacilityDetailView",
    # Tickets
    "TicketListCreateView",
    "TicketDetailView",
    "TicketEscalationView",
    "TicketCloseView",
    "ApproveTicketView",
    "RejectTicketView",
    "OrganizationalTicketListView",
    # Comments
    "CommentListCreateView",
    # Feedback
    "FeedbackListCreateView",
    # Users
    "UserListCreateView",
    "UserDetailView",
    "TechniciansBySectionView",
    "AssignableUsersView",
    # Bulk Operations
    "BulkTicketStatusUpdateView",
    # Phase 4: Service Catalogue
    "DepartmentTypeListView",
    "SectionTypeDetailView",
    "ServiceCategoryListView",
    "ServiceItemListView",
    "ServiceCategoriesBySectionTypeView",
    "ServiceItemsByCategoryView",
    "ServiceItemDetailView",
    # Section Technician Management
    "SectionTechniciansView",
    "AddTechnicianToSectionView",
    "RemoveTechnicianFromSectionView",
]
