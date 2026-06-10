from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import RoleAssignment


class RoleAssignmentSerializer(serializers.ModelSerializer):
    """Read serializer for a RoleAssignment."""

    class Meta:
        model = RoleAssignment
        fields = [
            "id",
            "role",
            "section",
            "campus_department",
            "department",
            "is_primary",
            "valid_from",
            "valid_until",
            "assigned_by",
            "assigned_at",
        ]
        read_only_fields = fields


class RoleAssignmentCreateSerializer(serializers.ModelSerializer):
    """Write serializer for creating a cover RoleAssignment."""

    class Meta:
        model = RoleAssignment
        fields = [
            "role",
            "section",
            "campus_department",
            "department",
            "valid_from",
            "valid_until",
        ]

    def validate(self, attrs):
        # Run model-level scope validation.
        ra = RoleAssignment(**attrs)
        ra.clean()
        return attrs

    def validate_valid_until(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("valid_until must be in the future.")
        return value


class RoleAssignmentUpdateSerializer(serializers.ModelSerializer):
    """Partial update — only valid_until can be changed on a cover assignment."""

    class Meta:
        model = RoleAssignment
        fields = ["valid_until"]

    def validate_valid_until(self, value):
        if value is not None and value <= timezone.now():
            raise serializers.ValidationError("valid_until must be in the future.")
        return value
