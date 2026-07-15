"""TicketSequence — race-free per campus-department ticket numbering.

Replaces the old read-max-and-parse generation, which had two defects:
  1. Concurrent creates in the same campus department could both read the same
     max and collide on the ticket_no unique constraint.
  2. The max was found by string-ordering ticket_no, so once a sequence passed
     9999 the next number was parsed from the wrong row ("9999" > "10000"
     lexicographically) and numbering went backwards.

The counter table allocates under select_for_update; these tests pin the
allocation semantics (SQLite can't exercise the lock itself — single-writer).
"""

import pytest


@pytest.fixture
def campus(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Nairobi", code="NRB", location="CBD")


@pytest.fixture
def dept(db):
    from apps.org.models import Department

    return Department.objects.create(name="ICT", code="ICT")


@pytest.fixture
def other_dept(db):
    from apps.org.models import Department

    return Department.objects.create(name="Human Resources", code="HR")


@pytest.fixture
def campus_dept(campus, dept):
    from apps.org.models import CampusDepartment

    return CampusDepartment.objects.create(campus=campus, department=dept)


@pytest.fixture
def other_campus_dept(campus, other_dept):
    from apps.org.models import CampusDepartment

    return CampusDepartment.objects.create(campus=campus, department=other_dept)


@pytest.fixture
def section(campus_dept, dept):
    from apps.org.models import Section, SectionType

    st = SectionType.objects.create(department=dept, name="Support", code="SUP")
    return Section.objects.create(
        campus_department=campus_dept, section_type=st, is_active=True
    )


@pytest.fixture
def other_section(other_campus_dept, other_dept):
    from apps.org.models import Section, SectionType

    st = SectionType.objects.create(department=other_dept, name="Records", code="REC")
    return Section.objects.create(
        campus_department=other_campus_dept, section_type=st, is_active=True
    )


@pytest.fixture
def priority(db):
    from apps.sla.models import Priority

    return Priority.objects.create(
        name="Low", rank=1, response_minutes=480, resolution_minutes=4320
    )


@pytest.fixture
def requester(campus):
    from apps.accounts.models import CustomUser, UserProfile

    user = CustomUser.objects.create_user(username="seq_requester", password="pass")
    UserProfile.objects.create(user=user, campus=campus)
    return user


def _service_item(section, priority):
    from apps.catalog.models import ServiceCategory, ServiceItem

    cat, _ = ServiceCategory.objects.get_or_create(
        section_type=section.section_type,
        name=f"Cat-{section.pk}",
        defaults={"location_details": False, "default_priority": priority},
    )
    return ServiceItem.objects.get_or_create(category=cat, name=f"Item-{section.pk}")[0]


def _make_ticket(section, requester, priority, **kwargs):
    from apps.tickets.models import Ticket

    return Ticket.objects.create(
        raised_by=requester,
        requester_campus=section.campus_department.campus,
        service_item=_service_item(section, priority),
        section=section,
        priority=priority,
        status="open",
        **kwargs,
    )


@pytest.mark.django_db
class TestTicketSequenceAllocation:

    def test_first_ticket_starts_at_0001(self, section, requester, priority):
        t = _make_ticket(section, requester, priority)
        assert t.ticket_no == "TKT-NRB-ICT-0001"

    def test_numbers_are_sequential_within_campus_department(
        self, section, requester, priority
    ):
        nos = [_make_ticket(section, requester, priority).ticket_no for _ in range(3)]
        assert nos == [
            "TKT-NRB-ICT-0001",
            "TKT-NRB-ICT-0002",
            "TKT-NRB-ICT-0003",
        ]

    def test_sequences_are_independent_per_campus_department(
        self, section, other_section, requester, priority
    ):
        _make_ticket(section, requester, priority)
        _make_ticket(section, requester, priority)
        t = _make_ticket(other_section, requester, priority)
        assert t.ticket_no == "TKT-NRB-HR-0001"

    def test_explicit_ticket_no_bypasses_allocation(self, section, requester, priority):
        from apps.tickets.models import TicketSequence

        t = _make_ticket(section, requester, priority, ticket_no="TKT-MANUAL-99")
        assert t.ticket_no == "TKT-MANUAL-99"
        assert not TicketSequence.objects.exists()

    def test_fresh_sequence_seeds_from_existing_tickets(
        self, section, requester, priority
    ):
        """Tickets that predate the counter table must not be re-numbered over."""
        _make_ticket(section, requester, priority, ticket_no="TKT-NRB-ICT-0041")
        t = _make_ticket(section, requester, priority)
        assert t.ticket_no == "TKT-NRB-ICT-0042"

    def test_sequence_past_9999_keeps_climbing(self, section, requester, priority):
        """The old string-ordered parse went backwards after 9999."""
        from apps.tickets.models import TicketSequence

        TicketSequence.objects.create(
            campus_department=section.campus_department, last_number=9999
        )
        first = _make_ticket(section, requester, priority)
        second = _make_ticket(section, requester, priority)
        assert first.ticket_no == "TKT-NRB-ICT-10000"
        assert second.ticket_no == "TKT-NRB-ICT-10001"

    def test_allocate_increments_and_persists(self, campus_dept):
        from apps.tickets.models import TicketSequence

        assert TicketSequence.allocate(campus_dept) == 1
        assert TicketSequence.allocate(campus_dept) == 2
        row = TicketSequence.objects.get(campus_department=campus_dept)
        assert row.last_number == 2
