"""Phase 6 — WebSocket JWT authentication and channel scoping.

Tests the JWT middleware (token validation → scope injection) and
the consumer's auto-join and channel-guard logic.

Uses asgiref.sync.async_to_sync to run async operations from synchronous
pytest tests (pytest-asyncio not required).
"""

import pytest
from asgiref.sync import async_to_sync

# ---------------------------------------------------------------------------
# JWT middleware unit tests (no channels layer needed)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestJWTMiddlewareTokenValidation:
    """Unit-test _get_user_and_claims_from_token directly."""

    def _validate(self, token_str):
        from apps.realtime.middleware import _get_user_and_claims_from_token

        return async_to_sync(_get_user_and_claims_from_token)(token_str)

    def test_invalid_token_returns_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        user, claims = self._validate("not_a_jwt")
        assert isinstance(user, AnonymousUser)
        assert claims == {}

    def test_garbage_token_returns_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        user, claims = self._validate("eyJhbGciOiJIUzI1NiJ9.garbage.signature")
        assert isinstance(user, AnonymousUser)
        assert claims == {}

    def test_empty_string_returns_anonymous(self):
        from django.contrib.auth.models import AnonymousUser

        user, claims = self._validate("")
        assert isinstance(user, AnonymousUser)
        assert claims == {}

    def test_valid_token_returns_correct_user(self, db):
        from apps.accounts.models import CustomUser, UserProfile
        from apps.org.models import Campus
        from rest_framework_simplejwt.tokens import RefreshToken

        campus = Campus.objects.create(name="TS Campus", code="TSC")
        user = CustomUser.objects.create_user(username="ws_valid", password="pass")
        UserProfile.objects.create(user=user, campus=campus)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        result_user, claims = self._validate(access_token)
        assert result_user.pk == user.pk
        assert result_user.username == "ws_valid"

    def test_valid_token_with_role_claims(self, db):
        from apps.accounts.models import CustomUser, UserProfile, RoleAssignment
        from apps.org.models import (
            Campus,
            Department,
            SectionType,
            CampusDepartment,
            Section,
        )
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        campus = Campus.objects.create(name="ClaimC", code="CLC")
        dept = Department.objects.create(name="ClaimD", code="CLD")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st = SectionType.objects.create(department=dept, name="ClaimST", code="CST")
        section = Section.objects.create(campus_department=cd, section_type=st)

        user = CustomUser.objects.create_user(username="ws_claims", password="pass")
        UserProfile.objects.create(user=user, campus=campus)
        ra = RoleAssignment.objects.create(
            user=user, role="technician", section=section, is_primary=True
        )

        _, access = build_tokens_for_assignment(user, ra)
        result_user, claims = self._validate(str(access))
        assert result_user.pk == user.pk
        assert claims["role"] == "technician"
        assert claims["section_id"] == section.id


# ---------------------------------------------------------------------------
# Consumer channel-guard unit tests (no network I/O)
# ---------------------------------------------------------------------------


class TestConsumerChannelGuard:
    """Directly instantiate ServiceDeskConsumer and test _is_allowed_channel."""

    def _make_consumer(self, user_id, role=None):
        from apps.realtime.consumers import ServiceDeskConsumer
        from unittest.mock import MagicMock

        consumer = ServiceDeskConsumer.__new__(ServiceDeskConsumer)
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.is_authenticated = True
        mock_user.role = role
        consumer.user = mock_user
        consumer.scope = {"active_role": role}
        consumer.joined_groups = set()
        return consumer

    def test_own_user_channel_always_allowed(self):
        consumer = self._make_consumer(user_id=42, role="technician")
        assert consumer._is_allowed_channel("user_42") is True

    def test_other_user_channel_not_allowed(self):
        consumer = self._make_consumer(user_id=42, role="technician")
        assert consumer._is_allowed_channel("user_99") is False

    def test_ticket_channel_allowed_for_any_role(self):
        for role in ("technician", "hos", "hod", "manager", "admin", None):
            consumer = self._make_consumer(user_id=1, role=role)
            assert consumer._is_allowed_channel("ticket_123") is True

    def test_section_channel_allowed_for_technician(self):
        consumer = self._make_consumer(user_id=1, role="technician")
        assert consumer._is_allowed_channel("section_5") is True

    def test_section_channel_allowed_for_hos(self):
        consumer = self._make_consumer(user_id=1, role="hos")
        assert consumer._is_allowed_channel("section_5") is True

    def test_section_channel_allowed_for_hod(self):
        consumer = self._make_consumer(user_id=1, role="hod")
        assert consumer._is_allowed_channel("section_5") is True

    def test_section_channel_not_allowed_for_no_role(self):
        consumer = self._make_consumer(user_id=1, role=None)
        assert consumer._is_allowed_channel("section_5") is False

    def test_campus_department_channel_allowed_for_hod(self):
        consumer = self._make_consumer(user_id=1, role="hod")
        assert consumer._is_allowed_channel("campus_department_3") is True

    def test_campus_department_channel_allowed_for_manager(self):
        consumer = self._make_consumer(user_id=1, role="manager")
        assert consumer._is_allowed_channel("campus_department_3") is True

    def test_campus_department_channel_allowed_for_admin(self):
        consumer = self._make_consumer(user_id=1, role="admin")
        assert consumer._is_allowed_channel("campus_department_3") is True

    def test_campus_department_channel_not_allowed_for_technician(self):
        consumer = self._make_consumer(user_id=1, role="technician")
        assert consumer._is_allowed_channel("campus_department_3") is False

    def test_old_dept_prefix_not_allowed(self):
        """Verify old 'dept_' prefix is no longer accepted (role name fix check)."""
        consumer = self._make_consumer(user_id=1, role="hod")
        # The old prefix 'dept_' should not match the new 'campus_department_' guard.
        assert consumer._is_allowed_channel("dept_3") is False


# ---------------------------------------------------------------------------
# WebSocket integration tests using channels.testing
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestWebSocketIntegration:
    """Integration tests using WebsocketCommunicator with InMemoryChannelLayer."""

    def _reject_test(self, url):
        """Connect to url and return (connected, code) — for rejection tests."""
        from channels.testing import WebsocketCommunicator
        from resolver.asgi import application

        async def _run():
            communicator = WebsocketCommunicator(application, url)
            connected, code = await communicator.connect()
            return connected, code

        return async_to_sync(_run)()

    def test_missing_token_rejected_with_4001(self):
        connected, code = self._reject_test("/ws/")
        assert not connected
        assert code == 4001

    def test_invalid_token_rejected_with_4001(self):
        connected, code = self._reject_test("/ws/?token=garbage_token")
        assert not connected
        assert code == 4001

    def test_valid_token_accepted(self):
        from apps.accounts.models import CustomUser, UserProfile
        from apps.org.models import Campus
        from rest_framework_simplejwt.tokens import RefreshToken
        from channels.testing import WebsocketCommunicator
        from resolver.asgi import application

        campus = Campus.objects.create(name="WS Campus", code="WSC")
        user = CustomUser.objects.create_user(username="ws_conn", password="pass")
        UserProfile.objects.create(user=user, campus=campus)
        refresh = RefreshToken.for_user(user)
        token = str(refresh.access_token)

        async def _run():
            communicator = WebsocketCommunicator(application, f"/ws/?token={token}")
            connected, code = await communicator.connect()
            if connected:
                await communicator.disconnect()
            return connected, code

        connected, code = async_to_sync(_run)()
        assert connected, f"Expected connection accepted but got code {code}"
