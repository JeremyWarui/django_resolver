"""Shared display helpers used by serialize_auth_user() for the profile page.

Kept separate from jwt_utils.py so it can be imported without a circular
import.
"""


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


def section_from_role_assignment(ra):
    """Resolve the section object directly assigned on the role assignment, if any."""
    if ra is None:
        return None
    if ra.section_id and ra.section:
        return ra.section
    return None


def home_campus_from_user(user):
    """Resolve the user's home/routing campus (UserProfile.campus), independent of role."""
    profile = getattr(user, "profile", None)
    return profile.campus if profile and profile.campus_id else None


def resolve_campus_and_department_names(user, role_assignment=None):
    """Return {'home_campus_name', 'primary_department_name', 'section_name'} for display.

    home_campus_name comes from UserProfile.campus (routing/home campus,
    stable regardless of role). primary_department_name and section_name come
    from the given role_assignment's scope (None for roles with no such scope,
    e.g. the plain 'user' role has neither; 'hod' has a department but no section).
    """
    home_campus = home_campus_from_user(user)
    department = department_from_role_assignment(role_assignment)
    section = section_from_role_assignment(role_assignment)
    return {
        "home_campus_name": home_campus.name if home_campus else None,
        "primary_department_name": department.name if department else None,
        "section_name": str(section) if section else None,
    }
