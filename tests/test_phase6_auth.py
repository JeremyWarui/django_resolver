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
from unittest.mock import patch

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


def make_user(
    username,
    campus=None,
    role=None,
    section=None,
    campus_department=None,
    department=None,
):
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

    def test_demoted_assignment_hidden_from_available_roles(
        self, api_client, campus, section
    ):
        """C-2: demoted ex-primary rows (non-primary, no valid_until) are audit
        rows — the role switcher must not offer them."""
        from apps.accounts.models import RoleAssignment

        user = make_user("me_demoted", campus=campus, role="hod", section=section)
        RoleAssignment.objects.create(
            user=user, role="hos", section=section, is_primary=False, valid_until=None
        )
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 200
        roles = [ra["role"] for ra in response.data["available_roles"]]
        assert roles == ["hod"]


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
        response = api_client.post(
            "/api/v1/auth/switch-role/", {"roleAssignmentId": ra.id}
        )
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
        response = api_client.post(
            "/api/v1/auth/switch-role/", {"roleAssignmentId": ra_b.id}
        )
        assert response.status_code == 403

    def test_switch_to_nonexistent_assignment_returns_404(
        self, api_client, campus, section
    ):
        user = make_user("sw_404", campus=campus, role="technician", section=section)
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/switch-role/", {"roleAssignmentId": 99999}
        )
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
        response = api_client.post(
            "/api/v1/auth/switch-role/", {"roleAssignmentId": ra_expired.id}
        )
        assert response.status_code == 400

    def test_switch_to_demoted_assignment_returns_400(
        self, api_client, campus, section
    ):
        """C-2: a demoted ex-primary (non-primary, no valid_until — kept for
        audit per C16) must not be switchable — otherwise a promoted user
        retains their old role's scope indefinitely."""
        from apps.accounts.models import RoleAssignment

        user = make_user("sw_demoted", campus=campus, role="hod", section=section)
        ra_demoted = RoleAssignment.objects.create(
            user=user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=None,
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/switch-role/", {"roleAssignmentId": ra_demoted.id}
        )
        assert response.status_code == 400

    def test_active_cover_still_switchable(self, api_client, campus, section):
        """Regression: time-boxed covers within their window keep working."""
        from apps.accounts.models import RoleAssignment

        user = make_user("sw_cover", campus=campus, role="technician", section=section)
        ra_cover = RoleAssignment.objects.create(
            user=user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
        )
        api_client.force_authenticate(user=user)
        response = api_client.post(
            "/api/v1/auth/switch-role/", {"roleAssignmentId": ra_cover.id}
        )
        assert response.status_code == 200


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
                "section_id": section.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 201
        assert response.data["role"] == "technician"

    def test_primary_technician_assignment_syncs_section_technician(
        self, api_client, campus, section, campus_dept
    ):
        """QA A1 — the exact payload TechnicianForm sends (campus_id and
        department_id alongside section_id, is_primary=true) must create the
        RoleAssignment AND the SectionTechnician link the Technicians page and
        Assign dialog read."""
        from apps.accounts.models import RoleAssignment
        from apps.org.models import SectionTechnician

        admin = make_user("ra_admin_tech", campus=campus, role="admin")
        target = make_user("ra_target_tech", campus=campus, role="user")
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "is_primary": True,
                "section_id": section.id,
                "campus_id": campus.id,
                "department_id": None,
            },
            format="json",
        )
        assert response.status_code == 201, response.data
        assert SectionTechnician.objects.filter(user=target, section=section).exists()
        # New primary replaced the old one; old kept demoted for audit (C16).
        primary = RoleAssignment.objects.get(user=target, is_primary=True)
        assert primary.role == "technician"

    def test_hod_creates_cover_within_own_campus_dept(
        self, api_client, campus, section, campus_dept
    ):
        hod = make_user(
            "ra_hod", campus=campus, role="hod", campus_department=campus_dept
        )
        campus_dept.head_of_department = hod
        campus_dept.save()
        target = make_user("ra_target2", campus=campus)
        api_client.force_authenticate(user=hod)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "section_id": section.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 201

    def test_hod_cannot_create_cover_outside_campus_dept(
        self, api_client, campus, section, campus_dept
    ):
        from apps.org.models import Department, SectionType, CampusDepartment, Section

        hod = make_user(
            "ra_hod2", campus=campus, role="hod", campus_department=campus_dept
        )
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
                "section_id": section_other.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 403

    def test_plain_user_cannot_create_cover(self, api_client, campus, section):
        user = make_user("ra_plain", campus=campus)
        target = make_user("ra_target4", campus=campus)
        api_client.force_authenticate(user=user)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {"role": "technician", "section_id": section.id},
        )
        assert response.status_code == 403

    def test_technician_cannot_create_cover(self, api_client, campus, section):
        tech = make_user("ra_tech", campus=campus, role="technician", section=section)
        target = make_user("ra_target5", campus=campus)
        api_client.force_authenticate(user=tech)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {"role": "technician", "section_id": section.id},
        )
        assert response.status_code == 403

    def test_patch_valid_until_by_hod(self, api_client, campus, section, campus_dept):
        from apps.accounts.models import RoleAssignment

        hod = make_user(
            "ra_hod_patch", campus=campus, role="hod", campus_department=campus_dept
        )
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

    def test_delete_cover_by_hod(self, api_client, campus, section, campus_dept):
        from apps.accounts.models import RoleAssignment

        hod = make_user(
            "ra_hod_del", campus=campus, role="hod", campus_department=campus_dept
        )
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

    def test_admin_replacing_primary_role_demotes_old_one(
        self, api_client, campus, section, campus_dept
    ):
        """Promoting/demoting a user from the Users admin page: posting a new
        is_primary=True assignment must demote the existing primary rather than
        error, and the demoted assignment must remain (not be deleted)."""
        admin = make_user("ra_replace_admin", campus=campus, role="admin")
        target = make_user(
            "ra_replace_target", campus=campus, role="technician", section=section
        )
        old_primary = target.role_assignments.get(is_primary=True)

        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "hod",
                "campus_id": campus.id,
                "department_id": campus_dept.department_id,
                "is_primary": True,
            },
        )
        assert response.status_code == 201
        assert response.data["role"] == "hod"
        assert response.data["is_primary"] is True

        old_primary.refresh_from_db()
        assert old_primary.is_primary is False
        assert target.role_assignments.filter(is_primary=True).count() == 1
        assert target.role_assignments.get(is_primary=True).role == "hod"

    def test_promoting_to_technician_creates_section_technician_link(
        self, api_client, campus, section
    ):
        from apps.org.models import SectionTechnician

        admin = make_user("ra_promote_tech_admin", campus=campus, role="admin")
        target = make_user("ra_promote_tech_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "section_id": section.id,
                "is_primary": True,
            },
        )
        assert response.status_code == 201
        assert SectionTechnician.objects.filter(user=target, section=section).exists()

    def test_promoting_to_primary_hos_sets_section_hos(self, api_client, campus, section):
        admin = make_user("ra_promote_hos_admin", campus=campus, role="admin")
        target = make_user("ra_promote_hos_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "hos",
                "section_id": section.id,
                "is_primary": True,
            },
        )
        assert response.status_code == 201
        section.refresh_from_db()
        assert section.hos_id == target.id

    def test_promoting_to_primary_hod_sets_campus_department_head(
        self, api_client, campus, section, campus_dept
    ):
        admin = make_user("ra_promote_hod_admin", campus=campus, role="admin")
        target = make_user("ra_promote_hod_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "hod",
                "campus_id": campus.id,
                "department_id": campus_dept.department_id,
                "is_primary": True,
            },
        )
        assert response.status_code == 201
        campus_dept.refresh_from_db()
        assert campus_dept.head_of_department_id == target.id

    def test_promoting_to_primary_manager_sets_department_manager(
        self, api_client, campus, section, dept
    ):
        admin = make_user("ra_promote_manager_admin", campus=campus, role="admin")
        target = make_user("ra_promote_manager_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "manager",
                "department_id": dept.id,
                "is_primary": True,
            },
        )
        assert response.status_code == 201
        dept.refresh_from_db()
        assert dept.manager_user_id == target.id

    def test_replacing_primary_hos_clears_old_sections_hos_fk(
        self, api_client, campus, section
    ):
        admin = make_user("ra_clear_hos_admin", campus=campus, role="admin")
        target = make_user(
            "ra_clear_hos_target", campus=campus, role="hos", section=section
        )
        section.hos = target
        section.save()
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {"role": "user", "is_primary": True},
        )
        assert response.status_code == 201
        section.refresh_from_db()
        assert section.hos_id is None

    def test_cover_technician_assignment_also_creates_section_technician_link(
        self, api_client, campus, section
    ):
        from apps.org.models import SectionTechnician

        admin = make_user("ra_cover_tech_admin", campus=campus, role="admin")
        target = make_user("ra_cover_tech_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {
                "role": "technician",
                "section_id": section.id,
                "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
            },
        )
        assert response.status_code == 201
        assert response.data["is_primary"] is False
        assert SectionTechnician.objects.filter(user=target, section=section).exists()

    def test_cover_assignment_requires_valid_until(self, api_client, campus, section):
        """A non-primary (cover) assignment must always carry an end date —
        otherwise it's indistinguishable from a second standing role."""
        admin = make_user("ra_no_expiry_admin", campus=campus, role="admin")
        target = make_user("ra_no_expiry_target", campus=campus)
        api_client.force_authenticate(user=admin)
        response = api_client.post(
            f"/api/v1/users/{target.id}/role-assignments/",
            {"role": "technician", "section_id": section.id},
        )
        assert response.status_code == 400
        assert "valid_until" in response.data

    def test_list_role_assignments_returns_bare_list(self, api_client, campus, section):
        """GET /users/{id}/role-assignments/ must return a bare JSON array, not a
        paginated envelope — the frontend calls .map() directly on the response
        and a user only ever has a handful of assignments."""
        admin = make_user("ra_list_admin", campus=campus, role="admin")
        target = make_user(
            "ra_list_target", campus=campus, role="technician", section=section
        )
        api_client.force_authenticate(user=admin)
        response = api_client.get(f"/api/v1/users/{target.id}/role-assignments/")
        assert response.status_code == 200
        assert isinstance(response.data, list)

    def test_cannot_delete_primary_assignment(self, api_client, campus, section):
        admin = make_user("ra_del_primary_admin", campus=campus, role="admin")
        target = make_user(
            "ra_target8", campus=campus, role="technician", section=section
        )
        ra = target.role_assignments.first()
        api_client.force_authenticate(user=admin)
        response = api_client.delete(
            f"/api/v1/users/{target.id}/role-assignments/{ra.id}/"
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# TestRoleChangedWSPush — live role_changed event on RoleAssignment edits
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRoleChangedWSPush:

    def test_primary_swap_pushes_to_promoted_user_not_admin(
        self, api_client, django_capture_on_commit_callbacks, campus, section, campus_dept
    ):
        admin = make_user("wsrole_admin", campus=campus, role="admin")
        target = make_user(
            "wsrole_target", campus=campus, role="technician", section=section
        )
        old_primary = target.role_assignments.get(is_primary=True)

        api_client.force_authenticate(user=admin)
        with patch("apps.accounts.views.emit_role_changed") as mock_emit:
            with django_capture_on_commit_callbacks(execute=True):
                response = api_client.post(
                    f"/api/v1/users/{target.id}/role-assignments/",
                    {
                        "role": "hod",
                        "campus_id": campus.id,
                        "department_id": campus_dept.department_id,
                        "is_primary": True,
                    },
                )
        assert response.status_code == 201
        mock_emit.assert_called_once_with(target.id, old_primary.role, "hod")

    def test_cover_creation_does_not_push(self, api_client, campus, section):
        """A cover assignment doesn't take effect until the user explicitly
        switches into it, so creating one must not force a relogin."""
        admin = make_user("wsrole_cover_admin", campus=campus, role="admin")
        target = make_user("wsrole_cover_target", campus=campus)
        api_client.force_authenticate(user=admin)
        with patch("apps.accounts.views.emit_role_changed") as mock_emit:
            response = api_client.post(
                f"/api/v1/users/{target.id}/role-assignments/",
                {
                    "role": "technician",
                    "section_id": section.id,
                    "valid_until": (timezone.now() + timedelta(days=7)).isoformat(),
                },
            )
        assert response.status_code == 201
        mock_emit.assert_not_called()

    def test_patch_valid_until_pushes_to_target(
        self, api_client, campus, section, campus_dept
    ):
        from apps.accounts.models import RoleAssignment

        hod = make_user(
            "wsrole_hod_patch", campus=campus, role="hod", campus_department=campus_dept
        )
        campus_dept.head_of_department = hod
        campus_dept.save()
        target = make_user("wsrole_patch_target", campus=campus)
        ra = RoleAssignment.objects.create(
            user=target,
            role="technician",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
            assigned_by=hod,
        )
        api_client.force_authenticate(user=hod)
        with patch("apps.accounts.views.emit_role_changed") as mock_emit:
            response = api_client.patch(
                f"/api/v1/users/{target.id}/role-assignments/{ra.id}/",
                {"valid_until": (timezone.now() + timedelta(days=14)).isoformat()},
            )
        assert response.status_code == 200
        mock_emit.assert_called_once_with(target.id, "technician", "technician")


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

        user = make_user(
            "refresh_scope_user", campus=campus, role="hos", section=section
        )
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
        assert (
            new_access.get("section_id") == section.id
        ), "section_id claim lost after refresh"
        assert (
            new_access.get("role_assignment_id") == ra.pk
        ), "role_assignment_id claim lost after refresh"

    def test_scope_absent_before_fix_with_camel_casing(
        self, api_client, campus, section
    ):
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
        assert (
            token.get("roleAssignmentId") is None
        ), "camelCase roleAssignmentId found in token"


@pytest.mark.django_db
class TestRoleChangeOnRefresh:
    """jwt_refresh() must re-derive role/scope from the DB, not copy the old
    token's claims — otherwise a promoted/demoted user keeps acting on stale
    scope for up to REFRESH_TOKEN_LIFETIME. See resolve_active_assignment()."""

    def test_no_change_reports_role_changed_false(self, api_client, campus, section):
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        user = make_user("stable_role_user", campus=campus, role="hos", section=section)
        ra = user.role_assignments.first()
        refresh, _access = build_tokens_for_assignment(user, ra)

        api_client.cookies["resolver_refresh"] = str(refresh)
        response = api_client.post("/api/auth/refresh/")
        assert response.status_code == 200, response.data
        assert response.data["roleChanged"] is False

    def test_promotion_detected_and_new_role_applied(self, api_client, campus, section):
        """Mirrors UserRoleAssignmentListCreateView: demote the old primary,
        create a new one — the exact shape a real admin promotion leaves behind."""
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        from apps.accounts.models import RoleAssignment

        user = make_user("promoted_user", campus=campus, role="user")
        old_ra = user.role_assignments.first()
        refresh, _access = build_tokens_for_assignment(user, old_ra)

        # Simulate the admin promoting this user to technician.
        old_ra.is_primary = False
        old_ra.save()
        new_ra = RoleAssignment.objects.create(
            user=user, role="technician", section=section, is_primary=True
        )

        api_client.cookies["resolver_refresh"] = str(refresh)
        response = api_client.post("/api/auth/refresh/")
        assert response.status_code == 200, response.data
        assert response.data["roleChanged"] is True

        new_access = AccessToken(response.data["accessToken"])
        assert new_access.get("role") == "technician"
        assert new_access.get("role_assignment_id") == new_ra.pk

    def test_active_cover_assignment_preserved_on_refresh(
        self, api_client, campus, section
    ):
        """An explicit, still-open cover (non-primary + valid_until in the
        future) must survive a refresh — the user shouldn't be silently
        bounced back to their primary role mid-cover-window."""
        from django.utils import timezone
        from datetime import timedelta
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        from apps.accounts.models import RoleAssignment

        user = make_user("covering_user", campus=campus, role="user")
        cover_ra = RoleAssignment.objects.create(
            user=user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
        )
        refresh, _access = build_tokens_for_assignment(user, cover_ra)

        api_client.cookies["resolver_refresh"] = str(refresh)
        response = api_client.post("/api/auth/refresh/")
        assert response.status_code == 200, response.data
        assert response.data["roleChanged"] is False

        new_access = AccessToken(response.data["accessToken"])
        assert new_access.get("role") == "hos"
        assert new_access.get("role_assignment_id") == cover_ra.pk
