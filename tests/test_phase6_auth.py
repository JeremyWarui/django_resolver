"""Phase 6 — auth endpoints, switch-role, RoleAssignment CRUD.

Acceptance criteria:
- GET /auth/me/ returns profile + available roles for authenticated user
- POST /auth/switch-role/ re-issues JWT for chosen active assignment
- POST /users/{id}/role-assignments/ creates cover (HOD/admin within scope)
- Admin can create cover for any user
- Plain user/technician cannot create cover
- PATCH/DELETE on cover by HOD within scope succeeds
- Cannot DELETE a primary assignment
"""

import pytest
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def campus(db):
    from apps.org.models import Campus
    return Campus.objects.create(name="Nairobi", code="NRB")


@pytest.fixture
def dept(db):
    from apps.org.models import Department
    return Department.objects.create(name="ICT", code="ICT")


@pytest.fixture
def campus_dept(campus, dept):
    from apps.org.models import CampusDepartment
    return CampusDepartment.objects.create(campus=campus, department=dept)


@pytest.fixture
def section_type(dept):
    from apps.org.models import SectionType
    return SectionType.objects.create(department=dept, name="Software", code="SW")


@pytest.fixture
def section(campus_dept, section_type):
    from apps.org.models import Section
    return Section.objects.create(
        campus_department=campus_dept, section_type=section_type, is_active=True
    )


def make_user(username, campus=None, role=None, section=None, campus_department=None, department=None):
    from apps.accounts.models import CustomUser, UserProfile, RoleAssignment
    user = CustomUser.objects.create_user(username=username, password="pass")
    if campus:
        UserProfile.objects.create(user=user, campus=campus)
    if role:
        kwargs = {"user": user, "role": role, "is_primary": True}
        if section:
            kwargs["section"] = section
        if campus_department:
            kwargs["campus_department"] = campus_department
        if department:
            kwargs["department"] = department
        RoleAssignment.objects.create(**kwargs)
    return user


# ---------------------------------------------------------------------------
# TestMeEndpoint
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestMeEndpoint:

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 401

    def test_returns_user_profile(self, api_client, campus):
        user = make_user("me_user", campus=campus)
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        assert response.data["id"] == user.id
        assert response.data["username"] == "me_user"

    def test_returns_available_roles(self, api_client, campus, section):
        user = make_user("me_tech", campus=campus, role="technician", section=section)
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        assert "available_roles" in response.data
        assert len(response.data["available_roles"]) >= 1
        roles = [ra["role"] for ra in response.data["available_roles"]]
        assert "technician" in roles

    def test_returns_active_role_field(self, api_client, campus, section):
        user = make_user("me_hos", campus=campus, role="hos", section=section)
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        assert "active_role" in response.data

    def test_user_with_multiple_assignments_returns_all(
        self, api_client, campus, section, section_type, campus_dept
    ):
        from apps.accounts.models import RoleAssignment
        from apps.org.models import SectionType, Section
        user = make_user("me_multi", campus=campus, role="technician", section=section)
        # Add a cover HOS assignment.
        RoleAssignment.objects.create(
            user=user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
        )
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        assert len(response.data["available_roles"]) == 2


# ---------------------------------------------------------------------------
# TestSwitchRole
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSwitchRole:

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.post("/api/v1/auth/switch-role/", {"roleAssignmentId": 1})
        assert response.status_code == 401

    def test_missing_role_assignment_id(self, api_client, campus, section):
        user = make_user("sw_user", campus=campus, role="technician", section=section)
        api_client.force_authenticate(user=user)
        response = api_client.post("/api/v1/auth/switch-role/", {})
        assert response.status_code == 422

    def test_switch_to_own_active_assignment(self, api_client, campus, section):
        from apps.accounts.models import RoleAssignment
        user = make_user("sw_own", campus=campus, role="technician", section=section)
        ra = user.role_assignments.first()
        api_client.force_authenticate(user=user)
        response = api_client.post("/api/v1/auth/switch-role/", {"roleAssignmentId": ra.id})
        assert response.status_code == 200
        assert "accessToken" in response.data

    def test_switch_to_other_users_assignment_returns_403(
        self, api_client, campus, section
    ):
        from apps.accounts.models import RoleAssignment
        user_a = make_user("sw_a", campus=campus, role="technician", section=section)
        user_b = make_user("sw_b", campus=campus, role="hos", section=section)
        ra_b = user_b.role_assignments.first()

        api_client.force_authenticate(user=user_a)
        response = api_client.post("/api/v1/auth/switch-role/", {"roleAssignmentId": ra_b.id})
        assert response.status_code == 403

    def test_switch_to_nonexistent_assignment_returns_404(
        self, api_client, campus, section
    ):
        user = make_user("sw_404", campus=campus, role="technician", section=section)
        api_client.force_authenticate(user=user)
        response = api_client.post("/api/v1/auth/switch-role/", {"roleAssignmentId": 99999})
        assert response.status_code == 404

    def test_switch_to_expired_assignment_returns_400(
        self, api_client, campus, section
    ):
        from apps.accounts.models import RoleAssignment
        user = make_user("sw_exp", campus=campus, role="technician", section=section)
        ra_expired = RoleAssignment.objects.create(
            user=user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() - timedelta(days=1),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post("/api/v1/auth/switch-role/", {"roleAssignmentId": ra_expired.id})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestRoleAssignmentCRUD
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestRoleAssignmentCRUD:

    def test_admin_creates_cover_for_any_user(
        self, api_client, campus, section, campus_dept
    ):
        admin = make_user("ra_admin", campus=campus, role="admin")
        target = make_user("ra_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "section": section.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 201
        assert response.data["role"] == "technician"

    def test_hod_creates_cover_within_own_campus_dept(
        self, api_client, campus, section, campus_dept
    ):
        hod = make_user("ra_hod", campus=campus, role="hod", campus_department=campus_dept)
        campus_dept.head_of_department = hod
        campus_dept.save()
        target = make_user("ra_target2", campus=campus)
        api_client.force_authenticate(user=hod)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "section": section.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 201

    def test_hod_cannot_create_cover_outside_campus_dept(
        self, api_client, campus, section, campus_dept
    ):
        from apps.org.models import Department, SectionType, CampusDepartment, Section
        hod = make_user("ra_hod2", campus=campus, role="hod", campus_department=campus_dept)
        campus_dept.head_of_department = hod
        campus_dept.save()

        # Create a section in a different campus_dept.
        dept2 = Department.objects.create(name="HR2", code="HR2")
        st2 = SectionType.objects.create(department=dept2, name="Recr2", code="REC2")
        cd2 = CampusDepartment.objects.create(campus=campus, department=dept2)
        section_other = Section.objects.create(campus_department=cd2, section_type=st2)

        target = make_user("ra_target3", campus=campus)
        api_client.force_authenticate(user=hod)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "section": section_other.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 403

    def test_plain_user_cannot_create_cover(
        self, api_client, campus, section
    ):
        user = make_user("ra_plain", campus=campus)
        target = make_user("ra_target4", campus=campus)
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {"role": "technician", "section": section.id},
        )
        assert response.status_code == 403

    def test_technician_cannot_create_cover(
        self, api_client, campus, section
    ):
        tech = make_user("ra_tech", campus=campus, role="technician", section=section)
        target = make_user("ra_target5", campus=campus)
        api_client.force_authenticate(user=tech)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {"role": "technician", "section": section.id},
        )
        assert response.status_code == 403

    def test_patch_valid_until_by_hod(
        self, api_client, campus, section, campus_dept
    ):
        from apps.accounts.models import RoleAssignment
        hod = make_user("ra_hod_patch", campus=campus, role="hod", campus_department=campus_dept)
        campus_dept.head_of_department = hod
        campus_dept.save()
        target = make_user("ra_target6", campus=campus)
        ra = RoleAssignment.objects.create(
            user=target,
            role="technician",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
            assigned_by=hod,
        )
        new_until = timezone.now() + timedelta(days=14)
        api_client.force_authenticate(user=hod)
        response = api_client.patch(
            f"/api/v1/users/{target.id}/role-assignments/{ra.id}/",
            {"valid_until": new_until.isoformat()},
        )
        assert response.status_code == 200

    def test_delete_cover_by_hod(
        self, api_client, campus, section, campus_dept
    ):
        from apps.accounts.models import RoleAssignment
        hod = make_user("ra_hod_del", campus=campus, role="hod", campus_department=campus_dept)
        campus_dept.head_of_department = hod
        campus_dept.save()
        target = make_user("ra_target7", campus=campus)
        ra = RoleAssignment.objects.create(
            user=target,
            role="technician",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
            assigned_by=hod,
        )
        api_client.force_authenticate(user=hod)
        response = api_client.delete(
            f"/api/v1/users/{target.id}/role-assignments/{ra.id}/"
        )
        assert response.status_code == 204
        assert not RoleAssignment.objects.filter(pk=ra.id).exists()

    def test_cannot_delete_primary_assignment(
        self, api_client, campus, section
    ):
        admin = make_user("ra_del_primary_admin", campus=campus, role="admin")
        target = make_user("ra_target8", campus=campus, role="technician", section=section)
        ra = target.role_assignments.first()
        api_client.force_authenticate(user=admin)
        response = api_client.delete(
            f"/api/v1/users/{target.id}/role-assignments/{ra.id}/"
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestScopeClaimsCasing — scope must survive a token refresh (R: claim casing)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScopeClaimsCasing:
    """Verify that scope claims are preserved through the refresh rotation.

    Issuance writes snake_case (campus_id, section_id, department_id,
    role_assignment_id); the refresh endpoint must copy the same keys when
    rotating tokens, not camelCase variants.
    """

    def test_scope_claims_survive_refresh(self, api_client, campus, section):
        """After a token refresh the new access token must carry the same scope claims."""
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        user = make_user("refresh_scope_user", campus=campus, role="hos", section=section)
        section.hos = user
        section.save()
        ra = user.role_assignments.first()

        refresh, _access = build_tokens_for_assignment(user, ra)

        # Call the refresh endpoint (legacy path: /api/auth/refresh/).
        api_client.cookies["resolver_refresh"] = str(refresh)
        response = api_client.post("/api/auth/refresh/")
        assert response.status_code == 200, response.data

        new_access_str = response.data["accessToken"]
        new_access = AccessToken(new_access_str)

        # All scope claims must survive rotation — snake_case throughout.
        assert new_access.get("role") == "hos", "role claim lost after refresh"
        assert new_access.get("section_id") == section.id, "section_id claim lost after refresh"
        assert new_access.get("role_assignment_id") == ra.pk, "role_assignment_id claim lost after refresh"

    def test_scope_absent_before_fix_with_camel_casing(self, api_client, campus, section):
        """Regression guard: camelCase claim names must NOT appear in issued tokens."""
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        user = make_user("camel_guard_user", campus=campus, role="hos", section=section)
        section.hos = user
        section.save()
        ra = user.role_assignments.first()

        _refresh, access = build_tokens_for_assignment(user, ra)
        token = AccessToken(str(access))

        # Issuance must use snake_case — these camelCase names must be absent.
        assert token.get("sectionId") is None, "camelCase sectionId found in token"
        assert token.get("campusId") is None, "camelCase campusId found in token"
        assert token.get("deptId") is None, "camelCase deptId found in token"
        assert token.get("roleAssignmentId") is None, "camelCase roleAssignmentId found in token"
