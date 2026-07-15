from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import RoleAssignment, UserProfile

User = get_user_model()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _campus_from_ra(ra):
    """Resolve the campus object from any role assignment variant."""
    if ra is None:
        return None
    if ra.section_id and ra.section and ra.section.campus_department:
        return ra.section.campus_department.campus
    if ra.campus_department_id and ra.campus_department:
        return ra.campus_department.campus
    return None


def _department_from_ra(ra):
    """Resolve the department object from any role assignment variant."""
    if ra is None:
        return None
    if ra.department_id and ra.department:
        return ra.department
    if ra.section_id and ra.section and ra.section.campus_department:
        return ra.section.campus_department.department
    if ra.campus_department_id and ra.campus_department:
        return ra.campus_department.department
    return None


# ── RoleAssignment serializers ────────────────────────────────────────────────


class RoleAssignmentSerializer(serializers.ModelSerializer):
    """Read serializer — fields match the frontend RoleAssignment interface."""

    section_id = serializers.IntegerField(read_only=True)
    section_name = serializers.SerializerMethodField()
    campus_id = serializers.SerializerMethodField()
    campus_name = serializers.SerializerMethodField()
    department_id = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    assigned_by_username = serializers.SerializerMethodField()

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "role",
            "is_primary",
            "campus_id",
            "campus_name",
            "department_id",
            "department_name",
            "section_id",
            "section_name",
            "assigned_by_username",
            "assigned_at",
            "valid_until",
        ]
        read_only_fields = fields

    def get_section_name(self, obj):
        if obj.section_id and obj.section:
            return str(obj.section)  # e.g. "NRB-ICT-SW"
        return None

    def get_campus_id(self, obj):
        c = _campus_from_ra(obj)
        return c.pk if c else None

    def get_campus_name(self, obj):
        c = _campus_from_ra(obj)
        return c.name if c else None

    def get_department_id(self, obj):
        d = _department_from_ra(obj)
        return d.pk if d else None

    def get_department_name(self, obj):
        d = _department_from_ra(obj)
        return d.name if d else None

    def get_assigned_by_username(self, obj):
        return (
            obj.assigned_by.username if obj.assigned_by_id and obj.assigned_by else None
        )


class RoleAssignmentCreateSerializer(serializers.Serializer):
    """Write serializer — accepts frontend-friendly campus_id/department_id/section_id."""

    role = serializers.ChoiceField(choices=RoleAssignment.ROLE_CHOICES)
    is_primary = serializers.BooleanField(default=False)
    campus_id = serializers.IntegerField(required=False, allow_null=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    section_id = serializers.IntegerField(required=False, allow_null=True)
    valid_from = serializers.DateTimeField(required=False, allow_null=True)
    valid_until = serializers.DateTimeField(required=False, allow_null=True)

    def validate_valid_until(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("valid_until must be in the future.")
        return value

    def validate(self, attrs):
        from apps.org.models import CampusDepartment, Department, Section

        role = attrs["role"]
        campus_id = attrs.get("campus_id")
        department_id = attrs.get("department_id")
        section_id = attrs.get("section_id")

        attrs["section"] = None
        attrs["campus_department"] = None
        attrs["department"] = None

        if role in ("technician", "hos"):
            if not section_id:
                raise serializers.ValidationError(
                    {"section_id": f"A {role} assignment requires a section."}
                )
            try:
                attrs["section"] = Section.objects.get(pk=section_id)
            except Section.DoesNotExist:
                raise serializers.ValidationError({"section_id": "Section not found."})

        elif role == "hod":
            if not campus_id or not department_id:
                raise serializers.ValidationError(
                    {"campus_id": "HOD requires both campus_id and department_id."}
                )
            try:
                attrs["campus_department"] = CampusDepartment.objects.get(
                    campus_id=campus_id, department_id=department_id
                )
            except CampusDepartment.DoesNotExist:
                raise serializers.ValidationError(
                    {
                        "campus_id": "No campus-department found for that campus + department combination."
                    }
                )

        elif role == "manager":
            if not department_id:
                raise serializers.ValidationError(
                    {"department_id": "A manager assignment requires a department_id."}
                )
            try:
                attrs["department"] = Department.objects.get(pk=department_id)
            except Department.DoesNotExist:
                raise serializers.ValidationError(
                    {"department_id": "Department not found."}
                )

        elif role in ("admin", "user"):
            pass  # no scope required

        if not attrs.get("is_primary") and not attrs.get("valid_until"):
            raise serializers.ValidationError(
                {"valid_until": "A cover (non-primary) assignment requires an end date."}
            )

        return attrs


class RoleAssignmentUpdateSerializer(serializers.ModelSerializer):
    """Partial update — only valid_until can be changed on an existing assignment."""

    class Meta:
        model = RoleAssignment
        fields = ["valid_until"]

    def validate_valid_until(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("valid_until must be in the future.")
        return value


# ── User admin serializers ────────────────────────────────────────────────────


def _primary_ra(user_obj):
    """Return the primary RoleAssignment from the prefetched attribute or a DB hit."""
    ras = getattr(user_obj, "primary_ra_list", None)
    if ras is not None:
        return ras[0] if ras else None
    return (
        user_obj.role_assignments.filter(is_primary=True)
        .select_related(
            "section__campus_department__campus",
            "section__campus_department__department",
            "section__section_type",
            "campus_department__campus",
            "campus_department__department",
            "department",
        )
        .first()
    )


class UserAdminSerializer(serializers.ModelSerializer):
    """Read serializer for the admin user list — matches the frontend User interface."""

    role = serializers.SerializerMethodField()
    campus_name = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()
    section_names = serializers.SerializerMethodField()
    primary_campus_id = serializers.SerializerMethodField()
    primary_campus_display = serializers.SerializerMethodField()
    primary_department_id = serializers.SerializerMethodField()
    primary_department_display = serializers.SerializerMethodField()
    primary_department_name = serializers.SerializerMethodField()
    home_campus_id = serializers.SerializerMethodField()
    home_campus_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "date_joined",
            "role",
            "campus_name",
            "sections",
            "section_names",
            "primary_campus_id",
            "primary_campus_display",
            "primary_department_id",
            "primary_department_display",
            "primary_department_name",
            "home_campus_id",
            "home_campus_name",
        ]

    def get_role(self, obj):
        ra = _primary_ra(obj)
        return ra.role if ra else "user"

    def _home_campus(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.campus if profile and profile.campus_id else None

    def get_home_campus_id(self, obj):
        campus = self._home_campus(obj)
        return campus.pk if campus else None

    def get_home_campus_name(self, obj):
        campus = self._home_campus(obj)
        return campus.name if campus else None

    def get_campus_name(self, obj):
        ra = _primary_ra(obj)
        c = _campus_from_ra(ra)
        return c.name if c else None

    def get_sections(self, obj):
        ra = _primary_ra(obj)
        if ra and ra.section_id:
            return [ra.section_id]
        return []

    def get_section_names(self, obj):
        ra = _primary_ra(obj)
        if ra and ra.section_id and ra.section:
            return [str(ra.section)]
        return []

    def get_primary_campus_id(self, obj):
        ra = _primary_ra(obj)
        c = _campus_from_ra(ra)
        return c.pk if c else None

    def get_primary_campus_display(self, obj):
        ra = _primary_ra(obj)
        c = _campus_from_ra(ra)
        return c.name if c else None

    def get_primary_department_id(self, obj):
        ra = _primary_ra(obj)
        d = _department_from_ra(ra)
        return d.pk if d else None

    def get_primary_department_display(self, obj):
        ra = _primary_ra(obj)
        d = _department_from_ra(ra)
        return d.name if d else None

    def get_primary_department_name(self, obj):
        return self.get_primary_department_display(obj)


class UserCreateSerializer(serializers.Serializer):
    """Write serializer for admin user creation."""

    first_name = serializers.CharField()
    last_name = serializers.CharField()
    email = serializers.EmailField()
    username = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    campus_id = serializers.IntegerField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if value and User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "A user with this username already exists."
            )
        return value

    def validate_campus_id(self, value):
        from apps.org.models import Campus

        if not Campus.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Campus not found.")
        return value

    def create(self, validated_data):
        first = validated_data["first_name"].strip()
        last = validated_data["last_name"].strip()
        username = (validated_data.get("username") or "").strip()
        if not username:
            base = f"{first.lower()}.{last.lower()}"
            username = base
            n = 1
            while User.objects.filter(username=username).exists():
                username = f"{base}{n}"
                n += 1

        user = User.objects.create_user(
            username=username,
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=first,
            last_name=last,
        )
        RoleAssignment.objects.create(user=user, role="user", is_primary=True)
        UserProfile.objects.create(user=user, campus_id=validated_data["campus_id"])
        return user


class UserUpdateSerializer(serializers.Serializer):
    """Write serializer for admin user update."""

    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    campus_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_email(self, value):
        qs = User.objects.filter(email=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_campus_id(self, value):
        from apps.org.models import Campus

        if value is not None and not Campus.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Campus not found.")
        return value

    def update(self, instance, validated_data):
        campus_id = validated_data.pop("campus_id", serializers.empty)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        if validated_data:
            instance.save(update_fields=list(validated_data.keys()))
        if campus_id is not serializers.empty:
            UserProfile.objects.update_or_create(
                user=instance, defaults={"campus_id": campus_id}
            )
        return instance
