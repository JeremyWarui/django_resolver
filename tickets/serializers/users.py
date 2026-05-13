from rest_framework import serializers
from tickets.models import CustomUser, Section, Department


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    username = serializers.CharField(read_only=True)
    campus_name = serializers.CharField(
        source="primary_campus.name", read_only=True, allow_null=True
    )
    primary_department_name = serializers.CharField(
        source="primary_department.name", read_only=True, allow_null=True
    )
    sections = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Section.objects.all(), required=False
    )
    section_names = serializers.SerializerMethodField(read_only=True)
    primary_campus_id = serializers.IntegerField(
        source="primary_campus.id", read_only=True, allow_null=True
    )
    primary_department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source="primary_department",
        required=False,
        allow_null=True,
    )
    primary_campus_display = serializers.CharField(
        source="primary_campus", read_only=True, allow_null=True
    )
    primary_department_display = serializers.CharField(
        source="primary_department", read_only=True, allow_null=True
    )

    def get_section_names(self, obj):
        """Return formatted section display names bundled with the user — avoids a separate lookup."""
        result = []
        for s in obj.sections.select_related("campus_department__campus").all():
            campus_code = (
                s.campus_department.campus.code
                if s.campus_department and s.campus_department.campus
                else None
            )
            result.append(f"{campus_code}-{s.name}" if campus_code else s.name)
        return result

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
            "primary_department_name",
            "sections",
            "section_names",
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
