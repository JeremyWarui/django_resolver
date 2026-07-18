"""
Phase 4 acceptance tests — Ticket lifecycle, status transitions, assignment,
comments, feedback, and audit log.

Covers:
  - Lifecycle service: TransitionError, valid/invalid transitions, SLA pause/resume
  - TicketLog immutability (save + delete)
  - Status endpoint: valid transition, invalid transition, pending w/o reason, auth
  - Assign endpoint: in-pool, not-in-pool, open→assigned, reassignment
  - Comment endpoints: public, internal, requester visibility, staff visibility, auth
  - Feedback endpoints: resolved gate, non-requester 403, duplicate 409, invalid rating
  - Log endpoint: created event, transition event

All model imports are placed inside fixtures/test functions to avoid import-time
errors if Phase 4 modules are not yet wired up.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# shared fixtures
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

    return SectionType.objects.create(department=dept, name="Support", code="SUP")


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
def other_user(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create_user(username="other_user", password="pass")


@pytest.fixture
def open_ticket(requester, campus, service_item, section, priority):
    from apps.tickets.models import Ticket

    return Ticket.objects.create(
        ticket_no="TKT-000001",
        raised_by=requester,
        requester_campus=campus,
        service_item=service_item,
        section=section,
        priority=priority,
        status="open",
        response_due_at=timezone.now() + timedelta(hours=8),
        resolution_due_at=timezone.now() + timedelta(hours=72),
    )


# ---------------------------------------------------------------------------
# Lifecycle unit tests (no HTTP)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransitionValidSequence:

    def test_transition_valid_sequence(self, open_ticket, technician):
        """open→assigned→in_progress→resolved→closed all succeed."""
        from apps.tickets.services.lifecycle import transition_status

        ticket = open_ticket

        transition_status(ticket, "assigned", technician)
        ticket.refresh_from_db()
        assert ticket.status == "assigned"

        transition_status(ticket, "in_progress", technician)
        ticket.refresh_from_db()
        assert ticket.status == "in_progress"

        transition_status(ticket, "resolved", technician)
        ticket.refresh_from_db()
        assert ticket.status == "resolved"

        transition_status(ticket, "closed", technician)
        ticket.refresh_from_db()
        assert ticket.status == "closed"


@pytest.mark.django_db
class TestTransitionInvalidRaises:

    @pytest.mark.parametrize(
        "walk,bad_target",
        [
            ([], "in_progress"),  # open → in_progress skips assigned
            ([], "resolved"),  # open → resolved skips the whole ladder
            (["assigned", "in_progress"], "closed"),  # must go via resolved
        ],
    )
    def test_transition_invalid_raises(self, open_ticket, technician, walk, bad_target):
        """Illegal edges of the ALLOWED map raise TransitionError."""
        from apps.tickets.services.lifecycle import transition_status, TransitionError

        for status in walk:
            transition_status(open_ticket, status, technician)
        with pytest.raises(TransitionError):
            transition_status(open_ticket, bad_target, technician)


@pytest.mark.django_db
class TestPendingRequiresReason:

    def test_pending_requires_reason(self, open_ticket, technician):
        """Transitioning to 'pending' with empty reason raises TransitionError."""
        from apps.tickets.services.lifecycle import transition_status, TransitionError

        ticket = open_ticket
        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)

        with pytest.raises(TransitionError):
            transition_status(ticket, "pending", technician, reason="")


@pytest.mark.django_db
class TestPendingWithReasonOk:

    def test_pending_with_reason_ok(self, open_ticket, technician):
        """Transitioning to 'pending' with a non-empty reason succeeds and writes a log."""
        from apps.tickets.services.lifecycle import transition_status
        from apps.tickets.models import TicketLog

        ticket = open_ticket
        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)
        transition_status(ticket, "pending", technician, reason="Waiting for parts")

        ticket.refresh_from_db()
        assert ticket.status == "pending"

        assert TicketLog.objects.filter(
            ticket=ticket,
            event_type="status_changed",
            reason__icontains="Waiting",
        ).exists()


@pytest.mark.django_db
class TestSLAPauseResume:

    def test_sla_pause_resume(self, open_ticket, technician):
        """SLA pauses on 'pending' and resumes on 'in_progress'; accumulated_pause grows."""
        from apps.tickets.services.lifecycle import transition_status

        ticket = open_ticket
        original_response_due_at = ticket.response_due_at

        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)

        # Pause SLA by going pending
        transition_status(ticket, "pending", technician, reason="Waiting for parts")
        ticket.refresh_from_db()
        assert ticket.paused_at is not None

        # Resume SLA by going back to in_progress
        transition_status(ticket, "in_progress", technician)
        ticket.refresh_from_db()

        # After resume, paused_at should be cleared
        assert ticket.paused_at is None
        # accumulated_pause should be >= 0 and response_due_at should have been extended
        assert ticket.accumulated_pause >= timedelta(0)
        # The due date should not be earlier than the original (it should be extended)
        assert ticket.response_due_at >= original_response_due_at


@pytest.mark.django_db
class TestPendingToResolved:
    """QA B2b — pending → resolved is legal and settles the SLA pause (R9)."""

    def test_pending_to_resolved_settles_pause(self, open_ticket, technician):
        from apps.tickets.services.lifecycle import transition_status

        ticket = open_ticket
        original_resolution_due = ticket.resolution_due_at
        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)
        transition_status(ticket, "pending", technician, reason="Waiting for parts")

        # Backdate the pause start so the settled pause is measurable.
        ticket.paused_at = timezone.now() - timedelta(minutes=30)
        ticket.save(update_fields=["paused_at"])

        transition_status(ticket, "resolved", technician, reason="Parts arrived, fixed")
        ticket.refresh_from_db()

        assert ticket.status == "resolved"
        assert ticket.paused_at is None
        assert ticket.accumulated_pause >= timedelta(minutes=30)
        assert ticket.resolution_due_at >= original_resolution_due + timedelta(
            minutes=30
        )
        assert ticket.resolved_at is not None


@pytest.mark.django_db
class TestReopenRestartsLifecycle:
    """QA B2f — reopen is resolved/closed → open: unassigned, fresh SLA clock."""

    def _resolve(self, ticket, technician):
        from apps.tickets.services.lifecycle import transition_status

        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)
        transition_status(ticket, "resolved", technician, reason="done")

    @pytest.mark.parametrize("from_status", ["resolved", "closed"])
    def test_reopen_resets_state(self, open_ticket, technician, requester, from_status):
        from apps.tickets.models import TicketLog
        from apps.tickets.services.lifecycle import transition_status

        ticket = open_ticket
        ticket.assigned_to = technician
        ticket.save(update_fields=["assigned_to"])
        self._resolve(ticket, technician)
        if from_status == "closed":
            transition_status(ticket, "closed", requester)

        before = timezone.now()
        transition_status(ticket, "open", requester, reason="issue came back")
        ticket.refresh_from_db()

        assert ticket.status == "open"
        assert ticket.assigned_to is None
        assert ticket.resolved_at is None
        assert ticket.closed_at is None
        assert ticket.paused_at is None
        assert ticket.accumulated_pause == timedelta(0)
        # SLA restarted from the reopen time, not the original creation time.
        assert ticket.response_due_at >= before + timedelta(
            minutes=ticket.priority.response_minutes
        )
        assert ticket.resolution_due_at >= before + timedelta(
            minutes=ticket.priority.resolution_minutes
        )
        assert TicketLog.objects.filter(
            ticket=ticket, event_type="reopened", to_value="open"
        ).exists()

    def test_direct_resolved_to_in_progress_removed(self, open_ticket, technician):
        from apps.tickets.services.lifecycle import transition_status, TransitionError

        ticket = open_ticket
        self._resolve(ticket, technician)
        with pytest.raises(TransitionError):
            transition_status(ticket, "in_progress", technician)


# TicketLog immutability lives in test_phase1_models.py::TestR11TicketLogImmutable.


# ---------------------------------------------------------------------------
# Status endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def _assign_to(technician):
    """Make the technician the ticket's assignee (B1b: technicians may only
    transition tickets assigned to them)."""

    def _do(ticket):
        ticket.assigned_to = technician
        ticket.save(update_fields=["assigned_to"])
        return ticket

    return _do


@pytest.mark.django_db
class TestStatusTransitionViaApi:

    def test_status_transition_via_api(
        self, api_client, open_ticket, technician, _assign_to
    ):
        """POST /api/v1/tickets/{id}/status/ open→assigned returns 200 with updated status."""
        _assign_to(open_ticket)
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"
        response = api_client.post(url, {"status": "assigned"}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "assigned"

    def test_status_invalid_transition_returns_400(
        self, api_client, open_ticket, technician, _assign_to
    ):
        """POST open→resolved (invalid) returns 400."""
        _assign_to(open_ticket)
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"
        response = api_client.post(url, {"status": "resolved"}, format="json")
        assert response.status_code == 400

    def test_status_pending_without_reason_returns_400(
        self, api_client, open_ticket, technician, _assign_to
    ):
        """POST to 'pending' without reason returns 400."""
        _assign_to(open_ticket)
        api_client.force_authenticate(user=technician)
        base_url = f"/api/v1/tickets/{open_ticket.pk}/status/"

        # Advance to in_progress first
        api_client.post(base_url, {"status": "assigned"}, format="json")
        api_client.post(base_url, {"status": "in_progress"}, format="json")

        response = api_client.post(base_url, {"status": "pending"}, format="json")
        assert response.status_code == 400

    def test_status_pending_with_reason_ok(
        self, api_client, open_ticket, technician, _assign_to
    ):
        """POST to 'pending' with reason returns 200."""
        _assign_to(open_ticket)
        api_client.force_authenticate(user=technician)
        base_url = f"/api/v1/tickets/{open_ticket.pk}/status/"

        api_client.post(base_url, {"status": "assigned"}, format="json")
        api_client.post(base_url, {"status": "in_progress"}, format="json")

        response = api_client.post(
            base_url,
            {"status": "pending", "reason": "Waiting for parts"},
            format="json",
        )
        assert response.status_code == 200

    def test_status_unauthenticated_returns_401(self, api_client, open_ticket):
        """Unauthenticated requests return 401."""
        url = f"/api/v1/tickets/{open_ticket.pk}/status/"
        response = api_client.post(url, {"status": "assigned"}, format="json")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Assign endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAssignEndpoint:

    def test_assign_technician_in_pool(self, api_client, open_ticket, technician):
        """POST /api/v1/tickets/{id}/assign/ with a pool member returns 200."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/assign/"
        response = api_client.post(url, {"assigned_to": technician.pk}, format="json")
        assert response.status_code == 200
        open_ticket.refresh_from_db()
        assert open_ticket.assigned_to == technician

    def test_assign_not_in_pool_returns_400(
        self, api_client, open_ticket, technician, other_user
    ):
        """POST assign with a user who is not a SectionTechnician returns 400."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/assign/"
        response = api_client.post(url, {"assigned_to": other_user.pk}, format="json")
        assert response.status_code == 400

    def test_assign_open_ticket_transitions_to_assigned(
        self, api_client, open_ticket, technician
    ):
        """Assigning an open ticket auto-transitions it to 'assigned'."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/assign/"
        response = api_client.post(url, {"assigned_to": technician.pk}, format="json")
        assert response.status_code == 200
        assert response.data["status"] == "assigned"

    def test_assign_already_assigned_ticket_is_reassign(
        self, api_client, open_ticket, technician
    ):
        """Reassigning an already-assigned ticket returns 200 (not an error)."""
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/assign/"

        # First assignment
        api_client.post(url, {"assigned_to": technician.pk}, format="json")

        # Reassign to same technician
        response = api_client.post(url, {"assigned_to": technician.pk}, format="json")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Comment tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCommentEndpoints:

    # Public-comment 201 for the assignee is covered by
    # test_ticket_action_scope.py::TestCommentGating::test_assigned_technician_can_comment.

    def test_post_internal_comment(
        self, api_client, open_ticket, technician, _assign_to
    ):
        """POST an internal comment returns 201."""
        _assign_to(open_ticket)
        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/comments/"
        response = api_client.post(
            url, {"body": "Internal note", "visibility": "internal"}, format="json"
        )
        assert response.status_code == 201

    def test_requester_cannot_see_internal_comments(
        self, api_client, open_ticket, technician, requester
    ):
        """Requester sees public comments but NOT internal ones in the list."""
        from apps.tickets.models import TicketComment

        TicketComment.objects.create(
            ticket=open_ticket,
            author=technician,
            body="Public msg",
            visibility="public",
        )
        TicketComment.objects.create(
            ticket=open_ticket,
            author=technician,
            body="Secret note",
            visibility="internal",
        )

        api_client.force_authenticate(user=requester)
        url = f"/api/v1/tickets/{open_ticket.pk}/comments/"
        response = api_client.get(url)
        assert response.status_code == 200

        # Collect body texts from cursor-paginated or plain list response
        results = response.data.get("results", response.data)
        bodies = [c["body"] for c in results]

        assert "Public msg" in bodies
        assert "Secret note" not in bodies

    def test_staff_can_see_internal_comments(self, api_client, open_ticket, technician):
        """A non-requester (staff) user sees both public and internal comments."""
        from apps.tickets.models import TicketComment

        TicketComment.objects.create(
            ticket=open_ticket,
            author=technician,
            body="Public msg",
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
        response = api_client.get(url)
        assert response.status_code == 200

        results = response.data.get("results", response.data)
        bodies = [c["body"] for c in results]

        assert "Public msg" in bodies
        assert "Secret note" in bodies

    def test_comment_list_unauthenticated_returns_401(self, api_client, open_ticket):
        """GET comments without authentication returns 401."""
        url = f"/api/v1/tickets/{open_ticket.pk}/comments/"
        response = api_client.get(url)
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Feedback tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFeedbackEndpoints:

    def _advance_to_resolved(self, ticket, technician):
        """Helper: advance ticket state to resolved via the lifecycle service."""
        from apps.tickets.services.lifecycle import transition_status

        transition_status(ticket, "assigned", technician)
        transition_status(ticket, "in_progress", technician)
        transition_status(ticket, "resolved", technician)
        ticket.refresh_from_db()

    def test_feedback_on_resolved_ticket(
        self, api_client, open_ticket, technician, requester
    ):
        """Requester can submit feedback on a resolved ticket (201)."""
        self._advance_to_resolved(open_ticket, technician)

        api_client.force_authenticate(user=requester)
        url = f"/api/v1/tickets/{open_ticket.pk}/feedback/"
        response = api_client.post(url, {"rating": 4, "comment": "Good"}, format="json")
        assert response.status_code == 201

    def test_feedback_below_resolved_returns_400(
        self, api_client, open_ticket, requester, technician
    ):
        """Submitting feedback on a ticket that is not yet resolved returns 400."""
        # Advance only to in_progress, not resolved
        from apps.tickets.services.lifecycle import transition_status

        transition_status(open_ticket, "assigned", technician)
        transition_status(open_ticket, "in_progress", technician)
        open_ticket.refresh_from_db()

        api_client.force_authenticate(user=requester)
        url = f"/api/v1/tickets/{open_ticket.pk}/feedback/"
        response = api_client.post(url, {"rating": 3}, format="json")
        assert response.status_code == 400

    def test_feedback_non_requester_returns_403(
        self, api_client, open_ticket, technician, other_user
    ):
        """A user who is not the ticket requester receives 403."""
        self._advance_to_resolved(open_ticket, technician)

        api_client.force_authenticate(user=other_user)
        url = f"/api/v1/tickets/{open_ticket.pk}/feedback/"
        response = api_client.post(url, {"rating": 5}, format="json")
        assert response.status_code == 403

    def test_feedback_duplicate_returns_409(
        self, api_client, open_ticket, technician, requester
    ):
        """Submitting feedback a second time returns 409."""
        self._advance_to_resolved(open_ticket, technician)

        api_client.force_authenticate(user=requester)
        url = f"/api/v1/tickets/{open_ticket.pk}/feedback/"
        api_client.post(url, {"rating": 4}, format="json")
        response = api_client.post(url, {"rating": 5}, format="json")
        assert response.status_code == 409

    def test_feedback_invalid_rating_returns_400(
        self, api_client, open_ticket, technician, requester
    ):
        """A rating of 6 (outside 1–5) returns 400."""
        self._advance_to_resolved(open_ticket, technician)

        api_client.force_authenticate(user=requester)
        url = f"/api/v1/tickets/{open_ticket.pk}/feedback/"
        response = api_client.post(url, {"rating": 6}, format="json")
        assert response.status_code == 400

    def test_detail_includes_feedback_after_submission(
        self, api_client, open_ticket, technician, requester
    ):
        """QA D3 — ticket detail nests feedback once submitted; list stays lean."""
        self._advance_to_resolved(open_ticket, technician)

        api_client.force_authenticate(user=requester)
        detail_url = f"/api/v1/tickets/{open_ticket.pk}/"

        # Before submission: present but null (not erroring).
        response = api_client.get(detail_url)
        assert response.status_code == 200
        assert response.data["feedback"] is None

        api_client.post(
            f"/api/v1/tickets/{open_ticket.pk}/feedback/",
            {"rating": 4, "comment": "Quick fix, thanks"},
            format="json",
        )
        response = api_client.get(detail_url)
        assert response.data["feedback"]["rating"] == 4
        assert response.data["feedback"]["comment"] == "Quick fix, thanks"

        # List payload unchanged — no feedback key (detail-only nesting).
        response = api_client.get("/api/v1/tickets/?mine=1")
        results = response.data.get("results", response.data)
        assert results and "feedback" not in results[0]


# ---------------------------------------------------------------------------
# Log endpoint tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLogEndpoint:

    def test_logs_contain_created_event(
        self, api_client, open_ticket, technician, requester
    ):
        """GET /api/v1/tickets/{id}/logs/ returns a 'created' event log."""
        from apps.tickets.models import TicketLog

        # Ensure there is a created event (may have been written by fixture or must be added)
        if not TicketLog.objects.filter(
            ticket=open_ticket, event_type="created"
        ).exists():
            TicketLog.objects.create(
                ticket=open_ticket,
                actor=requester,
                event_type="created",
                to_value=open_ticket.ticket_no,
            )

        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/logs/"
        response = api_client.get(url)
        assert response.status_code == 200

        results = response.data.get("results", response.data)
        event_types = [entry["event_type"] for entry in results]
        assert "created" in event_types

    def test_transition_writes_log(self, api_client, open_ticket, technician):
        """After a status transition, GET logs includes the status_changed event."""
        from apps.tickets.services.lifecycle import transition_status

        transition_status(open_ticket, "assigned", technician)

        api_client.force_authenticate(user=technician)
        url = f"/api/v1/tickets/{open_ticket.pk}/logs/"
        response = api_client.get(url)
        assert response.status_code == 200

        results = response.data.get("results", response.data)
        event_types = [entry["event_type"] for entry in results]
        # The lifecycle service should write either "assigned" or "status_changed"
        assert any(et in event_types for et in ("assigned", "status_changed"))
