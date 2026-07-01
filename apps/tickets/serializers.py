from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import ServiceItem
from apps.facilities.models import Facility, FacilityType
from apps.facilities.validators import validate_location
from apps.org.models import SectionTechnician
from apps.tickets.models import (
    Ticket,
    TicketAttachment,
    TicketComment,
    TicketFeedback,
    TicketLocation,
    TicketLog,
)
from apps.tickets.services.routing import ServiceNotAvailableError, resolve_routing

User = get_user_model()


# ---------------------------------------------------------------------------
# Read serializers (Phase 6 — role-scoped list + detail)
# ---------------------------------------------------------------------------


class _UserMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name or obj.username


class _PriorityMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.IntegerField()


class _ServiceCategoryMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class _ServiceItemMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    category = _ServiceCategoryMinSerializer()


class _SectionMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    section_type_id = serializers.IntegerField()
    # section_type / campus_department are in select_related on ticket queryset (no N+1)
    section_type_name = serializers.CharField(
        source="section_type.name", read_only=True
    )
    name = serializers.CharField(source="section_type.name", read_only=True)
    campus_code = serializers.CharField(
        source="campus_department.campus.code", read_only=True
    )
    department_code = serializers.CharField(
        source="campus_department.department.code", read_only=True
    )


class _CampusMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class _FacilityTypeMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()


class _FacilityMinSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class _TicketLocationSerializer(serializers.Serializer):
    facility_type = _FacilityTypeMinSerializer(read_only=True)
    facility = _FacilityMinSerializer(read_only=True, allow_null=True)
    values = serializers.JSONField()


class TicketReadSerializer(serializers.ModelSerializer):
    """Role-aware read serializer for list and detail views."""

    service_item = _ServiceItemMinSerializer(read_only=True)
    section = _SectionMinSerializer(read_only=True)
    priority = _PriorityMinSerializer(read_only=True)
    assigned_to = _UserMinSerializer(read_only=True, allow_null=True)
    raised_by = _UserMinSerializer(read_only=True)
    raised_by_id = serializers.IntegerField(read_only=True)
    requester_campus = _CampusMinSerializer(read_only=True)
    location = _TicketLocationSerializer(read_only=True, allow_null=True)
    is_breaching = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_no",
            "raised_by",
            "raised_by_id",
            "requester_campus",
            "service_item",
            "section",
            "priority",
            "assigned_to",
            "description",
            "status",
            "current_level",
            "response_due_at",
            "resolution_due_at",
            "paused_at",
            "accumulated_pause",
            "is_breaching",
            "created_at",
            "updated_at",
            "resolved_at",
            "closed_at",
            "location",
        ]
        read_only_fields = fields

    def get_is_breaching(self, ticket):
        if ticket.status in ("resolved", "closed"):
            return False
        if ticket.resolution_due_at is None:
            return False
        return timezone.now() > ticket.resolution_due_at


class LocationInputSerializer(serializers.Serializer):
    facility_type = serializers.PrimaryKeyRelatedField(
        queryset=FacilityType.objects.all()
    )
    facility = serializers.PrimaryKeyRelatedField(
        queryset=Facility.objects.select_related("facility_type", "campus"),
        required=False,
        allow_null=True,
    )
    values = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )


class TicketCreateSerializer(serializers.Serializer):
    service_item = serializers.PrimaryKeyRelatedField(
        queryset=ServiceItem.objects.select_related(
            "category__section_type",
            "category__default_priority",
            "default_priority",
        )
    )
    location = LocationInputSerializer(required=False, allow_null=True)
    description = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        # 1. Resolve the requester's campus from their profile.
        try:
            campus = user.profile.campus
        except Exception:
            campus = None
        if campus is None:
            raise serializers.ValidationError("User has no campus assigned.")

        service_item = attrs["service_item"]

        # 2. Resolve the routing section.
        try:
            section = resolve_routing(campus.id, service_item.id)
        except ServiceNotAvailableError as exc:
            raise serializers.ValidationError({"service_item": str(exc)}) from exc

        # 3. Resolve priority: item-level override first, then category default.
        priority = (
            service_item.default_priority or service_item.category.default_priority
        )

        # 4. Handle location.
        location_input = attrs.get("location")
        if service_item.category.location_details:
            if not location_input:
                raise serializers.ValidationError(
                    {"location": "Location is required for this service."}
                )
            location_data = validate_location(
                location_input["facility_type"],
                location_input.get("facility"),
                location_input.get("values", {}),
                campus.id,
            )
        else:
            location_data = None

        # Store private attrs for use in create().
        attrs["_section"] = section
        attrs["_priority"] = priority
        attrs["_requester_campus"] = campus
        attrs["_location_data"] = location_data

        return attrs

    def create(self, validated_data):
        request = self.context["request"]

        section = validated_data.pop("_section")
        priority = validated_data.pop("_priority")
        requester_campus = validated_data.pop("_requester_campus")
        location_data = validated_data.pop("_location_data")

        # Remove the location input (not a model field).
        validated_data.pop("location", None)

        now = timezone.now()
        response_due_at = now + timedelta(minutes=priority.response_minutes)
        resolution_due_at = now + timedelta(minutes=priority.resolution_minutes)

        ticket = Ticket.objects.create(
            raised_by=request.user,
            requester_campus=requester_campus,
            service_item=validated_data["service_item"],
            section=section,
            priority=priority,
            description=validated_data.get("description", ""),
            response_due_at=response_due_at,
            resolution_due_at=resolution_due_at,
        )

        if location_data is not None:
            TicketLocation.objects.create(
                ticket=ticket,
                facility_type=location_data["facility_type"],
                facility=location_data["facility"],
                values=location_data["values"],
            )

        TicketLog.objects.create(
            ticket=ticket,
            event_type="created",
            actor=request.user,
            to_value=ticket.ticket_no,
        )

        return ticket


class TicketStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=["open", "assigned", "in_progress", "pending", "resolved", "closed"]
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")


class TicketAssignSerializer(serializers.Serializer):
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    def validate(self, attrs):
        ticket = self.context["ticket"]
        if not SectionTechnician.objects.filter(
            section=ticket.section, user=attrs["assigned_to"]
        ).exists():
            raise serializers.ValidationError(
                {"assigned_to": "User is not a technician in the ticket's section."}
            )
        return attrs


class TicketCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketComment
        fields = ["id", "author", "body", "visibility", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class TicketFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketFeedback
        fields = ["id", "rating", "comment", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value


class TicketAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = _UserMinSerializer(read_only=True)
    url = serializers.SerializerMethodField()
    size_saved_pct = serializers.SerializerMethodField()

    class Meta:
        model = TicketAttachment
        fields = [
            "id",
            "original_name",
            "mime_type",
            "original_size",
            "stored_size",
            "size_saved_pct",
            "url",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url

    def get_size_saved_pct(self, obj):
        if not obj.original_size:
            return 0
        return round((1 - obj.stored_size / obj.original_size) * 100, 1)
