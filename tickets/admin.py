from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.db.models import Count, Q
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from unfold.admin import ModelAdmin
from unfold.decorators import display
from unfold.contrib.filters.admin import RangeDateFilter
from tickets.models import CustomUser, Section, Facility, Ticket, Comment, Feedback

# CustomUser admin


class CustomUserAdmin(ModelAdmin):
    model = CustomUser
    list_display = (
        "username",
        "email",
        "role_badge",
        "is_staff",
        "is_active",
        "sections_count",
    )
    list_filter = ("role", "is_staff", "is_active", "sections")
    form = UserChangeForm
    add_form = UserCreationForm

    @display(description="Role", ordering="role")
    def role_badge(self, obj):
        role_colors = {
            "user": "#3b82f6",
            "technician": "#10b981",
            "manager": "#f59e0b",
            "admin": "#ef4444",
        }
        color = role_colors.get(obj.role, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>',
            color,
            obj.role.title(),
        )

    @display(description="Sections")
    def sections_count(self, obj):
        count = obj.sections.count()
        return format_html(
            '<span style="color: #6b7280; font-weight: 500;">{} sections</span>', count
        )

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
        if not obj:
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)

    def get_form(self, request, obj=None, **kwargs):
        defaults = {}
        if obj is None:
            defaults["form"] = self.add_form
        defaults.update(kwargs)
        return super().get_form(request, obj, **defaults)


class SectionAdmin(ModelAdmin):
    list_display = ("name", "description", "technicians_count", "tickets_count")
    search_fields = ("name", "description")

    @display(description="Technicians")
    def technicians_count(self, obj):
        count = obj.technicians.filter(role="technician").count()
        return format_html(
            '<span style="color: #059669; font-weight: 500;">{}</span>', count
        )

    @display(description="Active Tickets")
    def tickets_count(self, obj):
        count = obj.ticket_set.exclude(status__in=["resolved", "closed"]).count()
        return format_html(
            '<span style="color: #dc2626; font-weight: 500;">{}</span>', count
        )


class FacilityAdmin(ModelAdmin):
    list_display = ("name", "type_badge", "status_badge", "location", "tickets_count")
    list_filter = ("type", "status")
    search_fields = ("name", "location")

    @display(description="Type", ordering="type")
    def type_badge(self, obj):
        type_colors = {
            "building": "#3b82f6",
            "equipment": "#10b981",
            "vehicle": "#f59e0b",
            "infrastructure": "#8b5cf6",
        }
        color = type_colors.get(obj.type, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>',
            color,
            obj.type.title(),
        )

    @display(description="Status", ordering="status")
    def status_badge(self, obj):
        status_colors = {
            "active": "#10b981",
            "inactive": "#ef4444",
            "maintenance": "#f59e0b",
        }
        color = status_colors.get(obj.status, "#6b7280")
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 500;">{}</span>',
            color,
            obj.status.title(),
        )

    @display(description="Open Tickets")
    def tickets_count(self, obj):
        count = obj.ticket_set.exclude(status__in=["resolved", "closed"]).count()
        return format_html(
            '<span style="color: #dc2626; font-weight: 500;">{}</span>', count
        )


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
        ("created_at", RangeDateFilter),
        "raised_by",
        "assigned_to",
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

    def status_colored(self, obj):
        status_colors = {
            "open": "#dc2626",
            "assigned": "#d97706",
            "in_progress": "#0891b2",
            "pending": "#374151",
            "resolved": "#16a34a",
            "closed": "#6b7280",
        }
        color = status_colors.get(obj.status, "#374151")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status.replace("_", " ").title(),
        )

    status_colored.short_description = "Status"


class CommentAdmin(ModelAdmin):
    list_display = ("author", "ticket", "created_at")
    list_filter = ("created_at",)
    search_fields = ("text",)
    readonly_fields = ("created_at",)


class FeedbackAdmin(ModelAdmin):
    list_display = ("rated_by", "rating", "ticket", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("comments",)
    readonly_fields = ("created_at",)


# Register all models with Django's admin site using Unfold's ModelAdmin
admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Section, SectionAdmin)
admin.site.register(Facility, FacilityAdmin)
admin.site.register(Ticket, TicketAdmin)
admin.site.register(Comment, CommentAdmin)
admin.site.register(Feedback, FeedbackAdmin)

# Customize Django Admin Site
admin.site.site_header = "Resolver - Ticket Management"
admin.site.site_title = "Resolver Admin"
admin.site.index_title = "Maintenance Ticket Management Dashboard"


# Django Unfold Dashboard Callbacks and Badge Functions
def environment_callback(request):
    """Display environment information in header"""
    return "Development" if admin.site.name == "admin" else "Production"


def dashboard_callback(request, context):
    """Add dashboard cards with statistics"""
    # Get ticket statistics
    total_tickets = Ticket.objects.count()
    open_tickets = Ticket.objects.filter(
        status__in=["open", "assigned", "in_progress"]
    ).count()
    pending_tickets = Ticket.objects.filter(status="pending").count()
    resolved_tickets = Ticket.objects.filter(status="resolved").count()

    # Get user statistics
    total_users = CustomUser.objects.count()
    active_technicians = CustomUser.objects.filter(
        role="technician", is_active=True
    ).count()

    # Get facility statistics
    total_facilities = Facility.objects.count()
    active_facilities = Facility.objects.filter(status="active").count()

    # Dashboard cards data
    context.update(
        {
            "kpi": [
                {
                    "title": "Total Tickets",
                    "metric": total_tickets,
                    "footer": f"{open_tickets} active tickets",
                    "chart": 85,
                },
                {
                    "title": "Pending Tickets",
                    "metric": pending_tickets,
                    "footer": "Awaiting response",
                    "chart": (
                        (pending_tickets / total_tickets * 100)
                        if total_tickets > 0
                        else 0
                    ),
                },
                {
                    "title": "Resolution Rate",
                    "metric": (
                        f"{(resolved_tickets / total_tickets * 100):.1f}%"
                        if total_tickets > 0
                        else "0%"
                    ),
                    "footer": f"{resolved_tickets} resolved",
                    "chart": (
                        (resolved_tickets / total_tickets * 100)
                        if total_tickets > 0
                        else 0
                    ),
                },
                {
                    "title": "Active Technicians",
                    "metric": active_technicians,
                    "footer": f"{total_users} total users",
                    "chart": (
                        (active_technicians / total_users * 100)
                        if total_users > 0
                        else 0
                    ),
                },
            ]
        }
    )
    return context


def ticket_count_badge(request):
    """Display count of active tickets in sidebar"""
    count = Ticket.objects.filter(
        status__in=["open", "assigned", "in_progress"]
    ).count()
    return count if count > 0 else None


def user_count_badge(request):
    """Display count of active users in sidebar"""
    count = CustomUser.objects.filter(is_active=True).count()
    return count if count > 0 else None


def facility_count_badge(request):
    """Display count of active facilities in sidebar"""
    count = Facility.objects.filter(status="active").count()
    return count if count > 0 else None
