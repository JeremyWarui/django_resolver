"""
tickets.serializers package
============================
Re-exports all public names so that existing imports of the form
    from tickets.serializers import SomeSerializer
    from tickets.serializers import format_user_info
continue to work without modification.
"""

# Constants and helpers
from .common import (
    ESCALATION_STATUS_MAP,
    _ESCALATION_UNKNOWN,
    format_user_info,
    format_escalation_status,
    format_service_item,
    UsernameField,
)

# Org-level serializers
from .org import (
    NestedCampusSerializer,
    NestedDepartmentSerializer,
    CampusSerializer,
    DepartmentSerializer,
    CampusDepartmentSerializer,
    AssignHODSerializer,
)

# Section serializers
from .sections import (
    NestedSectionSerializer,
    SectionSerializer,
    SectionTypeSerializer,
    AssignHOSSerializer,
    TechnicianSectionSerializer,
)

# Facility serializers
from .facilities import (
    NestedFacilitySerializer,
    FacilitySerializer,
)

# Service catalogue serializers
from .catalogue import (
    ServiceCategorySerializer,
    ServiceItemSerializer,
)

# Ticket serializers
from .tickets import (
    TinyTicketSerializer,
    CommentSerializer,
    FeedbackSerializer,
    TicketListSerializer,
    TicketSerializer,
    TicketCreateSerializer,
)

# User serializer
from .users import UserSerializer

__all__ = [
    # Constants / helpers
    "ESCALATION_STATUS_MAP",
    "_ESCALATION_UNKNOWN",
    "format_user_info",
    "format_escalation_status",
    "format_service_item",
    "UsernameField",
    # Org
    "NestedCampusSerializer",
    "NestedDepartmentSerializer",
    "CampusSerializer",
    "DepartmentSerializer",
    "CampusDepartmentSerializer",
    "AssignHODSerializer",
    # Sections
    "NestedSectionSerializer",
    "SectionSerializer",
    "SectionTypeSerializer",
    "AssignHOSSerializer",
    "TechnicianSectionSerializer",
    # Facilities
    "NestedFacilitySerializer",
    "FacilitySerializer",
    # Catalogue
    "ServiceCategorySerializer",
    "ServiceItemSerializer",
    # Tickets
    "TinyTicketSerializer",
    "CommentSerializer",
    "FeedbackSerializer",
    "TicketListSerializer",
    "TicketSerializer",
    "TicketCreateSerializer",
    # Users
    "UserSerializer",
]
