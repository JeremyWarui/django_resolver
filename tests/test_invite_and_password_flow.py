"""
Invite-based registration + password-set/reset flow.

Covers:
  - Self-registration and admin-created users no longer accept a password;
    the account is created inactive with an unusable password and an invite
    email is sent (django.core.mail.outbox in tests).
  - Username auto-generation collisions (firstname.lastname, firstnamelastname1, ...).
  - POST /auth/set-password/ activates the account via a valid uid+token and
    logs the user in; invalid/expired/reused tokens are rejected.
  - POST /auth/forgot-password/ never leaks whether an email is registered,
    and the emailed link actually works via set-password.
  - Login against a not-yet-activated account fails.
"""

import re

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def campus(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Nairobi", code="NRB", location="CBD")


@pytest.fixture
def admin_user(db, campus):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import RoleAssignment

    User = get_user_model()
    user = User.objects.create_user(
        username="ipf_admin", email="ipf_admin@x.com", password="pw12345678"
    )
    RoleAssignment.objects.create(user=user, role="admin", is_primary=True)
    return user


def _extract_link(body):
    match = re.search(r"http\S+/set-password/(\S+)/(\S+)", body)
    assert match, f"no set-password link found in email body:\n{body}"
    return match.group(1), match.group(2)


@pytest.mark.django_db
class TestInviteOnRegistration:
    def test_register_creates_inactive_user_and_sends_invite(self, api_client, campus):
        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "alice@x.com",
                "first_name": "Alice",
                "last_name": "Wanjiru",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["username"] == "alice.wanjiru"
        assert len(mail.outbox) == 1
        assert "alice.wanjiru" in mail.outbox[0].body

    def test_username_collision_gets_suffixed(self, api_client, campus):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(username="bob.otieno", email="first@x.com")

        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "bob2@x.com",
                "first_name": "Bob",
                "last_name": "Otieno",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["username"] == "bob.otieno1"

    def test_admin_create_user_no_longer_accepts_password(
        self, api_client, admin_user, campus
    ):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            "/api/v1/users/",
            {
                "first_name": "Carol",
                "last_name": "Mwangi",
                "email": "carol@x.com",
                "campus_id": campus.id,
                "password": "shouldbeignored",
            },
            format="json",
        )
        assert resp.status_code == 201
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.get(username="carol.mwangi")
        assert user.is_active is False
        assert not user.has_usable_password()
        assert len(mail.outbox) == 1

    def test_register_with_existing_inactive_email_resends_invite(
        self, api_client, campus
    ):
        """A prior invite email that failed to send (e.g. a mail-server
        timeout) must not permanently lock the registrant out with a 409 —
        re-registering the same email should resend the invite instead."""
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        stuck = User.objects.create_user(
            username="hank.mutua", email="hank@x.com", password=None, is_active=False
        )
        RoleAssignment.objects.create(user=stuck, role="user", is_primary=True)
        UserProfile.objects.create(user=stuck, campus=campus)

        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "hank@x.com",
                "first_name": "Hank",
                "last_name": "Mutua",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["username"] == "hank.mutua"
        assert len(mail.outbox) == 1
        assert "hank.mutua" in mail.outbox[0].body

    def test_register_with_existing_active_email_still_conflicts(
        self, api_client, campus
    ):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        User.objects.create_user(
            username="ivy.kamau", email="ivy@x.com", password="pw12345678"
        )

        resp = api_client.post(
            "/api/v1/auth/register/",
            {
                "email": "ivy@x.com",
                "first_name": "Ivy",
                "last_name": "Kamau",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 409
        assert len(mail.outbox) == 0

    def test_admin_create_user_with_existing_inactive_email_resends_invite(
        self, api_client, admin_user, campus
    ):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        stuck = User.objects.create_user(
            username="ken.otieno", email="ken@x.com", password=None, is_active=False
        )
        RoleAssignment.objects.create(user=stuck, role="user", is_primary=True)
        UserProfile.objects.create(user=stuck, campus=campus)

        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            "/api/v1/users/",
            {
                "first_name": "Ken",
                "last_name": "Otieno",
                "email": "ken@x.com",
                "campus_id": campus.id,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["username"] == "ken.otieno"
        assert len(mail.outbox) == 1
        assert User.objects.filter(email="ken@x.com").count() == 1


@pytest.mark.django_db
class TestLoginGatedUntilActivated:
    def test_login_fails_for_inactive_account(self, api_client, campus):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        user = User.objects.create_user(
            username="dan.kimani", email="dan@x.com", password=None, is_active=False
        )
        RoleAssignment.objects.create(user=user, role="user", is_primary=True)
        UserProfile.objects.create(user=user, campus=campus)

        resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "dan.kimani", "password": "anything"},
            format="json",
        )
        assert resp.status_code == 401


@pytest.mark.django_db
class TestSetPassword:
    def _inactive_user(self, campus):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        user = User.objects.create_user(
            username="eve.njoroge", email="eve@x.com", password=None, is_active=False
        )
        RoleAssignment.objects.create(user=user, role="user", is_primary=True)
        UserProfile.objects.create(user=user, campus=campus)
        return user

    def test_valid_token_activates_and_logs_in(self, api_client, campus):
        user = self._inactive_user(campus)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        resp = api_client.post(
            "/api/v1/auth/set-password/",
            {
                "uid": uid,
                "token": token,
                "new_password": "S0meStrongPass!",
                "confirm_password": "S0meStrongPass!",
            },
            format="json",
        )
        assert resp.status_code == 200
        assert "accessToken" in resp.data
        user.refresh_from_db()
        assert user.is_active is True
        assert user.check_password("S0meStrongPass!")

        # New password now works via normal login.
        login_resp = api_client.post(
            "/api/v1/auth/login/",
            {"username": "eve.njoroge", "password": "S0meStrongPass!"},
            format="json",
        )
        assert login_resp.status_code == 200

    def test_invalid_token_rejected(self, api_client, campus):
        user = self._inactive_user(campus)
        uid = urlsafe_base64_encode(force_bytes(user.pk))

        resp = api_client.post(
            "/api/v1/auth/set-password/",
            {
                "uid": uid,
                "token": "not-a-real-token",
                "new_password": "S0meStrongPass!",
                "confirm_password": "S0meStrongPass!",
            },
            format="json",
        )
        assert resp.status_code == 400
        user.refresh_from_db()
        assert user.is_active is False

    def test_token_is_single_use(self, api_client, campus):
        user = self._inactive_user(campus)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        first = api_client.post(
            "/api/v1/auth/set-password/",
            {
                "uid": uid,
                "token": token,
                "new_password": "S0meStrongPass!",
                "confirm_password": "S0meStrongPass!",
            },
            format="json",
        )
        assert first.status_code == 200

        # Reusing the same token after the password hash changed must fail.
        second = api_client.post(
            "/api/v1/auth/set-password/",
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherPass!2",
                "confirm_password": "AnotherPass!2",
            },
            format="json",
        )
        assert second.status_code == 400

    def test_weak_password_rejected_by_validators(self, api_client, campus):
        user = self._inactive_user(campus)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        resp = api_client.post(
            "/api/v1/auth/set-password/",
            {
                "uid": uid,
                "token": token,
                "new_password": "password",
                "confirm_password": "password",
            },
            format="json",
        )
        assert resp.status_code == 400
        user.refresh_from_db()
        assert user.is_active is False


@pytest.mark.django_db
class TestForgotPassword:
    def test_unknown_email_returns_200_and_sends_nothing(self, api_client):
        resp = api_client.post(
            "/api/v1/auth/forgot-password/",
            {"email": "nobody@x.com"},
            format="json",
        )
        assert resp.status_code == 200
        assert len(mail.outbox) == 0

    def test_known_active_user_receives_working_link(self, api_client, campus):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        user = User.objects.create_user(
            username="frank.omondi", email="frank@x.com", password="OldPassw0rd!"
        )
        RoleAssignment.objects.create(user=user, role="user", is_primary=True)
        UserProfile.objects.create(user=user, campus=campus)

        resp = api_client.post(
            "/api/v1/auth/forgot-password/",
            {"email": "frank@x.com"},
            format="json",
        )
        assert resp.status_code == 200
        assert len(mail.outbox) == 1
        uid, token = _extract_link(mail.outbox[0].body)

        set_resp = api_client.post(
            "/api/v1/auth/set-password/",
            {
                "uid": uid,
                "token": token,
                "new_password": "BrandNewPassw0rd!",
                "confirm_password": "BrandNewPassw0rd!",
            },
            format="json",
        )
        assert set_resp.status_code == 200
        user.refresh_from_db()
        assert user.check_password("BrandNewPassw0rd!")

    def test_inactive_user_email_does_not_get_reset_link(self, api_client, campus):
        """PasswordResetForm.get_users() excludes is_active=False accounts —
        an un-activated invite should go through set-password via the invite
        link, not forgot-password."""
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile

        User = get_user_model()
        user = User.objects.create_user(
            username="grace.achieng",
            email="grace@x.com",
            password=None,
            is_active=False,
        )
        RoleAssignment.objects.create(user=user, role="user", is_primary=True)
        UserProfile.objects.create(user=user, campus=campus)

        resp = api_client.post(
            "/api/v1/auth/forgot-password/",
            {"email": "grace@x.com"},
            format="json",
        )
        assert resp.status_code == 200
        assert len(mail.outbox) == 0
