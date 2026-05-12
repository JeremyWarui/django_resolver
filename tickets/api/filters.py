"""
Organizational-aware filter classes for DRF.

These filters enable role-based filtering across the organizational hierarchy
while respecting user scope boundaries.
"""

from django_filters import rest_framework as filters
from tickets.models import Ticket, Section, Facility, Campus, Department, ServiceItem


class OrganizationalScopeFilterMixin:
    """
    Mixin to add organizational scope filtering to any filter class.
    Automatically restricts querysets based on user's role and organization hierarchy.

    Subclasses should define ORGANIZATIONAL_FILTER_PATHS as a dict mapping scope levels
    to field paths and user attributes. Example:

        ORGANIZATIONAL_FILTER_PATHS = {
            'organization': ('section__department__campus__organization', 'primary_campus'),
            'campus': ('section__department__campus', 'primary_campus'),
            'department': ('section__campus_department', 'primary_campus_department'),
            'section': ('section', 'sections'),
        }
    """

    # Default filter paths (can be overridden in subclasses)
    ORGANIZATIONAL_FILTER_PATHS = None

    def get_queryset(self, queryset):
        """Filter queryset based on user's organizational scope"""
        user = self.request.user if hasattr(self, "request") else None
        if not user or not user.is_authenticated:
            return queryset.none()

        # Apply role-based filtering
        if user.role == "admin":
            return queryset
        elif user.role == "manager":
            return self._apply_org_filter(queryset, user, 'organization')
        elif user.role == "hod":
            return self._apply_org_filter(queryset, user, 'campus')
        elif user.role == "head_of_section":
            return self._apply_org_filter(queryset, user, 'department')
        elif user.role in ["technician", "user"]:
            return self._apply_org_filter(queryset, user, 'section')

        return queryset.none()

    def _apply_org_filter(self, queryset, user, scope_level):
        """
        Generic filter application using ORGANIZATIONAL_FILTER_PATHS.
        If not defined, falls back to _filter_by_* methods for backward compatibility.
        """
        if not self.ORGANIZATIONAL_FILTER_PATHS:
            # Fallback to old method-based approach for backward compatibility
            method = getattr(self, f'_filter_by_{scope_level}', None)
            if method:
                return method(queryset, user)
            return queryset

        filter_config = self.ORGANIZATIONAL_FILTER_PATHS.get(scope_level)
        if not filter_config:
            return queryset

        field_path, user_attr = filter_config
        user_value = getattr(user, user_attr, None)

        # Handle special case for M2M fields (sections)
        if user_attr == 'sections':
            if user_value:
                return queryset.filter(**{f'{field_path}__in': user_value.all()})
        else:
            if user_value:
                return queryset.filter(**{field_path: user_value})

        return queryset

    # Keep deprecated methods for backward compatibility
    def _filter_by_organization(self, queryset, user):
        """Deprecated: Use ORGANIZATIONAL_FILTER_PATHS instead"""
        return queryset

    def _filter_by_campus(self, queryset, user):
        """Deprecated: Use ORGANIZATIONAL_FILTER_PATHS instead"""
        return queryset

    def _filter_by_department(self, queryset, user):
        """Deprecated: Use ORGANIZATIONAL_FILTER_PATHS instead"""
        return queryset

    def _filter_by_section(self, queryset, user):
        """Deprecated: Use ORGANIZATIONAL_FILTER_PATHS instead"""
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

    # Organizational filter field paths
    ORGANIZATIONAL_FILTER_PATHS = {
        'organization': ('section__department__campus__organization', 'primary_campus'),
        'campus': ('section__department__campus', 'primary_campus'),
        'department': ('section__campus_department', 'primary_campus_department'),
        'section': ('section', 'sections'),
    }

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

    service_item = filters.ModelChoiceFilter(
        queryset=ServiceItem.objects.all(), help_text="Filter by service item"
    )

    class Meta:
        model = Ticket
        fields = ["status", "escalation_level",
                  "section", "assigned_to", "service_item"]

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


class SectionFilter(filters.FilterSet, OrganizationalScopeFilterMixin):
    """Filter for sections with organizational scope awareness."""

    # Organizational filter field paths
    ORGANIZATIONAL_FILTER_PATHS = {
        'organization': ('department__campus__organization', 'primary_campus'),
        'campus': ('department__campus', 'primary_campus'),
        'department': ('department', 'primary_campus_department'),
        'section': ('pk', 'sections'),
    }

    department = filters.ModelChoiceFilter(
        queryset=Department.objects.all(), help_text="Filter by department"
    )

    is_active = filters.BooleanFilter(
        field_name="is_active", help_text="Filter by active status"
    )

    class Meta:
        model = Section
        fields = ["department", "is_active"]


class FacilityFilter(filters.FilterSet, OrganizationalScopeFilterMixin):
    """Filter for facilities with organizational scope awareness."""

    # Organizational filter field paths
    ORGANIZATIONAL_FILTER_PATHS = {
        'organization': ('campus__organization', 'primary_campus'),
        'campus': ('campus', 'primary_campus'),
        'department': ('department', 'primary_campus_department'),
        # Technicians/users see facilities in their campus
        'section': ('campus', 'primary_campus'),
    }

    campus = filters.ModelChoiceFilter(
        queryset=Campus.objects.all(), help_text="Filter by campus"
    )

    department = filters.ModelChoiceFilter(
        queryset=Department.objects.all(), help_text="Filter by department"
    )

    facility_type = filters.ChoiceFilter(
        choices=Facility.FACILITY_CHOICES, help_text="Filter by facility type"
    )

    status = filters.ChoiceFilter(
        choices=[
            ("active", "Active"),
            ("maintenance", "Under Maintenance"),
            ("inactive", "Inactive"),
            ("decommissioned", "Decommissioned"),
        ],
        help_text="Filter by facility status",
    )

    class Meta:
        model = Facility
        fields = ["campus", "department", "facility_type", "status"]
