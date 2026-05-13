from rest_framework import serializers
from tickets.models import (
    Ticket, Comment, Feedback, Section, Facility, CustomUser,
    ServiceItem, Department,
)
from .common import UsernameField, format_user_info, format_escalation_status, format_service_item
from .sections import NestedSectionSerializer
from .facilities import NestedFacilitySerializer


class TinyTicketSerializer(serializers.ModelSerializer):
    """Minimal ticket serializer to avoid circular dependency during nested serialization."""

    class Meta:
        model = Ticket
        fields = ["id", "ticket_no"]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for ticket comments. Author and ticket are set from context."""

    author = UsernameField(read_only=True)
    ticket = TinyTicketSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "ticket", "text", "author", "created_at"]


class FeedbackSerializer(serializers.ModelSerializer):
    """Serializer for ticket feedback. Rated_by and ticket are set from context."""

    ticket = TinyTicketSerializer(read_only=True)
    rated_by = UsernameField(read_only=True)

    class Meta:
        model = Feedback
        fields = ["id", "ticket", "rated_by",
                  "rating", "comment", "created_at"]


class TicketListSerializer(serializers.ModelSerializer):
    """
    Optimized serializer for ticket list view.
    - NO available_technicians (frontend fetches dynamically)
    - NO comments (loaded separately if needed)
    - NO feedback (loaded separately if needed)
    - Nested section/facility objects with id, code, name
    - Nested assigned_to with id and name
    - Escalation status as {code, label} object
    """

    section = NestedSectionSerializer(read_only=True)
    facility = NestedFacilitySerializer(read_only=True)
    raised_by = serializers.SerializerMethodField(read_only=True)
    assigned_to = serializers.SerializerMethodField(read_only=True)
    escalation_status = serializers.SerializerMethodField(read_only=True)
    service_item = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_no",
            "title",
            "description",
            "status",
            "priority",
            "section",
            "facility",
            "raised_by",
            "assigned_to",
            "created_at",
            "updated_at",
            "pending_reason",
            "pending_comment",
            "escalation_level",
            "escalation_status",
            "is_due_for_escalation",
            "service_item",
            "form_data",
        ]

    def get_raised_by(self, obj):
        user = obj.raised_by
        if not user:
            return None
        name = f"{user.first_name} {user.last_name}".strip()
        return name or user.username

    def get_assigned_to(self, obj):
        return format_user_info(obj.assigned_to)

    def get_escalation_status(self, obj):
        return format_escalation_status(obj.escalation_level)

    def get_service_item(self, obj):
        return format_service_item(obj.service_item)


class TicketSerializer(serializers.ModelSerializer):
    """Main ticket serializer with nested relationships and escalation support."""

    assigned_to_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role="technician"),
        source="assigned_to",
        allow_null=True,
        required=False,
        write_only=True,
        label="Assigned_To ID",
    )

    # Add field to show available technicians for the ticket's section
    available_technicians = serializers.SerializerMethodField(read_only=True)

    section_id = serializers.PrimaryKeyRelatedField(
        queryset=Section.objects.all(),
        source="section",
        write_only=True,
        required=False,
        allow_null=True,
        label="Section ID",
    )

    facility_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(),
        source="facility",
        write_only=True,
        allow_null=True,
        required=False,
        label="Facility ID",
    )

    location_detail = serializers.CharField(
        allow_blank=True,
        allow_null=True,
        required=False,
    )

    section = NestedSectionSerializer(read_only=True)
    facility = NestedFacilitySerializer(read_only=True)
    raised_by = serializers.SerializerMethodField(read_only=True)
    raised_by_id = serializers.IntegerField(
        source="raised_by.id", read_only=True)
    assigned_to = serializers.SerializerMethodField(read_only=True)
    escalated_to = serializers.SerializerMethodField(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    feedback = FeedbackSerializer(read_only=True)

    service_item_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceItem.objects.filter(is_active=True),
        source="service_item",
        allow_null=True,
        required=False,
        write_only=True,
        label="Service Item ID",
    )
    service_item = serializers.SerializerMethodField(read_only=True)

    # Escalation read-only fields
    escalation_status = serializers.SerializerMethodField(read_only=True)
    organizational_path = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_no",
            "title",
            "description",
            "status",
            "priority",
            "section_id",
            "section",
            "facility_id",
            "facility",
            "raised_by",
            "raised_by_id",
            "assigned_to_id",
            "assigned_to",
            "available_technicians",
            "created_at",
            "updated_at",
            "resolved_at",
            "location_detail",
            "pending_reason",
            "pending_comment",
            # Escalation fields
            "escalation_level",
            "escalated_to",
            "escalated_at",
            "escalation_reason",
            "escalation_status",
            # auto_escalation_enabled — omitted from response (internal system setting)
            # escalation_threshold_hours — TODO: move to Section model as per-section SLA
            "next_escalation_due",
            "is_due_for_escalation",
            "organizational_path",
            # Relationships
            "comments",
            "feedback",
            # Service catalogue
            "service_item_id",
            "service_item",
            "form_data",
        ]

    def get_available_technicians(self, obj):
        """Technicians linked to the ticket's section via TechnicianSection."""
        section = obj.section if not isinstance(obj, dict) else obj.get("section")
        if not section:
            return []
        return [
            {"id": ts.technician.id, "username": ts.technician.username,
             "full_name": ts.technician.get_full_name()}
            for ts in section.technician_links.select_related("technician").all()
        ]

    def get_raised_by(self, obj):
        user = obj.raised_by if not isinstance(
            obj, dict) else obj.get("raised_by")
        if not user:
            return None
        name = f"{user.first_name} {user.last_name}".strip()
        return name or user.username

    def get_assigned_to(self, obj):
        u = obj.assigned_to if not isinstance(
            obj, dict) else obj.get("assigned_to")
        return format_user_info(u)

    def get_escalated_to(self, obj):
        u = obj.escalated_to if not isinstance(
            obj, dict) else obj.get("escalated_to")
        return format_user_info(u)

    def get_service_item(self, obj):
        si = obj.get("service_item") if isinstance(
            obj, dict) else getattr(obj, "service_item", None)
        return format_service_item(si)

    def get_escalation_status(self, obj):
        level = obj.get("escalation_level", 0) if isinstance(
            obj, dict) else getattr(obj, "escalation_level", 0)
        return format_escalation_status(level)

    def get_organizational_path(self, obj):
        """Return campus → department → section hierarchy for display."""
        cd = obj.campus_department if not isinstance(obj, dict) else None
        section = obj.section if not isinstance(obj, dict) else None
        if not cd:
            return None
        return {
            "campus": {"id": cd.campus.id, "code": cd.campus.code, "name": cd.campus.name},
            "department": {"id": cd.department.id, "code": cd.department.code, "name": cd.department.name},
            "section": (
                {"id": section.id, "code": section.code, "name": section.name}
                if section else None
            ),
        }

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if not request:
            return fields
        role = request.user.role
        # available_technicians: only needed by those who can assign tickets
        if role not in ("head_of_section", "hod", "admin"):
            fields.pop("available_technicians", None)
        # Detailed escalation fields: not actionable for regular users
        if role == "user":
            for f in (
                "escalated_to",
                "escalated_at",
                "escalation_reason",
                "next_escalation_due",
            ):
                fields.pop(f, None)
        # Organizational path: only useful for management-level and above
        if role in ("user", "technician"):
            fields.pop("organizational_path", None)
        return fields

    def update(self, instance, validated_data):
        """Use default ModelSerializer update then let services call
        model-level change methods to perform and log stateful changes.

        We intentionally don't forward performed_by here; services should
        call `change_status` / `change_assignment` on the model to perform
        atomic state changes and logging.
        """
        return super().update(instance, validated_data)


class TicketCreateSerializer(serializers.Serializer):
    """Input serializer for the dedicated ticket creation endpoint.

    Accepts the user's department selection and optional service catalogue
    choice. The view resolves CampusDepartment and Section automatically
    from these fields + the authenticated user's primary_campus.
    """

    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
    )
    service_item_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceItem.objects.filter(is_active=True).select_related(
            "category__section_type__department"
        ),
        source="service_item",
        required=False,
        allow_null=True,
        help_text="Resolves the section automatically via service catalogue.",
    )
    title = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500)
    form_data = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Submission data for service item's dynamic form fields.",
    )
    facility_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(),
        source="facility",
        required=False,
        allow_null=True,
    )
    location_detail = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="",
    )
