"""Re-exports all views for convenient import in urls.py."""

from .org_views import (
    CampusListCreateView,
    CampusDetailView,
    DepartmentListCreateView,
    DepartmentDetailView,
    CampusDepartmentListCreateView,
    CampusDepartmentDetailView,
    AssignHODView,
    SectionListCreateView,
    SectionDetailView,
    AssignHOSView,
    FacilityListCreateView,
    FacilityDetailView,
)
from .ticket_views import (
    TicketListCreateView,
    TicketCreateView,
    TicketDetailView,
    TicketEscalationView,
    TicketCloseView,
    ApproveTicketView,
    RejectTicketView,
    BulkTicketStatusUpdateView,
    OrganizationalTicketListView,
    CommentListCreateView,
    FeedbackListCreateView,
)
from .user_views import (
    UserListCreateView,
    UserDetailView,
    TechniciansBySectionView,
    AssignableUsersView,
)
from .catalogue_views import (
    SectionTypeDetailView,
    ServiceCategoryListCreateView,
    ServiceCategoryDetailView,
    ServiceItemListCreateView,
    ServiceItemDetailView,
    ServiceCategoriesBySectionTypeView,
    ServiceItemsByCategoryView,
)
from .technician_views import (
    SectionTechniciansView,
    TechnicianSectionListCreateView,
    TechnicianSectionDestroyView,
    AddTechnicianToSectionView,
    RemoveTechnicianFromSectionView,
)

__all__ = [
    # Org hierarchy
    "CampusListCreateView",
    "CampusDetailView",
    "DepartmentListCreateView",
    "DepartmentDetailView",
    "CampusDepartmentListCreateView",
    "CampusDepartmentDetailView",
    "AssignHODView",
    "SectionListCreateView",
    "SectionDetailView",
    "AssignHOSView",
    "FacilityListCreateView",
    "FacilityDetailView",
    # Tickets
    "TicketListCreateView",
    "TicketCreateView",
    "TicketDetailView",
    "TicketEscalationView",
    "TicketCloseView",
    "ApproveTicketView",
    "RejectTicketView",
    "BulkTicketStatusUpdateView",
    "OrganizationalTicketListView",
    "CommentListCreateView",
    "FeedbackListCreateView",
    # Users
    "UserListCreateView",
    "UserDetailView",
    "TechniciansBySectionView",
    "AssignableUsersView",
    # Catalogue
    "SectionTypeDetailView",
    "ServiceCategoryListCreateView",
    "ServiceCategoryDetailView",
    "ServiceItemListCreateView",
    "ServiceItemDetailView",
    "ServiceCategoriesBySectionTypeView",
    "ServiceItemsByCategoryView",
    # Technician management
    "SectionTechniciansView",
    "TechnicianSectionListCreateView",
    "TechnicianSectionDestroyView",
    "AddTechnicianToSectionView",
    "RemoveTechnicianFromSectionView",
]
