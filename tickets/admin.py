from django.contrib import admin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display
from .models import *

# Register your models here.


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    list_display = ("username", "email", "role_badge", "is_staff", "is_active")
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
    search_fields = ("username", "email", "role")
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

    @display(description="Role", ordering="role")
    def role_badge(self, obj):
        """Display role as a colored badge"""
        role_colors = {
            "user": "#0ea5e9",
            "technician": "#10b981",
            "manager": "#f59e0b",
            "admin": "#ef4444",
        }
        color = role_colors.get(obj.role, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.role.title(),
        )


# register section
@admin.register(Section)
class SectionAdmin(ModelAdmin):
    list_display = ("name", "description", "get_technicians")
    search_fields = ("name", "description", "technicians__username")

    def get_technicians(self, obj):
        """Return list of technicians in this section"""
        return ", ".join([user.username for user in obj.technicians.all()])

    get_technicians.short_description = "Technicians"


# register facilities
@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = ("name", "type", "status_badge", "location")
    list_filter = ("type", "status")

    @display(description="Status")
    def status_badge(self, obj):
        """Display status as a colored badge"""
        status_colors = {
            "active": "#10b981",
            "maintenance": "#f59e0b",
            "inactive": "#6b7280",
        }
        color = status_colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.status.title(),
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
        "created_at",
    )
    list_filter = ("section", "facility", "status", "raised_by", "assigned_to")
    search_fields = (
        "title",
        "facility__name",
        "status",
        "assigned_to__username",
        "raised_by__username",
    )
    readonly_fields = ("ticket_no", "created_at", "updated_at", "resolved_at")

    @display(description="Status", ordering="status")
    def status_badge(self, obj):
        """Display ticket status as a colored badge"""
        status_colors = {
            "open": "#ef4444",
            "assigned": "#f59e0b",
            "in_progress": "#3b82f6",
            "pending": "#8b5cf6",
            "resolved": "#10b981",
            "closed": "#6b7280",
        }
        color = status_colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 6px 12px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.status.upper(),
        )


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
