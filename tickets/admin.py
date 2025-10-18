from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *



# Register your models here.

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "role", "is_staff", "is_active")
    list_filter = ("role","is_staff", "is_active", "sections_specialized_in")
    fieldsets = UserAdmin.fieldsets + (
        ('Role and Specialization', { 'fields': ('role', 'sections_specialized_in')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role', { 'fields': ('role', )}),
    )
    search_fields = ("username", "email", "role")
    ordering = ("username",)

# register section
@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "description")

# register facilities
@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "status", "location")
    list_filter = ("type", "status")

# register tickets
@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_no", "title", "description", "section", "facility", "raised_by", "status", "assigned_to", "created_at", "updated_at")
    list_filter = ("section", "facility", "status", "raised_by", "assigned_to")
    search_fields = ("title", "facility", "status", "assigned_to__username", "raised_by__username")

# register comments
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("author", "text", "created_at", "ticket")
    list_filter = ("author", "ticket")
    search_fields = ("author__username", "text", "ticket__title")

# register feedback
@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("rated_by", "rating", "created_at", "ticket")
    search_fields = ("rated_by__username", "ticket__title")