from rest_framework import serializers
from tickets.models import ServiceCategory, ServiceItem, SectionType


class ServiceItemSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=ServiceCategory.objects.all(),
        source="category",
        label="Category ID",
    )
    section_type_code = serializers.SerializerMethodField(read_only=True)

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
            "default_priority",
            "order",
            "section_type_code",
        ]

    def get_section_type_code(self, obj):
        return obj.category.section_type.code if obj.category else None


class ServiceCategorySerializer(serializers.ModelSerializer):
    section_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SectionType.objects.all(),
        source="section_type",
        label="SectionType ID",
    )
    service_items = ServiceItemSerializer(many=True, read_only=True)
    section_type_name = serializers.CharField(source="section_type.name", read_only=True)

    class Meta:
        model = ServiceCategory
        fields = [
            "id",
            "section_type_id",
            "section_type_name",
            "name",
            "description",
            "icon",
            "order",
            "is_active",
            "service_items",
        ]
