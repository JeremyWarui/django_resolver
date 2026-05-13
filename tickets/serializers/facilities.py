from rest_framework import serializers
from tickets.models import Facility, Campus
from .org import NestedCampusSerializer


class NestedFacilitySerializer(serializers.ModelSerializer):
    code = serializers.CharField(source="facility_code", read_only=True)

    class Meta:
        model = Facility
        fields = ["id", "code", "name"]


class FacilitySerializer(serializers.ModelSerializer):
    campus = NestedCampusSerializer(read_only=True)
    campus_id = serializers.PrimaryKeyRelatedField(
        queryset=Campus.objects.all(),
        source="campus",
        write_only=True,
        label="Campus ID",
    )

    class Meta:
        model = Facility
        fields = [
            "id",
            "name",
            "facility_code",
            "type",
            "status",
            "location",
            "campus",
            "campus_id",
            "purchase_date",
            "warranty_expiry",
            "asset_value",
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request and request.user.role not in ("hod", "manager", "admin"):
            for f in ("purchase_date", "warranty_expiry", "asset_value"):
                fields.pop(f, None)
        return fields
