"""Phase 5 tests: escalation engine, resolve_active_holder, and transfer handler."""

import pytest
from datetime import timedelta
from django.utils import timezone

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def campus(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Nairobi", code="NRB")


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
        campus_department=campus_dept,
        section_type=section_type,
        hos=None,
    )


@pytest.fixture
def priority(db):
    from apps.sla.models import Priority

    return Priority.objects.create(
        name="Low",
        rank=1,
        response_minutes=60,
        resolution_minutes=120,
    )


@pytest.fixture
def hos_rule(priority):
    from apps.sla.models import EscalationRule

    return EscalationRule.objects.create(
        priority=priority,
        to_level="hos",
        threshold_minutes=30,
        order=1,
    )


@pytest.fixture
def hod_rule(priority, hos_rule):
    from apps.sla.models import EscalationRule

    return EscalationRule.objects.create(
        priority=priority,
        to_level="hod",
        threshold_minutes=60,
        order=2,
    )


@pytest.fixture
def service_cat(section_type, priority):
    from apps.catalog.models import ServiceCategory

    return ServiceCategory.objects.create(
        section_type=section_type,
        name="General IT",
        location_details=False,
        default_priority=priority,
    )


@pytest.fixture
def service_item(service_cat):
    from apps.catalog.models import ServiceItem

    return ServiceItem.objects.create(
        category=service_cat,
        name="Password Reset",
    )


@pytest.fixture
def requester(campus):
    from apps.accounts.models import CustomUser, UserProfile

    user = CustomUser.objects.create_user(username="requester", password="pass")
    UserProfile.objects.create(user=user, campus=campus)
    return user


@pytest.fixture
def technician(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create_user(username="technician", password="pass")


@pytest.fixture
def hos_user(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create_user(username="hos_user", password="pass")


@pytest.fixture
def hod_user(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create_user(username="hod_user", password="pass")


@pytest.fixture
def cover_user(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create_user(username="cover_user", password="pass")


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
    )
    # Push created_at far enough back to exceed the 30-minute HOS threshold.
    Ticket.objects.filter(pk=t.pk).update(
        created_at=timezone.now() - timedelta(minutes=45)
    )
    t.refresh_from_db()
    return t


# ---------------------------------------------------------------------------
# TestResolveActiveHolder
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestResolveActiveHolder:

    def test_returns_standing_hos_when_no_cover(self, section, hos_user):
        from apps.sla.services.escalation import resolve_active_holder

        section.hos = hos_user
        section.save()
        section.refresh_from_db()

        result = resolve_active_holder(section, "hos")

        assert result == hos_user

    def test_returns_none_when_hos_vacant(self, section):
        from apps.sla.services.escalation import resolve_active_holder

        # section.hos is already None from the fixture.
        result = resolve_active_holder(section, "hos")

        assert result is None

    def test_cover_assignment_wins_over_standing_hos(
        self, section, hos_user, cover_user
    ):
        from apps.sla.services.escalation import resolve_active_holder
        from apps.accounts.models import RoleAssignment

        section.hos = hos_user
        section.save()

        RoleAssignment.objects.create(
            user=cover_user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )

        result = resolve_active_holder(section, "hos")

        assert result == cover_user

    def test_expired_cover_falls_back_to_standing_hos(
        self, section, hos_user, cover_user
    ):
        from apps.sla.services.escalation import resolve_active_holder
        from apps.accounts.models import RoleAssignment

        section.hos = hos_user
        section.save()

        RoleAssignment.objects.create(
            user=cover_user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() - timedelta(days=1),
        )

        result = resolve_active_holder(section, "hos")

        assert result == hos_user

    def test_returns_standing_hod_when_no_cover(self, section, campus_dept, hod_user):
        from apps.sla.services.escalation import resolve_active_holder

        campus_dept.head_of_department = hod_user
        campus_dept.save()
        section.refresh_from_db()

        result = resolve_active_holder(section, "hod")

        assert result == hod_user

    def test_hod_cover_wins(self, section, campus_dept, hod_user, cover_user):
        from apps.sla.services.escalation import resolve_active_holder
        from apps.accounts.models import RoleAssignment

        campus_dept.head_of_department = hod_user
        campus_dept.save()

        RoleAssignment.objects.create(
            user=cover_user,
            role="hod",
            campus_department=campus_dept,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )
        section.refresh_from_db()

        result = resolve_active_holder(section, "hod")

        assert result == cover_user


# ---------------------------------------------------------------------------
# TestEscalationEngine
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEscalationEngine:

    def _rules(self, ticket):
        from apps.sla.models import EscalationRule

        return list(
            EscalationRule.objects.filter(priority=ticket.priority).order_by("order")
        )

    def test_no_escalation_before_threshold(
        self, requester, campus, service_item, section, priority, hos_rule
    ):
        from apps.tickets.models import Ticket
        from apps.sla.services.escalation import run_escalation_for_ticket

        t = Ticket.objects.create(
            raised_by=requester,
            requester_campus=campus,
            service_item=service_item,
            section=section,
            priority=priority,
            status="open",
            current_level="technician",
        )
        # Only 10 minutes old — below the 30-minute threshold.
        Ticket.objects.filter(pk=t.pk).update(
            created_at=timezone.now() - timedelta(minutes=10)
        )
        t.refresh_from_db()

        result = run_escalation_for_ticket(t, timezone.now(), self._rules(t))

        assert result is False
        t.refresh_from_db()
        assert t.current_level == "technician"

    def test_escalates_to_hos_at_threshold(
        self, open_ticket, section, hos_user, hos_rule
    ):
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import TicketLog

        section.hos = hos_user
        section.save()
        open_ticket.section = section
        open_ticket.refresh_from_db()

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
        assert log.level_user == hos_user

    def test_never_escalates_resolved_ticket(
        self, open_ticket, section, hos_user, hos_rule, hod_rule
    ):
        from apps.sla.services.escalation import run_escalation_for_ticket

        section.hos = hos_user
        section.save()
        open_ticket.status = "resolved"
        open_ticket.save(update_fields=["status", "updated_at"])

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is False
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "technician"

    def test_never_escalates_closed_ticket(
        self, open_ticket, section, hos_user, hos_rule, hod_rule
    ):
        from apps.sla.services.escalation import run_escalation_for_ticket

        section.hos = hos_user
        section.save()
        open_ticket.status = "closed"
        open_ticket.save(update_fields=["status", "updated_at"])

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is False
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "technician"

    def test_skips_vacant_hos_escalates_to_hod(
        self, open_ticket, section, campus_dept, hod_user, hos_rule, hod_rule
    ):
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import TicketLog

        # section.hos is None (vacant)
        campus_dept.head_of_department = hod_user
        campus_dept.save()
        open_ticket.refresh_from_db()

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is True
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "hod"
        log = TicketLog.objects.filter(
            ticket=open_ticket, event_type="escalated"
        ).first()
        assert log is not None
        assert log.level_user == hod_user

    def test_does_not_escalate_when_all_vacant(
        self, open_ticket, section, campus_dept, hos_rule, hod_rule
    ):
        from apps.sla.services.escalation import run_escalation_for_ticket

        # Both section.hos and campus_dept.head_of_department are None.
        campus_dept.head_of_department = None
        campus_dept.save()
        open_ticket.refresh_from_db()

        result = run_escalation_for_ticket(
            open_ticket, timezone.now(), self._rules(open_ticket)
        )

        assert result is False
        open_ticket.refresh_from_db()
        assert open_ticket.current_level == "technician"

    def test_paused_time_excluded_from_active_clock(
        self, requester, campus, service_item, section, priority, hos_user, hos_rule
    ):
        from apps.tickets.models import Ticket
        from apps.sla.services.escalation import run_escalation_for_ticket

        section.hos = hos_user
        section.save()

        now = timezone.now()
        # Ticket was created 45 minutes ago.
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

        # Ticket went into pending (paused) 20 minutes after creation.
        # accumulated_pause covers a previously completed pause of 20 minutes.
        # paused_at = created_at + 25 min => raw elapsed = 25 min.
        # active_elapsed = (paused_at - created_at) - accumulated_pause
        #                = 25 min - 20 min = 5 min < 30-min threshold.
        t.paused_at = created_at + timedelta(minutes=25)
        t.accumulated_pause = timedelta(minutes=20)

        result = run_escalation_for_ticket(t, now, self._rules(t))

        assert result is False

    def test_active_cover_receives_escalation_instead_of_standing_hos(
        self, open_ticket, section, hos_user, cover_user, hos_rule
    ):
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import TicketLog

        section.hos = hos_user
        section.save()
        open_ticket.refresh_from_db()

        RoleAssignment.objects.create(
            user=cover_user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )

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
        assert log.level_user == cover_user

    def test_expired_cover_escalates_to_standing_hos(
        self, open_ticket, section, hos_user, cover_user, hos_rule
    ):
        from apps.accounts.models import RoleAssignment
        from apps.sla.services.escalation import run_escalation_for_ticket
        from apps.tickets.models import TicketLog

        section.hos = hos_user
        section.save()
        open_ticket.refresh_from_db()

        RoleAssignment.objects.create(
            user=cover_user,
            role="hos",
            section=section,
            is_primary=False,
            valid_until=timezone.now() - timedelta(days=1),
        )

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
        assert log.level_user == hos_user


# ---------------------------------------------------------------------------
# TestTransferHandler
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransferHandler:

    def test_transfers_assigned_tickets_to_pool(self, open_ticket, technician, section):
        from apps.org.services.transfer import transfer_open_tickets
        from apps.tickets.models import TicketLog

        open_ticket.assigned_to = technician
        open_ticket.status = "assigned"
        open_ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        transfer_open_tickets(technician, section)

        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to is None
        assert TicketLog.objects.filter(
            ticket=open_ticket, event_type="reassigned"
        ).exists()

    def test_returns_count_of_transferred(
        self, requester, campus, service_item, section, priority, technician
    ):
        from apps.tickets.models import Ticket
        from apps.org.services.transfer import transfer_open_tickets

        for i, status in enumerate(("open", "assigned", "in_progress"), start=1):
            t = Ticket.objects.create(
                raised_by=requester,
                requester_campus=campus,
                service_item=service_item,
                section=section,
                priority=priority,
                status=status,
                assigned_to=technician,
            )

        count = transfer_open_tickets(technician, section)

        assert count == 3

    def test_does_not_touch_resolved_tickets(self, open_ticket, technician, section):
        from apps.org.services.transfer import transfer_open_tickets

        open_ticket.assigned_to = technician
        open_ticket.status = "resolved"
        open_ticket.save(update_fields=["assigned_to", "status", "updated_at"])

        count = transfer_open_tickets(technician, section)

        assert count == 0
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to == technician

    def test_does_not_touch_tickets_in_other_section(
        self,
        requester,
        campus,
        service_item,
        section,
        priority,
        technician,
        campus_dept,
        section_type,
    ):
        from apps.org.models import Section
        from apps.tickets.models import Ticket
        from apps.org.services.transfer import transfer_open_tickets

        from apps.org.models import SectionType, Department

        dept2 = Department.objects.create(name="HR", code="HR")
        st2 = SectionType.objects.create(
            department=dept2, name="Recruitment", code="REC"
        )
        from apps.org.models import CampusDepartment

        cd2 = CampusDepartment.objects.create(
            campus=campus_dept.campus, department=dept2
        )
        other_section2 = Section.objects.create(
            campus_department=cd2,
            section_type=st2,
        )

        t = Ticket.objects.create(
            raised_by=requester,
            requester_campus=campus,
            service_item=service_item,
            section=other_section2,
            priority=priority,
            status="assigned",
            assigned_to=technician,
        )

        count = transfer_open_tickets(technician, section)

        assert count == 0
        t.refresh_from_db()
        assert t.assigned_to == technician
