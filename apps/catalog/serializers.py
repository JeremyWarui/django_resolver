from rest_framework import serializers

from apps.catalog.models import ServiceCategory, ServiceItem


class PriorityInlineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.IntegerField()
    response_minutes = serializers.IntegerField()
    resolution_minutes = serializers.IntegerField()


class ServiceItemSerializer(serializers.ModelSerializer):
    default_priority = PriorityInlineSerializer(read_only=True)

    class Meta:
        model = ServiceItem
        fields = ["id", "category", "name", "description", "is_active", "default_priority"]


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
        queryset=__import__("apps.sla.models", fromlist=["Priority"]).Priority.objects.all(),
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
