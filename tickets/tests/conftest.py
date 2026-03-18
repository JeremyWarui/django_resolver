"""
Pytest configuration and fixtures for Django Resolver tests.

This module provides reusable pytest fixtures that replace the BaseTicketTestCase.
Fixtures use factory pattern for easy customization and composition.

Usage:
    def test_user_creation(user_factory):
        user = user_factory(username="custom")
        assert user.username == "custom"
    
    def test_ticket_workflow(ticket_factory, admin_user):
        ticket = ticket_factory(raised_by=admin_user)
        assert ticket.raised_by == admin_user
"""

import pytest
from django.contrib.auth import get_user_model
from tickets.models import (
    Organization,
    Campus,
    Department,
    Section,
    Facility,
    Ticket,
    Comment,
    Feedback,
    TicketLog,
)
from rest_framework.test import APIClient


# ============================================================================
# USER FIXTURES (factories)
# ============================================================================

@pytest.fixture
def user_factory(db):
    """Factory for creating regular users (role='user')"""
    def create_user(username="testuser", email="test@example.com", password="testpass", **kwargs):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="user",
            **kwargs
        )
    return create_user


@pytest.fixture
def admin_user_factory(db):
    """Factory for creating admin users"""
    def create_admin(username="admin", email="admin@example.com", password="admin123", **kwargs):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="admin",
            **kwargs
        )
    return create_admin


@pytest.fixture
def technician_factory(db):
    """Factory for creating technician users"""
    def create_technician(username="technician", email="tech@example.com", password="techpass", **kwargs):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="technician",
            **kwargs
        )
    return create_technician


@pytest.fixture
def section_head_factory(db):
    """Factory for creating section head users"""
    def create_section_head(username="section_head", email="head@example.com", password="headpass", **kwargs):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="section_head",
            **kwargs
        )
    return create_section_head


@pytest.fixture
def hod_factory(db):
    """Factory for creating HOD (Head of Department) users"""
    def create_hod(username="hod", email="hod@example.com", password="hodpass", **kwargs):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="hod",
            **kwargs
        )
    return create_hod


@pytest.fixture
def director_factory(db):
    """Factory for creating director users"""
    def create_director(username="director", email="director@example.com", password="dirpass", **kwargs):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="director",
            **kwargs
        )
    return create_director


# ============================================================================
# ORGANIZATIONAL HIERARCHY FIXTURES
# ============================================================================

@pytest.fixture
def organization(db):
    """Create a test organization"""
    return Organization.objects.create(
        name="Test Organization",
        code="TEST",
        organization_type="corporate"
    )


@pytest.fixture
def campus(db, organization):
    """Create a test campus"""
    return Campus.objects.create(
        name="Main Campus",
        code="MAIN",
        organization=organization,
        location="123 Main St"
    )


@pytest.fixture
def department(db, campus):
    """Create a test department"""
    return Department.objects.create(
        name="IT Department",
        code="IT",
        campus=campus
    )


@pytest.fixture
def department_hvac(db, campus):
    """Create a second department for multi-department tests"""
    return Department.objects.create(
        name="Facilities Department",
        code="FAC",
        campus=campus
    )


@pytest.fixture
def section(db, department):
    """Create a test section"""
    return Section.objects.create(
        name="Network Section",
        code="NETWORK",
        department=department
    )


@pytest.fixture
def section_hvac(db, department_hvac):
    """Create a second section for multi-section tests"""
    return Section.objects.create(
        name="HVAC Section",
        code="HVAC",
        department=department_hvac
    )


# ============================================================================
# OTHER MODEL FIXTURES
# ============================================================================

@pytest.fixture
def facility(db, campus, department):
    """Create a test facility"""
    return Facility.objects.create(
        name="Main Building",
        type="building",
        status="active",
        location="123 Main St",
        campus=campus,
        department=department
    )


# ============================================================================
# TICKET FIXTURES (factories)
# ============================================================================

@pytest.fixture
def ticket_factory(db, section, facility, user_factory, technician_factory):
    """Factory for creating tickets with customizable parameters"""
    def create_ticket(
        title="Test Ticket",
        description="Test ticket description",
        status="open",
        priority="low",
        section=section,
        facility=facility,
        raised_by=None,
        assigned_to=None,
        **kwargs
    ):
        if raised_by is None:
            raised_by = user_factory()
        if assigned_to is None:
            assigned_to = technician_factory()

        return Ticket.objects.create(
            title=title,
            description=description,
            status=status,
            priority=priority,
            section=section,
            facility=facility,
            raised_by=raised_by,
            assigned_to=assigned_to,
            **kwargs
        )
    return create_ticket


# ============================================================================
# COMMENT/FEEDBACK FIXTURES
# ============================================================================

@pytest.fixture
def comment_factory(db, ticket_factory, user_factory):
    """Factory for creating comments"""
    def create_comment(text="Test comment", ticket=None, created_by=None):
        if ticket is None:
            ticket = ticket_factory()
        if created_by is None:
            created_by = user_factory()

        return Comment.objects.create(
            ticket=ticket,
            text=text,
            created_by=created_by
        )
    return create_comment


@pytest.fixture
def feedback_factory(db, ticket_factory, user_factory):
    """Factory for creating feedback"""
    def create_feedback(rating=5, comment="Great service", ticket=None, submitted_by=None):
        if ticket is None:
            ticket = ticket_factory()
        if submitted_by is None:
            submitted_by = user_factory()

        return Feedback.objects.create(
            ticket=ticket,
            rating=rating,
            comment=comment,
            submitted_by=submitted_by
        )
    return create_feedback


# ============================================================================
# COMMON TEST SETUP FIXTURES
# ============================================================================

@pytest.fixture
def basic_setup(db, user_factory, admin_user_factory, technician_factory,
                organization, campus, department, section, facility):
    """Complete basic setup with all common objects"""
    return {
        'organization': organization,
        'campus': campus,
        'department': department,
        'section': section,
        'facility': facility,
        'user': user_factory(),
        'admin': admin_user_factory(),
        'technician': technician_factory(),
    }


@pytest.fixture
def api_client():
    """Create an API client for testing endpoints"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, user_factory):
    """Create an authenticated API client"""
    user = user_factory(username="authuser", password="authpass")
    api_client.force_authenticate(user=user)
    return {
        'client': api_client,
        'user': user,
        'token': None  # Token would be set after login if needed
    }


@pytest.fixture
def authenticated_admin_client(api_client, admin_user_factory):
    """Create an authenticated admin API client"""
    admin = admin_user_factory(username="authadmin", password="adminpass")
    api_client.force_authenticate(user=admin)
    return {
        'client': api_client,
        'user': admin,
        'token': None
    }


@pytest.fixture
def authenticated_technician_client(api_client, technician_factory, section):
    """Create an authenticated technician API client"""
    technician = technician_factory(username="authtech", password="techpass")
    technician.sections.add(section)
    api_client.force_authenticate(user=technician)
    return {
        'client': api_client,
        'user': technician,
        'token': None
    }


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
