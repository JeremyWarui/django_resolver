from django.contrib import admin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html
from django.db.models import Count, Q
from django.urls import reverse
from django.utils.safestring import mark_safe
from unfold.admin import ModelAdmin
from unfold.decorators import display, action
from unfold.contrib.filters.admin import RangeDateFilter
from .models import *

# Register your models here.


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    list_display = ("username", "email", "role_badge",
                    "ticket_stats", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_active", "sections")

    # Form for editing existing users
    form = UserChangeForm

    # Form for creating new users
    add_form = UserCreationForm

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal Info", {"fields": ("first_name", "last_name", "email")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Role and Sections", {"fields": ("role", "sections")}),
        ("Important Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "password1", "password2", "email"),
            },
        ),
        ("Role and Sections", {"fields": ("role", "sections")}),
    )
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)
    filter_horizontal = ("groups", "user_permissions", "sections")
    readonly_fields = ("last_login", "date_joined")

    def get_fieldsets(self, request, obj=None):
        """Use different fieldsets for add vs change forms"""
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        """Use special form for user creation"""
        defaults = {}
        if obj is None:
            defaults["form"] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)

    @display(description="Role", ordering="role", label=True)
    def role_badge(self, obj):
        """Display role as a colored badge"""
        role_colors = {
            "user": "info",
            "technician": "success",
            "manager": "warning",
            "admin": "danger",
        }
        return role_colors.get(obj.role, "secondary")

    @display(description="Tickets")
    def ticket_stats(self, obj):
        """Show ticket statistics for technicians"""
        if obj.role == 'technician':
            assigned = obj.assigned_tickets.exclude(
                status__in=['resolved', 'closed']).count()
            resolved = obj.assigned_tickets.filter(status='resolved').count()
            return format_html(
                '<span style="color: #f59e0b; font-weight: bold;">{}</span> active | '
                '<span style="color: #10b981; font-weight: bold;">{}</span> resolved',
                assigned,
                resolved
            )
        elif obj.role == 'user':
            raised = obj.raised_tickets.count()
            return format_html('<span>{} raised</span>', raised)
        return "—"


# register section
@admin.register(Section)
class SectionAdmin(ModelAdmin):
    list_display = ("name", "description", "technician_count",
                    "active_tickets_count")
    search_fields = ("name", "description", "technicians__username")

    @display(description="Technicians")
    def technician_count(self, obj):
        """Return count of technicians in section"""
        count = obj.technicians.count()
        return format_html(
            '<span style="font-weight: bold; color: #3b82f6;">{}</span>',
            count
        )

    @display(description="Active Tickets")
    def active_tickets_count(self, obj):
        """Return count of active tickets in section"""
        count = obj.ticket_set.exclude(
            status__in=['resolved', 'closed']).count()
        color = "#ef4444" if count > 10 else "#10b981" if count == 0 else "#f59e0b"
        return format_html(
            '<span style="font-weight: bold; color: {};">{}</span>',
            color,
            count
        )


# register facilities
@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = ("name", "type", "status_badge", "location", "ticket_count")
    list_filter = ("type", "status")
    search_fields = ("name", "location")

    @display(description="Status", label=True)
    def status_badge(self, obj):
        """Display status as a colored badge"""
        status_colors = {
            "active": "success",
            "maintenance": "warning",
            "inactive": "secondary",
        }
        return status_colors.get(obj.status, "secondary")

    @display(description="Tickets")
    def ticket_count(self, obj):
        """Show ticket count for facility"""
        total = obj.ticket_set.count()
        active = obj.ticket_set.exclude(
            status__in=['resolved', 'closed']).count()
        return format_html(
            '<span style="color: #f59e0b; font-weight: bold;">{}</span> active / '
            '<span style="color: #6b7280;">{}</span> total',
            active,
            total
        )


# register tickets
@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = (
        "ticket_no",
        "title",
        "section",
        "facility",
        "status_badge",
        "assigned_to",
        "days_old",
        "created_at",
    )
    list_filter = (
        "section",
        "facility",
        "status",
        ("created_at", RangeDateFilter),
        "raised_by",
        "assigned_to"
    )
    search_fields = (
        "ticket_no",
        "title",
        "description",
        "facility__name",
        "status",
        "assigned_to__username",
        "raised_by__username",
    )
    readonly_fields = ("ticket_no", "created_at", "updated_at", "resolved_at")
    list_per_page = 25
    date_hierarchy = "created_at"

    actions_list = ["assign_to_me", "mark_resolved", "mark_closed"]
    actions_detail = ["assign_to_me", "mark_resolved"]

    fieldsets = (
        ("Ticket Information", {
            "fields": ("ticket_no", "title", "description")
        }),
        ("Location & Category", {
            "fields": ("section", "facility")
        }),
        ("Status & Assignment", {
            "fields": ("status", "raised_by", "assigned_to", "pending_reason")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at", "resolved_at"),
            "classes": ("collapse",)
        }),
    )

    @display(description="Status", ordering="status", label=True)
    def status_badge(self, obj):
        """Display ticket status as a colored badge"""
        status_colors = {
            "open": "danger",
            "assigned": "warning",
            "in_progress": "info",
            "pending": "dark",
            "resolved": "success",
            "closed": "secondary",
        }
        return status_colors.get(obj.status, "secondary")

    @display(description="Priority", ordering="created_at")
    def priority_indicator(self, obj):
        """Show priority based on ticket age"""
        from django.utils import timezone
        age_days = (timezone.now() - obj.created_at).days

        if obj.status in ['resolved', 'closed']:
            icon = "✓"
            color = "#10b981"
        elif age_days > 7:
            icon = "🔴"
            color = "#ef4444"
        elif age_days > 3:
            icon = "🟡"
            color = "#f59e0b"
        else:
            icon = "🟢"
            color = "#10b981"

        return format_html(
            '<span style="font-size: 18px;" title="{} days old">{}</span>',
            age_days,
            icon
        )

    @display(description="Age", ordering="created_at")
    def days_old(self, obj):
        """Display how many days old the ticket is"""
        from django.utils import timezone
        age_days = (timezone.now() - obj.created_at).days

        if age_days == 0:
            return "Today"
        elif age_days == 1:
            return "1 day"
        else:
            return f"{age_days} days"

    @action(description="Assign to me")
    def assign_to_me(self, request, queryset):
        """Assign selected tickets to current user"""
        if request.user.role == 'technician':
            updated = queryset.update(
                assigned_to=request.user, status='assigned')
            self.message_user(request, f"{updated} ticket(s) assigned to you.")
        else:
            self.message_user(
                request, "Only technicians can be assigned tickets.", level='error')

    @action(description="Mark as Resolved")
    def mark_resolved(self, request, queryset):
        """Mark selected tickets as resolved"""
        from django.utils import timezone
        updated = queryset.exclude(status__in=['resolved', 'closed']).update(
            status='resolved',
            resolved_at=timezone.now()
        )
        self.message_user(request, f"{updated} ticket(s) marked as resolved.")

    @action(description="Mark as Closed", permissions=["change"])
    def mark_closed(self, request, queryset):
        """Mark selected tickets as closed (admin/manager only)"""
        if request.user.role in ['admin', 'manager']:
            from django.utils import timezone
            updated = queryset.filter(status='resolved').update(
                status='closed',
                resolved_at=timezone.now()
            )
            self.message_user(request, f"{updated} ticket(s) closed.")
        else:
            self.message_user(
                request, "Only admins/managers can close tickets.", level='error')


# register comments
@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ("author", "ticket", "created_at")
    list_filter = ("author", "ticket", "created_at")
    search_fields = ("author__username", "text", "ticket__title")
    readonly_fields = ("created_at",)


# register feedback
@admin.register(Feedback)
class FeedbackAdmin(ModelAdmin):
    list_display = ("rated_by", "rating_stars", "ticket", "created_at")
    list_filter = ("rating", "ticket", "created_at")
    search_fields = ("rated_by__username", "ticket__title")
    readonly_fields = ("created_at",)

    @display(description="Rating", ordering="rating")
    def rating_stars(self, obj):
        """Display rating as stars"""
        stars = "⭐" * int(obj.rating)
        return format_html(
            '<span style="font-size: 16px;">{} ({})</span>',
            stars,
            obj.rating,
        )
