"""Shared account-creation and display helpers used across serializers/views.

Kept separate from serializers.py/jwt_utils.py so both can import the same
logic without a circular import.
"""

from django.contrib.auth import get_user_model

User = get_user_model()


def generate_unique_username(first_name, last_name):
    """Generate a unique 'firstname.lastname' username, suffixing on collision."""
    base = f"{first_name.strip().lower()}.{last_name.strip().lower()}"
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        username = f"{base}{n}"
        n += 1
    return username


def campus_from_role_assignment(ra):
    """Resolve the campus object from any role-assignment scope variant."""
    if ra is None:
        return None
    if ra.section_id and ra.section and ra.section.campus_department:
        return ra.section.campus_department.campus
    if ra.campus_department_id and ra.campus_department:
        return ra.campus_department.campus
    return None


def department_from_role_assignment(ra):
    """Resolve the department object from any role-assignment scope variant."""
    if ra is None:
        return None
    if ra.department_id and ra.department:
        return ra.department
    if ra.section_id and ra.section and ra.section.campus_department:
        return ra.section.campus_department.department
    if ra.campus_department_id and ra.campus_department:
        return ra.campus_department.department
    return None


def home_campus_from_user(user):
    """Resolve the user's home/routing campus (UserProfile.campus), independent of role."""
    profile = getattr(user, "profile", None)
    return profile.campus if profile and profile.campus_id else None


def resolve_campus_and_department_names(user, role_assignment=None):
    """Return {'home_campus_name', 'primary_department_name'} for display purposes.

    home_campus_name comes from UserProfile.campus (routing/home campus,
    stable regardless of role). primary_department_name comes from the given
    role_assignment's scope (None for the plain 'user' role, which has none).
    Matches the naming UserAdminSerializer already uses for the same concept.
    """
    home_campus = home_campus_from_user(user)
    department = department_from_role_assignment(role_assignment)
    return {
        "home_campus_name": home_campus.name if home_campus else None,
        "primary_department_name": department.name if department else None,
    }
