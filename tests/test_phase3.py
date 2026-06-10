"""
Phase 3 acceptance tests — Ticket creation endpoint (POST /api/v1/tickets/).

Covers:
  - routing resolution (campus → section)
  - priority resolution (item override vs category default)
  - location validation (office_block, equipment, unknown fields, missing fields)
  - SLA deadline computation
  - authentication enforcement
  - server-side-only fields (section, priority ignored from client)

Uses pytest + pytest-django.  All tests target the 8-app layout (apps.*).
"""

import pytest
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

TICKETS_URL = "/api/v1/tickets/"


# ── helpers ───────────────────────────────────────────────────────────────────

@pytest.fixture
def api_client():
    return APIClient()


# ── core org / catalogue fixtures ─────────────────────────────────────────────

@pytest.fixture
def campus(db):
    from apps.org.models import Campus
    return Campus.objects.create(name="Nairobi", code="NRB", location="CBD")


@pytest.fixture
def campus_msa(db):
    """A second campus with NO section for the SectionType — used to test routing rejection."""
    from apps.org.models import Campus
    return Campus.objects.create(name="Mombasa", code="MSA", location="Coast")


@pytest.fixture
def dept(db):
    from apps.org.models import Department
    return Department.objects.create(name="ICT", code="ICT")


@pytest.fixture
def section_type(dept):
    from apps.org.models import SectionType
    return SectionType.objects.create(department=dept, name="Support", code="SUP")


@pytest.fixture
def campus_dept(campus, dept):
    from apps.org.models import CampusDepartment
    return CampusDepartment.objects.create(campus=campus, department=dept)


@pytest.fixture
def active_section(campus_dept, section_type):
    from apps.org.models import Section
    return Section.objects.create(
        campus_department=campus_dept, section_type=section_type, is_active=True
    )


@pytest.fixture
def priority(db):
    from apps.sla.models import Priority
    return Priority.objects.create(
        name="Low", rank=1, response_minutes=480, resolution_minutes=4320
    )


@pytest.fixture
def service_category(section_type, priority):
    from apps.catalog.models import ServiceCategory
    return ServiceCategory.objects.create(
        section_type=section_type,
        name="Network Issues",
        default_priority=priority,
        location_details=False,
        is_active=True,
    )


@pytest.fixture
def service_item(service_category):
    from apps.catalog.models import ServiceItem
    return ServiceItem.objects.create(
        category=service_category,
        name="No Internet",
        is_active=True,
        default_priority=None,   # no item-level override — falls back to category
    )


@pytest.fixture
def user(db, campus):
    from apps.accounts.models import CustomUser, UserProfile
    u = CustomUser.objects.create_user(username="requester", password="pass")
    UserProfile.objects.create(user=u, campus=campus)
    return u


# ── location-related fixtures ─────────────────────────────────────────────────

@pytest.fixture
def office_block_ft(db):
    from apps.facilities.models import FacilityType
    return FacilityType.objects.create(name="Office Block", code="office_block")


@pytest.fixture
def equipment_ft(db):
    from apps.facilities.models import FacilityType
    return FacilityType.objects.create(name="Equipment", code="equipment")


@pytest.fixture
def block_a(campus, office_block_ft):
    from apps.facilities.models import Facility
    return Facility.objects.create(
        campus=campus, facility_type=office_block_ft, name="Block A", code="BLK-A"
    )


@pytest.fixture
def service_category_with_location(section_type, priority):
    from apps.catalog.models import ServiceCategory
    return ServiceCategory.objects.create(
        section_type=section_type,
        name="Hardware Issues",
        default_priority=priority,
        location_details=True,
        is_active=True,
    )


@pytest.fixture
def service_item_with_location(service_category_with_location):
    from apps.catalog.models import ServiceItem
    return ServiceItem.objects.create(
        category=service_category_with_location,
        name="Broken Printer",
        is_active=True,
        default_priority=None,
    )


# ── Test 1: happy-path ticket creation ───────────────────────────────────────

@pytest.mark.django_db
def test_create_ticket_success(api_client, user, service_item, active_section):
    """POST with valid service_item and authenticated user returns 201 with ticket_no."""
    from apps.tickets.models import Ticket, TicketLog

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "test"},
        format="json",
    )

    assert resp.status_code == 201, resp.data
    assert "ticket_no" in resp.data
    assert resp.data["ticket_no"].startswith("TKT-")
    assert Ticket.objects.count() == 1

    ticket = Ticket.objects.get(id=resp.data["id"])
    assert TicketLog.objects.filter(
        ticket=ticket, event_type="created").count() == 1


# ── Test 2: server resolves section and priority; client values ignored ────────

@pytest.mark.django_db
def test_ticket_has_correct_section_and_priority_resolved_server_side(
    api_client, user, service_item, active_section, priority
):
    """Client-supplied priority/section are silently ignored; server resolves them."""
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "priority": 999, "section": 999},
        format="json",
    )

    # Must succeed despite bogus priority/section values
    assert resp.status_code == 201, resp.data

    from apps.tickets.models import Ticket
    ticket = Ticket.objects.get(id=resp.data["id"])
    assert ticket.section == active_section
    assert ticket.priority == priority


# ── Test 3: unauthenticated request rejected ──────────────────────────────────

@pytest.mark.django_db
def test_create_ticket_unauthenticated(api_client, service_item):
    """No auth → 401."""
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "test"},
        format="json",
    )
    assert resp.status_code == 401


# ── Test 4: service not available at requester's campus ───────────────────────

@pytest.mark.django_db
def test_unserved_service_item_rejected(
    api_client, campus_msa, service_item, active_section
):
    """User at MSA campus where no section handles the service → 400 on service_item."""
    from apps.accounts.models import CustomUser, UserProfile

    msa_user = CustomUser.objects.create_user(
        username="msa_user", password="pass")
    UserProfile.objects.create(user=msa_user, campus=campus_msa)

    api_client.force_authenticate(user=msa_user)
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "help"},
        format="json",
    )

    assert resp.status_code == 400
    # Error must surface on the service_item field
    errors = resp.data if isinstance(resp.data, dict) else {}
    assert "service_item" in errors


# ── Test 5: location required when category.location_details=True ─────────────

@pytest.mark.django_db
def test_location_required_when_category_location_details(
    api_client, user, service_item_with_location, active_section
):
    """category.location_details=True and no location sent → 400 with error on location."""
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item_with_location.id, "description": "broken"},
        format="json",
    )

    assert resp.status_code == 400
    errors = resp.data if isinstance(resp.data, dict) else {}
    assert "location" in errors


# ── Test 6: successful ticket with office_block location ──────────────────────

@pytest.mark.django_db
def test_create_ticket_with_office_block_location(
    api_client, user, service_item_with_location, active_section,
    office_block_ft, block_a,
):
    """POST with valid office_block location → 201, TicketLocation created."""
    from apps.tickets.models import TicketLocation

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {
            "service_item": service_item_with_location.id,
            "description": "printer broken",
            "location": {
                "facility_type": office_block_ft.id,
                "facility": block_a.id,
                "values": {"floor": "2", "room": "101"},
            },
        },
        format="json",
    )

    assert resp.status_code == 201, resp.data

    from apps.tickets.models import Ticket
    ticket = Ticket.objects.get(id=resp.data["id"])
    loc = TicketLocation.objects.get(ticket=ticket)

    assert loc.facility == block_a
    assert loc.facility_type == office_block_ft
    assert loc.values.get("floor") == "2"
    assert loc.values.get("room") == "101"


# ── Test 7: facility from wrong campus rejected ───────────────────────────────

@pytest.mark.django_db
def test_office_block_location_rejects_wrong_campus_facility(
    api_client, user, service_item_with_location, active_section,
    office_block_ft, campus_msa,
):
    """User at NRB, facility from MSA → 400 with error on facility."""
    from apps.facilities.models import Facility

    msa_facility = Facility.objects.create(
        campus=campus_msa,
        facility_type=office_block_ft,
        name="Block B",
        code="BLK-B",
    )

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {
            "service_item": service_item_with_location.id,
            "location": {
                "facility_type": office_block_ft.id,
                "facility": msa_facility.id,
                "values": {"floor": "1", "room": "10"},
            },
        },
        format="json",
    )

    assert resp.status_code == 400
    # The error must reference the facility field within location
    response_str = str(resp.data)
    assert "facility" in response_str


# ── Test 8: office_block without facility rejected ────────────────────────────

@pytest.mark.django_db
def test_office_block_location_requires_facility(
    api_client, user, service_item_with_location, active_section,
    office_block_ft,
):
    """office_block type without a facility → 400."""
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {
            "service_item": service_item_with_location.id,
            "location": {
                "facility_type": office_block_ft.id,
                # facility intentionally omitted
                "values": {"floor": "1", "room": "10"},
            },
        },
        format="json",
    )

    assert resp.status_code == 400
    response_str = str(resp.data)
    assert "facility" in response_str


# ── Test 9: unknown field in location values rejected ─────────────────────────

@pytest.mark.django_db
def test_location_unknown_field_rejected(
    api_client, user, service_item_with_location, active_section,
    office_block_ft, block_a,
):
    """Unknown field in location values dict → 400 with error on values."""
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {
            "service_item": service_item_with_location.id,
            "location": {
                "facility_type": office_block_ft.id,
                "facility": block_a.id,
                "values": {"floor": "2", "room": "101", "bogus_field": "x"},
            },
        },
        format="json",
    )

    assert resp.status_code == 400
    response_str = str(resp.data)
    assert "values" in response_str


# ── Test 10: missing required field in location values rejected ───────────────

@pytest.mark.django_db
def test_location_missing_required_field_rejected(
    api_client, user, service_item_with_location, active_section,
    office_block_ft, block_a,
):
    """Missing required 'room' field in office_block values → 400 with error on values."""
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {
            "service_item": service_item_with_location.id,
            "location": {
                "facility_type": office_block_ft.id,
                "facility": block_a.id,
                "values": {"floor": "2"},   # room is missing
            },
        },
        format="json",
    )

    assert resp.status_code == 400
    response_str = str(resp.data)
    assert "values" in response_str


# ── Test 11: equipment location — no facility required ───────────────────────

@pytest.mark.django_db
def test_equipment_location_no_facility_required(
    api_client, user, service_item_with_location, active_section,
    equipment_ft,
):
    """equipment type needs no facility; TicketLocation.facility is None."""
    from apps.tickets.models import Ticket, TicketLocation

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {
            "service_item": service_item_with_location.id,
            "description": "HP Printer issue",
            "location": {
                "facility_type": equipment_ft.id,
                "values": {"asset_name": "HP Printer"},
            },
        },
        format="json",
    )

    assert resp.status_code == 201, resp.data

    ticket = Ticket.objects.get(id=resp.data["id"])
    loc = TicketLocation.objects.get(ticket=ticket)
    assert loc.facility is None
    assert loc.values.get("asset_name") == "HP Printer"


# ── Test 12: ticket_no is generated and unique ────────────────────────────────

@pytest.mark.django_db
def test_ticket_no_is_generated(api_client, user, service_item, active_section):
    """Each created ticket gets a non-empty, unique ticket_no."""
    from apps.tickets.models import Ticket

    api_client.force_authenticate(user=user)

    expected_prefix = (
        f"TKT-{active_section.campus_department.campus.code}-"
        f"{active_section.campus_department.department.code}-"
    )
    resp1 = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "first"},
        format="json",
    )
    resp2 = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "second"},
        format="json",
    )

    assert resp1.status_code == 201
    assert resp2.status_code == 201

    no1 = resp1.data["ticket_no"]
    no2 = resp2.data["ticket_no"]

    assert no1  # not empty
    assert no2
    assert no1.startswith(expected_prefix)
    assert no2.startswith(expected_prefix)
    assert no1 != no2   # unique

    # Both exist in the database
    assert Ticket.objects.filter(ticket_no=no1).exists()
    assert Ticket.objects.filter(ticket_no=no2).exists()


# ── Test 13: SLA deadlines set correctly on creation ─────────────────────────

@pytest.mark.django_db
def test_sla_times_set_on_create(api_client, user, service_item, active_section, priority):
    """response_due_at ≈ now+480min and resolution_due_at ≈ now+4320min (±60s)."""
    from apps.tickets.models import Ticket

    before = timezone.now()

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "slow network"},
        format="json",
    )

    after = timezone.now()

    assert resp.status_code == 201, resp.data

    ticket = Ticket.objects.get(id=resp.data["id"])

    tolerance = timedelta(seconds=60)

    expected_response_min = before + \
        timedelta(minutes=priority.response_minutes)
    expected_response_max = after + \
        timedelta(minutes=priority.response_minutes)
    assert expected_response_min - \
        tolerance <= ticket.response_due_at <= expected_response_max + tolerance

    expected_resolution_min = before + \
        timedelta(minutes=priority.resolution_minutes)
    expected_resolution_max = after + \
        timedelta(minutes=priority.resolution_minutes)
    assert expected_resolution_min - \
        tolerance <= ticket.resolution_due_at <= expected_resolution_max + tolerance


# ── Test 14: user without campus rejected ────────────────────────────────────

@pytest.mark.django_db
def test_user_without_campus_rejected(api_client, service_item, active_section):
    """User with no UserProfile (no campus) → 400 with message about campus."""
    from apps.accounts.models import CustomUser

    campusless_user = CustomUser.objects.create_user(
        username="nocampus", password="pass"
    )
    # Deliberately do NOT create a UserProfile for this user.

    api_client.force_authenticate(user=campusless_user)
    resp = api_client.post(
        TICKETS_URL,
        {"service_item": service_item.id, "description": "help"},
        format="json",
    )

    assert resp.status_code == 400
    # The error message must mention campus
    response_str = str(resp.data).lower()
    assert "campus" in response_str
