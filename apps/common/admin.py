"""Admin registrations for all domain models.

This module centralises admin for all apps in the service desk.
Unfold callback stubs are defined here and referenced in settings.UNFOLD.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from unfold.admin import ModelAdmin

from apps.accounts.models import CustomUser, UserProfile, RoleAssignment
from apps.org.models import Campus, Department, CampusDepartment, SectionType, Section, SectionTechnician
from apps.facilities.models import FacilityType, Facility
from apps.sla.models import Priority, EscalationRule
from apps.catalog.models import ServiceCategory, ServiceItem
from apps.tickets.models import Ticket, TicketLocation, TicketLog, TicketComment, TicketFeedback


# ── Unfold sidebar / environment callbacks ─────────────────────────────────────

def environment_callback(request):
    import os
    env = os.getenv("ENVIRONMENT", "development")
    return env, "info" if env == "production" else "warning"


def dashboard_callback(request, context):
    context.update(
        {
            "tickets_total": Ticket.objects.count(),
            "open_tickets": Ticket.objects.filter(status="open").count(),
        }
    )
    return context


def ticket_count_badge(request):
    return Ticket.objects.filter(status__in=["open", "assigned", "in_progress"]).count()


def user_count_badge(request):
    return CustomUser.objects.filter(is_active=True).count()


def facility_count_badge(request):
    return Facility.objects.count()


# ── Admin registrations ────────────────────────────────────────────────────────

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin, ModelAdmin):
    list_display = ("username", "email", "is_staff", "is_active")
    search_fields = ("username", "email")


admin.site.register(UserProfile)
admin.site.register(RoleAssignment)
admin.site.register(Campus)
admin.site.register(Department)
admin.site.register(CampusDepartment)
admin.site.register(SectionType)
admin.site.register(Section)
admin.site.register(SectionTechnician)
admin.site.register(FacilityType)
admin.site.register(Facility)
admin.site.register(Priority)
admin.site.register(EscalationRule)
admin.site.register(ServiceCategory)
admin.site.register(ServiceItem)
admin.site.register(Ticket)
admin.site.register(TicketLocation)
admin.site.register(TicketComment)
admin.site.register(TicketFeedback)

admin.site.site_header = "Resolver — Service Desk"
admin.site.site_title = "Resolver Admin"
admin.site.index_title = "Service Desk Management"
