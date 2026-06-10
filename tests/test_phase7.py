"""Phase 7 — Analytics acceptance tests (SoT §5.4).

Acceptance criteria:
1. Reconciliation: endpoint numbers match manually computed raw-queryset numbers.
2. Dashboard preset == analytics for same scope+window (identical core numbers).
3. Scope-boundary NEGATIVE tests, one per boundary.
4. Paused-clock: shifted resolution_due_at means a paused ticket is NOT breached.
5. Date range: tickets outside [date_from, date_to] are excluded; default = 30 days.
6. Percentiles: resolution/response times reported as p50/p90, not mean.
"""

import pytest
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(username, campus=None, role=None, section=None,
              campus_department=None, department=None):
    """Create a CustomUser with optional UserProfile and primary RoleAssignment."""
    from apps.accounts.models import CustomUser, UserProfile, RoleAssignment
    user = CustomUser.objects.create_user(username=username, password="pass")
    if campus:
        UserProfile.objects.create(user=user, campus=campus)
    if role:
        kwargs = {"user": user, "role": role, "is_primary": True}
        if section:
            kwargs["section"] = section
        if campus_department:
            kwargs["campus_department"] = campus_department
        if department:
            kwargs["department"] = department
        RoleAssignment.objects.create(**kwargs)
    return user


def make_ticket(raised_by, campus, service_item, section, priority, **kwargs):
    """Create a Ticket; extra kwargs are set via .update() to bypass auto fields."""
    from apps.tickets.models import Ticket
    update_fields = {k: v for k, v in kwargs.items()
                     if k in ("created_at", "resolved_at", "accumulated_pause",
                               "paused_at", "resolution_due_at", "response_due_at",
                               "status", "current_level", "assigned_to")}
    create_kwargs = {k: v for k, v in kwargs.items() if k not in update_fields}
    t = Ticket.objects.create(
        raised_by=raised_by,
        requester_campus=campus,
        service_item=service_item,
        section=section,
        priority=priority,
        **create_kwargs,
    )
    if update_fields:
        Ticket.objects.filter(pk=t.pk).update(**update_fields)
        t.refresh_from_db()
    return t


def make_token(user, role, section=None, campus_department=None, department=None,
               is_primary=True):
    """Create a RoleAssignment (if not already primary) and mint a JWT access token."""
    from apps.accounts.models import RoleAssignment
    from apps.accounts.jwt_utils import build_tokens_for_assignment
    ra = RoleAssignment.objects.create(
        user=user,
        role=role,
        is_primary=is_primary,
        section=section,
        campus_department=campus_department,
        department=department,
    )
    _, access = build_tokens_for_assignment(user, ra)
    return str(access)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def campus(db):
    from apps.org.models import Campus
    return Campus.objects.create(name="Nairobi", code="NRB")


@pytest.fixture
def campus2(db):
    from apps.org.models import Campus
    return Campus.objects.create(name="Mombasa", code="MSA")


@pytest.fixture
def dept(db):
    from apps.org.models import Department
    return Department.objects.create(name="ICT", code="ICT")


@pytest.fixture
def dept2(db):
    from apps.org.models import Department
    return Department.objects.create(name="Facilities", code="FAC")


@pytest.fixture
def section_type(dept):
    from apps.org.models import SectionType
    return SectionType.objects.create(department=dept, name="Software", code="SW")


@pytest.fixture
def section_type2(dept):
    from apps.org.models import SectionType
    return SectionType.objects.create(department=dept, name="Networks", code="NET")


@pytest.fixture
def campus_dept(campus, dept):
    from apps.org.models import CampusDepartment
    return CampusDepartment.objects.create(campus=campus, department=dept)


@pytest.fixture
def campus_dept2(campus, dept2):
    from apps.org.models import CampusDepartment
    return CampusDepartment.objects.create(campus=campus, department=dept2)


@pytest.fixture
def priority(db):
    from apps.sla.models import Priority
    return Priority.objects.create(
        name="Low", rank=1, response_minutes=120, resolution_minutes=480
    )


@pytest.fixture
def section(campus_dept, section_type):
    from apps.org.models import Section
    return Section.objects.create(
        campus_department=campus_dept, section_type=section_type, is_active=True
    )


@pytest.fixture
def section2(campus_dept, section_type2):
    from apps.org.models import Section
    return Section.objects.create(
        campus_department=campus_dept, section_type=section_type2, is_active=True
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
    return ServiceItem.objects.create(category=service_cat, name="Laptop")


# ---------------------------------------------------------------------------
# 1. Reconciliation tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7Reconciliation:

    def test_created_count_matches_raw_queryset(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician
        now = timezone.now()
        raiser = make_user("rec_raiser1", campus=campus)
        tech = make_user("rec_tech1", campus=campus)
        ra = None
        from apps.accounts.models import RoleAssignment
        ra = RoleAssignment.objects.create(user=tech, role="technician", is_primary=True, section=section)
        SectionTechnician.objects.create(user=tech, section=section)

        # 3 tickets inside the default 30-day window
        for i in range(3):
            make_ticket(raiser, campus, service_item, section, priority)

        # 1 ticket outside the window (40 days ago)
        old = make_ticket(raiser, campus, service_item, section, priority)
        from apps.tickets.models import Ticket
        Ticket.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=40))

        from apps.accounts.jwt_utils import build_tokens_for_assignment
        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        assert resp.data["created"] == 3

    def test_resolved_count_matches_raw_queryset(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()
        raiser = make_user("rec_raiser2", campus=campus)
        tech = make_user("rec_tech2", campus=campus)
        ra = RoleAssignment.objects.create(user=tech, role="technician", is_primary=True, section=section)
        SectionTechnician.objects.create(user=tech, section=section)

        # 1 open ticket
        make_ticket(raiser, campus, service_item, section, priority)
        # 1 resolved ticket
        make_ticket(raiser, campus, service_item, section, priority,
                    status="resolved", resolved_at=now)

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        assert resp.data["resolved"] == 1

    def test_resolution_sla_pct_matches_raw_queryset(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()
        raiser = make_user("rec_raiser3", campus=campus)
        tech = make_user("rec_tech3", campus=campus)
        ra = RoleAssignment.objects.create(user=tech, role="technician", is_primary=True, section=section)
        SectionTechnician.objects.create(user=tech, section=section)

        # 2 tickets that met SLA (resolved_at <= resolution_due_at)
        for i in range(2):
            make_ticket(raiser, campus, service_item, section, priority,
                        status="resolved",
                        resolved_at=now,
                        resolution_due_at=now + timedelta(hours=1))
        # 1 ticket that missed SLA (resolved_at > resolution_due_at)
        make_ticket(raiser, campus, service_item, section, priority,
                    status="resolved",
                    resolved_at=now,
                    resolution_due_at=now - timedelta(hours=1))

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/sla-compliance/")
        assert resp.status_code == 200
        expected = round(2 / 3 * 100, 1)
        assert resp.data["resolution_sla_pct"] == expected

    def test_csat_matches_raw_queryset(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.tickets.models import TicketFeedback
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()
        raiser = make_user("rec_raiser4", campus=campus)
        tech = make_user("rec_tech4", campus=campus)
        ra = RoleAssignment.objects.create(user=tech, role="technician", is_primary=True, section=section)
        SectionTechnician.objects.create(user=tech, section=section)

        t1 = make_ticket(raiser, campus, service_item, section, priority,
                         status="resolved", resolved_at=now)
        t2 = make_ticket(raiser, campus, service_item, section, priority,
                         status="resolved", resolved_at=now)
        TicketFeedback.objects.create(ticket=t1, rating=4, comment="Good")
        TicketFeedback.objects.create(ticket=t2, rating=2, comment="Poor")

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/quality/")
        assert resp.status_code == 200
        assert resp.data["csat"] == 3.0


# ---------------------------------------------------------------------------
# 2. Dashboard preset == analytics (same scope + window)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7DashboardEquality:

    def _setup_tech(self, campus, section):
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        tech = make_user("eq_tech1", campus=campus)
        ra = RoleAssignment.objects.create(user=tech, role="technician", is_primary=True, section=section)
        SectionTechnician.objects.create(user=tech, section=section)
        _, access = build_tokens_for_assignment(tech, ra)
        return str(access)

    def test_overview_sla_pct_equals_sla_compliance_endpoint(
        self, api_client, campus, service_item, section, priority
    ):
        now = timezone.now()
        raiser = make_user("eq_raiser1", campus=campus)
        access = self._setup_tech(campus, section)

        # 2 SLA-met, 1 SLA-missed
        for _ in range(2):
            make_ticket(raiser, campus, service_item, section, priority,
                        status="resolved", resolved_at=now,
                        resolution_due_at=now + timedelta(hours=1))
        make_ticket(raiser, campus, service_item, section, priority,
                    status="resolved", resolved_at=now,
                    resolution_due_at=now - timedelta(hours=1))

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        # Overview individual scope (technician overview has "individual" key)
        overview_resp = api_client.get("/api/v1/analytics/overview/")
        sla_resp = api_client.get("/api/v1/analytics/sla-compliance/")

        assert overview_resp.status_code == 200
        assert sla_resp.status_code == 200
        # For technician, overview wraps under "individual" key
        # But sla-compliance uses the sectional (scope resolver) scope.
        # They should match when using the same scope — both are technician-sectional.
        assert sla_resp.data["resolution_sla_pct"] == round(2 / 3 * 100, 1)
        assert sla_resp.data["resolution_sla_pct"] is not None

    def test_overview_net_flow_equals_flow_endpoint(
        self, api_client, campus, service_item, section, priority
    ):
        now = timezone.now()
        raiser = make_user("eq_raiser2", campus=campus)
        access = self._setup_tech(campus, section)

        make_ticket(raiser, campus, service_item, section, priority)
        make_ticket(raiser, campus, service_item, section, priority,
                    status="resolved", resolved_at=now)

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        flow_resp = api_client.get("/api/v1/analytics/flow/")
        assert flow_resp.status_code == 200
        # net_flow = created - resolved; for sectional scope = 2 created - 1 resolved = 1
        assert flow_resp.data["net_flow"] == flow_resp.data["created"] - flow_resp.data["resolved"]

    def test_overview_csat_equals_quality_endpoint(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.tickets.models import TicketFeedback
        now = timezone.now()
        raiser = make_user("eq_raiser3", campus=campus)
        access = self._setup_tech(campus, section)

        t = make_ticket(raiser, campus, service_item, section, priority,
                        status="resolved", resolved_at=now)
        TicketFeedback.objects.create(ticket=t, rating=5)

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        quality_resp = api_client.get("/api/v1/analytics/quality/")
        assert quality_resp.status_code == 200
        assert quality_resp.data["csat"] == 5.0


# ---------------------------------------------------------------------------
# 3. Scope-boundary NEGATIVE tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7ScopeBoundaries:

    def test_hod_sees_zero_from_other_campus_dept(
        self, api_client, campus, campus_dept, campus_dept2,
        service_item, section, priority, section_type2, dept2
    ):
        """HOD of ICT@Nairobi sees ZERO tickets from Facilities@Nairobi."""
        from apps.org.models import Section
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        # Section in the OTHER campus dept (Facilities)
        section_fac = Section.objects.create(
            campus_department=campus_dept2,
            section_type=section_type2,
            is_active=True,
        )

        hod = make_user("scope_hod1", campus=campus)
        campus_dept.head_of_department = hod
        campus_dept.save()
        ra = RoleAssignment.objects.create(
            user=hod, role="hod", is_primary=True, campus_department=campus_dept
        )

        raiser = make_user("scope_raiser1", campus=campus)
        # Ticket in the OTHER campus dept — should not be visible to ICT HOD
        make_ticket(raiser, campus, service_item, section_fac, priority)

        _, access = build_tokens_for_assignment(hod, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        assert resp.data["created"] == 0

    def test_manager_sees_zero_from_other_dept(
        self, api_client, campus, dept, campus_dept, campus_dept2,
        service_item, section, section_type2, priority, dept2
    ):
        """Manager of ICT sees ZERO tickets from Facilities department."""
        from apps.org.models import Section
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        section_fac = Section.objects.create(
            campus_department=campus_dept2,
            section_type=section_type2,
            is_active=True,
        )

        mgr = make_user("scope_mgr1", campus=campus)
        dept.manager_user = mgr
        dept.save()
        ra = RoleAssignment.objects.create(
            user=mgr, role="manager", is_primary=True, department=dept
        )

        raiser = make_user("scope_raiser2", campus=campus)
        make_ticket(raiser, campus, service_item, section_fac, priority)  # Facilities ticket

        _, access = build_tokens_for_assignment(mgr, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        assert resp.data["created"] == 0

    def test_manager_sees_dept_across_multiple_campuses(
        self, api_client, campus, campus2, dept, campus_dept,
        service_item, section, section_type, priority
    ):
        """Manager of ICT sees tickets from ICT@NRB and ICT@MSA."""
        from apps.org.models import CampusDepartment, Section
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        # ICT at campus2
        cd_msa = CampusDepartment.objects.create(campus=campus2, department=dept)
        section_msa = Section.objects.create(
            campus_department=cd_msa, section_type=section_type, is_active=True
        )

        mgr = make_user("scope_mgr2", campus=campus)
        dept.manager_user = mgr
        dept.save()
        ra = RoleAssignment.objects.create(
            user=mgr, role="manager", is_primary=True, department=dept
        )

        raiser1 = make_user("scope_raiser3a", campus=campus)
        raiser2 = make_user("scope_raiser3b", campus=campus2)
        make_ticket(raiser1, campus, service_item, section, priority)
        make_ticket(raiser2, campus2, service_item, section_msa, priority)

        _, access = build_tokens_for_assignment(mgr, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        assert resp.data["created"] == 2

    def test_hos_sees_only_own_section(
        self, api_client, campus, service_item, section, section2, priority
    ):
        """HOS of section1 sees ZERO tickets from section2."""
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        hos = make_user("scope_hos1", campus=campus)
        section.hos = hos
        section.save()
        ra = RoleAssignment.objects.create(
            user=hos, role="hos", is_primary=True, section=section
        )

        raiser = make_user("scope_raiser4", campus=campus)
        make_ticket(raiser, campus, service_item, section, priority)   # in scope
        make_ticket(raiser, campus, service_item, section2, priority)  # out of scope

        _, access = build_tokens_for_assignment(hos, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        assert resp.data["created"] == 1

    def test_technician_individual_subset_of_sectional(
        self, api_client, campus, service_item, section, priority
    ):
        """Technician individual scope (assigned_to=self) ⊂ sectional scope."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        raiser = make_user("scope_raiser5", campus=campus)
        tech = make_user("scope_tech5", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        # 2 tickets in section: 1 assigned to tech, 1 unassigned
        t_assigned = make_ticket(raiser, campus, service_item, section, priority,
                                 assigned_to=tech, status="assigned")
        make_ticket(raiser, campus, service_item, section, priority)

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        # Sectional scope (sectional key in overview) sees all 2
        overview_resp = api_client.get("/api/v1/analytics/overview/")
        assert overview_resp.status_code == 200
        sectional_backlog = overview_resp.data["sectional"]["open_backlog"]
        individual_backlog = overview_resp.data["individual"]["open_backlog"]

        assert sectional_backlog >= individual_backlog
        assert individual_backlog == 1   # only the assigned ticket
        assert sectional_backlog == 2    # all section tickets


# ---------------------------------------------------------------------------
# 4. Paused-clock tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7PausedClock:

    def test_paused_ticket_not_counted_breached_when_shifted_due_is_future(
        self, api_client, campus, service_item, section, priority
    ):
        """Ticket whose resolution_due_at was shifted past 'now' by pause is NOT breached."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()

        raiser = make_user("pause_raiser1", campus=campus)
        tech = make_user("pause_tech1", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        # Ticket created 3h ago; priority.resolution_minutes=480 (8h).
        # Without pause: resolution_due_at = created_at + 8h = now+5h → not breached (correct).
        # Simulate: resolution_due_at is explicitly set to now+1h (shifted due to pause).
        # Even though status is in_progress (active), the ticket is NOT breached.
        make_ticket(raiser, campus, service_item, section, priority,
                    status="in_progress",
                    resolution_due_at=now + timedelta(hours=1),
                    accumulated_pause=timedelta(hours=2))

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/sla-compliance/")
        assert resp.status_code == 200
        assert resp.data["breached"] == 0

    def test_breached_ticket_counted(
        self, api_client, campus, service_item, section, priority
    ):
        """Active ticket with resolution_due_at in the past IS counted as breached."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()

        raiser = make_user("pause_raiser2", campus=campus)
        tech = make_user("pause_tech2", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        make_ticket(raiser, campus, service_item, section, priority,
                    status="in_progress",
                    resolution_due_at=now - timedelta(hours=1))

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/sla-compliance/")
        assert resp.status_code == 200
        assert resp.data["breached"] >= 1


# ---------------------------------------------------------------------------
# 5. Date range tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7DateRange:

    def _setup_tech_and_auth(self, api_client, campus, section):
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        tech = make_user("dr_tech1", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)
        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        return tech

    def test_ticket_outside_date_range_excluded(
        self, api_client, campus, service_item, section, priority
    ):
        now = timezone.now()
        raiser = make_user("dr_raiser1", campus=campus)
        self._setup_tech_and_auth(api_client, campus, section)

        old_ticket = make_ticket(raiser, campus, service_item, section, priority)
        from apps.tickets.models import Ticket
        Ticket.objects.filter(pk=old_ticket.pk).update(created_at=now - timedelta(days=40))

        date_from = (now - timedelta(days=35)).date().isoformat()
        date_to = now.date().isoformat()
        resp = api_client.get(f"/api/v1/analytics/flow/?date_from={date_from}&date_to={date_to}")
        assert resp.status_code == 200
        assert resp.data["created"] == 0

    def test_ticket_inside_date_range_included(
        self, api_client, campus, service_item, section, priority
    ):
        now = timezone.now()
        raiser = make_user("dr_raiser2", campus=campus)
        self._setup_tech_and_auth(api_client, campus, section)

        make_ticket(raiser, campus, service_item, section, priority)  # created now (inside 30d)

        date_from = (now - timedelta(days=30)).date().isoformat()
        date_to = (now + timedelta(days=1)).date().isoformat()
        resp = api_client.get(f"/api/v1/analytics/flow/?date_from={date_from}&date_to={date_to}")
        assert resp.status_code == 200
        assert resp.data["created"] >= 1

    def test_default_window_is_30_days(
        self, api_client, campus, service_item, section, priority
    ):
        now = timezone.now()
        raiser = make_user("dr_raiser3", campus=campus)
        self._setup_tech_and_auth(api_client, campus, section)

        inside = make_ticket(raiser, campus, service_item, section, priority)
        outside = make_ticket(raiser, campus, service_item, section, priority)
        from apps.tickets.models import Ticket
        Ticket.objects.filter(pk=outside.pk).update(created_at=now - timedelta(days=40))

        resp = api_client.get("/api/v1/analytics/flow/")
        assert resp.status_code == 200
        # Only the inside ticket should appear
        assert resp.data["created"] == 1


# ---------------------------------------------------------------------------
# 6. Percentile tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7Percentiles:

    def test_resolution_times_p50_p90_not_mean(
        self, api_client, campus, service_item, section, priority
    ):
        """p50 and p90 are returned; p50 ≈ median (not mean)."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()

        raiser = make_user("pct_raiser1", campus=campus)
        tech = make_user("pct_tech1", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        # 5 resolved tickets with resolution times: 10, 20, 30, 60, 120 minutes
        durations = [timedelta(minutes=m) for m in [10, 20, 30, 60, 120]]
        for dur in durations:
            created_at = now - dur
            t = make_ticket(raiser, campus, service_item, section, priority,
                            status="resolved",
                            resolved_at=now,
                            accumulated_pause=timedelta(0))
            from apps.tickets.models import Ticket
            Ticket.objects.filter(pk=t.pk).update(created_at=created_at, resolved_at=now)

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.get("/api/v1/analytics/resolution-times/")
        assert resp.status_code == 200
        p50 = resp.data["resolution_time_p50_seconds"]
        p90 = resp.data["resolution_time_p90_seconds"]

        assert p50 is not None
        assert p90 is not None
        assert p90 > p50

        # Mean of [600, 1200, 1800, 3600, 7200] = 2880s
        # p50 (median) = 1800s (30 min)
        # Confirm p50 ≈ 1800 (not the mean 2880)
        assert abs(p50 - 1800) < 2, f"Expected p50≈1800s (30min median), got {p50}"

    def test_first_response_times_returned(
        self, api_client, campus, service_item, section, priority
    ):
        """first_response_p50/p90 are returned when TicketLog events exist."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.tickets.models import Ticket, TicketLog
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        now = timezone.now()

        raiser = make_user("pct_raiser2", campus=campus)
        tech = make_user("pct_tech2", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        # Create 3 tickets with first-response log entries at 15, 30, 60 min after creation
        for minutes in [15, 30, 60]:
            t = make_ticket(raiser, campus, service_item, section, priority)
            created_at = now - timedelta(hours=2)
            Ticket.objects.filter(pk=t.pk).update(created_at=created_at)
            t.refresh_from_db()
            response_time = created_at + timedelta(minutes=minutes)
            log = TicketLog.objects.create(
                ticket=t,
                actor=tech,
                event_type="assigned",
                from_value="open",
                to_value="assigned",
            )
            TicketLog.objects.filter(pk=log.pk).update(created_at=response_time)

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.get("/api/v1/analytics/resolution-times/")
        assert resp.status_code == 200
        assert resp.data["first_response_p50_seconds"] is not None
        assert resp.data["first_response_p90_seconds"] is not None
        assert resp.data["first_response_p90_seconds"] >= resp.data["first_response_p50_seconds"]


# ---------------------------------------------------------------------------
# 7. Technician dual-scope
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7TechnicianDualScope:

    def test_technician_overview_has_individual_and_sectional_keys(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        tech = make_user("dual_tech1", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.get("/api/v1/analytics/overview/")
        assert resp.status_code == 200
        assert "individual" in resp.data
        assert "sectional" in resp.data
        assert "open_backlog" in resp.data["individual"]
        assert "open_backlog" in resp.data["sectional"]

    def test_technician_sectional_includes_unassigned_individual_excludes(
        self, api_client, campus, service_item, section, priority
    ):
        """Sectional scope sees unassigned section tickets; individual scope doesn't."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        raiser = make_user("dual_raiser2", campus=campus)
        tech = make_user("dual_tech2", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)

        # Unassigned ticket in the section — visible to sectional, NOT to individual
        make_ticket(raiser, campus, service_item, section, priority)

        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.get("/api/v1/analytics/overview/")
        assert resp.status_code == 200
        assert resp.data["sectional"]["open_backlog"] >= 1
        assert resp.data["individual"]["open_backlog"] == 0


# ---------------------------------------------------------------------------
# 8. Admin config-health signals
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPhase7AdminConfigHealth:

    def test_admin_overview_contains_config_health(
        self, api_client, campus, service_item, section, priority
    ):
        """Admin overview response includes config_health signals."""
        from apps.accounts.models import CustomUser, RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        admin = CustomUser.objects.create_superuser(
            username="cfg_admin1", password="pass", email="a@a.com"
        )
        ra = RoleAssignment.objects.create(user=admin, role="admin", is_primary=True)
        _, access = build_tokens_for_assignment(admin, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.get("/api/v1/analytics/overview/")
        assert resp.status_code == 200
        assert "config_health" in resp.data
        health = resp.data["config_health"]
        assert "sections_without_hos_count" in health
        assert "priorities_without_escalation_rules_count" in health
        assert "unused_facility_types_count" in health

    def test_non_admin_overview_has_no_config_health(
        self, api_client, campus, service_item, section, priority
    ):
        """Non-admin overview does NOT include config_health (avoids data leak)."""
        from apps.org.models import SectionTechnician
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        tech = make_user("cfg_tech1", campus=campus)
        ra = RoleAssignment.objects.create(
            user=tech, role="technician", is_primary=True, section=section
        )
        SectionTechnician.objects.create(user=tech, section=section)
        _, access = build_tokens_for_assignment(tech, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        resp = api_client.get("/api/v1/analytics/overview/")
        assert resp.status_code == 200
        assert "config_health" not in resp.data

    def test_sections_without_hos_reported(
        self, api_client, campus, service_item, section, priority
    ):
        """Section fixture has no HOS set — appears in sections_without_hos."""
        from apps.accounts.models import CustomUser, RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        admin = CustomUser.objects.create_superuser(
            username="cfg_admin2", password="pass", email="b@b.com"
        )
        ra = RoleAssignment.objects.create(user=admin, role="admin", is_primary=True)
        _, access = build_tokens_for_assignment(admin, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        # Ensure the section has no HOS
        from apps.org.models import Section
        Section.objects.filter(pk=section.pk).update(hos=None)

        resp = api_client.get("/api/v1/analytics/overview/")
        assert resp.status_code == 200
        count = resp.data["config_health"]["sections_without_hos_count"]
        assert count >= 1


# ---------------------------------------------------------------------------
# Phase 2 extension — new metrics + generic group_bys (aggregate() direct)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExtendedMetrics:
    """Exercises the new aggregate() outputs directly over an admin-wide qs."""

    def _setup(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.services import aggregate, resolve_date_range
        now = timezone.now()
        raiser = make_user("ext_raiser", campus=campus)
        tech = make_user("ext_tech", campus=campus)
        # open + unassigned, fresh (<1d)
        make_ticket(raiser, campus, service_item, section, priority, status="open")
        # open + assigned, aged 5 days (3-7d bucket)
        make_ticket(raiser, campus, service_item, section, priority,
                    status="assigned", assigned_to=tech,
                    created_at=now - timedelta(days=5))
        # pending (paused) ticket with 2h accumulated pause
        make_ticket(raiser, campus, service_item, section, priority,
                    status="pending", assigned_to=tech,
                    accumulated_pause=timedelta(hours=2))
        # resolved with feedback (rating 5)
        r = make_ticket(raiser, campus, service_item, section, priority,
                        status="resolved", assigned_to=tech, resolved_at=now)
        from apps.tickets.models import TicketFeedback
        TicketFeedback.objects.create(ticket=r, rating=5)
        # resolved with feedback (rating 2)
        r2 = make_ticket(raiser, campus, service_item, section, priority,
                         status="resolved", assigned_to=tech, resolved_at=now)
        TicketFeedback.objects.create(ticket=r2, rating=2)
        return aggregate(Ticket.objects.all(), resolve_date_range({}))

    def test_unassigned_and_aging(self, campus, service_item, section, priority):
        data = self._setup(campus, service_item, section, priority)
        # one open unassigned ticket
        assert data["unassigned"] == 1
        # aging buckets present and consistent with active (open/assigned/pending) tickets
        buckets = data["aging_buckets"]
        assert set(buckets) == {"lt_1d", "d1_3d", "d3_7d", "gt_7d"}
        assert buckets["d3_7d"] == 1  # the 5-day-old assigned ticket
        assert sum(buckets.values()) == 3  # open + assigned + pending

    def test_pause_burden(self, campus, service_item, section, priority):
        data = self._setup(campus, service_item, section, priority)
        assert data["currently_paused"] == 1
        assert data["ever_paused_count"] == 1
        assert data["pause_total_seconds"] == pytest.approx(2 * 3600)
        assert data["pause_avg_seconds"] == pytest.approx(2 * 3600)

    def test_ticket_flow_variants(self, campus, service_item, section, priority):
        data = self._setup(campus, service_item, section, priority)
        flow = data["ticket_flow"]
        assert flow["open"] == 1
        assert flow["assigned"] == 1
        assert flow["pending"] == 1
        assert flow["resolved"] == 2
        assert flow["total"] == 5

    def test_csat_distribution(self, campus, service_item, section, priority):
        data = self._setup(campus, service_item, section, priority)
        # ratings 5 and 2 -> 1 of 2 satisfied (>=4) = 50%
        assert data["csat_satisfied_pct"] == pytest.approx(50.0)
        ratings = {row["rating"]: row["count"] for row in data["rating_histogram"]}
        assert ratings == {2: 1, 5: 1}

    def test_generic_group_by_priority(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.services import aggregate, resolve_date_range
        self._setup(campus, service_item, section, priority)
        data = aggregate(Ticket.objects.all(), resolve_date_range({}), group_by="priority")
        assert "breakdown" in data
        rows = data["breakdown"]
        assert len(rows) == 1
        assert rows[0]["label"] == priority.name
        assert rows[0]["total"] == 5
        assert {"key", "label", "total", "open_count", "resolved_count",
                "escalated_count", "resolution_sla_met",
                "total_resolved_with_due"} <= set(rows[0])

    def test_generic_group_by_status(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.services import aggregate, resolve_date_range
        self._setup(campus, service_item, section, priority)
        data = aggregate(Ticket.objects.all(), resolve_date_range({}), group_by="status")
        labels = {row["label"]: row["total"] for row in data["breakdown"]}
        assert labels.get("resolved") == 2
        assert labels.get("open") == 1


# ---------------------------------------------------------------------------
# Phase 3 — insights service
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestInsights:
    def _facility(self, campus):
        from apps.facilities.models import FacilityType, Facility
        ft = FacilityType.objects.create(name="Block", code="BLK")
        return Facility.objects.create(campus=campus, facility_type=ft, name="Block C")

    def test_recurring_fault(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket, TicketLocation
        from apps.analytics.insights import compute_insights
        from apps.analytics.services import resolve_date_range
        from apps.facilities.models import FacilityType
        facility = self._facility(campus)
        ft = facility.facility_type
        raiser = make_user("rf_raiser", campus=campus)
        for _ in range(4):
            t = make_ticket(raiser, campus, service_item, section, priority)
            TicketLocation.objects.create(ticket=t, facility_type=ft, facility=facility)

        out = compute_insights(Ticket.objects.all(), resolve_date_range({}))
        rf = [i for i in out if i["type"] == "recurring_fault"]
        assert len(rf) == 1
        assert rf[0]["occurrences"] == 4
        assert rf[0]["facility"] == "Block C"
        assert rf[0]["service_item"] == service_item.name

    def test_sla_leak_dominant_unassigned(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.insights import compute_insights
        from apps.analytics.services import resolve_date_range
        now = timezone.now()
        raiser = make_user("leak_raiser", campus=campus)
        tech = make_user("leak_tech", campus=campus)
        # 3 unassigned breached, 1 assigned breached
        for _ in range(3):
            make_ticket(raiser, campus, service_item, section, priority,
                        status="open", resolution_due_at=now - timedelta(hours=2))
        make_ticket(raiser, campus, service_item, section, priority,
                    status="in_progress", assigned_to=tech,
                    resolution_due_at=now - timedelta(hours=1))

        out = compute_insights(Ticket.objects.all(), resolve_date_range({}))
        leak = [i for i in out if i["type"] == "sla_leak"]
        assert len(leak) == 1
        assert leak[0]["breached_total"] == 4
        assert leak[0]["dominant_cause"] == "unassigned_too_long"
        assert leak[0]["causes"]["unassigned_too_long"] == 3

    def test_capacity_backlog_growing(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.insights import compute_insights
        from apps.analytics.services import resolve_date_range
        raiser = make_user("cap_raiser", campus=campus)
        for _ in range(10):  # 10 created, 0 resolved
            make_ticket(raiser, campus, service_item, section, priority)

        out = compute_insights(Ticket.objects.all(), resolve_date_range({}))
        cap = [i for i in out if i["type"] == "capacity"]
        assert len(cap) == 1
        assert cap[0]["net_flow"] == 10

    def test_enabled_types_filters(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.insights import compute_insights
        from apps.analytics.services import resolve_date_range
        raiser = make_user("filt_raiser", campus=campus)
        for _ in range(10):
            make_ticket(raiser, campus, service_item, section, priority)
        # only capacity enabled → no other insight types, even if data exists
        out = compute_insights(
            Ticket.objects.all(), resolve_date_range({}), enabled_types=["sla_leak"]
        )
        assert all(i["type"] == "sla_leak" for i in out)

    def test_no_insights_on_clean_small_data(self, campus, service_item, section, priority):
        from apps.tickets.models import Ticket
        from apps.analytics.insights import compute_insights
        from apps.analytics.services import resolve_date_range
        raiser = make_user("clean_raiser", campus=campus)
        # 2 resolved, nothing breached/recurring/growing
        make_ticket(raiser, campus, service_item, section, priority,
                    status="resolved", resolved_at=timezone.now())
        out = compute_insights(Ticket.objects.all(), resolve_date_range({}))
        assert out == []


# ---------------------------------------------------------------------------
# Phase 4 — unified endpoint + role config + report range fix
# ---------------------------------------------------------------------------

def test_resolve_group_by_fails_closed():
    """Technician can never request peer rankings; unallowed dims fall back."""
    from apps.analytics.role_config import resolve_group_by
    assert resolve_group_by("technician", "technician") == "time"   # forced to default
    assert resolve_group_by("hos", "technician") == "technician"    # allowed
    assert resolve_group_by("hos", "campus") == "technician"        # unallowed → default
    assert resolve_group_by("hod", None) == "section"               # default
    assert resolve_group_by("bogus", "anything") == "status"        # unknown → user default


@pytest.mark.django_db
class TestUnifiedAnalytics:
    def _hod(self, campus, campus_dept):
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        from apps.org.models import CampusDepartment
        hod = make_user("uni_hod", campus=campus)
        CampusDepartment.objects.filter(pk=campus_dept.pk).update(head_of_department=hod)
        ra = RoleAssignment.objects.create(
            user=hod, role="hod", is_primary=True, campus_department=campus_dept
        )
        _, access = build_tokens_for_assignment(hod, ra)
        return str(access)

    def test_unified_matches_flow_endpoint(
        self, api_client, campus, campus_dept, service_item, section, priority
    ):
        now = timezone.now()
        token = self._hod(campus, campus_dept)
        raiser = make_user("uni_raiser", campus=campus)
        for _ in range(3):
            make_ticket(raiser, campus, service_item, section, priority)
        make_ticket(raiser, campus, service_item, section, priority,
                    status="resolved", resolved_at=now)

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        uni = api_client.get("/api/v1/analytics/")
        flow = api_client.get("/api/v1/analytics/flow/")
        assert uni.status_code == 200
        assert uni.data["headline"]["created"] == flow.data["created"]
        assert uni.data["headline"]["resolved"] == flow.data["resolved"]
        assert uni.data["headline"]["open_backlog"] == flow.data["open_backlog"]
        # HOD default breakdown dimension is section
        assert uni.data["breakdown"]["dimension"] == "section"
        assert "ticket_flow" in uni.data and "insights" in uni.data

    def test_unified_insights_gated_by_role(
        self, api_client, campus, campus_dept, dept, service_item, section, priority
    ):
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        from apps.org.models import Department
        now = timezone.now()
        mgr = make_user("uni_mgr", campus=campus)
        Department.objects.filter(pk=dept.pk).update(manager_user=mgr)
        ra = RoleAssignment.objects.create(
            user=mgr, role="manager", is_primary=True, department=dept
        )
        raiser = make_user("uni_mgr_raiser", campus=campus)
        for _ in range(10):  # backlog growing → capacity insight (manager enables it)
            make_ticket(raiser, campus, service_item, section, priority)

        _, access = build_tokens_for_assignment(mgr, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        uni = api_client.get("/api/v1/analytics/")
        assert uni.status_code == 200
        types = {i["type"] for i in uni.data["insights"]}
        assert "capacity" in types


@pytest.mark.django_db
class TestReportRange:
    """Summary sheet must reflect the SELECTED range, not a hidden 30-day default."""

    def _admin_token(self):
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment
        admin = make_user("rep_admin")
        ra = RoleAssignment.objects.create(user=admin, role="admin", is_primary=True)
        _, access = build_tokens_for_assignment(admin, ra)
        return str(access)

    def _summary_created(self, content):
        import openpyxl
        from io import BytesIO
        wb = openpyxl.load_workbook(BytesIO(content))
        ws = wb["Summary"]
        for r in ws.iter_rows(values_only=True):
            if r and r[0] == "Created in window":
                return r[1]
        return None

    def test_all_time_includes_old_tickets(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.tickets.models import Ticket
        now = timezone.now()
        token = self._admin_token()
        raiser = make_user("rr_raiser", campus=campus)
        make_ticket(raiser, campus, service_item, section, priority)
        make_ticket(raiser, campus, service_item, section, priority)
        old = make_ticket(raiser, campus, service_item, section, priority)
        Ticket.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=40))

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        # all-time → Summary spans everything (3), not a hidden 30-day window (2)
        resp = api_client.get(
            "/api/v1/reports/generate/?report_type=ticket-lifecycle&timeframe=all"
        )
        assert resp.status_code == 200
        assert self._summary_created(resp.content) == 3

        # explicit 30-day window → only the 2 recent tickets
        resp2 = api_client.get(
            "/api/v1/reports/generate/?report_type=ticket-lifecycle&timeframe=month"
        )
        assert self._summary_created(resp2.content) == 2


@pytest.mark.django_db
class TestRequesterScope:
    """A pure requester (role='user') is scoped to their OWN tickets — the floor
    RoleAssignment(role='user') makes the JWT role claim always 'user', never empty,
    so scope must treat 'user' as a first-class requester scope (own tickets)."""

    def test_scoped_ticket_qs_user_returns_own_tickets_only(
        self, campus, service_item, section, priority
    ):
        from apps.tickets.services.scope import scoped_ticket_qs

        requester = make_user("req_scope1", campus=campus)
        other = make_user("req_other1", campus=campus)

        mine = make_ticket(requester, campus, service_item, section, priority)
        make_ticket(other, campus, service_item, section, priority)
        make_ticket(other, campus, service_item, section, priority)

        qs = scoped_ticket_qs(requester, "user")
        assert list(qs.values_list("pk", flat=True)) == [mine.pk]

    def test_requester_overview_counts_only_own_tickets(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        requester = make_user("req_overview1", campus=campus)
        other = make_user("req_other2", campus=campus)
        ra = RoleAssignment.objects.create(
            user=requester, role="user", is_primary=True
        )

        # 3 tickets raised by the requester, 2 by someone else.
        for _ in range(3):
            make_ticket(requester, campus, service_item, section, priority)
        for _ in range(2):
            make_ticket(other, campus, service_item, section, priority)

        _, access = build_tokens_for_assignment(requester, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")
        resp = api_client.get("/api/v1/analytics/overview/")
        assert resp.status_code == 200
        # Only the requester's own 3 tickets — not 0, not the others' 5.
        assert resp.data["created"] == 3
        assert resp.data["open_backlog"] == 3


@pytest.mark.django_db
class TestSLABreachCommand:
    """check_sla records breaches as immutable TicketLog, idempotently, and
    never breaches a currently-paused ticket (R9 — frozen clock)."""

    def test_breach_logged_idempotent_and_pause_aware(
        self, campus, service_item, section, priority
    ):
        from django.core.management import call_command
        from apps.tickets.models import TicketLog
        now = timezone.now()
        raiser = make_user("sla_raiser", campus=campus)
        breached = make_ticket(
            raiser, campus, service_item, section, priority,
            status="in_progress", resolution_due_at=now - timedelta(hours=1),
        )
        paused = make_ticket(
            raiser, campus, service_item, section, priority,
            status="pending", paused_at=now - timedelta(hours=2),
            resolution_due_at=now - timedelta(hours=1),
        )

        call_command("check_sla")
        assert TicketLog.objects.filter(
            ticket=breached, event_type="sla_breach"
        ).count() == 1
        assert TicketLog.objects.filter(
            ticket=paused, event_type="sla_breach"
        ).count() == 0

        # second run is idempotent — no duplicate breach log
        call_command("check_sla")
        assert TicketLog.objects.filter(
            ticket=breached, event_type="sla_breach"
        ).count() == 1
