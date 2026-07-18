"""
Phase 10 acceptance tests — coverage that has no home in phases 1-7:

  R7  — priority resolution: item-level override vs category default (property level)
  E2E — requester journey: create → ?mine=1 → feedback after resolved
  E2E — HOS assigns from the section pool (supervisor actor on /assign/)
  Model gap-fill: TicketFeedback.clean() bounds, resolved_priority is a
  property not a column, TicketLog newest-first ordering, choice-set guards,
  SectionType (department, name) uniqueness.

Everything else this file once held (R6/R8-R17 re-verification, escalation
edge cases, scope walkthroughs, seed invariants) was a duplicate of
test_phase1_models / test_phase2 / test_phase3 / test_phase4 / test_phase5 /
test_phase6_permissions / test_phase6_auth and was consolidated there.
"""

import pytest
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def campus(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Nairobi", code="NRB", location="CBD")


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


@pytest.fixture
def priority(db):
    from apps.sla.models import Priority

    return Priority.objects.create(
        name="Low", rank=1, response_minutes=480, resolution_minutes=4320
    )


@pytest.fixture
def priority_high(db):
    from apps.sla.models import Priority

    return Priority.objects.create(
        name="High", rank=4, response_minutes=60, resolution_minutes=240
    )


@pytest.fixture
def service_cat(section_type, priority):
    from apps.catalog.models import ServiceCategory

    return ServiceCategory.objects.create(
        section_type=section_type,
        name="Hardware",
        location_details=False,
        default_priority=priority,
        is_active=True,
    )


@pytest.fixture
def service_item(service_cat):
    from apps.catalog.models import ServiceItem

    return ServiceItem.objects.create(
        category=service_cat,
        name="Laptop Repair",
        is_active=True,
        default_priority=None,  # falls back to category default
    )


@pytest.fixture
def requester(campus):
    from apps.accounts.models import CustomUser, UserProfile

    user = CustomUser.objects.create_user(username="requester", password="pass")
    UserProfile.objects.create(user=user, campus=campus)
    return user


@pytest.fixture
def technician(section):
    from apps.accounts.models import CustomUser, RoleAssignment
    from apps.org.models import SectionTechnician

    user = CustomUser.objects.create_user(username="technician", password="pass")
    SectionTechnician.objects.create(user=user, section=section)
    RoleAssignment.objects.create(
        user=user, role="technician", section=section, is_primary=True
    )
    return user


@pytest.fixture
def hos_user(section):
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(username="hos_user", password="pass")
    section.hos = user
    section.save()
    RoleAssignment.objects.create(
        user=user, role="hos", section=section, is_primary=True
    )
    return user


@pytest.fixture
def open_ticket(requester, campus, service_item, section, priority):
    from apps.tickets.models import Ticket

    t = Ticket.objects.create(
        raised_by=requester,
        requester_campus=campus,
        service_item=service_item,
        section=section,
        priority=priority,
        status="open",
        current_level="technician",
        response_due_at=timezone.now() + timedelta(hours=8),
        resolution_due_at=timezone.now() + timedelta(hours=72),
    )
    return t


# ---------------------------------------------------------------------------
# R7 — Priority server-set from item.default_priority or category.default_priority
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR7PriorityResolution:
    """
    R7: Priority is resolved server-side. Item-level override takes precedence
    over category default.
    """

    def test_item_default_priority_overrides_category_default(
        self, service_cat, priority, priority_high
    ):
        """ServiceItem.resolved_priority returns the item's own default_priority
        when set, not the category's default_priority (R7, R16 config-driven)."""
        from apps.catalog.models import ServiceItem

        item = ServiceItem.objects.create(
            category=service_cat,
            name="Priority Override Item",
            is_active=True,
            default_priority=priority_high,  # item overrides category
        )
        assert item.resolved_priority == priority_high
        assert item.resolved_priority != priority  # != category default

    def test_item_without_override_falls_back_to_category_default(
        self, service_cat, priority
    ):
        """ServiceItem with no default_priority inherits category.default_priority."""
        from apps.catalog.models import ServiceItem

        item = ServiceItem.objects.create(
            category=service_cat,
            name="No Override Item",
            is_active=True,
            default_priority=None,
        )
        assert item.resolved_priority == priority  # falls back to category


# ---------------------------------------------------------------------------
# E2E role walkthrough: RequesterFlow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequesterFlow:
    """
    E2E: A plain requester creates a ticket, views it via ?mine=1,
    and submits feedback after the ticket is resolved.
    """

    def test_requester_full_lifecycle_create_view_feedback(
        self, api_client, requester, service_item, section, campus, priority, technician
    ):
        """Full requester lifecycle: create → ?mine=1 view → feedback after resolved."""
        from apps.tickets.models import Ticket, TicketFeedback
        from apps.tickets.services.lifecycle import transition_status

        api_client.force_authenticate(user=requester)

        # Step 1: Create ticket
        resp = api_client.post(
            "/api/v1/tickets/",
            {"service_item": service_item.id, "description": "E2E requester test"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        ticket_id = resp.data["id"]
        ticket = Ticket.objects.get(id=ticket_id)

        # Step 2: View own tickets via ?mine=1
        resp_mine = api_client.get("/api/v1/tickets/?mine=1")
        assert resp_mine.status_code == 200
        ids = [t["id"] for t in resp_mine.data.get("results", resp_mine.data)]
        assert ticket_id in ids

        # Step 3: Advance to resolved via service layer
        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)
        transition_status(ticket, "resolved", technician)
        ticket.refresh_from_db()

        # Step 4: Requester submits feedback
        resp_fb = api_client.post(
            f"/api/v1/tickets/{ticket_id}/feedback/",
            {"rating": 5, "comment": "Excellent!"},
            format="json",
        )
        assert resp_fb.status_code == 201
        fb = TicketFeedback.objects.get(ticket=ticket)
        assert fb.rating == 5


# ---------------------------------------------------------------------------
# E2E role walkthrough: HOSFlow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHOSFlow:
    """
    E2E: An HOS user assigns a ticket from the section pool (the phase4 assign
    tests drive /assign/ as a technician; this covers the supervisor actor).
    """

    def test_hos_can_assign_ticket_from_pool(
        self, api_client, hos_user, technician, open_ticket
    ):
        """HOS can assign an unassigned ticket to a technician in the section pool."""
        api_client.force_authenticate(user=hos_user)
        url = f"/api/v1/tickets/{open_ticket.pk}/assign/"
        resp = api_client.post(url, {"assigned_to": technician.pk}, format="json")
        assert resp.status_code == 200
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to == technician


# ---------------------------------------------------------------------------
# Additional model-level tests not in phases 1-7
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestModelInvariantsGapFill:
    """Catches model-level gaps not addressed in test_phase1_models through test_phase7."""

    def test_ticket_feedback_rating_too_high_raises(self, open_ticket):
        """TicketFeedback.clean() must reject ratings > 5."""
        from apps.tickets.models import TicketFeedback
        from django.core.exceptions import ValidationError

        fb = TicketFeedback(ticket=open_ticket, rating=6)
        with pytest.raises(ValidationError):
            fb.clean()

    def test_ticket_feedback_rating_zero_raises(self, open_ticket):
        """TicketFeedback.clean() must reject rating=0."""
        from apps.tickets.models import TicketFeedback
        from django.core.exceptions import ValidationError

        fb = TicketFeedback(ticket=open_ticket, rating=0)
        with pytest.raises(ValidationError):
            fb.clean()

    def test_ticket_feedback_valid_ratings_pass(self, open_ticket):
        """Ratings 1–5 must all pass TicketFeedback.clean()."""
        from apps.tickets.models import TicketFeedback

        for rating in range(1, 6):
            fb = TicketFeedback(ticket=open_ticket, rating=rating)
            fb.clean()  # must not raise

    def test_service_item_resolved_priority_property_not_a_field(self, service_cat):
        """ServiceItem.resolved_priority must be a @property, not a DB column."""
        from apps.catalog.models import ServiceItem

        db_fields = [f.name for f in ServiceItem._meta.get_fields()]
        assert "resolved_priority" not in db_fields
        item = ServiceItem.objects.create(category=service_cat, name="Prop Check")
        # Must have the property
        assert hasattr(item, "resolved_priority")

    def test_section_type_unique_per_department_r3(self, db):
        """UniqueConstraint on (department, name) for SectionType rejects duplicates."""
        from apps.org.models import Department, SectionType

        dept = Department.objects.create(name="Dup Test Dept", code="DTD")
        SectionType.objects.create(department=dept, name="Dup ST", code="DST")
        with pytest.raises(Exception):
            SectionType.objects.create(department=dept, name="Dup ST", code="DST2")

    def test_ticket_log_default_ordering_newest_first(self, open_ticket, requester):
        """TicketLog default ordering is newest-first (-created_at)."""
        from apps.tickets.models import TicketLog

        log1 = TicketLog.objects.create(
            ticket=open_ticket, actor=requester, event_type="created"
        )
        # Set log1 to 10 seconds in the past so it is definitely older
        TicketLog.objects.filter(pk=log1.pk).update(
            created_at=timezone.now() - timedelta(seconds=10)
        )
        log2 = TicketLog.objects.create(
            ticket=open_ticket, actor=requester, event_type="assigned"
        )

        logs = list(TicketLog.objects.filter(ticket=open_ticket))
        assert (
            logs[0].pk == log2.pk
        ), "Most recent log must come first (newest-first ordering)"
        assert logs[1].pk == log1.pk

    def test_ticket_comment_visibility_choices_are_public_and_internal(self):
        """TicketComment.VISIBILITY must contain exactly 'public' and 'internal'."""
        from apps.tickets.models import TicketComment

        choices = {v for v, _ in TicketComment.VISIBILITY}
        assert choices == {"public", "internal"}

    def test_escalation_rule_has_hos_and_hod_to_level_choices(self):
        """EscalationRule.TO_LEVEL_CHOICES must contain 'hos' and 'hod'."""
        from apps.sla.models import EscalationRule

        choices = {v for v, _ in EscalationRule.TO_LEVEL_CHOICES}
        assert "hos" in choices
        assert "hod" in choices
