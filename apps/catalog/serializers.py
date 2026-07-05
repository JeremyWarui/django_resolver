from rest_framework import serializers

from apps.catalog.models import ServiceCategory, ServiceItem
from apps.sla.models import Priority


class PriorityInlineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.IntegerField()
    response_minutes = serializers.IntegerField()
    resolution_minutes = serializers.IntegerField()


class ServiceItemSerializer(serializers.ModelSerializer):
    """default_priority is a nullable override of the parent category's priority —
    read as a nested object, written via default_priority_id. Null means "inherit
    the category's default_priority" (see TicketCreateSerializer.validate)."""

    # Read: full nested object with minutes
    default_priority = PriorityInlineSerializer(read_only=True)
    # Write: accept the FK as an integer PK; null clears the override (inherit category)
    default_priority_id = serializers.PrimaryKeyRelatedField(
        source="default_priority",
        queryset=Priority.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    class Meta:
        model = ServiceItem
        fields = [
            "id",
            "category",
            "name",
            "description",
            "is_active",
            "default_priority",
            "default_priority_id",
        ]


class ServiceCategorySerializer(serializers.ModelSerializer):
    """R4: ServiceCategory has NO department FK.
    department is a derived read-only field computed from section_type.department.

    default_priority is a nested read representation but accepts a PK on write
    via the separate default_priority_id write field (excluded from output).
    """

    department = serializers.SerializerMethodField()
    # Read: full nested object with minutes
    default_priority = PriorityInlineSerializer(read_only=True)
    # Write: accept the FK as an integer PK
    default_priority_id = serializers.PrimaryKeyRelatedField(
        source="default_priority",
        queryset=Priority.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    items = ServiceItemSerializer(source="service_items", many=True, read_only=True)

    class Meta:
        model = ServiceCategory
        fields = [
            "id",
            "section_type",
            "name",
            "description",
            "is_active",
            "location_details",
            "default_priority",
            "default_priority_id",
            "department",
            "items",
        ]
        read_only_fields = ["department", "default_priority", "items"]

    def get_department(self, obj):
        dept = obj.section_type.department
        return {"id": dept.id, "name": dept.name, "code": dept.code}
