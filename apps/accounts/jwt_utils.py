"""
JWT token helpers — scope-aware authentication (SoT §3.6).

Claims on every token (beyond SimpleJWT defaults):
  role               — active role string (user/technician/hos/hod/manager/admin)
  campus_id          — user's home campus from UserProfile (routing source for requesters)
  department_id      — for hod/manager scope
  section_id         — for technician/hos scope
  role_assignment_id — pk of the active RoleAssignment
"""

from apps.accounts.models import RoleAssignment
from apps.accounts.services import resolve_campus_and_department_names
from rest_framework_simplejwt.tokens import RefreshToken


def ensure_floor_assignment(user):
    """Guarantee the user has a primary RoleAssignment(role='user').

    Called at registration and wherever a new user is created.  If the user
    already has a primary assignment (any role) this is a no-op, so it is safe
    to call unconditionally.
    """
    if not user.role_assignments.filter(is_primary=True).exists():
        RoleAssignment.objects.create(
            user=user,
            role="user",
            is_primary=True,
        )


def _campus_id_for_user(user):
    """Return the user's home campus id from their UserProfile, or None."""
    try:
        return user.profile.campus_id
    except Exception:
        return None


def _department_id_for_assignment(role_assignment):
    """Resolve department_id: direct FK or via campus_department."""
    if role_assignment.department_id:
        return role_assignment.department_id
    if role_assignment.campus_department_id:
        try:
            return role_assignment.campus_department.department_id
        except Exception:
            pass
    return None


def build_tokens_for_assignment(user, role_assignment):
    """Return (refresh, access) token pair scoped to the given RoleAssignment.

    Both tokens carry the scope payload defined in SoT §3.6:
      sub, role, campus_id, department_id, section_id, role_assignment_id

    role_assignment should always be non-None after ensure_floor_assignment() runs
    at user creation.  None is still handled defensively for legacy data.
    """
    refresh = RefreshToken.for_user(
        user
    )  # sets token["sub"] = user.pk via USER_ID_CLAIM

    if role_assignment is not None:
        role = role_assignment.role
        department_id = _department_id_for_assignment(role_assignment)
        section_id = role_assignment.section_id
        ra_id = role_assignment.pk
    else:
        role = None
        department_id = None
        section_id = None
        ra_id = None

    scope_claims = {
        "email": user.email,
        "role": role,
        "campus_id": _campus_id_for_user(user),
        "department_id": department_id,
        "campus_department_id": (
            role_assignment.campus_department_id if role_assignment else None
        ),
        "section_id": section_id,
        "role_assignment_id": ra_id,
    }
    for key, value in scope_claims.items():
        refresh[key] = value

    access = refresh.access_token
    return refresh, access


def get_primary_assignment_or_infer(user):
    """Return the user's primary RoleAssignment, or None."""
    return (
        user.role_assignments.filter(is_primary=True)
        .select_related("section", "campus_department", "department")
        .first()
    )


def serialize_role_assignment(ra):
    """Return a dict representation of a RoleAssignment."""
    return {
        "id": ra.pk,
        "role": ra.role,
        "section_id": ra.section_id,
        "campus_department_id": ra.campus_department_id,
        "department_id": ra.department_id,
        "is_primary": ra.is_primary,
        "valid_until": ra.valid_until.isoformat() if ra.valid_until else None,
    }


def serialize_auth_user(user, active_assignment):
    """Return the AuthUser shape expected by the frontend (SoT §5.1 GET /auth/me/)."""
    available = list(
        user.role_assignments.select_related(
            "section", "campus_department", "department"
        ).all()
    )
    if not available and active_assignment:
        available = [active_assignment]
    names = resolve_campus_and_department_names(user, active_assignment)
    return {
        "id": user.pk,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": getattr(user, "phone_number", None) or None,
        "is_active": user.is_active,
        "home_campus_name": names["home_campus_name"],
        "primary_department_name": names["primary_department_name"],
        "section_name": names["section_name"],
        "active_role": (
            serialize_role_assignment(active_assignment) if active_assignment else None
        ),
        "available_roles": [serialize_role_assignment(ra) for ra in available],
    }
