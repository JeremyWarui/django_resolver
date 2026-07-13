"""
Registration + home-campus tests.

Covers:
  - Self-registration requires campus_id and creates a UserProfile with it
    (ticket creation depends on user.profile.campus — SoT requester_campus
    resolution — so a campus-less account can never raise a ticket).
  - Admin can set/update a user's home campus, independent of role scope.
"""

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def campus(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Nairobi", code="NRB", location="CBD")


@pytest.fixture
def campus_b(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Mombasa", code="MSA", location="Coast")


@pytest.fixture
def admin_user(db, campus):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import RoleAssignment

    User = get_user_model()
    user = User.objects.create_user(
        username="reg_admin", email="reg_admin@x.com", password="pw12345678"
    )
    RoleAssignment.objects.create(user=user, role="admin", is_primary=True)
    return user


@pytest.mark.django_db
def test_public_campus_list_requires_no_auth(api_client, campus, campus_b):
    """Registration form needs the campus list before any account/JWT exists."""
    resp = api_client.get("/api/v1/auth/campuses/")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.data]
    assert campus.name in names
    assert campus_b.name in names


@pytest.mark.django_db
class TestRegistrationRequiresCampus:
    def test_register_without_campus_id_fails(self, api_client):
        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "newbie@x.com",
                "first_name": "New",
                "last_name": "Bie",
            },
            format="json",
        )
        assert resp.status_code == 422

    def test_register_with_campus_id_creates_profile(self, api_client, campus):
        from django.contrib.auth import get_user_model

        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "newbie2@x.com",
                "first_name": "New",
                "last_name": "Bie",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["username"] == "new.bie"
        assert "accessToken" not in resp.data
        User = get_user_model()
        user = User.objects.get(username="new.bie")
        assert user.profile.campus_id == campus.id
        assert user.is_active is False
        assert not user.has_usable_password()

    def test_register_with_unknown_campus_id_fails(self, api_client):
        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "newbie3@x.com",
                "first_name": "New",
                "last_name": "Bie",
                "campus_id": 999999,
            },
            format="json",
        )
        assert resp.status_code == 422


@pytest.mark.django_db
class TestAdminManagesHomeCampus:
    def test_admin_creates_user_with_campus(self, api_client, admin_user, campus):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            "/api/v1/users/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane@x.com",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["home_campus_id"] == campus.id
        assert resp.data["home_campus_name"] == campus.name
        assert resp.data["username"] == "jane.doe"

        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(username="jane.doe")
        assert user.is_active is False
        assert not user.has_usable_password()

    def test_admin_create_user_without_campus_fails(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            "/api/v1/users/",
            {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane2@x.com",
            },
            format="json",
        )
        assert resp.status_code == 400

    def test_admin_updates_existing_users_campus(
        self, api_client, admin_user, campus, campus_b
    ):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        target = User.objects.create_user(
            username="target1", email="target1@x.com", password="pw12345678"
        )
        RoleAssignment.objects.create(user=target, role="user", is_primary=True)
        UserProfile.objects.create(user=target, campus=campus)

        api_client.force_authenticate(user=admin_user)
        resp = api_client.patch(
            f"/api/v1/users/{target.id}/",
            {"campus_id": campus_b.id},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["home_campus_id"] == campus_b.id

        target.refresh_from_db()
        assert target.profile.campus_id == campus_b.id
