from rest_framework import serializers
from .models import *

ESCALATION_STATUS_MAP = {
    0: {"code": "none", "label": "Not escalated"},
    1: {"code": "head_of_section", "label": "Escalated to Section Head"},
    2: {"code": "hod", "label": "Escalated to HOD (Maximum Level)"},
}
_ESCALATION_UNKNOWN = {"code": "unknown", "label": "Unknown"}


class UsernameField(serializers.RelatedField):
    """Custom field that returns just the username for user references"""

    def to_representation(self, value):
        return value.username


class NestedOrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "code", "name"]


class NestedCampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "code", "name"]


class NestedDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]


class NestedSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = ["id", "code", "name"]


class NestedFacilitySerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="facility_code", read_only=True)

    class Meta:
        model = Facility
        fields = ["id", "code", "name"]


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "code", "organization_type", "headquarters"]


class CampusSerializer(serializers.ModelSerializer):
    organization = NestedOrganizationSerializer(read_only=True)
    organization_id = serializers.PrimaryKeyRelatedField(
        queryset=Organization.objects.all(),
        source="organization",
        write_only=True,
        label="Organization ID",
    )

    class Meta:
        model = Campus
        fields = ["id", "name", "code", "location",
                  "organization", "organization_id"]


class DepartmentSerializer(serializers.ModelSerializer):
    campus = NestedCampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.all(),
        source="campus",
        write_only=True,
        label="Campus ID",
    )
    head_of_department = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "name",
            "code",
            "campus",
            "campus_id",
            "head_of_department",
            "is_active",
        ]

    def get_head_of_department(self, obj):
        if not obj.head_of_department:
            return None
        u = obj.head_of_department
        return {
            "id": u.id,
            "username": u.username,
            "name": f"{u.first_name} {u.last_name}".strip() or u.username,
        }


class FacilitySerializer(serializers.ModelSerializer):
    campus = NestedCampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.all(),
        source="campus",
        write_only=True,
        label="Campus ID",
    )

    class Meta:
        model = Facility
        fields = [
            "id",
            "name",
            "facility_code",
            "type",
            "status",
            "location",
            "campus",
            "campus_id",
            "purchase_date",
            "warranty_expiry",
            "asset_value",
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.role not in ("hod", "manager", "admin"):
            for f in ("purchase_date", "warranty_expiry", "asset_value"):
                fields.pop(f, None)
        return fields


class SectionSerializer(serializers.ModelSerializer):
    campus = NestedCampusSerializer(source="department.campus", read_only=True)
    department = NestedDepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        required=True,
    )
    section_head = serializers.SerializerMethodField()
    technicians = serializers.StringRelatedField(many=True, read_only=True)
    effective_sla_hours = serializers.IntegerField(read_only=True)

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "description",
            "code",
            "campus",
            "department",
            "department_id",
            "section_type",
            "sla_hours",
            "effective_sla_hours",
            "head_of_section",
            "technicians",
            "is_active",
        ]

    def get_section_head(self, obj):
        if not obj.head_of_section:
            return None
        u = obj.head_of_section
        return {
            "id": u.id,
            "username": u.username,
            "name": f"{u.first_name} {u.last_name}".strip() or u.username,
        }

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.role in ("user", "technician"):
            fields.pop("technicians", None)
        return fields


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(read_only=True)
    campus_name = serializers.CharField(
        source="primary_campus.name", read_only=True, allow_null=True
    )
    sections = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Section.objects.all(), required=False
    )
    primary_campus_id = serializers.IntegerField(
        source="primary_campus.id", read_only=True, allow_null=True
    )
    primary_department_id = serializers.IntegerField(
        source="primary_department.id", read_only=True, allow_null=True
    )
    primary_campus_display = serializers.CharField(
        source="primary_campus", read_only=True, allow_null=True
    )
    primary_department_display = serializers.CharField(
        source="primary_department", read_only=True, allow_null=True
    )

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
            "campus_name",
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
    raised_by = UsernameField(read_only=True)
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

    def get_assigned_to(self, obj):
        if not obj.assigned_to:
            return None
        name = f"{obj.assigned_to.first_name} {obj.assigned_to.last_name}".strip()
        return {"id": obj.assigned_to.id, "name": name or obj.assigned_to.username}

    def get_escalation_status(self, obj):
        return ESCALATION_STATUS_MAP.get(obj.escalation_level, _ESCALATION_UNKNOWN)

    def get_service_item(self, obj):
        if not obj.service_item:
            return None
        return {"id": obj.service_item.id, "name": obj.service_item.name}


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

    facility_id = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.all(),
        source="facility",
        write_only=True,
        allow_null=True,
        required=False,
        label="Facility ID",
    )

    floor_id = serializers.PrimaryKeyRelatedField(
        queryset=FacilityFloor.objects.all(),
        source="floor",
        write_only=True,
        allow_null=True,
        required=False,
        label="Floor ID",
    )

    room_id = serializers.PrimaryKeyRelatedField(
        queryset=FacilityRoom.objects.all(),
        source="room",
        write_only=True,
        allow_null=True,
        required=False,
        label="Room ID",
    )

    location_detail = serializers.CharField(
        source="location_details",
        allow_blank=True,
        allow_null=True,
        required=False,
        label="Location Detail",
    )

    section = NestedSectionSerializer(read_only=True)
    facility = NestedFacilitySerializer(read_only=True)
    floor = serializers.SerializerMethodField(read_only=True)
    room = serializers.SerializerMethodField(read_only=True)
    raised_by = UsernameField(read_only=True)
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
            "assigned_to_id",
            "assigned_to",
            "floor_id",
            "floor",
            "room_id",
            "room",
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

    def get_assigned_to(self, obj):
        u = obj.assigned_to if not isinstance(
            obj, dict) else obj.get("assigned_to")
        if not u:
            return None
        return {
            "id": u.id,
            "username": u.username,
            "name": f"{u.first_name} {u.last_name}".strip() or u.username,
            "role": u.role,
        }

    def get_floor(self, obj):
        floor = obj.floor if not isinstance(obj, dict) else obj.get("floor")
        if not floor:
            return None
        return {
            "id": floor.id,
            "name": floor.name,
            "order": floor.order,
            "facility": floor.facility_id,
        }

    def get_room(self, obj):
        room = obj.room if not isinstance(obj, dict) else obj.get("room")
        if not room:
            return None
        return {
            "id": room.id,
            "name": room.name,
            "code": room.code,
            "floor": room.floor_id,
        }

    def get_escalated_to(self, obj):
        u = obj.escalated_to if not isinstance(
            obj, dict) else obj.get("escalated_to")
        if not u:
            return None
        return {
            "id": u.id,
            "username": u.username,
            "name": f"{u.first_name} {u.last_name}".strip() or u.username,
            "role": u.role,
        }

    def get_available_technicians(self, obj):
        """Return technicians assignable to this ticket's section.

        Uses prefetched data from TicketDetailView (available_technicians_prefetch)
        to avoid a per-ticket DB query. Falls back to a direct query when the
        prefetch isn't present (e.g. in the create response path).
        """
        section = (
            obj.get("section")
            if isinstance(obj, dict)
            else getattr(obj, "section", None)
        )
        if not section:
            return []

        if hasattr(section, "available_technicians_prefetch"):
            return [
                {
                    "id": t.id,
                    "username": t.username,
                    "first_name": t.first_name,
                    "last_name": t.last_name,
                }
                for t in section.available_technicians_prefetch
            ]

        return list(
            CustomUser.objects.filter(role="technician", sections=section).values(
                "id", "username", "first_name", "last_name"
            )
        )

    def get_service_item(self, obj):
        si = obj.get("service_item") if isinstance(
            obj, dict) else getattr(obj, "service_item", None)
        if not si:
            return None
        return {"id": si.id, "name": si.name, "requires_approval": si.requires_approval}

    def get_escalation_status(self, obj):
        level = (
            obj.get("escalation_level", 0) if isinstance(obj, dict)
            else getattr(obj, "escalation_level", 0)
        )
        return ESCALATION_STATUS_MAP.get(level, _ESCALATION_UNKNOWN)

    def get_organizational_path(self, obj):
        """Return full organizational hierarchy as nested {id, code, name} objects."""
        section = (
            obj.get("section")
            if isinstance(obj, dict)
            else getattr(obj, "section", None)
        )
        if not section:
            return None
        try:
            dept = section.department
            campus = dept.campus if dept else None
            org = campus.organization if campus else None
            return {
                "organization": (
                    {"id": org.id, "code": org.code,
                        "name": org.name} if org else None
                ),
                "campus": (
                    {"id": campus.id, "code": campus.code, "name": campus.name}
                    if campus
                    else None
                ),
                "department": (
                    {"id": dept.id, "code": dept.code, "name": dept.name}
                    if dept
                    else None
                ),
                "section": {
                    "id": section.id,
                    "code": section.code,
                    "name": section.name,
                },
            }
        except (AttributeError, TypeError):
            return None

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


# PHASE 4: SERVICE CATALOGUE SERIALIZERS


class ServiceItemSerializer(serializers.ModelSerializer):
    section_type_code = serializers.SerializerMethodField()

    class Meta:
        model = ServiceItem
        fields = [
            "id",
            "category_id",
            "name",
            "description",
            "sla_hours",
            "requires_approval",
            "form_schema",
            "is_active",
            "section_type_code",
            "default_priority",
            "order",
            "request_count",
        ]

    def get_section_type_code(self, obj):
        return obj.category.section_type.code if obj.category else None


class ServiceCategorySerializer(serializers.ModelSerializer):
    service_items = ServiceItemSerializer(many=True, read_only=True)
    section_type_code = serializers.SerializerMethodField()

    class Meta:
        model = ServiceCategory
        fields = [
            "id",
            "section_type_id",
            "name",
            "description",
            "icon",
            "color",
            "order",
            "is_active",
            "service_items",
            "section_type_code",
        ]

    def get_section_type_code(self, obj):
        return obj.section_type.code if obj.section_type else None


class SectionTypeSerializer(serializers.ModelSerializer):
    service_categories = ServiceCategorySerializer(many=True, read_only=True)
    department_type_code = serializers.SerializerMethodField()

    class Meta:
        model = SectionType
        fields = [
            "id",
            "department_type_id",
            "name",
            "code",
            "staff_label",
            "default_sla_hours",
            "service_categories",
            "department_type_code",
        ]

    def get_department_type_code(self, obj):
        return obj.department_type.code if obj.department_type else None


class DepartmentTypeSerializer(serializers.ModelSerializer):
    section_types = SectionTypeSerializer(many=True, read_only=True)

    class Meta:
        model = DepartmentType
        fields = ["id", "name", "code", "description",
                  "is_active", "section_types"]


# PHASE 1: FACILITY FLOOR AND ROOM SERIALIZERS

class FacilityFloorSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(
        source='facility.name', read_only=True)
    rooms_count = serializers.SerializerMethodField()

    class Meta:
        model = FacilityFloor
        fields = ['id', 'facility', 'facility_name',
                  'name', 'order', 'rooms_count']

    def get_rooms_count(self, obj):
        return obj.rooms.count()


class FacilityRoomSerializer(serializers.ModelSerializer):
    floor_name = serializers.CharField(source='floor.name', read_only=True)

    class Meta:
        model = FacilityRoom
        fields = ['id', 'floor', 'floor_name', 'name', 'code']
