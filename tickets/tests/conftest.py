"""
Pytest configuration and fixtures for Django Resolver tests.

Fixtures use the updated model structure:
  - Campus / Department are standalone (no Organisation FK)
  - CampusDepartment joins Campus + Department
  - Section requires campus_department + section_type
  - Ticket requires campus_department (non-nullable)

All fixture names are preserved so test files that import them by name
(section, campus, department, etc.) continue to work.
"""

import pytest
import uuid
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

from tickets.models import (
    Campus,
    CampusDepartment,
    Department,
    Facility,
    Section,
    SectionType,
    ServiceCategory,
    ServiceItem,
    Ticket,
    Comment,
    Feedback,
    TicketLog,
)
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear in-memory cache before each test to prevent cache poisoning."""
    cache.clear()
    yield
    cache.clear()


# ── User factories ────────────────────────────────────────────────────────────


@pytest.fixture
def user_factory(db):
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
    def create_technician(username=None, email=None, password="techpass", **kwargs):
        if username is None:
            username = f"technician_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"tech_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="technician", **kwargs
        )
    return create_technician


@pytest.fixture
def section_head_factory(db):
    def create_section_head(username=None, email=None, password="headpass", **kwargs):
        if username is None:
            username = f"head_of_section_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"head_of_section_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="head_of_section", **kwargs
        )
    return create_section_head


@pytest.fixture
def hod_factory(db):
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
def manager_factory(db):
    def create_manager(username=None, email=None, password="managerpass", **kwargs):
        if username is None:
            username = f"manager_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"manager_{uuid.uuid4().hex[:8]}@example.com"
        return get_user_model().objects.create_user(
            username=username, email=email, password=password, role="manager", **kwargs
        )
    return create_manager


# ── Organisational hierarchy ──────────────────────────────────────────────────

@pytest.fixture
def campus(db):
    """Standalone campus — no Organisation FK in new model."""
    return Campus.objects.create(
        name="Main Campus", code="MAIN", location="123 Main St"
    )


@pytest.fixture
def department(db):
    """Global department — no Campus FK in new model."""
    return Department.objects.create(name="IT Department", code="IT")


@pytest.fixture
def department_hvac(db):
    """Second department for multi-department tests."""
    return Department.objects.create(name="Facilities Department", code="FAC")


@pytest.fixture
def campus_department(db, campus, department, hod_factory):
    """CampusDepartment joins Campus + Department and assigns an HOD."""
    hod = hod_factory()
    hod.primary_campus = campus
    hod.save()
    cd = CampusDepartment.objects.create(
        campus=campus, department=department, head_of_department=hod
    )
    hod.primary_department = department
    hod.save()
    return cd


@pytest.fixture
def section_type(db, department):
    """Default SectionType for the IT department."""
    return SectionType.objects.create(
        department=department,
        name="Network Section Type",
        code="NET",
        default_sla_hours=48,
    )


@pytest.fixture
def section(db, campus_department, section_type, section_head_factory):
    """Section linked to CampusDepartment + SectionType."""
    section_head = section_head_factory()
    section_head.primary_campus = campus_department.campus
    section_head.primary_department = campus_department.department
    section_head.save()

    sec = Section.objects.create(
        campus_department=campus_department,
        section_type=section_type,
        name="Network Section",
        code="NETWORK",
        head_of_section=section_head,
    )
    section_head.sections.add(sec)
    return sec


@pytest.fixture
def section_hvac(db, campus, department_hvac, section_head_factory):
    """Second section for multi-section tests."""
    section_head = section_head_factory()
    section_head.primary_campus = campus
    section_head.primary_department = department_hvac
    section_head.save()

    st = SectionType.objects.create(
        department=department_hvac, name="HVAC Section Type", code="HVAC"
    )
    cd = CampusDepartment.objects.create(campus=campus, department=department_hvac)
    sec = Section.objects.create(
        campus_department=cd,
        section_type=st,
        name="HVAC Section",
        code="HVAC",
        head_of_section=section_head,
    )
    section_head.sections.add(sec)
    return sec


# ── Org-aware user factory ────────────────────────────────────────────────────

@pytest.fixture
def org_aware_user_factory(db, campus, department, section):
    def create_user(
        username=None, email=None, password="testpass", role="user",
        add_to_section=False, **kwargs,
    ):
        if username is None:
            username = f"org_user_{uuid.uuid4().hex[:8]}"
        if email is None:
            email = f"org_user_{uuid.uuid4().hex[:8]}@example.com"

        user = get_user_model().objects.create_user(
            username=username, email=email, password=password, role=role,
            primary_campus=campus, primary_department=department, **kwargs,
        )
        if add_to_section:
            user.sections.add(section)
        return user
    return create_user


# ── Service catalogue fixtures ────────────────────────────────────────────────

@pytest.fixture
def service_category(db, section_type):
    return ServiceCategory.objects.create(
        section_type=section_type,
        name="Hardware",
        description="Hardware requests",
        order=1,
    )


@pytest.fixture
def service_item(db, service_category):
    return ServiceItem.objects.create(
        category=service_category,
        name="Laptop Repair",
        description="Repair a laptop",
        sla_hours=48,
        requires_approval=False,
    )


@pytest.fixture
def service_item_requires_approval(db, service_category):
    return ServiceItem.objects.create(
        category=service_category,
        name="New Workstation",
        description="Request new workstation — requires approval",
        sla_hours=72,
        requires_approval=True,
    )


# ── Other model fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def facility(db, campus):
    return Facility.objects.create(
        name="Main Building",
        type="building",
        status="active",
        location="123 Main St",
        campus=campus,
    )


# ── Ticket factory ────────────────────────────────────────────────────────────

@pytest.fixture
def ticket_factory(db, section, facility, user_factory, technician_factory):
    def create_ticket(
        title="Test Ticket",
        description="Test ticket description",
        status="open",
        priority="low",
        section=section,
        facility=facility,
        raised_by=None,
        assigned_to=...,  # Sentinel value; ... means create default, None means unassigned
        **kwargs,
    ):
        if raised_by is None:
            raised_by = user_factory()
        if assigned_to is ...:
            assigned_to = technician_factory()

        created_at = kwargs.pop("created_at", None)
        assigned_at = kwargs.pop("assigned_at", None)

        # campus_department is required on Ticket — derive from section if not supplied
        if "campus_department" not in kwargs and section is not None:
            kwargs["campus_department"] = section.campus_department

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

        if created_at:
            Ticket.objects.filter(id=ticket.id).update(created_at=created_at)
            ticket.refresh_from_db()

        if assigned_at is not None:
            Ticket.objects.filter(id=ticket.id).update(assigned_at=assigned_at)
            ticket.refresh_from_db()
        elif assigned_to is not None:
            Ticket.objects.filter(id=ticket.id).update(assigned_at=timezone.now())
            ticket.refresh_from_db()

        return ticket

    return create_ticket


# ── Comment / Feedback factories ──────────────────────────────────────────────

@pytest.fixture
def comment_factory(db, ticket_factory, user_factory):
    def create_comment(text="Test comment", ticket=None, author=None):
        if ticket is None:
            ticket = ticket_factory()
        if author is None:
            author = user_factory()
        return Comment.objects.create(ticket=ticket, text=text, author=author)
    return create_comment


@pytest.fixture
def feedback_factory(db, ticket_factory, user_factory):
    def create_feedback(rating=5, comment="Great service", ticket=None, rated_by=None):
        if ticket is None:
            ticket = ticket_factory()
        if rated_by is None:
            rated_by = user_factory()
        return Feedback.objects.create(
            ticket=ticket, rating=rating, comment=comment, rated_by=rated_by
        )
    return create_feedback


# ── Common composite fixtures ─────────────────────────────────────────────────

@pytest.fixture
def basic_setup(
    db, user_factory, admin_user_factory, technician_factory,
    campus, department, section, facility,
):
    return {
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
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, org_aware_user_factory, campus, section):
    user = org_aware_user_factory(
        username="authuser", password="authpass", add_to_section=True
    )
    api_client.force_authenticate(user=user)
    return {"client": api_client, "user": user, "token": None}


@pytest.fixture
def authenticated_admin_client(admin_user_factory, campus):
    admin = admin_user_factory(username="authadmin", password="adminpass")
    admin.primary_campus = campus
    admin.save()
    client = APIClient()
    client.force_authenticate(user=admin)
    return {"client": client, "user": admin, "token": None}


@pytest.fixture
def authenticated_technician_client(technician_factory, section, campus, department):
    technician = technician_factory(username="authtech", password="techpass")
    technician.sections.add(section)
    technician.primary_campus = campus
    technician.primary_department = department
    technician.save()
    client = APIClient()
    client.force_authenticate(user=technician)
    return {"client": client, "user": technician, "token": None}


# ── Pytest markers ────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
