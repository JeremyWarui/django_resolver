"""Comprehensive authentication and authorization tests."""
import unittest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from tickets.models import Section, Facility, Ticket
from tickets.auth_models import MagicLink, LoginSession
from datetime import timedelta
from django.utils import timezone

User = get_user_model()


class AuthenticationTestCase(APITestCase):
    """Test authentication and authorization implementation."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create sections
        self.it_section = Section.objects.create(
            name="IT", description="Information Technology"
        )
        self.maintenance_section = Section.objects.create(
            name="Maintenance", description="Building Maintenance"
        )

        # Create facility
        self.facility = Facility.objects.create(
            name="Main Office", type="building", location="Building A"
        )

        # Create users with different roles
        self.user = User.objects.create_user(
            username="user1",
            email="user@example.com",
            password="testpass123",
            first_name="Regular",
            last_name="User",
            role="user",
        )

        self.technician = User.objects.create_user(
            username="tech1",
            email="tech@example.com",
            password="testpass123",
            first_name="Tech",
            last_name="User",
            role="technician",
        )
        self.technician.sections.add(self.it_section)

        self.admin = User.objects.create_user(
            username="admin1",
            email="admin@example.com",
            password="testpass123",
            first_name="Admin",
            last_name="User",
            role="admin",
        )

        self.manager = User.objects.create_user(
            username="manager1",
            email="manager@example.com",
            password="testpass123",
            first_name="Manager",
            last_name="User",
            role="manager",
        )

    @unittest.skip(reason="Magic link authentication is currently disabled")
    def test_auth_method_check(self):
        """Test authentication method detection based on role."""
        # Test staff roles should use password
        response = self.client.post(
            "/api/auth/check-method/", {"email": "tech@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["auth_method"], "password")
        self.assertEqual(response.data["user_role"], "technician")

        response = self.client.post(
            "/api/auth/check-method/", {"email": "admin@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["auth_method"], "password")

        # Test user role should use magic link
        response = self.client.post(
            "/api/auth/check-method/", {"email": "user@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["auth_method"], "magic_link")
        self.assertEqual(response.data["user_role"], "user")

    def test_password_login_staff_roles(self):
        """Test password login for technician, admin, manager."""
        # Test technician login
        response = self.client.post(
            "/api/auth/login/",
            {"username": "tech1", "password": "testpass123", "remember_me": True},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertTrue(response.data["remember_me"])
        self.assertEqual(response.data["role"], "technician")

        # Test admin login
        response = self.client.post(
            "/api/auth/login/", {"username": "admin1",
                                 "password": "testpass123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "admin")

    @unittest.skip(reason="Magic link authentication is currently disabled - all roles use password auth")
    def test_password_login_blocked_for_users(self):
        """Test that regular users cannot use password login."""
        response = self.client.post(
            "/api/auth/login/", {"username": "user1",
                                 "password": "testpass123"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("should use magic link", response.data["error"])

    @unittest.skip(reason="Magic link authentication is currently disabled")
    def test_magic_link_request_users_only(self):
        """Test magic link requests work for users only."""
        # Test user can request magic link
        response = self.client.post(
            "/api/auth/magic-link/request/", {"email": "user@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Magic link sent", response.data["message"])

        # Verify magic link was created
        self.assertTrue(MagicLink.objects.filter(user=self.user).exists())

    @unittest.skip(reason="Magic link authentication is currently disabled")
    def test_magic_link_blocked_for_staff(self):
        """Test that staff roles cannot use magic links."""
        response = self.client.post(
            "/api/auth/magic-link/request/", {"email": "tech@example.com"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("should use password", response.data["error"])

    @unittest.skip(reason="Magic link authentication is currently disabled")
    def test_magic_link_login(self):
        """Test login with magic link."""
        # Create magic link
        magic_link = MagicLink.create_for_user(self.user)

        # Test login with magic link
        response = self.client.post(
            f"/api/auth/magic-link/{magic_link.token}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)
        self.assertEqual(response.data["role"], "user")
        self.assertEqual(response.data["login_method"], "magic_link")

        # Verify magic link is marked as used
        magic_link.refresh_from_db()
        self.assertTrue(magic_link.used)

    def test_session_management(self):
        """Test session creation and tracking."""
        # Login as technician with remember me
        response = self.client.post(
            "/api/auth/login/",
            {"username": "tech1", "password": "testpass123", "remember_me": True},
        )

        token = response.data["token"]
        token_obj = Token.objects.get(key=token)

        # Verify session was created
        self.assertTrue(
            LoginSession.objects.filter(
                token=token_obj,
                user=self.technician,
                login_method="password",
                remember_me=True,
            ).exists()
        )

    def test_role_based_permissions_tickets(self):
        """Test role-based permissions for ticket access."""
        # Create tickets
        user_ticket = Ticket.objects.create(
            title="User Ticket",
            description="User created ticket",
            section=self.it_section,
            facility=self.facility,
            raised_by=self.user,
        )

        admin_ticket = Ticket.objects.create(
            title="Admin Ticket",
            description="Admin created ticket",
            section=self.it_section,
            facility=self.facility,
            raised_by=self.admin,
        )

        # Test user can only see own tickets
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/tickets/")
        self.assertEqual(response.status_code, 200)

        ticket_ids = [ticket["id"] for ticket in response.data["results"]]
        self.assertIn(user_ticket.id, ticket_ids)
        self.assertNotIn(admin_ticket.id, ticket_ids)

        # Test admin can see all tickets
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/tickets/")
        self.assertEqual(response.status_code, 200)

        ticket_ids = [ticket["id"] for ticket in response.data["results"]]
        self.assertIn(user_ticket.id, ticket_ids)
        self.assertIn(admin_ticket.id, ticket_ids)

    def test_section_facility_permissions(self):
        """Test admin/manager only permissions for sections and facilities."""
        # Test unauthenticated access
        response = self.client.post(
            "/api/sections/", {"name": "New Section",
                               "description": "Test section"}
        )
        self.assertEqual(response.status_code, 401)

        # Test user cannot create sections
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/sections/", {"name": "New Section",
                               "description": "Test section"}
        )
        self.assertEqual(response.status_code, 403)

        # Test admin can create sections
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            "/api/sections/", {"name": "New Section",
                               "description": "Test section"}
        )
        self.assertEqual(response.status_code, 201)

    def test_technician_access_permissions(self):
        """Test technician-specific permissions."""
        # Test technician can access technicians endpoint
        self.client.force_authenticate(user=self.technician)
        response = self.client.get("/api/technicians/")
        self.assertEqual(response.status_code, 200)

        # Test user cannot access technicians endpoint
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/technicians/")
        self.assertEqual(response.status_code, 403)

    def test_logout_functionality(self):
        """Test logout cleans up sessions and tokens."""
        # Login first to get a real token
        response = self.client.post(
            "/api/auth/login/", {"username": "tech1",
                                 "password": "testpass123"}
        )
        self.assertEqual(response.status_code, 200)
        token_key = response.data["token"]

        # Set the token in the client
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token_key}")

        token = Token.objects.get(key=token_key)
        session = LoginSession.objects.get(token=token)

        # Test logout
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 200)

        # Verify token is deleted
        self.assertFalse(Token.objects.filter(user=self.technician).exists())

        # Verify session is deleted
        self.assertFalse(LoginSession.objects.filter(id=session.id).exists())

    def test_profile_access(self):
        """Test authenticated profile access."""
        # Test unauthenticated access
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)

        # Test authenticated access
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["username"], "user1")
        self.assertEqual(response.data["role"], "user")

    @unittest.skip(reason="Magic link authentication is currently disabled - all roles use password auth")
    def test_registration_assigns_correct_auth_method(self):
        """Test that registration returns correct auth method for role."""
        # Test user registration
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "testpass123",
                "first_name": "New",
                "last_name": "User",
                "role": "user",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["auth_method"], "magic_link")

        # Test technician registration
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "newtech",
                "email": "newtech@example.com",
                "password": "testpass123",
                "first_name": "New",
                "last_name": "Tech",
                "role": "technician",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["auth_method"], "password")


class AuthorizationIntegrationTestCase(APITestCase):
    """Test authorization integration with the existing permission system."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create test data
        self.section = Section.objects.create(name="IT")
        self.facility = Facility.objects.create(name="Office")

        self.user = User.objects.create_user(
            username="user1", password="pass", role="user", email="u@test.com"
        )
        self.technician = User.objects.create_user(
            username="tech1", password="pass", role="technician", email="t@test.com"
        )
        self.admin = User.objects.create_user(
            username="admin1", password="pass", role="admin", email="a@test.com"
        )

        self.technician.sections.add(self.section)

    def test_authentication_required_for_all_endpoints(self):
        """Test that all main endpoints require authentication."""
        endpoints = [
            "/api/tickets/",
            "/api/sections/",
            "/api/facilities/",
            "/api/users/",
            "/api/technicians/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertIn(
                response.status_code,
                [401, 403],
                f"Endpoint {endpoint} should require auth",
            )

    def test_role_based_endpoint_access(self):
        """Test role-based access to different endpoints."""
        # Test analytics access (technician and above)
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/analytics/tickets/")
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=self.technician)
        response = self.client.get("/api/analytics/tickets/")
        # Should work (might return 500 due to no data, but auth passes)
        self.assertNotEqual(response.status_code, 403)

        # Test admin dashboard (accessible to all authenticated users per current implementation)
        self.client.force_authenticate(user=self.technician)
        response = self.client.get("/api/analytics/admin-dashboard/")
        # AdminDashboardAnalyticsView uses IsAuthenticated, so all authenticated users can view
        self.assertEqual(response.status_code, 200)

        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/api/analytics/admin-dashboard/")
        self.assertNotEqual(response.status_code, 403)

    @unittest.skip(reason="Magic link authentication is currently disabled - all roles use password auth")
    def test_authentication_strategy_consistency(self):
        """Test that authentication strategy is consistently applied."""
        # Verify that the system properly distinguishes between roles

        # Staff roles should get password auth
        for role in ["technician", "admin", "manager"]:
            user = User.objects.create_user(
                username=f"{role}test",
                email=f"{role}@test.com",
                password="pass",
                role=role,
            )

            response = self.client.post(
                "/api/auth/check-method/", {"email": f"{role}@test.com"}
            )
            self.assertEqual(response.data["auth_method"], "password")

        # User role should get magic link
        response = self.client.post(
            "/api/auth/check-method/", {"email": "u@test.com"})
        self.assertEqual(response.data["auth_method"], "magic_link")
