from django.contrib import admin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import *

# Register your models here.


@admin.register(CustomUser)
class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    list_display = ("username", "email", "role", "is_staff", "is_active")
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


# register section
@admin.register(Section)
class SectionAdmin(ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description")


# register facilities
@admin.register(Facility)
class FacilityAdmin(ModelAdmin):
    list_display = ("name", "type", "status", "location")
    list_filter = ("type", "status")
    search_fields = ("name", "location")


# register tickets
@admin.register(Ticket)
class TicketAdmin(ModelAdmin):
    list_display = (
        "ticket_no",
        "title",
        "section",
        "facility",
        "status_colored",
        "assigned_to",
        "created_at",
    )
    list_filter = (
        "section",
        "facility",
        "status",
        "created_at",
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

    def status_colored(self, obj):
        """Display ticket status with colors"""
        status_colors = {
            "open": "#dc2626",        # red
            "assigned": "#d97706",    # orange
            "in_progress": "#0891b2",  # blue
            "pending": "#374151",     # gray
            "resolved": "#16a34a",    # green
            "closed": "#6b7280",      # light gray
        }

        color = status_colors.get(obj.status, "#374151")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status.replace("_", " ").title()
        )
    status_colored.short_description = "Status"


# register comments
@admin.register(Comment)
class CommentAdmin(ModelAdmin):
    list_display = ("author", "ticket", "created_at")
    list_filter = ("created_at",)
    search_fields = ("text",)
    readonly_fields = ("created_at",)


# register feedback
@admin.register(Feedback)
class FeedbackAdmin(ModelAdmin):
    list_display = ("rated_by", "rating", "ticket", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comments",)
    readonly_fields = ("created_at",)
