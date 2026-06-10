"""Single source of truth for resolving the caller's active role.

Reads the role from the JWT claim (SoT §3.8 — JWT claim is authoritative for the
request), with a DB fallback to the user's primary RoleAssignment for tests that
use `force_authenticate` and therefore have no token. Every view/analytic/report
must resolve role through here so behaviour does not diverge between code paths.
"""


def resolve_role(request):
    """Return the caller's active role string, or None.

    1. JWT claim `role` (works for both a SimpleJWT Token, which proxies `.get`
       to its payload, and a plain dict).
    2. Fallback: the user's primary RoleAssignment (force_authenticate in tests).
    """
    try:
        auth = getattr(request, "auth", None)
        role = auth.get("role") if auth else None
        if role:
            return role
    except Exception:
        pass

    ra = getattr(getattr(request, "user", None), "primary_role_assignment", None)
    return ra.role if ra else None
