# tickets/models/__init__.py
#
# Re-exports every model class so that existing imports of the form
#   from tickets.models import X
# continue to work unchanged after the package split.
#
# app_label = "tickets" is set on every model's Meta class to ensure
# Django migration machinery keeps all tables under the "tickets" app.

from .organisation import Campus, Department, CampusDepartment
from .users import CustomUser
from .sections import SectionType, Section, TechnicianSection
from .facilities import Facility, FacilityFloor, FacilityRoom
from .catalogue import ServiceCategory, ServiceItem
from .tickets import Ticket, TicketLog, Comment, Feedback

__all__ = [
    # org
    "Campus",
    "Department",
    "CampusDepartment",
    # users
    "CustomUser",
    # sections
    "SectionType",
    "Section",
    "TechnicianSection",
    # facilities
    "Facility",
    "FacilityFloor",
    "FacilityRoom",
    # catalogue
    "ServiceCategory",
    "ServiceItem",
    # tickets
    "Ticket",
    "TicketLog",
    "Comment",
    "Feedback",
]
