from rest_framework import serializers
from tickets.models import (
    Section, SectionType, CampusDepartment, CustomUser, TechnicianSection, Department,
)
from .common import format_user_info
from .org import NestedCampusSerializer, NestedDepartmentSerializer
from .catalogue import ServiceCategorySerializer


class NestedSectionSerializer(serializers.ModelSerializer):
    campus_code = serializers.CharField(
        source="campus_department.campus.code", read_only=True, default=None
    )
    department_code = serializers.CharField(
        source="campus_department.department.code", read_only=True, default=None
    )

    class Meta:
        model = Section
        fields = ["id", "code", "name", "campus_code", "department_code"]


class SectionSerializer(serializers.ModelSerializer):
    campus = NestedCampusSerializer(source="campus_department.campus", read_only=True)
    department = NestedDepartmentSerializer(source="campus_department.department", read_only=True)
    campus_department_id = serializers.PrimaryKeyRelatedField(
        queryset=CampusDepartment.objects.all(),
        source="campus_department",
        write_only=True,
        label="CampusDepartment ID",
    )
    section_type_id = serializers.PrimaryKeyRelatedField(
        queryset=SectionType.objects.all(),
        source="section_type",
        write_only=True,
        label="SectionType ID",
    )
    section_type_name = serializers.CharField(source="section_type.name", read_only=True)
    head_of_section = serializers.SerializerMethodField()
    effective_sla_hours = serializers.IntegerField(read_only=True)
    technician_count = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "code",
            "description",
            "campus",
            "department",
            "campus_department_id",
            "section_type_id",
            "section_type_name",
            "sla_hours",
            "effective_sla_hours",
            "head_of_section",
            "technician_count",
        ]

    def get_head_of_section(self, obj):
        return format_user_info(obj.head_of_section)

    def get_technician_count(self, obj):
        # Use annotated value if available (avoids N+1), otherwise query
        if hasattr(obj, "technician_count_annotated"):
            return obj.technician_count_annotated
        return obj.technician_links.count()


class SectionTypeSerializer(serializers.ModelSerializer):
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        label="Department ID",
    )
    department_code = serializers.CharField(source="department.code", read_only=True)
    service_categories = ServiceCategorySerializer(many=True, read_only=True)

    class Meta:
        model = SectionType
        fields = [
            "id",
            "department_id",
            "department_code",
            "name",
            "code",
            "description",
            "staff_label",
            "default_sla_hours",
            "service_categories",
        ]


class AssignHOSSerializer(serializers.ModelSerializer):
    """Slim serializer used only for the assign-HOS endpoint."""

    head_of_section_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role__in=("head_of_section", "admin")),
        source="head_of_section",
        allow_null=True,
        label="Head of Section user ID",
    )
    head_of_section = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Section
        fields = ["head_of_section_id", "head_of_section"]

    def get_head_of_section(self, obj):
        return format_user_info(obj.head_of_section)


class TechnicianSectionSerializer(serializers.ModelSerializer):
    """Serializer for TechnicianSection join table entries."""

    technician_info = serializers.SerializerMethodField(read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)
    section_display = serializers.CharField(source="section.__str__", read_only=True)

    class Meta:
        model = TechnicianSection
        fields = [
            "id",
            "technician",
            "section",
            "technician_info",
            "section_name",
            "section_display",
            "added_at",
        ]
        read_only_fields = ["added_at"]

    def get_technician_info(self, obj):
        return format_user_info(obj.technician)
