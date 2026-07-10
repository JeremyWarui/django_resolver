"""Admin registrations for all domain models.

This module centralises admin for all apps in the service desk.
Unfold callback stubs are defined here and referenced in settings.UNFOLD.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from unfold.admin import ModelAdmin

from apps.accounts.models import CustomUser, UserProfile, RoleAssignment
from apps.org.models import (
    Campus,
    Department,
    CampusDepartment,
    SectionType,
    Section,
    SectionTechnician,
)
from apps.facilities.models import FacilityType, Facility
from apps.sla.models import Priority, EscalationRule
from apps.catalog.models import ServiceCategory, ServiceItem
from apps.tickets.models import (
    Ticket,
    TicketLocation,
    TicketLog,
    TicketComment,
    TicketFeedback,
)

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
    list_display = ("username", "first_name", "last_name", "email", "is_staff", "is_active")
    search_fields = ("username", "first_name", "last_name", "email")


@admin.register(UserProfile)
class UserProfileAdmin(ModelAdmin):
    list_display = ("user", "campus")
    list_filter = ("campus",)
    search_fields = ("user__username", "user__email")


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(ModelAdmin):
    list_display = (
        "user",
        "role",
        "is_primary",
        "section",
        "campus_department",
        "department",
        "valid_until",
    )
    list_filter = ("role", "is_primary")
    search_fields = ("user__username", "user__email")


@admin.register(Campus)
class CampusAdmin(ModelAdmin):
    list_display = ("code", "name", "location")
    search_fields = ("name", "code")


@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ("code", "name", "manager_user")
    search_fields = ("name", "code")


@admin.register(CampusDepartment)
class CampusDepartmentAdmin(ModelAdmin):
    list_display = ("campus", "department", "head_of_department")
    list_filter = ("campus", "department")


@admin.register(SectionType)
class SectionTypeAdmin(ModelAdmin):
    list_display = ("department", "name", "code")
    list_filter = ("department",)
    search_fields = ("name", "code")


@admin.register(Section)
class SectionAdmin(ModelAdmin):
    list_display = ("campus_department", "section_type", "hos", "is_active")
    list_filter = ("is_active", "campus_department__campus")


@admin.register(SectionTechnician)
class SectionTechnicianAdmin(ModelAdmin):
    list_display = ("section", "user", "added_at")
    list_filter = ("section",)


@admin.register(FacilityType)
class FacilityTypeAdmin(ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")


@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = ("name", "code", "campus", "facility_type")
    list_filter = ("campus", "facility_type")
    search_fields = ("name", "code")


@admin.register(Priority)
class PriorityAdmin(ModelAdmin):
    list_display = ("name", "rank", "response_minutes", "resolution_minutes")


@admin.register(EscalationRule)
class EscalationRuleAdmin(ModelAdmin):
    list_display = ("priority", "to_level", "threshold_minutes", "order")
    list_filter = ("to_level", "priority")


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(ModelAdmin):
    list_display = ("name", "section_type", "is_active", "default_priority")
    list_filter = ("is_active", "section_type")
    search_fields = ("name",)


@admin.register(ServiceItem)
class ServiceItemAdmin(ModelAdmin):
    list_display = ("name", "category", "is_active", "default_priority")
    list_filter = ("is_active", "category")
    search_fields = ("name",)


@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = (
        "ticket_no",
        "raised_by",
        "section",
        "status",
        "current_level",
        "priority",
        "created_at",
    )
    list_filter = ("status", "current_level", "priority")
    search_fields = ("ticket_no", "raised_by__username", "raised_by__email")


@admin.register(TicketLocation)
class TicketLocationAdmin(ModelAdmin):
    list_display = ("ticket", "facility_type", "facility")
    list_filter = ("facility_type",)


@admin.register(TicketComment)
class TicketCommentAdmin(ModelAdmin):
    list_display = ("ticket", "author", "visibility", "created_at")
    list_filter = ("visibility",)
    search_fields = ("ticket__ticket_no", "author__username")


@admin.register(TicketFeedback)
class TicketFeedbackAdmin(ModelAdmin):
    list_display = ("ticket", "rating", "created_at")
    list_filter = ("rating",)

admin.site.site_header = "Resolver — Service Desk"
admin.site.site_title = "Resolver Admin"
admin.site.index_title = "Service Desk Management"
