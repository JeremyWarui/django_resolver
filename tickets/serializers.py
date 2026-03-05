from rest_framework import serializers
from .models import *


class FacilitySerializer(serializers.ModelSerializer):
    campus_display = serializers.CharField(
        source='campus', read_only=True, allow_null=True)
    department_display = serializers.CharField(
        source='department', read_only=True, allow_null=True)
    campus_id = serializers.IntegerField(
        source='campus.id', read_only=True, allow_null=True)
    department_id = serializers.IntegerField(
        source='department.id', read_only=True, allow_null=True)

    class Meta:
        model = Facility
        fields = [
            "id", "name", "facility_type", "status", "location",
            "campus_id", "campus_display",
            "department_id", "department_display",
            "purchase_date", "warranty_expiry", "asset_value"
        ]


class SectionSerializer(serializers.ModelSerializer):
    technicians = serializers.StringRelatedField(many=True, read_only=True)
    department_id = serializers.IntegerField(
        source='department.id', read_only=True, allow_null=True)
    department_display = serializers.CharField(
        source='department', read_only=True, allow_null=True)
    section_head_display = serializers.CharField(
        source='section_head', read_only=True, allow_null=True)
    section_head_id = serializers.IntegerField(
        source='section_head.id', read_only=True, allow_null=True)

    class Meta:
        model = Section
        fields = [
            "id", "name", "description", "code",
            "department_id", "department_display",
            "section_head_id", "section_head_display",
            "technicians", "is_active"
        ]


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(read_only=True)
    sections = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Section.objects.all(), required=False
    )
    primary_campus_id = serializers.IntegerField(
        source='primary_campus.id', read_only=True, allow_null=True)
    primary_department_id = serializers.IntegerField(
        source='primary_department.id', read_only=True, allow_null=True)
    primary_campus_display = serializers.CharField(
        source='primary_campus', read_only=True, allow_null=True)
    primary_department_display = serializers.CharField(
        source='primary_department', read_only=True, allow_null=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "password",
            "role",
            "sections",
            "primary_campus_id",
            "primary_campus_display",
            "primary_department_id",
            "primary_department_display",
            "can_assign_tickets",
            "can_escalate_tickets",
            "can_view_analytics",
        ]

    def create(self, validated_data):
        first_name = validated_data.get("first_name")
        last_name = validated_data.get("last_name")
        email = validated_data.get("email", "")
        password = validated_data["password"]
        role = validated_data.get("role", "user")
        sections = validated_data.pop("sections", [])

        base_username = f"{first_name.lower()}.{last_name.lower()}"
        username = base_username
        counter = 1

        # Ensure username is unique
        while CustomUser.objects.filter(username=username).exists():
            username = f"{username}-{counter}"
            counter += 1

        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            role=role,
        )
        if sections:
            user.sections.set(sections)
        return user


class TinyTicketSerializer(serializers.ModelSerializer):
    """Minimal ticket serializer to avoid circular dependency during nested serialization."""

    class Meta:
        model = Ticket
        fields = ["id", "ticket_no"]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for ticket comments. Author and ticket are set from context."""

    author = serializers.StringRelatedField(read_only=True)
    ticket = TinyTicketSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "ticket", "text", "author", "created_at"]


class FeedbackSerializer(serializers.ModelSerializer):
    """Serializer for ticket feedback. Rated_by and ticket are set from context."""

    ticket = TinyTicketSerializer(read_only=True)
    rated_by = serializers.StringRelatedField(read_only=True)

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
    - Simple string for assigned_to_name (matches Nov 2025 optimization)
    - Escalation status included for list filtering/display
    """

    assigned_to_name = serializers.SerializerMethodField(read_only=True)
    section_id_value = serializers.IntegerField(
        source="section.id", read_only=True)
    facility_id_value = serializers.IntegerField(
        source="facility.id", read_only=True)
    escalation_status = serializers.SerializerMethodField(read_only=True)

    section = serializers.StringRelatedField(read_only=True)
    facility = serializers.StringRelatedField(read_only=True)
    raised_by = serializers.StringRelatedField(read_only=True)

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
            "section_id_value",
            "facility",
            "facility_id_value",
            "raised_by",
            "assigned_to_name",
            "created_at",
            "updated_at",
            "pending_reason",
            "escalation_level",
            "escalation_status",
            "is_due_for_escalation",
        ]

    def get_assigned_to_name(self, obj):
        """Return assigned technician name as simple string (no extra query)."""
        if obj.assigned_to:
            return f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}"
        return None

    def get_escalation_status(self, obj):
        """Return human-readable escalation status"""
        if obj.escalation_level == 0:
            return "Not escalated"
        elif obj.escalation_level == 1:
            return "Escalated to Section Head"
        elif obj.escalation_level == 2:
            return "Escalated to HOD (Maximum Level)"
        return "Unknown"


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
        label="Section ID",
    )

    # Read-only section_id for frontend consumption
    section_id_value = serializers.IntegerField(
        source="section.id", read_only=True)

    facility_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(),
        source="facility",
        write_only=True,
        label="Facility ID",
    )

    # Read-only facility_id for frontend consumption
    facility_id_value = serializers.IntegerField(
        source="facility.id", read_only=True)

    section = serializers.StringRelatedField(read_only=True)
    facility = serializers.StringRelatedField(read_only=True)
    raised_by = serializers.StringRelatedField(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    escalated_to = serializers.StringRelatedField(read_only=True)
    comments = CommentSerializer(many=True, read_only=True)
    feedback = FeedbackSerializer(read_only=True)

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
            "section_id_value",
            "facility_id",
            "facility",
            "facility_id_value",
            "raised_by",
            "assigned_to_id",
            "assigned_to",
            "available_technicians",
            "created_at",
            "updated_at",
            "resolved_at",
            "pending_reason",
            # Escalation fields
            "escalation_level",
            "escalated_to",
            "escalated_at",
            "escalation_reason",
            "escalation_status",
            "auto_escalation_enabled",
            "next_escalation_due",
            "escalation_threshold_hours",
            "is_due_for_escalation",
            "organizational_path",
            # Relationships
            "comments",
            "feedback",
        ]

    def get_available_technicians(self, obj):
        """Return list of technicians who can be assigned to this ticket."""
        if obj.section:
            technicians = CustomUser.objects.filter(
                role="technician", sections=obj.section
            ).values("id", "username", "first_name", "last_name")
            return list(technicians)
        return []

    def get_escalation_status(self, obj):
        """Return human-readable escalation status"""
        if obj.escalation_level == 0:
            return "Not escalated"
        elif obj.escalation_level == 1:
            return "Escalated to Section Head"
        elif obj.escalation_level == 2:
            return "Escalated to HOD (Maximum Level)"
        return "Unknown"

    def get_organizational_path(self, obj):
        """Return full organizational hierarchy path for the ticket"""
        try:
            if obj.section and obj.section.department:
                campus = obj.section.department.campus
                org = campus.organization if campus else None
                return {
                    'organization': str(org) if org else None,
                    'campus': str(campus) if campus else None,
                    'department': str(obj.section.department) if obj.section.department else None,
                    'section': str(obj.section) if obj.section else None,
                }
        except (AttributeError, TypeError):
            pass
        return None

    def update(self, instance, validated_data):
        """Use default ModelSerializer update then let services call
        model-level change methods to perform and log stateful changes.

        We intentionally don't forward performed_by here; services should
        call `change_status` / `change_assignment` on the model to perform
        atomic state changes and logging.
        """
        return super().update(instance, validated_data)
