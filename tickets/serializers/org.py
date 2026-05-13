from rest_framework import serializers
from tickets.models import Campus, Department, CampusDepartment, CustomUser
from .common import format_user_info


class NestedCampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "code", "name"]


class NestedDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "code", "name"]


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "name", "code", "location"]


class DepartmentSerializer(serializers.ModelSerializer):
    manager_user = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["id", "name", "code", "manager_user"]

    def get_manager_user(self, obj):
        return format_user_info(obj.manager_user)


class CampusDepartmentSerializer(serializers.ModelSerializer):
    """Read/write serializer for CampusDepartment.

    On write: accepts campus_id, department_id, and optional head_of_department_id.
    On read: returns nested campus, department, and head_of_department info.
    """

    campus = NestedCampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.all(),
        source="campus",
        write_only=True,
        label="Campus ID",
    )
    department = NestedDepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="department",
        write_only=True,
        label="Department ID",
    )
    head_of_department = serializers.SerializerMethodField(read_only=True)
    head_of_department_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role__in=("hod", "admin")),
        source="head_of_department",
        write_only=True,
        required=False,
        allow_null=True,
        label="Head of Department user ID",
    )
    sections_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampusDepartment
        fields = [
            "id",
            "campus",
            "campus_id",
            "department",
            "department_id",
            "head_of_department",
            "head_of_department_id",
            "sections_count",
        ]

    def get_head_of_department(self, obj):
        return format_user_info(obj.head_of_department)

    def get_sections_count(self, obj):
        return obj.sections.count()


class AssignHODSerializer(serializers.ModelSerializer):
    """Slim serializer used only for the assign-HOD endpoint."""

    head_of_department_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role__in=("hod", "admin")),
        source="head_of_department",
        allow_null=True,
        label="Head of Department user ID",
    )
    head_of_department = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CampusDepartment
        fields = ["head_of_department_id", "head_of_department"]

    def get_head_of_department(self, obj):
        return format_user_info(obj.head_of_department)
