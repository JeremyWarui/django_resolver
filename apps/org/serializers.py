from rest_framework import serializers
from apps.org.models import (
    Campus,
    CampusDepartment,
    Department,
    Section,
    SectionTechnician,
    SectionType,
)


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "name", "code", "location"]


class DepartmentSerializer(serializers.ModelSerializer):
    campuses = serializers.SerializerMethodField()
    heads_of_department = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ["id", "name", "code", "manager_user", "campuses", "heads_of_department"]

    def get_campuses(self, obj):
        return [
            {
                "campus_department_id": cd.id,
                "id": cd.campus.id,
                "name": cd.campus.name,
                "code": cd.campus.code,
            }
            for cd in obj.campus_departments.select_related("campus").all()
        ]

    def get_heads_of_department(self, obj):
        result = []
        for cd in obj.campus_departments.select_related("campus", "head_of_department").all():
            if cd.head_of_department:
                hod = cd.head_of_department
                result.append({
                    "campus_department_id": cd.id,
                    "campus": cd.campus.code,
                    "hod": {
                        "id": hod.id,
                        "name": f"{hod.first_name} {hod.last_name}".strip() or hod.username,
                        "username": hod.username,
                    },
                })
        return result


class SectionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SectionType
        fields = ["id", "department", "name", "code"]


class SectionTypeWithCategoriesSerializer(serializers.ModelSerializer):
    """Read serializer for the QuickActions widget.
    Returns each section type with flattened department fields and its
    active service categories — the shape expected by the frontend."""

    department_id = serializers.IntegerField(source="department.id", read_only=True)
    department_code = serializers.CharField(source="department.code", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    service_categories = serializers.SerializerMethodField()

    class Meta:
        model = SectionType
        fields = [
            "id",
            "name",
            "code",
            "department_id",
            "department_code",
            "department_name",
            "service_categories",
        ]

    def get_service_categories(self, obj):
        return [
            {
                "id": cat.id,
                "name": cat.name,
                "section_type_name": obj.name,
                "is_active": cat.is_active,
                "location_details": cat.location_details,
                "icon": None,
                "service_items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "description": item.description,
                        "is_active": item.is_active,
                    }
                    for item in cat.service_items.filter(is_active=True).order_by(
                        "name"
                    )
                ],
            }
            for cat in obj.service_categories.filter(is_active=True).order_by("name")
        ]


class CampusDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampusDepartment
        fields = ["id", "campus", "department", "head_of_department"]


class SectionSerializer(serializers.ModelSerializer):
    """Read/write serializer for Section.

    Read (list/retrieve): returns enriched fields the frontend expects —
    name, code, campus, department, technician_count.
    Write (create/update): accepts campus_department + section_type FKs as before.
    """

    # ── Computed read fields ──────────────────────────────────────────────
    name = serializers.SerializerMethodField()
    code = serializers.SerializerMethodField()
    campus = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    technician_count = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = [
            "id",
            "name",
            "code",
            "campus",
            "department",
            "section_type",
            "campus_department",
            "hos",
            "is_active",
            "technician_count",
            "description",
        ]

    def get_name(self, obj):
        return obj.section_type.name if obj.section_type_id else None

    def get_code(self, obj):
        return obj.section_type.code if obj.section_type_id else None

    def get_campus(self, obj):
        campus = obj.campus_department.campus
        return {"id": campus.id, "name": campus.name, "code": campus.code}

    def get_department(self, obj):
        dept = obj.campus_department.department
        return {"id": dept.id, "name": dept.name, "code": dept.code}

    def get_technician_count(self, obj):
        # Populated by annotate(technician_count=...) on the viewset queryset;
        # fall back to a live count only when the annotation is absent.
        if hasattr(obj, "technician_count"):
            return obj.technician_count
        return obj.technician_links.count()

    def get_description(self, obj):
        return ""


class SectionTechnicianSerializer(serializers.ModelSerializer):
    class Meta:
        model = SectionTechnician
        fields = ["id", "user", "section", "added_at"]
        read_only_fields = ["added_at"]
