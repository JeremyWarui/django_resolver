from rest_framework import serializers

TYPE_SPECS = {
    "office_block": {
        "required": {"floor", "room"},
        "optional": {"area"},
        "known": {"floor", "room", "area"},
        "building_dropdown": True,
    },
    "building": {
        "required": {"area"},
        "optional": {"room"},
        "known": {"area", "room"},
        "building_dropdown": True,
    },
    "equipment": {
        "required": {"asset_name"},
        "optional": {"asset_id", "description"},
        "known": {"asset_name", "asset_id", "description"},
        "building_dropdown": False,
    },
    "residential": {
        "required": {"unit_number"},
        "optional": {"tenant_name"},
        "known": {"unit_number", "tenant_name"},
        "building_dropdown": False,
    },
    "grounds": {
        "required": {"zone"},
        "optional": {"landmark"},
        "known": {"zone", "landmark"},
        "building_dropdown": False,
    },
}


def validate_location(facility_type, facility, values, requester_campus_id):
    """Validate location data for a ticket.

    Args:
        facility_type: FacilityType instance (already resolved).
        facility: Facility instance or None (already resolved).
        values: dict of location field values.
        requester_campus_id: int campus PK of the requester.

    Returns:
        Cleaned dict {"facility_type": ft, "facility": f_or_none, "values": clean_values}.

    Raises:
        rest_framework.serializers.ValidationError on any validation failure.
    """
    type_code = facility_type.code
    spec = TYPE_SPECS.get(type_code)
    if spec is None:
        raise serializers.ValidationError(
            {"facility_type": f"Unknown facility type code: '{type_code}'."}
        )

    # Reject unknown keys in values.
    unknown_keys = set(values.keys()) - spec["known"]
    if unknown_keys:
        raise serializers.ValidationError(
            {"values": f"Unknown location field(s): {sorted(unknown_keys)}."}
        )

    # Reject missing required keys.
    missing_keys = spec["required"] - set(values.keys())
    if missing_keys:
        raise serializers.ValidationError(
            {"values": f"Missing required location field(s): {sorted(missing_keys)}."}
        )

    if spec["building_dropdown"]:
        # Facility is required for building-dropdown types.
        if facility is None:
            raise serializers.ValidationError(
                {"facility": "A facility must be selected for this location type."}
            )
        # Facility must belong to the requester's campus.
        if facility.campus_id != requester_campus_id:
            raise serializers.ValidationError(
                {
                    "facility": "The selected facility does not belong to the requester's campus."
                }
            )
        # Facility must match the declared facility type.
        if facility.facility_type.code != type_code:
            raise serializers.ValidationError(
                {
                    "facility": (
                        f"The selected facility is of type '{facility.facility_type.code}', "
                        f"but '{type_code}' was expected."
                    )
                }
            )
    else:
        # Non-building-dropdown types should have no facility; silently ignore if passed.
        facility = None

    clean_values = {k: values[k] for k in spec["known"] if k in values}

    return {
        "facility_type": facility_type,
        "facility": facility,
        "values": clean_values,
    }
