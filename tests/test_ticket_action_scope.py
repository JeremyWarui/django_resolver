"""IDOR guard tests — ticket action endpoints must enforce scope (SoT §3.5, R15).

Every ticket sub-endpoint (status, assign, comments, logs, attachments) must
reject callers whose role scope does not contain the ticket, even though they
are authenticated. Own tickets (raised_by) stay accessible per R15, except for
staff-only actions (assign).

Negative actors:
  - out-of-scope technician (different section, different campus)
  - out-of-scope HOS (different section)
  - unrelated requester (role 'user', did not raise the ticket)
Positive controls:
  - in-scope technician can act
  - the ticket's own requester can read comments/logs but cannot assign
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def campus(db):
    from apps.org.models import Campus

    return Campus.objects.create(name="Nairobi", code="NRB", location="CBD")


@pytest.fixture
def other_campus(db):
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
def other_campus_dept(other_campus, dept):
    from apps.org.models import CampusDepartment

    return CampusDepartment.objects.create(campus=other_campus, department=dept)


@pytest.fixture
def section_type(dept):
    from apps.org.models import SectionType

    return SectionType.objects.create(department=dept, name="Support", code="SUP")


@pytest.fixture
def section(campus_dept, section_type):
    from apps.org.models import Section

    return Section.objects.create(
        campus_department=campus_dept, section_type=section_type, is_active=True
    )


@pytest.fixture
def other_section(other_campus_dept, section_type):
    from apps.org.models import Section

    return Section.objects.create(
        campus_department=other_campus_dept, section_type=section_type, is_active=True
    )


@pytest.fixture
def priority(db):
    from apps.sla.models import Priority

    return Priority.objects.create(
        name="Low", rank=1, response_minutes=480, resolution_minutes=4320
    )


@pytest.fixture
def service_cat(section_type, priority):
    from apps.catalog.models import ServiceCategory

    return ServiceCategory.objects.create(
        section_type=section_type,
        name="Hardware",
        location_details=False,
        default_priority=priority,
    )


@pytest.fixture
def service_item(service_cat):
    from apps.catalog.models import ServiceItem

    return ServiceItem.objects.create(category=service_cat, name="Laptop Repair")


@pytest.fixture
def requester(campus):
    from apps.accounts.models import CustomUser, UserProfile

    user = CustomUser.objects.create_user(username="ticket_owner", password="pass")
    UserProfile.objects.create(user=user, campus=campus)
    return user


@pytest.fixture
def in_scope_technician(section):
    from apps.accounts.models import CustomUser, RoleAssignment
    from apps.org.models import SectionTechnician

    user = CustomUser.objects.create_user(username="tech_in_scope", password="pass")
    SectionTechnician.objects.create(user=user, section=section)
    RoleAssignment.objects.create(
        user=user, role="technician", section=section, is_primary=True
    )
    return user


@pytest.fixture
def outsider_technician(other_section):
    """Technician with full role setup — but in a different section/campus."""
    from apps.accounts.models import CustomUser, RoleAssignment
    from apps.org.models import SectionTechnician

    user = CustomUser.objects.create_user(username="tech_outsider", password="pass")
    SectionTechnician.objects.create(user=user, section=other_section)
    RoleAssignment.objects.create(
        user=user, role="technician", section=other_section, is_primary=True
    )
    return user


@pytest.fixture
def outsider_hos(other_section):
    """HOS of a different section — zero overlap with the ticket's section."""
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(username="hos_outsider", password="pass")
    other_section.hos = user
    other_section.save()
    RoleAssignment.objects.create(
        user=user, role="hos", section=other_section, is_primary=True
    )
    return user


@pytest.fixture
def outsider_requester(campus):
    """Plain requester (role 'user') who did not raise the ticket."""
    from apps.accounts.models import CustomUser, RoleAssignment, UserProfile

    user = CustomUser.objects.create_user(username="user_outsider", password="pass")
    UserProfile.objects.create(user=user, campus=campus)
    RoleAssignment.objects.create(user=user, role="user", is_primary=True)
    return user


@pytest.fixture
def second_technician(section):
    """Another technician in the SAME section — in scope but never the assignee."""
    from apps.accounts.models import CustomUser, RoleAssignment
    from apps.org.models import SectionTechnician

    user = CustomUser.objects.create_user(username="tech_second", password="pass")
    SectionTechnician.objects.create(user=user, section=section)
    RoleAssignment.objects.create(
        user=user, role="technician", section=section, is_primary=True
    )
    return user


@pytest.fixture
def in_scope_hos(section):
    """HOS of the ticket's own section."""
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(username="hos_in_scope", password="pass")
    section.hos = user
    section.save()
    RoleAssignment.objects.create(
        user=user, role="hos", section=section, is_primary=True
    )
    return user


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(
        username="admin_actor", password="pass", is_staff=True
    )
    RoleAssignment.objects.create(user=user, role="admin", is_primary=True)
    return user


@pytest.fixture
def open_ticket(requester, campus, service_item, section, priority):
    from apps.tickets.models import Ticket

    return Ticket.objects.create(
        raised_by=requester,
        requester_campus=campus,
        service_item=service_item,
        section=section,
        priority=priority,
        status="open",
        response_due_at=timezone.now() + timedelta(hours=8),
        resolution_due_at=timezone.now() + timedelta(hours=72),
    )


def _status_url(t):
    return f"/api/v1/tickets/{t.pk}/status/"


def _assign_url(t):
    return f"/api/v1/tickets/{t.pk}/assign/"


def _comments_url(t):
    return f"/api/v1/tickets/{t.pk}/comments/"


def _logs_url(t):
    return f"/api/v1/tickets/{t.pk}/logs/"


def _attachments_url(t):
    return f"/api/v1/tickets/{t.pk}/attachments/"


@pytest.mark.django_db
class TestOutOfScopeActorsAreRejected:
    """An authenticated user whose scope excludes the ticket gets 403 everywhere."""

    @pytest.fixture(
        params=["outsider_technician", "outsider_hos", "outsider_requester"]
    )
    def outsider(self, request):
        return request.getfixturevalue(request.param)

    def test_status_transition_forbidden(self, api_client, open_ticket, outsider):
        api_client.force_authenticate(user=outsider)
        resp = api_client.post(
            _status_url(open_ticket), {"status": "assigned"}, format="json"
        )
        assert resp.status_code == 403
        open_ticket.refresh_from_db()
        assert open_ticket.status == "open"

    def test_assign_forbidden(
        self, api_client, open_ticket, outsider, in_scope_technician
    ):
        api_client.force_authenticate(user=outsider)
        resp = api_client.post(
            _assign_url(open_ticket),
            {"assigned_to": in_scope_technician.pk},
            format="json",
        )
        assert resp.status_code == 403
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to is None

    def test_comment_list_forbidden(self, api_client, open_ticket, outsider):
        api_client.force_authenticate(user=outsider)
        resp = api_client.get(_comments_url(open_ticket))
        assert resp.status_code == 403

    def test_comment_create_forbidden(self, api_client, open_ticket, outsider):
        from apps.tickets.models import TicketComment

        api_client.force_authenticate(user=outsider)
        resp = api_client.post(
            _comments_url(open_ticket),
            {"body": "should not land", "visibility": "public"},
            format="json",
        )
        assert resp.status_code == 403
        assert not TicketComment.objects.filter(ticket=open_ticket).exists()

    def test_log_list_forbidden(self, api_client, open_ticket, outsider):
        api_client.force_authenticate(user=outsider)
        resp = api_client.get(_logs_url(open_ticket))
        assert resp.status_code == 403

    def test_attachment_list_forbidden(self, api_client, open_ticket, outsider):
        api_client.force_authenticate(user=outsider)
        resp = api_client.get(_attachments_url(open_ticket))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestRequesterOwnTicketAccess:
    """R15 — the requester keeps read/interact access to their own ticket."""

    def test_owner_can_list_logs(self, api_client, open_ticket, requester):
        api_client.force_authenticate(user=requester)
        resp = api_client.get(_logs_url(open_ticket))
        assert resp.status_code == 200

    # Owner commenting on an assigned ticket is covered by
    # TestCommentGating::test_requester_can_comment_once_assigned.

    def test_owner_cannot_assign_own_ticket(
        self, api_client, open_ticket, requester, in_scope_technician
    ):
        """Assignment is a staff action — the 'user' role scope must not unlock it."""
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            _assign_url(open_ticket),
            {"assigned_to": in_scope_technician.pk},
            format="json",
        )
        assert resp.status_code == 403
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to is None


@pytest.mark.django_db
class TestInScopeStaffStillAllowed:
    """Positive control — the guard must not lock out legitimate actors."""

    def test_assigned_technician_can_transition(
        self, api_client, open_ticket, in_scope_technician
    ):
        # B1b: section scope alone is view-only — assignment unlocks transitions.
        open_ticket.assigned_to = in_scope_technician
        open_ticket.save(update_fields=["assigned_to"])
        api_client.force_authenticate(user=in_scope_technician)
        resp = api_client.post(
            _status_url(open_ticket), {"status": "assigned"}, format="json"
        )
        assert resp.status_code == 200

    def test_in_scope_technician_can_assign(
        self, api_client, open_ticket, in_scope_technician
    ):
        api_client.force_authenticate(user=in_scope_technician)
        resp = api_client.post(
            _assign_url(open_ticket),
            {"assigned_to": in_scope_technician.pk},
            format="json",
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# QA B2a — claim (self-assign): technician-only, own section, unassigned+open.
# ---------------------------------------------------------------------------


def _claim_url(t):
    return f"/api/v1/tickets/{t.pk}/claim/"


@pytest.mark.django_db
class TestClaimEndpoint:

    def test_out_of_section_technician_forbidden(
        self, api_client, open_ticket, outsider_technician
    ):
        api_client.force_authenticate(user=outsider_technician)
        resp = api_client.post(_claim_url(open_ticket))
        assert resp.status_code == 403
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to is None

    @pytest.fixture(params=["requester", "in_scope_hos", "admin_user"])
    def non_technician(self, request):
        return request.getfixturevalue(request.param)

    def test_non_technician_roles_forbidden(
        self, api_client, open_ticket, non_technician
    ):
        api_client.force_authenticate(user=non_technician)
        resp = api_client.post(_claim_url(open_ticket))
        assert resp.status_code == 403

    def test_claim_success(self, api_client, open_ticket, in_scope_technician):
        from apps.tickets.models import TicketLog

        api_client.force_authenticate(user=in_scope_technician)
        resp = api_client.post(_claim_url(open_ticket))
        assert resp.status_code == 200
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to == in_scope_technician
        assert open_ticket.status == "in_progress"
        events = list(
            TicketLog.objects.filter(ticket=open_ticket)
            .order_by("created_at", "pk")
            .values_list("event_type", flat=True)
        )
        assert "assigned" in events
        assert events.count("status_changed") == 2  # open→assigned, assigned→in_progress
        # The claiming technician is the actor on the assigned event.
        assigned_log = TicketLog.objects.get(ticket=open_ticket, event_type="assigned")
        assert assigned_log.actor == in_scope_technician

    def test_double_claim_second_loses(
        self, api_client, open_ticket, in_scope_technician, second_technician
    ):
        api_client.force_authenticate(user=in_scope_technician)
        assert api_client.post(_claim_url(open_ticket)).status_code == 200
        api_client.force_authenticate(user=second_technician)
        resp = api_client.post(_claim_url(open_ticket))
        assert resp.status_code == 409
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to == in_scope_technician

    def test_claim_assigned_ticket_conflicts(
        self, api_client, open_ticket, in_scope_technician, second_technician
    ):
        open_ticket.assigned_to = second_technician
        open_ticket.status = "assigned"
        open_ticket.save(update_fields=["assigned_to", "status"])
        api_client.force_authenticate(user=in_scope_technician)
        resp = api_client.post(_claim_url(open_ticket))
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# QA B1 — comment gating: comments open only once assigned, close with the
# ticket, and only the assigned technician may comment among technicians.
# ---------------------------------------------------------------------------


def _post_comment(api_client, ticket, user):
    api_client.force_authenticate(user=user)
    return api_client.post(
        _comments_url(ticket), {"body": "hello", "visibility": "public"}, format="json"
    )


@pytest.mark.django_db
class TestCommentGating:

    def test_requester_cannot_comment_while_unassigned(
        self, api_client, open_ticket, requester
    ):
        resp = _post_comment(api_client, open_ticket, requester)
        assert resp.status_code == 400

    def test_technician_cannot_comment_while_unassigned(
        self, api_client, open_ticket, in_scope_technician
    ):
        resp = _post_comment(api_client, open_ticket, in_scope_technician)
        assert resp.status_code == 400

    @pytest.fixture(params=["in_scope_hos", "admin_user"])
    def supervisor(self, request):
        return request.getfixturevalue(request.param)

    def test_supervisor_cannot_comment_while_unassigned(
        self, api_client, open_ticket, supervisor
    ):
        resp = _post_comment(api_client, open_ticket, supervisor)
        assert resp.status_code == 400

    def test_unassigned_same_section_technician_forbidden(
        self, api_client, open_ticket, in_scope_technician, second_technician
    ):
        open_ticket.assigned_to = in_scope_technician
        open_ticket.save(update_fields=["assigned_to"])
        resp = _post_comment(api_client, open_ticket, second_technician)
        assert resp.status_code == 403

    def test_requester_can_comment_once_assigned(
        self, api_client, open_ticket, requester, in_scope_technician
    ):
        open_ticket.assigned_to = in_scope_technician
        open_ticket.save(update_fields=["assigned_to"])
        resp = _post_comment(api_client, open_ticket, requester)
        assert resp.status_code == 201

    def test_assigned_technician_can_comment(
        self, api_client, open_ticket, in_scope_technician
    ):
        open_ticket.assigned_to = in_scope_technician
        open_ticket.save(update_fields=["assigned_to"])
        resp = _post_comment(api_client, open_ticket, in_scope_technician)
        assert resp.status_code == 201

    def test_supervisor_can_comment_once_assigned(
        self, api_client, open_ticket, in_scope_technician, supervisor
    ):
        open_ticket.assigned_to = in_scope_technician
        open_ticket.save(update_fields=["assigned_to"])
        resp = _post_comment(api_client, open_ticket, supervisor)
        assert resp.status_code == 201

    @pytest.fixture(
        params=["requester", "in_scope_technician", "in_scope_hos", "admin_user"]
    )
    def any_actor(self, request):
        return request.getfixturevalue(request.param)

    def test_nobody_can_comment_on_closed(
        self, api_client, open_ticket, in_scope_technician, any_actor
    ):
        open_ticket.assigned_to = in_scope_technician
        open_ticket.status = "closed"
        open_ticket.save(update_fields=["assigned_to", "status"])
        resp = _post_comment(api_client, open_ticket, any_actor)
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# QA B1b — status transitions: technicians only on tickets assigned to them;
# the requester only close-own (resolved→closed) and reopen-own (→open).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStatusUpdateGating:

    def test_unassigned_section_technician_forbidden(
        self, api_client, open_ticket, in_scope_technician, second_technician
    ):
        open_ticket.assigned_to = in_scope_technician
        open_ticket.status = "in_progress"
        open_ticket.save(update_fields=["assigned_to", "status"])
        api_client.force_authenticate(user=second_technician)
        resp = api_client.post(
            _status_url(open_ticket), {"status": "resolved"}, format="json"
        )
        assert resp.status_code == 403
        open_ticket.refresh_from_db()
        assert open_ticket.status == "in_progress"

    def test_requester_cannot_start_progress(self, api_client, open_ticket, requester):
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            _status_url(open_ticket), {"status": "in_progress"}, format="json"
        )
        assert resp.status_code == 403

    def test_requester_can_close_own_resolved(self, api_client, open_ticket, requester):
        open_ticket.status = "resolved"
        open_ticket.save(update_fields=["status"])
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            _status_url(open_ticket), {"status": "closed"}, format="json"
        )
        assert resp.status_code == 200
        open_ticket.refresh_from_db()
        assert open_ticket.status == "closed"

    @pytest.mark.parametrize("from_status", ["resolved", "closed"])
    def test_requester_can_reopen_own(
        self, api_client, open_ticket, requester, in_scope_technician, from_status
    ):
        open_ticket.status = from_status
        open_ticket.assigned_to = in_scope_technician
        open_ticket.save(update_fields=["status", "assigned_to"])
        api_client.force_authenticate(user=requester)
        resp = api_client.post(
            _status_url(open_ticket), {"status": "open"}, format="json"
        )
        assert resp.status_code == 200
        open_ticket.refresh_from_db()
        assert open_ticket.status == "open"
        assert open_ticket.assigned_to is None
