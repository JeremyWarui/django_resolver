from rest_framework import serializers

from apps.facilities.models import Facility, FacilityType


class FacilityTypeSerializer(serializers.ModelSerializer):
    """D9: FacilityType is a fixed set — exposes name and code only (no field_schema)."""

    class Meta:
        model = FacilityType
        fields = ["id", "name", "code"]


class FacilitySerializer(serializers.ModelSerializer):
    type = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    campus_name = serializers.SerializerMethodField()
    openTickets = serializers.SerializerMethodField()
    resolvedTickets = serializers.SerializerMethodField()
    closedTickets = serializers.SerializerMethodField()

    class Meta:
        model = Facility
        fields = [
            "id",
            "name",
            "code",
            "campus",
            "campus_name",
            "facility_type",
            "type",
            "status",
            "openTickets",
            "resolvedTickets",
            "closedTickets",
        ]

    def get_type(self, obj):
        return obj.facility_type.code if obj.facility_type_id else None

    def get_status(self, obj):
        # Derive status from open ticket count if annotated; default to operational
        open_count = getattr(obj, "open_ticket_count", 0) or 0
        return "maintenance" if open_count > 0 else "operational"

    def get_campus_name(self, obj):
        return obj.campus.name if obj.campus_id else None

    def get_openTickets(self, obj):
        return getattr(obj, "open_ticket_count", 0) or 0

    def get_resolvedTickets(self, obj):
        return getattr(obj, "resolved_ticket_count", 0) or 0

    def get_closedTickets(self, obj):
        return getattr(obj, "closed_ticket_count", 0) or 0
