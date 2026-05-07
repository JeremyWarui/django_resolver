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
import uuid
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

    def create_user(username=None, email=None, password="testpass", **kwargs):
        if username is None:
            username = f"testuser_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="user", **kwargs
        )

    return create_user


@pytest.fixture
def admin_user_factory(db):
    """Factory for creating admin users"""

    def create_admin(username=None, email=None, password="admin123", **kwargs):
        if username is None:
            username = f"admin_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="admin", **kwargs
        )

    return create_admin


@pytest.fixture
def technician_factory(db):
    """Factory for creating technician users"""

    def create_technician(username=None, email=None, password="techpass", **kwargs):
        if username is None:
            username = f"technician_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"tech_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="technician",
            **kwargs,
        )

    return create_technician


@pytest.fixture
def section_head_factory(db):
    """Factory for creating section head users"""

    def create_section_head(username=None, email=None, password="headpass", **kwargs):
        if username is None:
            username = f"section_head_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"head_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role="section_head",
            **kwargs,
        )

    return create_section_head


@pytest.fixture
def hod_factory(db):
    """Factory for creating HOD (Head of Department) users"""

    def create_hod(username=None, email=None, password="hodpass", **kwargs):
        if username is None:
            username = f"hod_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"hod_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="hod", **kwargs
        )

    return create_hod


@pytest.fixture
def director_factory(db):
    """Factory for creating director users"""

    def create_director(username=None, email=None, password="dirpass", **kwargs):
        if username is None:
            username = f"director_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"director_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="director", **kwargs
        )

    return create_director


# ============================================================================
# ORGANIZATIONAL-AWARE USER FIXTURES
# ============================================================================


@pytest.fixture
def org_aware_user_factory(db, campus, department, section):
    """Factory for creating users with organizational assignments"""

    def create_user(
        username=None,
        email=None,
        password="testpass",
        role="user",
        add_to_section=False,
        **kwargs,
    ):
        if username is None:
            username = f"org_user_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"org_user_{uuid.uuid4().hex[:8]}@example.com"

        user = get_user_model().objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            primary_campus=campus,
            primary_department=department,
            **kwargs,
        )

        # Add to section if requested (useful for technicians)
        if add_to_section and hasattr(section, "pk"):
            user.sections.add(section)

        return user

    return create_user


# ============================================================================
# ORGANIZATIONAL HIERARCHY FIXTURES
# ============================================================================


@pytest.fixture
def organization(db):
    """Create a test organization"""
    return Organization.objects.create(
        name="Test Organization", code="TEST", organization_type="corporate"
    )


@pytest.fixture
def campus(db, organization):
    """Create a test campus"""
    return Campus.objects.create(
        name="Main Campus",
        code="MAIN",
        organization=organization,
        location="123 Main St",
    )


@pytest.fixture
def department(db, campus, hod_factory):
    """Create a test department with HOD"""
    hod = hod_factory()
    hod.primary_campus = campus
    hod.save()

    dept = Department.objects.create(
        name="IT Department", code="IT", campus=campus, head_of_department=hod
    )
    return dept


@pytest.fixture
def department_hvac(db, campus, hod_factory):
    """Create a second department for multi-department tests"""
    hod = hod_factory()
    hod.primary_campus = campus
    hod.save()

    dept = Department.objects.create(
        name="Facilities Department", code="FAC", campus=campus, head_of_department=hod
    )
    return dept


@pytest.fixture
def section(db, department, section_head_factory):
    """Create a test section with section head"""
    section_head = section_head_factory()
    section_head.primary_campus = department.campus
    section_head.primary_department = department
    section_head.save()

    sec = Section.objects.create(
        name="Network Section",
        code="NETWORK",
        department=department,
        section_head=section_head,
    )
    sec.section_head.sections.add(sec)
    return sec


@pytest.fixture
def section_hvac(db, department_hvac, section_head_factory):
    """Create a second section for multi-section tests"""
    section_head = section_head_factory()
    section_head.primary_campus = department_hvac.campus
    section_head.primary_department = department_hvac
    section_head.save()

    sec = Section.objects.create(
        name="HVAC Section",
        code="HVAC",
        department=department_hvac,
        section_head=section_head,
    )
    sec.section_head.sections.add(sec)
    return sec


# ============================================================================
# OTHER MODEL FIXTURES
# ============================================================================


@pytest.fixture
def facility(db, campus):
    """Create a test facility"""
    return Facility.objects.create(
        name="Main Building",
        type="building",
        status="active",
        location="123 Main St",
        campus=campus,
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
        **kwargs,
    ):
        if raised_by is None:
            raised_by = user_factory()
        if assigned_to is None:
            assigned_to = technician_factory()

        # Extract created_at and assigned_at if provided (since auto_now_add prevents manual setting)
        created_at = kwargs.pop("created_at", None)
        assigned_at = kwargs.pop("assigned_at", None)

        ticket = Ticket.objects.create(
            title=title,
            description=description,
            status=status,
            priority=priority,
            section=section,
            facility=facility,
            raised_by=raised_by,
            assigned_to=assigned_to,
            **kwargs,
        )

        # Manually set created_at if provided
        if created_at:
            Ticket.objects.filter(id=ticket.id).update(created_at=created_at)
            ticket.refresh_from_db()

        # Manually set assigned_at if provided
        # If not provided but assigned_to is set, use current time (default behavior)
        if assigned_at is not None:
            Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_at)
            ticket.refresh_from_db()
        elif assigned_to is not None and not assigned_at:
            # Auto-set assigned_at to now if ticket is assigned and assigned_at not explicitly set to None
            from django.utils import timezone

            Ticket.objects.filter(id=ticket.id).update(assigned_at=timezone.now())
            ticket.refresh_from_db()

        return ticket

    return create_ticket


# ============================================================================
# COMMENT/FEEDBACK FIXTURES
# ============================================================================


@pytest.fixture
def comment_factory(db, ticket_factory, user_factory):
    """Factory for creating comments"""

    def create_comment(text="Test comment", ticket=None, author=None):
        if ticket is None:
            ticket = ticket_factory()
        if author is None:
            author = user_factory()

        return Comment.objects.create(ticket=ticket, text=text, author=author)

    return create_comment


@pytest.fixture
def feedback_factory(db, ticket_factory, user_factory):
    """Factory for creating feedback"""

    def create_feedback(rating=5, comment="Great service", ticket=None, rated_by=None):
        if ticket is None:
            ticket = ticket_factory()
        if rated_by is None:
            rated_by = user_factory()

        return Feedback.objects.create(
            ticket=ticket, rating=rating, comment=comment, rated_by=rated_by
        )

    return create_feedback


# ============================================================================
# COMMON TEST SETUP FIXTURES
# ============================================================================


@pytest.fixture
def basic_setup(
    db,
    user_factory,
    admin_user_factory,
    technician_factory,
    organization,
    campus,
    department,
    section,
    facility,
):
    """Complete basic setup with all common objects"""
    return {
        "organization": organization,
        "campus": campus,
        "department": department,
        "section": section,
        "facility": facility,
        "user": user_factory(),
        "admin": admin_user_factory(),
        "technician": technician_factory(),
    }


@pytest.fixture
def api_client():
    """Create an API client for testing endpoints"""
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, org_aware_user_factory, campus, section):
    """Create an authenticated API client with organizational context"""
    user = org_aware_user_factory(
        username="authuser", password="authpass", add_to_section=True
    )
    api_client.force_authenticate(user=user)
    return {
        "client": api_client,
        "user": user,
        "token": None,  # Token would be set after login if needed
    }


@pytest.fixture
def authenticated_admin_client(admin_user_factory, campus):
    """Create an authenticated admin API client with organizational context"""
    admin = admin_user_factory(username="authadmin", password="adminpass")
    admin.primary_campus = campus
    admin.save()
    client = APIClient()
    client.force_authenticate(user=admin)
    return {"client": client, "user": admin, "token": None}


@pytest.fixture
def authenticated_technician_client(technician_factory, section, campus, department):
    """Create an authenticated technician API client with organizational context"""
    technician = technician_factory(username="authtech", password="techpass")
    technician.sections.add(section)
    technician.primary_campus = campus
    technician.primary_department = department
    technician.save()
    client = APIClient()
    client.force_authenticate(user=technician)
    return {"client": client, "user": technician, "token": None}


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
