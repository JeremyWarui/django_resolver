from rest_framework import serializers

ESCALATION_STATUS_MAP = {
    0: {"code": "none", "label": "Not escalated"},
    1: {"code": "head_of_section", "label": "Escalated to Section Head"},
    2: {"code": "hod", "label": "Escalated to HOD (Maximum Level)"},
}
_ESCALATION_UNKNOWN = {"code": "unknown", "label": "Unknown"}


# ─── SERIALIZER HELPER FUNCTIONS ────────────────────────────────────────────

def format_user_info(user):
    """Convert user object to standardized dict format.

    Handles both ORM model instances and dict representations.
    Returns None if user is None.
    """
    if not user:
        return None

    if isinstance(user, dict):
        return {
            "id": user.get("id"),
            "name": user.get("name") or user.get("username"),
            "username": user.get("username"),
            "role": user.get("role"),
        }

    # ORM model instance
    name = f"{user.first_name} {user.last_name}".strip() or user.username
    return {
        "id": user.id,
        "name": name,
        "username": user.username,
        "role": getattr(user, "role", None),
    }


def format_escalation_status(escalation_level):
    """Convert escalation level to standardized status dict.

    Args:
        escalation_level: Integer escalation level (0, 1, 2, etc.)

    Returns:
        Dict with code and label for the escalation status
    """
    return ESCALATION_STATUS_MAP.get(escalation_level, _ESCALATION_UNKNOWN)


def format_service_item(service_item):
    """Convert service item object to standardized dict format.

    Handles both ORM model instances and dict representations.
    Returns None if service_item is None.
    """
    if not service_item:
        return None

    if isinstance(service_item, dict):
        return {
            "id": service_item.get("id"),
            "name": service_item.get("name"),
            "requires_approval": service_item.get("requires_approval", False),
        }

    # ORM model instance
    return {
        "id": service_item.id,
        "name": service_item.name,
        "requires_approval": getattr(service_item, "requires_approval", False),
    }


class UsernameField(serializers.RelatedField):
    """Custom field that returns just the username for user references"""

    def to_representation(self, value):
        return value.username
