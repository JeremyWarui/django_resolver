"""
Organizational-aware filter classes for DRF.

These filters enable role-based filtering across the organizational hierarchy
while respecting user scope boundaries.
"""

from django_filters import rest_framework as filters
from tickets.models import Ticket, Section, Facility, Campus, Department


class OrganizationalScopeFilterMixin:
    """
    Mixin to add organizational scope filtering to any filter class.
    Automatically restricts querysets based on user's role and organization hierarchy.
    """

    def get_queryset(self, queryset):
        """Filter queryset based on user's organizational scope"""
        user = self.request.user if hasattr(self, "request") else None
        if not user or not user.is_authenticated:
            return queryset.none()

        # Apply role-based filtering
        if user.role == "admin":
            return queryset
        elif user.role == "director":
            # Director sees items in their organization
            return self._filter_by_organization(queryset, user)
        elif user.role == "hod":
            # HOD sees items in their campus
            return self._filter_by_campus(queryset, user)
        elif user.role == "section_head":
            # Section head sees items in their department
            return self._filter_by_department(queryset, user)
        elif user.role in ["technician", "user"]:
            # Technician/user sees items in their accessible sections
            return self._filter_by_section(queryset, user)

        return queryset.none()

    def _filter_by_organization(self, queryset, user):
        """Override in subclass to implement organization filtering"""
        return queryset

    def _filter_by_campus(self, queryset, user):
        """Override in subclass to implement campus filtering"""
        return queryset

    def _filter_by_department(self, queryset, user):
        """Override in subclass to implement department filtering"""
        return queryset

    def _filter_by_section(self, queryset, user):
        """Override in subclass to implement section filtering"""
        return queryset


class TicketFilter(filters.FilterSet, OrganizationalScopeFilterMixin):
    """
    Advanced filter for tickets with organizational scope awareness.

    Supports filtering by:
    - status: open, assigned, in_progress, pending, resolved, closed
    - escalation_level: 0 (none), 1 (section_head), 2 (hod)
    - escalation_status: not escalated, escalated to section head, escalated to hod
    - assigned_to: specific technician
    - section: specific section
    - is_due_for_escalation: boolean
    """

    status = filters.ChoiceFilter(
        choices=Ticket.STATUS_CHOICES, help_text="Filter by ticket status"
    )

    escalation_level = filters.NumberFilter(
        field_name="escalation_level",
        help_text="Filter by escalation level (0=none, 1=section_head, 2=hod)",
    )

    escalation_status = filters.CharFilter(
        method="filter_by_escalation_status",
        help_text="Filter by escalation status (not_escalated, escalated_l1, escalated_l2)",
    )

    is_overdue = filters.BooleanFilter(
        method="filter_by_overdue",
        help_text="Filter overdue tickets (>7 days in open/assigned/in_progress)",
    )

    is_due_for_escalation = filters.BooleanFilter(
        field_name="is_due_for_escalation",
        help_text="Filter tickets due for auto-escalation",
    )

    section = filters.ModelChoiceFilter(
        queryset=Section.objects.all(), help_text="Filter by section"
    )

    department = filters.ModelChoiceFilter(
        queryset=Department.objects.all(), help_text="Filter by department"
    )

    campus = filters.ModelChoiceFilter(
        queryset=Campus.objects.all(), help_text="Filter by campus"
    )

    class Meta:
        model = Ticket
        fields = ["status", "escalation_level", "section", "assigned_to"]

    def filter_by_escalation_status(self, queryset, name, value):
        """Filter by escalation status"""
        if value == "not_escalated":
            return queryset.filter(escalation_level=0)
        elif value == "escalated_l1":
            return queryset.filter(escalation_level=1)
        elif value == "escalated_l2":
            return queryset.filter(escalation_level=2)
        return queryset

    def filter_by_overdue(self, queryset, name, value):
        """Filter by overdue status"""
        if value:
            from django.utils import timezone
            from datetime import timedelta

            seven_days_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(
                created_at__lt=seven_days_ago,
                status__in=["open", "assigned", "in_progress"],
            )
        return queryset

    def _filter_by_organization(self, queryset, user):
        """Filter to organization level"""
        if user.primary_campus:
            return queryset.filter(
                section__department__campus__organization=user.primary_campus.organization
            )
        return queryset

    def _filter_by_campus(self, queryset, user):
        """Filter to campus level"""
        if user.primary_campus:
            return queryset.filter(section__department__campus=user.primary_campus)
        return queryset

    def _filter_by_department(self, queryset, user):
        """Filter to department level"""
        if user.primary_department:
            return queryset.filter(section__department=user.primary_department)
        return queryset

    def _filter_by_section(self, queryset, user):
        """Filter to section level"""
        return queryset.filter(section__in=user.sections.all())


class SectionFilter(filters.FilterSet, OrganizationalScopeFilterMixin):
    """Filter for sections with organizational scope awareness."""

    department = filters.ModelChoiceFilter(
        queryset=Department.objects.all(), help_text="Filter by department"
    )

    is_active = filters.BooleanFilter(
        field_name="is_active", help_text="Filter by active status"
    )

    class Meta:
        model = Section
        fields = ["department", "is_active"]

    def _filter_by_organization(self, queryset, user):
        if user.primary_campus:
            return queryset.filter(
                department__campus__organization=user.primary_campus.organization
            )
        return queryset

    def _filter_by_campus(self, queryset, user):
        if user.primary_campus:
            return queryset.filter(department__campus=user.primary_campus)
        return queryset

    def _filter_by_department(self, queryset, user):
        if user.primary_department:
            return queryset.filter(department=user.primary_department)
        return queryset

    def _filter_by_section(self, queryset, user):
        return queryset.filter(pk__in=user.sections.all())


class FacilityFilter(filters.FilterSet, OrganizationalScopeFilterMixin):
    """Filter for facilities with organizational scope awareness."""

    campus = filters.ModelChoiceFilter(
        queryset=Campus.objects.all(), help_text="Filter by campus"
    )

    department = filters.ModelChoiceFilter(
        queryset=Department.objects.all(), help_text="Filter by department"
    )

    facility_type = filters.ChoiceFilter(
        choices=Facility.FACILITY_TYPE_CHOICES, help_text="Filter by facility type"
    )

    status = filters.ChoiceFilter(
        choices=Facility.STATUS_CHOICES, help_text="Filter by facility status"
    )

    class Meta:
        model = Facility
        fields = ["campus", "department", "facility_type", "status"]

    def _filter_by_organization(self, queryset, user):
        if user.primary_campus:
            return queryset.filter(
                campus__organization=user.primary_campus.organization
            )
        return queryset

    def _filter_by_campus(self, queryset, user):
        if user.primary_campus:
            return queryset.filter(campus=user.primary_campus)
        return queryset

    def _filter_by_department(self, queryset, user):
        if user.primary_department:
            return queryset.filter(department=user.primary_department)
        return queryset

    def _filter_by_section(self, queryset, user):
        # Technicians/users see facilities in their campus
        if user.primary_campus:
            return queryset.filter(campus=user.primary_campus)
        return queryset
