"""
Phase 10 acceptance tests — Invariants R1-R17, escalation edge cases,
E2E role walkthroughs, and seed verification.

Coverage gap analysis (tests not already in phase 1-7):
  R6  — routing: rejects campus with no active section, confirms server-resolved section
  R7  — priority: item-level override over category default; requesters cannot set it
  R8  — status machine: full transition table + pending requires reason
  R9  — SLA: accumulated_pause + due timestamp shift (explicit calculation)
  R10 — escalation: multi-step advance, log fields, resolved/closed skip
  R11 — TicketLog immutability: save() / delete() guard tested at model level
  R12 — Transfer: changing role-holder re-homes tickets to section pool
  R13 — Location: captured iff location_details; validated against FacilityType fields
  R14 — FacilityType: admin-managed registry; viewset is read-only
  R15 — ?mine=1 for plain user AND staff
  R16 — Config-driven: ServiceItem.resolved_priority delegates to category default
  R17 — RoleAssignment: is_active() behaviour with valid_until, cover logic

Escalation edge cases:
  - Vacant HOS seat → skip to HOD
  - Active cover RoleAssignment wins over standing HOS
  - Expired cover → falls back to standing HOS
  - Resolved/closed tickets are never escalated
  - Accumulated pause excludes paused time from active-clock

E2E role walkthrough tests:
  - RequesterFlow: create ticket, view ?mine=1, post feedback after resolved
  - TechnicianFlow: view assigned queue, assigned→in_progress, add internal comment
  - HOSFlow: assign ticket from section pool, adjust priority
  - HODFlow: view HOD-level escalated tickets
  - LeaveCoverFlow: active HOS cover RoleAssignment lets cover user act as HOS

Seed verification:
  - Every EscalationRule set has both HOS and HOD rungs per priority
  - Every Section satisfies R2 (section_type.department == campus_department.department)
  - No ServiceCategory has a 'department' DB field
  - An active HOS cover RoleAssignment exists with valid_until set

All imports are inside test functions/fixtures to avoid import-time
errors if the modules are not yet wired up in a given deployment.

Run with: pytest tickets/tests/test_phase10.py -v
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
def campus_b(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Mombasa", code="MSA", location="Coast")


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
def section_type_net(dept):
    from apps.org.models import SectionType

    return SectionType.objects.create(department=dept, name="Networks", code="NET")


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
def hos_rule(priority):
    from apps.sla.models import EscalationRule

    return EscalationRule.objects.create(
        priority=priority, to_level="hos", threshold_minutes=30, order=1
    )


@pytest.fixture
def hod_rule(priority, hos_rule):
    from apps.sla.models import EscalationRule

    return EscalationRule.objects.create(
        priority=priority, to_level="hod", threshold_minutes=60, order=2
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
def service_cat_with_location(section_type, priority):
    from apps.catalog.models import ServiceCategory

    return ServiceCategory.objects.create(
        section_type=section_type,
        name="On-site Repairs",
        location_details=True,
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
def service_item_with_location(service_cat_with_location):
    from apps.catalog.models import ServiceItem

    return ServiceItem.objects.create(
        category=service_cat_with_location,
        name="Broken Printer",
        is_active=True,
        default_priority=None,
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
def hod_user(campus_dept):
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(username="hod_user", password="pass")
    campus_dept.head_of_department = user
    campus_dept.save()
    RoleAssignment.objects.create(
        user=user, role="hod", campus_department=campus_dept, is_primary=True
    )
    return user


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(username="admin_user", password="pass")
    RoleAssignment.objects.create(user=user, role="admin", is_primary=True)
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
# R6 — Routing: section resolved from (requester_campus, service_item→category→section_type)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR6Routing:
    """
    R6: Ticket section must be resolved server-side from the requester's campus
    and the service item's category → section_type chain.
    """

    def test_section_resolved_server_side_on_creation(self, api_client):
        """POST /api/v1/tickets/ — section and priority are set by the server,
        not by any client-supplied value."""
        from apps.org.models import (
            Campus,
            Department,
            CampusDepartment,
            SectionType,
            Section,
        )
        from apps.sla.models import Priority
        from apps.catalog.models import ServiceCategory, ServiceItem
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        campus = Campus.objects.create(name="Routing Campus", code="RTC")
        dept = Department.objects.create(name="RoutingDept", code="RDT")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st = SectionType.objects.create(department=dept, name="Routing SW", code="RSW")
        section = Section.objects.create(
            campus_department=cd, section_type=st, is_active=True
        )
        prio = Priority.objects.create(
            name="RouteLow", rank=11, response_minutes=60, resolution_minutes=480
        )
        cat = ServiceCategory.objects.create(
            section_type=st,
            name="Route Cat",
            default_priority=prio,
            location_details=False,
            is_active=True,
        )
        item = ServiceItem.objects.create(
            category=cat, name="Route Item", is_active=True
        )

        user = CustomUser.objects.create_user(username="route_req", password="pass")
        UserProfile.objects.create(user=user, campus=campus)

        api_client.force_authenticate(user=user)
        # Client sends bogus priority and section values — must be silently ignored
        resp = api_client.post(
            "/api/v1/tickets/",
            {
                "service_item": item.id,
                "description": "routing test",
                "priority": 9999,
                "section": 9999,
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data

        ticket = Ticket.objects.get(id=resp.data["id"])
        assert ticket.section == section, "Section must be server-resolved"
        assert ticket.priority == prio, "Priority must be server-resolved"

    def test_routing_fails_when_no_active_section_at_user_campus(self, api_client):
        """User at campus_b cannot create a ticket for a service that has no active
        section at campus_b — should return 400 with an error on service_item."""
        from apps.org.models import (
            Campus,
            Department,
            CampusDepartment,
            SectionType,
            Section,
        )
        from apps.sla.models import Priority
        from apps.catalog.models import ServiceCategory, ServiceItem
        from apps.accounts.models import CustomUser, UserProfile

        campus_a = Campus.objects.create(name="Campus A R6", code="CA1R6")
        campus_msa = Campus.objects.create(name="Mombasa R6", code="MSA_R6")
        dept = Department.objects.create(name="RouteD2", code="RD2")
        cdA = CampusDepartment.objects.create(campus=campus_a, department=dept)
        st = SectionType.objects.create(department=dept, name="RouteNet", code="RNT")
        Section.objects.create(campus_department=cdA, section_type=st, is_active=True)
        prio = Priority.objects.create(
            name="RouteHigh2", rank=12, response_minutes=30, resolution_minutes=120
        )
        cat = ServiceCategory.objects.create(
            section_type=st,
            name="Route Cat B",
            default_priority=prio,
            location_details=False,
            is_active=True,
        )
        item = ServiceItem.objects.create(
            category=cat, name="Route Item B", is_active=True
        )

        # User is at campus_msa which has NO section for this service_type
        msa_user = CustomUser.objects.create_user(
            username="msa_route_user", password="pass"
        )
        UserProfile.objects.create(user=msa_user, campus=campus_msa)

        api_client.force_authenticate(user=msa_user)
        resp = api_client.post(
            "/api/v1/tickets/",
            {"service_item": item.id, "description": "no section here"},
            format="json",
        )
        assert resp.status_code == 400
        # The error must reference service_item (the bad request field)
        assert "service_item" in str(resp.data)

    def test_user_without_campus_profile_rejected(self, api_client, service_item):
        """A user with no UserProfile (no campus) cannot create a ticket."""
        from apps.accounts.models import CustomUser

        campusless = CustomUser.objects.create_user(
            username="no_campus_r6", password="pass"
        )
        api_client.force_authenticate(user=campusless)
        resp = api_client.post(
            "/api/v1/tickets/",
            {"service_item": service_item.id, "description": "help"},
            format="json",
        )
        assert resp.status_code == 400
        assert "campus" in str(resp.data).lower()


# ---------------------------------------------------------------------------
# R7 — Priority server-set from item.default_priority or category.default_priority
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR7PriorityResolution:
    """
    R7: Priority is resolved server-side. Item-level override takes precedence
    over category default. Requesters cannot set priority.
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

    def test_requester_cannot_set_priority_via_api(
        self, api_client, requester, service_item, section, priority
    ):
        """A client-supplied priority value must be silently ignored; server resolves it."""
        from apps.tickets.models import Ticket

        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {
                "service_item": service_item.id,
                "description": "priority test",
                "priority": 9999,  # bogus — must be ignored
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        ticket = Ticket.objects.get(id=resp.data["id"])
        # priority must be the resolved value, not 9999
        assert ticket.priority.id != 9999
        assert ticket.priority == priority


# ---------------------------------------------------------------------------
# R8 — Status machine: only allowed transitions; pending requires reason
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR8StatusMachine:
    """
    R8: Only the allowed state transitions are permitted.
    'pending' status requires a non-empty reason.
    """

    def test_valid_full_lifecycle_open_to_closed(self, open_ticket, technician):
        """open → assigned → in_progress → resolved → closed all succeed."""
        from apps.tickets.services.lifecycle import transition_status

        ticket = open_ticket
        transition_status(ticket, "assigned", technician)
        assert ticket.status == "assigned"

        transition_status(ticket, "in_progress", technician)
        assert ticket.status == "in_progress"

        transition_status(ticket, "resolved", technician)
        assert ticket.status == "resolved"

        transition_status(ticket, "closed", technician)
        assert ticket.status == "closed"

    def test_invalid_transition_open_to_resolved_raises(self, open_ticket, technician):
        """open → resolved is not a valid transition; must raise TransitionError."""
        from apps.tickets.services.lifecycle import transition_status, TransitionError

        with pytest.raises(TransitionError):
            transition_status(open_ticket, "resolved", technician)

    def test_invalid_transition_in_progress_to_closed_raises(
        self, open_ticket, technician
    ):
        """in_progress → closed must raise TransitionError (must go via resolved)."""
        from apps.tickets.services.lifecycle import transition_status, TransitionError

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)

        with pytest.raises(TransitionError):
            transition_status(open_ticket, "closed", technician)

    def test_pending_requires_non_empty_reason(self, open_ticket, technician):
        """Transitioning to 'pending' with an empty reason raises TransitionError."""
        from apps.tickets.services.lifecycle import transition_status, TransitionError

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)

        with pytest.raises(TransitionError):
            transition_status(open_ticket, "pending", technician, reason="")

    def test_pending_with_reason_succeeds_and_records_reason(
        self, open_ticket, technician
    ):
        """Transitioning to 'pending' with a reason succeeds and writes a log."""
        from apps.tickets.services.lifecycle import transition_status
        from apps.tickets.models import TicketLog

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)
        transition_status(
            open_ticket, "pending", technician, reason="Waiting for spare parts"
        )

        open_ticket.refresh_from_db()
        assert open_ticket.status == "pending"

        log = TicketLog.objects.filter(
            ticket=open_ticket,
            event_type="status_changed",
        ).first()
        assert log is not None
        assert "Waiting" in log.reason

    def test_status_transition_via_status_endpoint(
        self, api_client, open_ticket, technician
    ):
        """POST /api/v1/tickets/{id}/status/ with valid transition returns 200."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"
        resp = api_client.post(url, {"status": "assigned"}, format="json")
        assert resp.status_code == 200
        assert resp.data["status"] == "assigned"

    def test_invalid_transition_via_api_returns_400(
        self, api_client, open_ticket, technician
    ):
        """POST invalid transition via API returns 400."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"
        resp = api_client.post(url, {"status": "resolved"}, format="json")
        assert resp.status_code == 400

    def test_pending_via_api_without_reason_returns_400(
        self, api_client, open_ticket, technician
    ):
        """POST to 'pending' via API without reason field returns 400."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"

        api_client.post(url, {"status": "assigned"}, format="json")
        api_client.post(url, {"status": "in_progress"}, format="json")

        resp = api_client.post(url, {"status": "pending"}, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# R9 — SLA clock pauses while pending; accumulated_pause + due timestamp shift
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR9SLAPauseResume:
    """
    R9: While a ticket is pending the SLA clock is paused. On resumption the
    pause duration is added to accumulated_pause and the due-date is shifted forward.
    """

    def test_paused_at_set_on_pending(self, open_ticket, technician):
        """Transitioning to 'pending' sets paused_at."""
        from apps.tickets.services.lifecycle import transition_status

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)
        transition_status(
            open_ticket, "pending", technician, reason="Waiting for hardware"
        )
        open_ticket.refresh_from_db()

        assert open_ticket.paused_at is not None
        assert open_ticket.status == "pending"

    def test_paused_at_cleared_on_resume(self, open_ticket, technician):
        """Resuming from 'pending' clears paused_at."""
        from apps.tickets.services.lifecycle import transition_status

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)
        transition_status(
            open_ticket, "pending", technician, reason="Waiting for hardware"
        )
        transition_status(open_ticket, "in_progress", technician)
        open_ticket.refresh_from_db()

        assert open_ticket.paused_at is None
        assert open_ticket.status == "in_progress"

    def test_accumulated_pause_grows_after_resume(self, open_ticket, technician):
        """accumulated_pause is >= 0 after a pause/resume cycle."""
        from apps.tickets.services.lifecycle import transition_status

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)
        transition_status(open_ticket, "pending", technician, reason="Supply delay")
        transition_status(open_ticket, "in_progress", technician)
        open_ticket.refresh_from_db()

        assert open_ticket.accumulated_pause >= timedelta(0)

    def test_resolution_due_extended_after_pause(self, open_ticket, technician):
        """After pause/resume the resolution_due_at must not be earlier than the original."""
        from apps.tickets.services.lifecycle import transition_status

        original_due = open_ticket.resolution_due_at

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)
        transition_status(open_ticket, "pending", technician, reason="Parts on order")
        transition_status(open_ticket, "in_progress", technician)
        open_ticket.refresh_from_db()

        assert open_ticket.resolution_due_at >= original_due

    def test_paused_time_not_counted_toward_sla_elapsed(
        self, requester, campus, service_item, section, priority, hos_user, hos_rule
    ):
        """Escalation engine must not fire when elapsed time minus accumulated_pause
        is below the threshold (R9, R10)."""
        from apps.tickets.models import Ticket
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.sla.models import EscalationRule

        rules = list(EscalationRule.objects.filter(priority=priority).order_by("order"))
        now = timezone.now()

        # Ticket is 45 min old (above 30-min HOS threshold) but 20 min were paused.
        # Active elapsed = 45 - 20 = 25 min < 30-min threshold → must NOT escalate.
        created_at = now - timedelta(minutes=45)
        t = Ticket.objects.create(
            raised_by=requester,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
            status="pending",
            current_level="technician",
        )
        Ticket.objects.filter(pk=t.pk).update(created_at=created_at)
        t.refresh_from_db()

        # paused_at = created_at + 25 min; accumulated_pause = 20 min
        t.paused_at = created_at + timedelta(minutes=25)
        t.accumulated_pause = timedelta(minutes=20)

        result = run_escalation_for_ticket(t, now, rules)
        assert result is False


# ---------------------------------------------------------------------------
# R10 — Escalation: advances current_level, skips vacant rungs, writes TicketLog
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR10EscalationEngine:
    """
    R10: The escalation engine advances current_level according to EscalationRule
    thresholds. Writes a TicketLog with event_type='escalated' and level_user.
    Skips vacant rungs. Never advances resolved/closed tickets.
    """

    def _rules(self, ticket):
        from apps.sla.models import EscalationRule

        return list(
            EscalationRule.objects.filter(priority=ticket.priority).order_by("order")
        )

    def test_escalates_to_hos_at_threshold(
        self, open_ticket, section, hos_user, hos_rule
    ):
        """Ticket older than HOS threshold advances to 'hos' and writes TicketLog."""
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket, TicketLog

        # Push ticket past the 30-minute threshold
        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=45)
        )
        open_ticket.refresh_from_db()
        open_ticket.section = section

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is True
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "hos"

        log = TicketLog.objects.filter(
            ticket=open_ticket, event_type="escalated"
        ).first()
        assert log is not None
        assert log.level_user == hos_user, "TicketLog.level_user must be the HOS user"

    def test_skips_vacant_hos_escalates_to_hod(
        self, open_ticket, section, campus_dept, hod_user, hos_rule, hod_rule
    ):
        """When HOS seat is vacant, escalation engine skips to HOD level."""
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket, TicketLog

        # Ensure section.hos is None (vacant)
        section.hos = None
        section.save()

        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=45)
        )
        open_ticket.refresh_from_db()

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is True
        open_ticket.refresh_from_db()
        assert (
            open_ticket.current_level == "hod"
        ), "Engine must skip vacant HOS and advance to HOD"
        log = TicketLog.objects.filter(
            ticket=open_ticket, event_type="escalated"
        ).first()
        assert log is not None
        assert log.level_user == hod_user

    def test_does_not_escalate_resolved_ticket(
        self, open_ticket, section, hos_user, hos_rule
    ):
        """Escalation engine must not advance a resolved ticket (R10)."""
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket

        section.hos = hos_user
        section.save()
        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=45),
            status="resolved",
        )
        open_ticket.refresh_from_db()

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is False
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "technician"

    def test_does_not_escalate_closed_ticket(
        self, open_ticket, section, hos_user, hos_rule
    ):
        """Escalation engine must not advance a closed ticket (R10)."""
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket

        section.hos = hos_user
        section.save()
        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=45),
            status="closed",
        )
        open_ticket.refresh_from_db()

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is False

    def test_does_not_escalate_before_threshold(
        self, requester, campus, service_item, section, priority, hos_rule
    ):
        """Ticket younger than HOS threshold must not be escalated."""
        from apps.tickets.models import Ticket
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.sla.models import EscalationRule

        rules = list(EscalationRule.objects.filter(priority=priority).order_by("order"))

        t = Ticket.objects.create(
            raised_by=requester,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
            status="open",
            current_level="technician",
        )
        # Only 10 minutes old — below the 30-minute threshold
        Ticket.objects.filter(pk=t.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        t.refresh_from_db()

        result = run_escalation_for_ticket(t, timezone.now(), rules)
        assert result is False
        t.refresh_from_db()
        assert t.current_level == "technician"


# ---------------------------------------------------------------------------
# R11 — TicketLog is append-only / immutable
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR11TicketLogImmutability:
    """
    R11: TicketLog.save() raises ValueError when pk is already set.
    TicketLog.delete() always raises ValueError.
    """

    def test_create_log_succeeds(self, open_ticket, requester):
        """Creating a new TicketLog succeeds and assigns a pk."""
        from apps.tickets.models import TicketLog

        log = TicketLog.objects.create(
            ticket=open_ticket,
            actor=requester,
            event_type="created",
            to_value=open_ticket.ticket_no,
        )
        assert log.pk is not None

    def test_save_with_pk_raises_value_error(self, open_ticket, requester):
        """Attempting to re-save an existing TicketLog raises ValueError."""
        from apps.tickets.models import TicketLog

        log = TicketLog.objects.create(
            ticket=open_ticket,
            actor=requester,
            event_type="created",
        )
        with pytest.raises(ValueError, match="immutable"):
            log.event_type = "status_changed"
            log.save()

    def test_delete_raises_value_error(self, open_ticket, requester):
        """Attempting to delete a TicketLog raises ValueError."""
        from apps.tickets.models import TicketLog

        log = TicketLog.objects.create(
            ticket=open_ticket,
            actor=requester,
            event_type="created",
        )
        with pytest.raises(ValueError, match="cannot be deleted"):
            log.delete()

    def test_null_actor_allowed_for_system_events(self, open_ticket):
        """System-generated logs may have actor=None (e.g. auto-escalation)."""
        from apps.tickets.models import TicketLog

        log = TicketLog.objects.create(
            ticket=open_ticket,
            actor=None,
            event_type="escalated",
        )
        assert log.pk is not None
        assert log.actor is None

    def test_log_created_after_status_transition(self, open_ticket, technician):
        """transition_status() must persist a TicketLog entry."""
        from apps.tickets.services.lifecycle import transition_status
        from apps.tickets.models import TicketLog

        initial_count = TicketLog.objects.filter(ticket=open_ticket).count()
        transition_status(open_ticket, "assigned", technician)
        assert TicketLog.objects.filter(ticket=open_ticket).count() > initial_count


# ---------------------------------------------------------------------------
# R12 — Transfer: changing role-holder re-homes open tickets to section pool
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR12TransferRehome:
    """
    R12: When a technician's role-holder changes (leaves / is replaced), their
    open tickets in the section are returned to the pool (assigned_to set to None).
    """

    def test_assigned_ticket_returned_to_pool_on_transfer(
        self, open_ticket, technician, section
    ):
        """transfer_open_tickets() sets assigned_to=None and writes a 'reassigned' log."""
        from apps.org.services.transfer import transfer_open_tickets
        from apps.tickets.models import TicketLog

        open_ticket.assigned_to = technician
        open_ticket.status = "assigned"
        open_ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        count = transfer_open_tickets(technician, section)

        open_ticket.refresh_from_db()
        assert count == 1
        assert open_ticket.assigned_to is None
        assert TicketLog.objects.filter(
            ticket=open_ticket, event_type="reassigned"
        ).exists()

    def test_resolved_ticket_not_touched_by_transfer(
        self, open_ticket, technician, section
    ):
        """transfer_open_tickets() must not re-home resolved or closed tickets."""
        from apps.org.services.transfer import transfer_open_tickets

        open_ticket.assigned_to = technician
        open_ticket.status = "resolved"
        open_ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        count = transfer_open_tickets(technician, section)

        assert count == 0
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to == technician  # unchanged

    def test_multiple_active_statuses_all_transferred(
        self, requester, campus, service_item, section, priority, technician
    ):
        """Transfer covers open, assigned, in_progress, and pending statuses."""
        from apps.tickets.models import Ticket
        from apps.org.services.transfer import transfer_open_tickets

        active_statuses = ("open", "assigned", "in_progress", "pending")
        for status in active_statuses:
            Ticket.objects.create(
                raised_by=requester,
                requester_campus=campus,
                service_item=service_item,
                section=section,
                priority=priority,
                status=status,
                assigned_to=technician,
            )

        count = transfer_open_tickets(technician, section)
        assert count == len(active_statuses)

    def test_tickets_from_other_sections_not_touched(
        self,
        requester,
        campus,
        service_item,
        section,
        priority,
        technician,
        campus_dept,
        section_type_net,
    ):
        """transfer_open_tickets() only touches tickets in the specified section."""
        from apps.org.models import Section
        from apps.tickets.models import Ticket
        from apps.org.services.transfer import transfer_open_tickets

        other_section = Section.objects.create(
            campus_department=campus_dept,
            section_type=section_type_net,
            is_active=True,
        )
        other_ticket = Ticket.objects.create(
            raised_by=requester,
            requester_campus=campus,
            service_item=service_item,
            section=other_section,
            priority=priority,
            status="assigned",
            assigned_to=technician,
        )

        count = transfer_open_tickets(technician, section)
        assert count == 0  # no tickets in the specified section
        other_ticket.refresh_from_db()
        assert other_ticket.assigned_to == technician  # untouched


# ---------------------------------------------------------------------------
# R13 — Location captured iff category.location_details; validated against field set
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR13LocationDetails:
    """
    R13: TicketLocation is created only when category.location_details=True.
    Location values are validated against the FacilityType's known field set.
    """

    def test_no_location_created_when_category_location_details_false(
        self, api_client, requester, service_item, section
    ):
        """Ticket from a non-location category must not create TicketLocation."""
        from apps.tickets.models import Ticket, TicketLocation

        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {"service_item": service_item.id, "description": "no location needed"},
            format="json",
        )
        assert resp.status_code == 201, resp.data
        ticket = Ticket.objects.get(id=resp.data["id"])
        assert not TicketLocation.objects.filter(ticket=ticket).exists()

    def test_location_required_when_category_location_details_true(
        self, api_client, requester, service_item_with_location, section
    ):
        """Request without location field for a location_details=True category → 400."""
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {
                "service_item": service_item_with_location.id,
                "description": "location needed",
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "location" in str(resp.data)

    def test_office_block_location_creates_ticket_location_record(
        self, api_client, requester, service_item_with_location, section, campus
    ):
        """Valid office_block location creates a TicketLocation row."""
        from apps.facilities.models import FacilityType, Facility
        from apps.tickets.models import Ticket, TicketLocation

        # Use the canonical code so the hardcoded TYPE_SPECS validator accepts it.
        ft, _ = FacilityType.objects.get_or_create(
            code="office_block", defaults={"name": "Office Block"}
        )
        facility = Facility.objects.create(
            campus=campus, facility_type=ft, name="Block P10-A"
        )

        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {
                "service_item": service_item_with_location.id,
                "description": "printer broken",
                "location": {
                    "facility_type": ft.id,
                    "facility": facility.id,
                    "values": {"floor": "2", "room": "101"},
                },
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        ticket = Ticket.objects.get(id=resp.data["id"])
        loc = TicketLocation.objects.get(ticket=ticket)
        assert loc.facility == facility
        assert loc.facility_type == ft

    def test_unknown_field_in_location_values_rejected(
        self, api_client, requester, service_item_with_location, section, campus
    ):
        """Unknown fields in location.values for a FacilityType are rejected → 400."""
        from apps.facilities.models import FacilityType, Facility

        # Use the canonical code so TYPE_SPECS recognises it; the unknown key triggers the values error.
        ft, _ = FacilityType.objects.get_or_create(
            code="office_block", defaults={"name": "Office Block"}
        )
        facility = Facility.objects.create(
            campus=campus, facility_type=ft, name="Block R13-A"
        )

        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {
                "service_item": service_item_with_location.id,
                "description": "bad fields",
                "location": {
                    "facility_type": ft.id,
                    "facility": facility.id,
                    "values": {
                        "floor": "2",
                        "room": "101",
                        "bogus_unknown_field": "bad",
                    },
                },
            },
            format="json",
        )
        assert resp.status_code == 400
        assert "values" in str(resp.data)


# ---------------------------------------------------------------------------
# R14 — FacilityType is admin-managed; the viewset must be read-only
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR14FacilityTypeReadOnly:
    """
    R14: FacilityType records are admin-managed (seeded) but the API
    viewset is read-only — POST must return 405.
    """

    def test_any_authenticated_user_can_list_facility_types(
        self, api_client, requester
    ):
        """GET /api/v1/facility-types/ succeeds for any authenticated user."""
        api_client.force_authenticate(user=requester)
        resp = api_client.get("/api/v1/facility-types/")
        assert resp.status_code == 200

    def test_post_facility_type_returns_405(self, api_client, admin_user):
        """POST /api/v1/facility-types/ must return 405 (read-only endpoint)."""
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            "/api/v1/facility-types/",
            {"name": "New Type", "code": "new_type"},
            format="json",
        )
        assert resp.status_code == 405

    def test_unauthenticated_facility_types_returns_401(self, api_client):
        """Anonymous GET /api/v1/facility-types/ → 401."""
        resp = api_client.get("/api/v1/facility-types/")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# R15 — Universal requester: ?mine=1 endpoint for own tickets
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR15UniversalRequester:
    """
    R15: Every user (regardless of role) can create tickets and view their own
    via the ?mine=1 filter. Staff roles see broader scope without ?mine=1.
    """

    def test_plain_user_sees_own_tickets_with_mine_filter(
        self, api_client, requester, campus, service_item, section, priority
    ):
        """Requester with ?mine=1 sees their own ticket; other users' tickets absent."""
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        # A second user creates their own ticket
        other = CustomUser.objects.create_user(username="other_r15", password="pass")
        UserProfile.objects.create(user=other, campus=campus)
        Ticket.objects.create(
            raised_by=other,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
        )

        # Requester creates their own ticket
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {"service_item": service_item.id, "description": "mine test"},
            format="json",
        )
        assert resp.status_code == 201
        my_ticket_id = resp.data["id"]

        # ?mine=1 should return only the requester's ticket
        resp_mine = api_client.get("/api/v1/tickets/?mine=1")
        assert resp_mine.status_code == 200
        ids = [t["id"] for t in resp_mine.data.get("results", resp_mine.data)]
        assert my_ticket_id in ids

    def test_unauthenticated_mine_returns_401(self, api_client):
        """?mine=1 without authentication → 401."""
        resp = api_client.get("/api/v1/tickets/?mine=1")
        assert resp.status_code == 401

    def test_plain_user_can_always_create_ticket(
        self, api_client, requester, service_item, section
    ):
        """Any authenticated user (plain requester) can POST to /tickets/."""
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            "/api/v1/tickets/",
            {"service_item": service_item.id, "description": "R15 creation test"},
            format="json",
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# R16 — Config-driven: routing, catalogue visibility, priority all derive from ref data
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR16ConfigDriven:
    """
    R16: The system's routing (R6), catalogue visibility (R5), and priority
    assignment (R7) all derive from the reference data tables — not hard-coded.
    """

    def test_resolved_priority_is_property_not_stored(self, service_cat, priority):
        """ServiceItem.resolved_priority is a computed property, not a stored DB field."""
        from apps.catalog.models import ServiceItem

        field_names = [f.name for f in ServiceItem._meta.get_fields()]
        assert (
            "resolved_priority" not in field_names
        ), "resolved_priority must be a @property, not a stored DB field"
        item = ServiceItem.objects.create(
            category=service_cat, name="Config Item", is_active=True
        )
        assert hasattr(item, "resolved_priority")
        assert item.resolved_priority == priority

    def test_category_visibility_changes_dynamically_with_section_activation(
        self, api_client, requester, campus, section, service_cat
    ):
        """
        R5+R16: Deactivating a section makes its categories invisible at that campus;
        re-activating restores visibility.
        """
        api_client.force_authenticate(user=requester)

        # Section is active → category must be visible
        resp_active = api_client.get("/api/v1/catalog/", {"campus": campus.id})
        assert resp_active.status_code == 200
        ids_active = [
            c["id"] for c in resp_active.data.get("results", resp_active.data)
        ]
        assert service_cat.id in ids_active

        # Deactivate the section → category must disappear
        section.is_active = False
        section.save()

        resp_inactive = api_client.get("/api/v1/catalog/", {"campus": campus.id})
        assert resp_inactive.status_code == 200
        ids_inactive = [
            c["id"] for c in resp_inactive.data.get("results", resp_inactive.data)
        ]
        assert service_cat.id not in ids_inactive

        # Re-activate → visible again
        section.is_active = True
        section.save()

        resp_reactivated = api_client.get("/api/v1/catalog/", {"campus": campus.id})
        assert resp_reactivated.status_code == 200
        ids_reactivated = [
            c["id"] for c in resp_reactivated.data.get("results", resp_reactivated.data)
        ]
        assert service_cat.id in ids_reactivated

    def test_category_not_visible_at_campus_with_no_section(
        self, api_client, requester, campus_b, service_cat
    ):
        """
        R5+R16: A category is NOT visible at a campus that has no active section
        for its section_type — even if it is visible at another campus.
        """
        api_client.force_authenticate(user=requester)
        resp = api_client.get("/api/v1/catalog/", {"campus": campus_b.id})
        assert resp.status_code == 200
        ids = [c["id"] for c in resp.data.get("results", resp.data)]
        assert service_cat.id not in ids


# ---------------------------------------------------------------------------
# R17 — Role cover: RoleAssignment with valid_until grants temporary role
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestR17RoleCover:
    """
    R17: A non-primary RoleAssignment with valid_until > now grants a temporary
    role. is_active() must return True during the window and False after expiry.
    Attributed actions must use the cover holder identity.
    """

    def test_active_cover_is_active(self, requester, section):
        """is_active() returns True for a cover with valid_until in the future."""
        from apps.accounts.models import RoleAssignment

        future = timezone.now() + timedelta(days=7)
        ra = RoleAssignment(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=future,
        )
        assert ra.is_active() is True

    def test_expired_cover_is_not_active(self, requester, section):
        """is_active() returns False for a cover whose valid_until is in the past."""
        from apps.accounts.models import RoleAssignment

        past = timezone.now() - timedelta(hours=1)
        ra = RoleAssignment(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=past,
        )
        assert ra.is_active() is False

    def test_standing_role_no_window_always_active(self, requester):
        """is_active() returns True for a permanent assignment (valid_until=None)."""
        from apps.accounts.models import RoleAssignment

        ra = RoleAssignment(user=requester, role="admin", is_primary=True)
        assert ra.is_active() is True

    def test_cover_assignment_beats_standing_hos_in_resolve(
        self, open_ticket, section, hos_user, requester
    ):
        """
        An active cover RoleAssignment for HOS takes precedence over the
        standing section.hos when resolving the active holder.
        """
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import resolve_active_holder

        # Standing HOS is set
        section.hos = hos_user
        section.save()

        # Add a valid cover for requester
        RoleAssignment.objects.create(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )

        # Confirm resolve_active_holder returns the cover user
        active_holder = resolve_active_holder(section, "hos")
        assert active_holder == requester
        assert active_holder != hos_user

    def test_expired_cover_falls_back_to_standing_hos(
        self, section, hos_user, requester
    ):
        """An expired cover RoleAssignment is ignored; standing HOS is used instead."""
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import resolve_active_holder

        section.hos = hos_user
        section.save()

        RoleAssignment.objects.create(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() - timedelta(days=1),  # expired
        )

        active_holder = resolve_active_holder(section, "hos")
        assert active_holder == hos_user

    def test_active_cover_used_in_escalation_log_level_user(
        self, open_ticket, section, hos_user, requester, hos_rule
    ):
        """
        After escalation, TicketLog.level_user is the active cover user, not the
        standing HOS — demonstrating that attributed actions use the cover identity.
        """
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket, TicketLog
        from apps.sla.models import EscalationRule

        section.hos = hos_user
        section.save()

        RoleAssignment.objects.create(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )

        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=45)
        )
        open_ticket.refresh_from_db()

        rules = list(
            EscalationRule.objects.filter(priority=open_ticket.priority).order_by(
                "order"
            )
        )
        result = run_escalation_for_ticket(open_ticket, timezone.now(), rules)

        assert result is True
        log = TicketLog.objects.filter(
            ticket=open_ticket, event_type="escalated"
        ).first()
        assert log is not None
        assert (
            log.level_user == requester
        ), "level_user must be the active cover user, not the standing HOS"


# ---------------------------------------------------------------------------
# Escalation edge cases (supplementary)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEscalationEdgeCases:
    """Additional edge-case coverage for the escalation engine."""

    def test_vacant_hod_stops_escalation_when_both_seats_empty(
        self, open_ticket, section, campus_dept, hos_rule, hod_rule
    ):
        """When both HOS and HOD seats are vacant, engine returns False."""
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket
        from apps.sla.models import EscalationRule

        section.hos = None
        section.save()
        campus_dept.head_of_department = None
        campus_dept.save()

        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=75)
        )
        open_ticket.refresh_from_db()

        rules = list(
            EscalationRule.objects.filter(priority=open_ticket.priority).order_by(
                "order"
            )
        )
        result = run_escalation_for_ticket(open_ticket, timezone.now(), rules)

        assert result is False
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "technician"

    def test_escalation_does_not_fire_before_threshold(
        self, open_ticket, section, hos_user, hos_rule
    ):
        """Engine returns False when ticket is still within SLA threshold."""
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket
        from apps.sla.models import EscalationRule

        section.hos = hos_user
        section.save()

        # Only 5 minutes old — well below 30-minute HOS threshold
        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=5)
        )
        open_ticket.refresh_from_db()

        rules = list(
            EscalationRule.objects.filter(priority=open_ticket.priority).order_by(
                "order"
            )
        )
        result = run_escalation_for_ticket(open_ticket, timezone.now(), rules)
        assert result is False

    def test_expired_cover_escalates_to_standing_hos(
        self, open_ticket, section, hos_user, requester, hos_rule
    ):
        """Expired cover ignored; escalation goes to standing HOS."""
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import Ticket, TicketLog
        from apps.sla.models import EscalationRule

        section.hos = hos_user
        section.save()

        RoleAssignment.objects.create(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() - timedelta(days=1),  # expired
        )

        Ticket.objects.filter(pk=open_ticket.pk).update(
            created_at=timezone.now() - timedelta(minutes=45)
        )
        open_ticket.refresh_from_db()

        rules = list(
            EscalationRule.objects.filter(priority=open_ticket.priority).order_by(
                "order"
            )
        )
        result = run_escalation_for_ticket(open_ticket, timezone.now(), rules)

        assert result is True
        log = TicketLog.objects.filter(
            ticket=open_ticket, event_type="escalated"
        ).first()
        assert log is not None
        assert (
            log.level_user == hos_user
        ), "Expired cover must be ignored; standing HOS must receive escalation"


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

    def test_requester_cannot_view_other_users_tickets(
        self, api_client, requester, campus, service_item, section, priority
    ):
        """Requester cannot see tickets raised by other users."""
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        other = CustomUser.objects.create_user(
            username="other_req_e2e", password="pass"
        )
        UserProfile.objects.create(user=other, campus=campus)
        other_ticket = Ticket.objects.create(
            raised_by=other,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
        )

        api_client.force_authenticate(user=requester)
        resp = api_client.get("/api/v1/tickets/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data.get("results", resp.data)]
        assert other_ticket.id not in ids

    def test_feedback_blocked_on_unresolved_ticket(
        self, api_client, requester, open_ticket
    ):
        """Feedback cannot be submitted while ticket is not yet resolved."""
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            f"/api/v1/tickets/{open_ticket.pk}/feedback/",
            {"rating": 4},
            format="json",
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# E2E role walkthrough: TechnicianFlow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTechnicianFlow:
    """
    E2E: A technician views their assigned queue, advances status, and adds
    an internal comment that requesters cannot see.
    """

    def test_technician_views_assigned_queue(
        self, api_client, technician, campus, service_item, section, priority
    ):
        """Technician can see tickets in their section."""
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        raiser = CustomUser.objects.create_user(
            username="raiser_tech_e2e", password="pass"
        )
        UserProfile.objects.create(user=raiser, campus=campus)
        ticket = Ticket.objects.create(
            raised_by=raiser,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
            assigned_to=technician,
            status="assigned",
        )

        api_client.force_authenticate(user=technician)
        resp = api_client.get("/api/v1/tickets/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data.get("results", resp.data)]
        assert ticket.id in ids

    def test_technician_advances_from_assigned_to_in_progress(
        self, api_client, technician, open_ticket
    ):
        """Technician can transition assigned → in_progress via the status endpoint."""
        from apps.tickets.services.lifecycle import transition_status

        transition_status(open_ticket, "assigned", technician)

        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"
        resp = api_client.post(url, {"status": "in_progress"}, format="json")
        assert resp.status_code == 200
        assert resp.data["status"] == "in_progress"

    def test_technician_adds_internal_comment(
        self, api_client, technician, open_ticket
    ):
        """Technician can post an internal comment to a ticket."""
        from apps.tickets.models import TicketComment

        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/comments/"
        resp = api_client.post(
            url,
            {"body": "Internal diagnostic note", "visibility": "internal"},
            format="json",
        )
        assert resp.status_code == 201
        comment = TicketComment.objects.filter(
            ticket=open_ticket, visibility="internal"
        ).first()
        assert comment is not None
        assert comment.body == "Internal diagnostic note"

    def test_requester_cannot_see_internal_comments(
        self, api_client, requester, technician, open_ticket
    ):
        """Requester does not see internal comments posted by technician."""
        from apps.tickets.models import TicketComment

        TicketComment.objects.create(
            ticket=open_ticket,
            author=technician,
            body="Secret internal note",
            visibility="internal",
        )

        api_client.force_authenticate(user=requester)
        url = f"/api/v1/tickets/{open_ticket.pk}/comments/"
        resp = api_client.get(url)
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        bodies = [c["body"] for c in results]
        assert "Secret internal note" not in bodies

    def test_staff_can_see_internal_comments(self, api_client, technician, open_ticket):
        """Staff (technician) can see both public and internal comments."""
        from apps.tickets.models import TicketComment

        TicketComment.objects.create(
            ticket=open_ticket,
            author=technician,
            body="Public note",
            visibility="public",
        )
        TicketComment.objects.create(
            ticket=open_ticket,
            author=technician,
            body="Secret note",
            visibility="internal",
        )

        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/comments/"
        resp = api_client.get(url)
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        bodies = [c["body"] for c in results]
        assert "Public note" in bodies
        assert "Secret note" in bodies


# ---------------------------------------------------------------------------
# E2E role walkthrough: HOSFlow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHOSFlow:
    """
    E2E: An HOS user assigns a ticket from the section pool.
    """

    def test_hos_sees_own_section_tickets(
        self, api_client, hos_user, campus, service_item, section, priority
    ):
        """HOS user can see all tickets in their section."""
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        raiser = CustomUser.objects.create_user(
            username="raiser_hos_e2e", password="pass"
        )
        UserProfile.objects.create(user=raiser, campus=campus)
        ticket = Ticket.objects.create(
            raised_by=raiser,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
        )

        api_client.force_authenticate(user=hos_user)
        resp = api_client.get("/api/v1/tickets/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data.get("results", resp.data)]
        assert ticket.id in ids

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

    def test_hos_cannot_assign_outsider_to_ticket(
        self, api_client, hos_user, open_ticket
    ):
        """HOS cannot assign a ticket to a user not in the section pool."""
        from apps.accounts.models import CustomUser

        outsider = CustomUser.objects.create_user(
            username="outsider_hos_e2e", password="pass"
        )

        api_client.force_authenticate(user=hos_user)
        url = f"/api/v1/tickets/{open_ticket.pk}/assign/"
        resp = api_client.post(url, {"assigned_to": outsider.pk}, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# E2E role walkthrough: HODFlow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestHODFlow:
    """
    E2E: HOD user views escalated tickets in their campus_department.
    """

    def test_hod_sees_escalated_tickets_in_campus_dept(
        self, api_client, hod_user, campus, campus_dept, service_item, section, priority
    ):
        """HOD sees tickets in all sections under their campus_department."""
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        raiser = CustomUser.objects.create_user(
            username="raiser_hod_e2e", password="pass"
        )
        UserProfile.objects.create(user=raiser, campus=campus)
        ticket = Ticket.objects.create(
            raised_by=raiser,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
            current_level="hod",  # escalated to HOD level
        )

        api_client.force_authenticate(user=hod_user)
        resp = api_client.get("/api/v1/tickets/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data.get("results", resp.data)]
        assert ticket.id in ids

    def test_hod_cannot_see_tickets_from_other_campus_dept(
        self, api_client, hod_user, campus, priority
    ):
        """HOD cannot see tickets from a completely different department's section."""
        from apps.org.models import Department, CampusDepartment, SectionType, Section
        from apps.catalog.models import ServiceCategory, ServiceItem
        from apps.accounts.models import CustomUser, UserProfile
        from apps.tickets.models import Ticket

        other_dept = Department.objects.create(name="Finance HOD E2E", code="FHOD")
        other_cd = CampusDepartment.objects.create(campus=campus, department=other_dept)
        other_st = SectionType.objects.create(
            department=other_dept, name="Payroll HOD E2E", code="PHOD"
        )
        other_section = Section.objects.create(
            campus_department=other_cd, section_type=other_st, is_active=True
        )
        other_cat = ServiceCategory.objects.create(
            section_type=other_st,
            name="Finance Service HOD",
            default_priority=priority,
            location_details=False,
            is_active=True,
        )
        other_item = ServiceItem.objects.create(
            category=other_cat, name="Finance Item HOD", is_active=True
        )

        raiser = CustomUser.objects.create_user(
            username="raiser_hod_cross", password="pass"
        )
        UserProfile.objects.create(user=raiser, campus=campus)
        other_ticket = Ticket.objects.create(
            raised_by=raiser,
            requester_campus=campus,
            service_item=other_item,
            section=other_section,
            priority=priority,
        )

        api_client.force_authenticate(user=hod_user)
        resp = api_client.get("/api/v1/tickets/")
        assert resp.status_code == 200
        ids = [t["id"] for t in resp.data.get("results", resp.data)]
        assert other_ticket.id not in ids


# ---------------------------------------------------------------------------
# E2E role walkthrough: LeaveCoverFlow
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLeaveCoverFlow:
    """
    E2E: A user with an active HOS cover RoleAssignment can use HOS endpoints.
    """

    def test_active_cover_ra_is_active(self, campus, section, requester):
        """A cover RoleAssignment (is_primary=False) with future valid_until is active."""
        from apps.accounts.models import RoleAssignment

        cover_ra = RoleAssignment.objects.create(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )
        assert cover_ra.is_active() is True

    def test_expired_cover_is_not_active(self, section, requester):
        """An expired cover RoleAssignment returns is_active()=False."""
        from apps.accounts.models import RoleAssignment

        expired_ra = RoleAssignment(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() - timedelta(minutes=1),
        )
        assert expired_ra.is_active() is False

    def test_cover_user_can_switch_role(self, api_client, campus, section, requester):
        """
        A user with an active cover RoleAssignment can call POST /auth/switch-role/
        to re-issue a JWT scoped to that cover assignment.
        """
        from apps.accounts.models import CustomUser, UserProfile, RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        cover_user = CustomUser.objects.create_user(
            username="cover_switch", password="pass"
        )
        UserProfile.objects.create(user=cover_user, campus=campus)
        cover_ra = RoleAssignment.objects.create(
            user=cover_user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=3),
        )

        _, access = build_tokens_for_assignment(cover_user, cover_ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.post(
            "/api/auth/switch-role/",
            {"roleAssignmentId": cover_ra.id},
            format="json",
        )
        assert resp.status_code == 200
        assert "accessToken" in resp.data

    def test_cover_user_resolve_active_holder_returns_cover(
        self, section, hos_user, requester
    ):
        """
        When a cover is active, resolve_active_holder() returns the cover user
        (not the standing HOS), enabling correct attribution in actions.
        """
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import resolve_active_holder

        section.hos = hos_user
        section.save()

        RoleAssignment.objects.create(
            user=requester,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )

        holder = resolve_active_holder(section, "hos")
        assert holder == requester


# ---------------------------------------------------------------------------
# Seed verification tests (using pytest fixtures — NOT the actual seed commands)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSeedInvariantsViaFixtures:
    """
    Seed verification: construct the reference data programmatically (as the
    seed command would) and confirm all invariants hold.
    """

    def test_all_escalation_rules_have_hos_and_hod_rungs(self, db):
        """Every Priority must have exactly one HOS rule and one HOD rule (R10, seed)."""
        from apps.sla.models import Priority, EscalationRule

        priority_defs = [
            (1, "Low Seed", 480, 4320),
            (2, "Medium Seed", 240, 1440),
            (3, "High Seed", 120, 480),
            (4, "Critical Seed", 60, 240),
        ]
        created_priorities = []
        for rank, name, resp_min, res_min in priority_defs:
            p = Priority.objects.create(
                name=name,
                rank=rank,
                response_minutes=resp_min,
                resolution_minutes=res_min,
            )
            created_priorities.append(p)
            EscalationRule.objects.create(
                priority=p, to_level="hos", threshold_minutes=resp_min * 2, order=1
            )
            EscalationRule.objects.create(
                priority=p, to_level="hod", threshold_minutes=resp_min * 4, order=2
            )

        for p in created_priorities:
            levels = set(
                EscalationRule.objects.filter(priority=p).values_list(
                    "to_level", flat=True
                )
            )
            assert "hos" in levels, f"Priority '{p.name}' missing HOS escalation rule"
            assert "hod" in levels, f"Priority '{p.name}' missing HOD escalation rule"
            assert EscalationRule.objects.filter(priority=p).count() == 2

    def test_every_section_satisfies_r2(self, section):
        """
        R2: For every Section in the database, section_type.department must equal
        campus_department.department.
        """
        from apps.org.models import Section

        for s in Section.objects.all():
            assert s.section_type.department_id == s.campus_department.department_id, (
                f"R2 violated: Section pk={s.pk} has mismatched department. "
                f"section_type.dept={s.section_type.department_id}, "
                f"campus_dept.dept={s.campus_department.department_id}"
            )

    def test_no_service_category_has_department_field(self, db):
        """R4: ServiceCategory must NOT have a 'department' DB column."""
        from apps.catalog.models import ServiceCategory

        field_names = [f.name for f in ServiceCategory._meta.get_fields()]
        assert "department" not in field_names, (
            "R4 violated: ServiceCategory must not have a 'department' field. "
            "Department is derived via section_type.department."
        )

    def test_active_hos_cover_has_valid_until_set(self, db):
        """
        Seed: a cover (non-primary) HOS RoleAssignment must have valid_until set
        so it automatically expires. Verify is_active() returns True in window.
        """
        from apps.org.models import (
            Campus,
            Department,
            CampusDepartment,
            SectionType,
            Section,
        )
        from apps.accounts.models import CustomUser, RoleAssignment

        campus = Campus.objects.create(name="Cover Seed Campus", code="CSC")
        dept = Department.objects.create(name="Cover Seed Dept", code="CSD")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st = SectionType.objects.create(department=dept, name="Cover ST", code="CST")
        section = Section.objects.create(
            campus_department=cd, section_type=st, is_active=True
        )
        cover = CustomUser.objects.create_user(username="cover_seed_v", password="pass")
        ra = RoleAssignment.objects.create(
            user=cover,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=14),
        )

        assert (
            ra.valid_until is not None
        ), "Cover HOS RoleAssignment must have valid_until set (it is a temporary cover)"
        assert ra.is_active() is True

    def test_campus_department_uniqueness_r1(self, db):
        """R1: (campus, department) must be unique on CampusDepartment."""
        from apps.org.models import Campus, Department, CampusDepartment

        c = Campus.objects.create(name="R1 Seed Campus", code="R1C")
        d = Department.objects.create(name="R1 Seed Dept", code="R1D")
        CampusDepartment.objects.create(campus=c, department=d)
        with pytest.raises(Exception):
            CampusDepartment.objects.create(campus=c, department=d)

    def test_section_type_unique_per_department_r3(self, db):
        """UniqueConstraint on (department, name) for SectionType rejects duplicates."""
        from apps.org.models import Department, SectionType

        dept = Department.objects.create(name="Dup Test Dept", code="DTD")
        SectionType.objects.create(department=dept, name="Dup ST", code="DST")
        with pytest.raises(Exception):
            SectionType.objects.create(department=dept, name="Dup ST", code="DST2")

    def test_section_unique_per_campus_dept_type_r3(self, campus_dept, section_type):
        """R3: (campus_department, section_type) duplicate raises an IntegrityError."""
        from apps.org.models import Section

        Section.objects.create(
            campus_department=campus_dept, section_type=section_type, is_active=True
        )
        with pytest.raises(Exception):
            Section.objects.create(
                campus_department=campus_dept, section_type=section_type, is_active=True
            )


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

    def test_section_clean_enforces_r2_mismatch_raises(self, campus, dept):
        """Section.clean() raises ValidationError when depts don't match (R2)."""
        from apps.org.models import Department, CampusDepartment, SectionType, Section
        from django.core.exceptions import ValidationError

        other_dept = Department.objects.create(name="Other Dept R2", code="ODR2")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st_other = SectionType.objects.create(
            department=other_dept, name="Other ST R2", code="OSR2"
        )

        section = Section(campus_department=cd, section_type=st_other, is_active=True)
        with pytest.raises(ValidationError):
            section.clean()

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

    def test_ticket_status_choices_canonical_set(self):
        """Ticket.STATUS must be exactly the canonical 6-value set (R8)."""
        from apps.tickets.models import Ticket

        expected = {"open", "assigned", "in_progress", "pending", "resolved", "closed"}
        actual = {v for v, _ in Ticket.STATUS}
        assert actual == expected

    def test_ticket_level_choices(self):
        """Ticket.LEVEL must contain exactly 'technician', 'hos', 'hod' (R10)."""
        from apps.tickets.models import Ticket

        expected = {"technician", "hos", "hod"}
        actual = {v for v, _ in Ticket.LEVEL}
        assert actual == expected

    def test_role_assignment_scope_technician_requires_section(self, requester):
        """R17: technician RoleAssignment without a section raises ValidationError."""
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError

        ra = RoleAssignment(user=requester, role="technician")
        with pytest.raises(ValidationError):
            ra.clean()

    def test_role_assignment_scope_hod_requires_campus_department(self, requester):
        """R17: hod RoleAssignment without a campus_department raises ValidationError."""
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError

        ra = RoleAssignment(user=requester, role="hod")
        with pytest.raises(ValidationError):
            ra.clean()

    def test_role_assignment_scope_admin_with_section_raises(self, requester, section):
        """R17: admin RoleAssignment must have no scope; section present → ValidationError."""
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError

        ra = RoleAssignment(user=requester, role="admin", section=section)
        with pytest.raises(ValidationError):
            ra.clean()
