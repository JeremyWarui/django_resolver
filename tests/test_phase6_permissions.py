"""Phase 6 — object-level permissions, scoped ticket list/detail, ?mine=1 (R15).

Acceptance criteria:
- Each role (technician/HOS/HOD/manager/admin) sees exactly their scope
- Cross-scope access is denied (403 or excluded from list)
- ?mine=1 works for a plain user AND for staff
- A user with an active cover assignment sees the covered scope
- Unauthenticated requests → 401
"""

import pytest
from datetime import timedelta

from django.utils import timezone
from rest_framework.test import APIClient

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
def campus_dept(campus, dept):
    from apps.org.models import CampusDepartment

    return CampusDepartment.objects.create(campus=campus, department=dept)


@pytest.fixture
def campus_dept2(campus, dept2):
    from apps.org.models import CampusDepartment

    return CampusDepartment.objects.create(campus=campus, department=dept2)


@pytest.fixture
def section_type(dept):
    from apps.org.models import SectionType

    return SectionType.objects.create(department=dept, name="Software", code="SW")


@pytest.fixture
def section_type2(dept):
    from apps.org.models import SectionType

    return SectionType.objects.create(department=dept, name="Networks", code="NET")


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


def make_user(
    username,
    campus=None,
    role=None,
    section=None,
    campus_department=None,
    department=None,
):
    """Create a user with optional profile and primary RoleAssignment."""
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


def make_ticket(raised_by, campus, service_item, section, priority):
    from apps.tickets.models import Ticket

    return Ticket.objects.create(
        raised_by=raised_by,
        requester_campus=campus,
        service_item=service_item,
        section=section,
        priority=priority,
    )


# ---------------------------------------------------------------------------
# TestTicketListScoping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketListScoping:

    def test_unauthenticated_returns_401(self, api_client):
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 401

    def test_plain_user_no_role_returns_empty_list(
        self, api_client, campus, service_item, section, priority
    ):
        user = make_user("plain", campus=campus)
        raiser = make_user("raiser", campus=campus)
        make_ticket(raiser, campus, service_item, section, priority)
        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_technician_sees_own_section_tickets(
        self, api_client, campus, service_item, section, section2, priority
    ):
        from apps.org.models import SectionTechnician

        tech = make_user("tech1", campus=campus, role="technician", section=section)
        SectionTechnician.objects.create(user=tech, section=section)
        raiser = make_user("raiser1", campus=campus)

        ticket_mine = make_ticket(raiser, campus, service_item, section, priority)
        make_ticket(raiser, campus, service_item, section2, priority)  # other section

        api_client.force_authenticate(user=tech)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert ticket_mine.id in ids
        assert len(ids) == 1

    def test_technician_with_no_section_technician_link_sees_nothing(
        self, api_client, campus, service_item, section, priority
    ):
        tech = make_user(
            "tech_nolink", campus=campus, role="technician", section=section
        )
        raiser = make_user("raiser2", campus=campus)
        make_ticket(raiser, campus, service_item, section, priority)

        api_client.force_authenticate(user=tech)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        assert response.data["count"] == 0

    def test_hos_sees_own_section_tickets(
        self, api_client, campus, service_item, section, section2, priority
    ):
        hos = make_user("hos1", campus=campus, role="hos", section=section)
        section.hos = hos
        section.save()

        raiser = make_user("raiser3", campus=campus)
        ticket_mine = make_ticket(raiser, campus, service_item, section, priority)
        make_ticket(raiser, campus, service_item, section2, priority)

        api_client.force_authenticate(user=hos)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert ticket_mine.id in ids
        assert len(ids) == 1

    def test_hod_sees_all_tickets_in_campus_dept(
        self, api_client, campus, campus_dept, service_item, section, section2, priority
    ):
        hod = make_user(
            "hod1", campus=campus, role="hod", campus_department=campus_dept
        )
        campus_dept.head_of_department = hod
        campus_dept.save()

        raiser = make_user("raiser4", campus=campus)
        t1 = make_ticket(raiser, campus, service_item, section, priority)
        t2 = make_ticket(raiser, campus, service_item, section2, priority)

        api_client.force_authenticate(user=hod)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t1.id in ids
        assert t2.id in ids

    def test_manager_sees_all_dept_tickets_across_sections(
        self,
        api_client,
        campus,
        dept,
        campus_dept,
        service_item,
        section,
        section2,
        priority,
    ):
        mgr = make_user("mgr1", campus=campus, role="manager", department=dept)
        dept.manager_user = mgr
        dept.save()

        raiser = make_user("raiser5", campus=campus)
        t1 = make_ticket(raiser, campus, service_item, section, priority)
        t2 = make_ticket(raiser, campus, service_item, section2, priority)

        api_client.force_authenticate(user=mgr)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t1.id in ids
        assert t2.id in ids

    def test_admin_sees_all_tickets(
        self,
        api_client,
        campus,
        service_item,
        section,
        section2,
        priority,
        campus_dept2,
    ):
        from apps.org.models import SectionType, Section

        admin_user = make_user("admin1", campus=campus, role="admin")

        # Create ticket in a completely different dept's section.
        from apps.org.models import SectionType, Department

        dept3 = Department.objects.create(name="HR", code="HR")
        st3 = SectionType.objects.create(department=dept3, name="Recruit", code="REC")
        from apps.org.models import CampusDepartment

        cd3 = CampusDepartment.objects.create(campus=campus, department=dept3)
        s3 = Section.objects.create(campus_department=cd3, section_type=st3)

        raiser = make_user("raiser6", campus=campus)
        t1 = make_ticket(raiser, campus, service_item, section, priority)
        t2 = make_ticket(raiser, campus, service_item, s3, priority)

        api_client.force_authenticate(user=admin_user)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t1.id in ids
        assert t2.id in ids

    def test_hos_with_active_cover_sees_covered_section(
        self, api_client, campus, service_item, section, section2, priority
    ):
        """After switch-role to the cover HOS assignment, user sees the covered section."""
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        cover_user = make_user(
            "cover_hos", campus=campus, role="technician", section=section
        )
        raiser = make_user("raiser7", campus=campus)
        covered_ticket = make_ticket(raiser, campus, service_item, section2, priority)

        cover_ra = RoleAssignment.objects.create(
            user=cover_user,
            role="hos",
            section=section2,
            is_primary=False,
            valid_until=timezone.now() + timedelta(days=7),
        )

        # Simulate switch-role: issue a JWT scoped to the cover HOS assignment.
        _, access = build_tokens_for_assignment(cover_user, cover_ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert covered_ticket.id in ids


# ---------------------------------------------------------------------------
# TestMineFilter — R15 universal requester
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMineFilter:

    def test_plain_user_sees_only_own_tickets(
        self, api_client, campus, service_item, section, priority
    ):
        user_a = make_user("mine_a", campus=campus)
        user_b = make_user("mine_b", campus=campus)
        t_a = make_ticket(user_a, campus, service_item, section, priority)
        make_ticket(user_b, campus, service_item, section, priority)

        api_client.force_authenticate(user=user_a)
        response = api_client.get("/api/v1/tickets/?mine=1")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t_a.id in ids
        assert len(ids) == 1

    def test_staff_mine_returns_own_tickets_not_section_queue(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician

        tech = make_user("mine_tech", campus=campus, role="technician", section=section)
        SectionTechnician.objects.create(user=tech, section=section)

        other = make_user("mine_other", campus=campus)
        section_ticket = make_ticket(other, campus, service_item, section, priority)
        own_ticket = make_ticket(tech, campus, service_item, section, priority)

        api_client.force_authenticate(user=tech)
        response = api_client.get("/api/v1/tickets/?mine=1")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        # Own ticket visible; section queue ticket by other user NOT included.
        assert own_ticket.id in ids
        assert section_ticket.id not in ids

    def test_mine_cross_user_isolation(
        self, api_client, campus, service_item, section, priority
    ):
        user_x = make_user("mine_x", campus=campus)
        user_y = make_user("mine_y", campus=campus)
        make_ticket(user_x, campus, service_item, section, priority)
        t_y = make_ticket(user_y, campus, service_item, section, priority)

        api_client.force_authenticate(user=user_y)
        response = api_client.get("/api/v1/tickets/?mine=1")
        ids = [r["id"] for r in response.data["results"]]
        assert len(ids) == 1
        assert t_y.id in ids


# ---------------------------------------------------------------------------
# TestTicketDetail — R15 + scoping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTicketDetail:

    def test_requester_can_view_own_ticket(
        self, api_client, campus, service_item, section, priority
    ):
        user = make_user("det_requester", campus=campus)
        ticket = make_ticket(user, campus, service_item, section, priority)
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")
        assert response.status_code == 200
        assert response.data["ticket_no"] == ticket.ticket_no

    def test_technician_can_view_section_ticket(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician

        tech = make_user("det_tech", campus=campus, role="technician", section=section)
        SectionTechnician.objects.create(user=tech, section=section)
        raiser = make_user("det_raiser", campus=campus)
        ticket = make_ticket(raiser, campus, service_item, section, priority)

        api_client.force_authenticate(user=tech)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")
        assert response.status_code == 200

    def test_technician_cannot_view_other_section_ticket(
        self, api_client, campus, service_item, section, section2, priority
    ):
        from apps.org.models import SectionTechnician

        tech = make_user("det_tech2", campus=campus, role="technician", section=section)
        SectionTechnician.objects.create(user=tech, section=section)
        raiser = make_user("det_raiser2", campus=campus)
        ticket = make_ticket(raiser, campus, service_item, section2, priority)

        api_client.force_authenticate(user=tech)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")
        assert response.status_code == 403

    def test_unauthenticated_returns_401(
        self, api_client, campus, service_item, section, priority
    ):
        user = make_user("det_anon", campus=campus)
        ticket = make_ticket(user, campus, service_item, section, priority)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")
        assert response.status_code == 401

    def test_ticket_response_includes_expected_fields(
        self, api_client, campus, service_item, section, priority
    ):
        user = make_user("det_fields", campus=campus)
        ticket = make_ticket(user, campus, service_item, section, priority)
        api_client.force_authenticate(user=user)
        response = api_client.get(f"/api/v1/tickets/{ticket.id}/")
        assert response.status_code == 200
        for field in (
            "ticket_no",
            "status",
            "current_level",
            "priority",
            "service_item",
            "is_breaching",
        ):
            assert field in response.data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# TestStatusFilters
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStatusFilters:

    def test_filter_by_status(
        self, api_client, campus, service_item, section, priority
    ):
        from apps.org.models import SectionTechnician

        tech = make_user("filt_tech", campus=campus, role="technician", section=section)
        SectionTechnician.objects.create(user=tech, section=section)
        raiser = make_user("filt_raiser", campus=campus)

        t_open = make_ticket(raiser, campus, service_item, section, priority)
        t_resolved = make_ticket(raiser, campus, service_item, section, priority)
        from apps.tickets.models import Ticket

        Ticket.objects.filter(pk=t_resolved.pk).update(status="resolved")

        api_client.force_authenticate(user=tech)
        response = api_client.get("/api/v1/tickets/?status=open")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t_open.id in ids
        assert t_resolved.id not in ids


# ---------------------------------------------------------------------------
# TestNegativeScopeBoundaries — HOD / Manager cross-scope isolation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNegativeScopeBoundaries:
    """Negative tests: each role sees ZERO tickets outside their scope boundary."""

    def test_hod_sees_zero_from_other_campus_dept(
        self,
        api_client,
        campus,
        dept,
        campus_dept,
        campus_dept2,
        section,
        section2,
        service_item,
        priority,
    ):
        """HOD of campus-dept A sees zero tickets belonging to campus-dept B."""
        hod_a = make_user(
            "neg_hod_a", campus=campus, role="hod", campus_department=campus_dept
        )
        campus_dept.head_of_department = hod_a
        campus_dept.save()

        raiser = make_user("neg_raiser_a", campus=campus)
        # ticket in campus_dept (scope A) — should be visible
        t_a = make_ticket(raiser, campus, service_item, section, priority)
        # ticket in campus_dept2 (scope B) — must be invisible to hod_a
        from apps.org.models import SectionType, Section

        st2 = SectionType.objects.create(
            department=campus_dept2.department, name="NegST2", code="NST2"
        )
        s_b = Section.objects.create(campus_department=campus_dept2, section_type=st2)
        from apps.sla.models import Priority
        from apps.catalog.models import ServiceCategory, ServiceItem

        cat_b = ServiceCategory.objects.create(
            section_type=st2,
            name="NegCat2",
            location_details=False,
            default_priority=priority,
        )
        item_b = ServiceItem.objects.create(category=cat_b, name="NegItem2")
        t_b = make_ticket(raiser, campus, item_b, s_b, priority)

        api_client.force_authenticate(user=hod_a)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t_a.id in ids
        assert t_b.id not in ids

    def test_manager_sees_zero_from_other_dept(
        self, api_client, campus, dept, campus_dept, section, service_item, priority
    ):
        """Manager of dept X sees zero tickets belonging to an unrelated dept Y."""
        mgr_x = make_user("neg_mgr_x", campus=campus, role="manager", department=dept)
        dept.manager_user = mgr_x
        dept.save()

        # dept_y — completely different department
        from apps.org.models import Department, SectionType, CampusDepartment, Section

        dept_y = Department.objects.create(name="NegDeptY", code="NDY")
        cd_y = CampusDepartment.objects.create(campus=campus, department=dept_y)
        st_y = SectionType.objects.create(department=dept_y, name="NegSTY", code="NSTY")
        s_y = Section.objects.create(campus_department=cd_y, section_type=st_y)
        from apps.catalog.models import ServiceCategory, ServiceItem

        cat_y = ServiceCategory.objects.create(
            section_type=st_y,
            name="NegCatY",
            location_details=False,
            default_priority=priority,
        )
        item_y = ServiceItem.objects.create(category=cat_y, name="NegItemY")

        raiser = make_user("neg_raiser_mgr", campus=campus)
        t_x = make_ticket(raiser, campus, service_item, section, priority)
        t_y = make_ticket(raiser, campus, item_y, s_y, priority)

        api_client.force_authenticate(user=mgr_x)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t_x.id in ids
        assert t_y.id not in ids

    def test_manager_sees_dept_across_multiple_campuses(
        self, api_client, campus, campus2, dept, section, service_item, priority
    ):
        """Manager of dept X sees tickets at ALL campuses, not just their home campus."""
        from apps.org.models import CampusDepartment, SectionType, Section

        mgr = make_user("neg_mgr_multi", campus=campus, role="manager", department=dept)
        dept.manager_user = mgr
        dept.save()

        # same dept at campus2
        cd_c2 = CampusDepartment.objects.create(campus=campus2, department=dept)
        # section_type is already linked to dept; create a section at campus2
        from apps.org.models import SectionType

        st2 = SectionType.objects.create(department=dept, name="NegNet2", code="NN2")
        s_c2 = Section.objects.create(campus_department=cd_c2, section_type=st2)
        from apps.catalog.models import ServiceCategory, ServiceItem

        cat_c2 = ServiceCategory.objects.create(
            section_type=st2,
            name="NegCat_C2",
            location_details=False,
            default_priority=priority,
        )
        item_c2 = ServiceItem.objects.create(category=cat_c2, name="NegItem_C2")

        raiser = make_user("neg_raiser_multi", campus=campus)
        t_c1 = make_ticket(raiser, campus, service_item, section, priority)
        t_c2 = make_ticket(raiser, campus2, item_c2, s_c2, priority)

        api_client.force_authenticate(user=mgr)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        assert t_c1.id in ids
        assert t_c2.id in ids


# ---------------------------------------------------------------------------
# TestFailClosed — unresolvable scope must return NONE, never everything
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFailClosed:

    def test_user_with_role_but_no_structural_assignment_gets_empty(
        self, api_client, campus, service_item, section, priority
    ):
        """User with role=hod in JWT but no matching head_of_department FK → empty queryset.

        This specifically tests the fail-closed path: if the scope resolver can't
        resolve a structural assignment it must return none(), not the unfiltered set.
        """
        from apps.accounts.models import RoleAssignment
        from apps.org.models import CampusDepartment, Department
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        # Create an HOD RoleAssignment but deliberately do NOT set
        # campus_department.head_of_department — the structural FK is absent.
        dept_fc = Department.objects.create(name="FCDept", code="FCD")
        cd_fc = CampusDepartment.objects.create(campus=campus, department=dept_fc)
        user_fc = make_user("fail_closed_hod", campus=campus)
        ra = RoleAssignment.objects.create(
            user=user_fc,
            role="hod",
            campus_department=cd_fc,
            is_primary=True,
        )
        # NOTE: cd_fc.head_of_department is intentionally NOT set to user_fc

        raiser = make_user("fc_raiser", campus=campus)
        make_ticket(raiser, campus, service_item, section, priority)

        # Issue a JWT scoped to the HOD assignment.
        _, access = build_tokens_for_assignment(user_fc, ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        # Must return NONE — not the unfiltered queryset.
        assert response.data["count"] == 0

    def test_role_none_returns_empty_not_all_tickets(
        self, api_client, campus, service_item, section, priority
    ):
        """A user with no role gets an empty queryset, not everything (R15 aside)."""
        plain = make_user("fc_plain2", campus=campus)
        raiser = make_user("fc_raiser2", campus=campus)
        make_ticket(raiser, campus, service_item, section, priority)

        api_client.force_authenticate(user=plain)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        assert response.data["count"] == 0


# ---------------------------------------------------------------------------
# TestTechnicianScopeSubset — individual ⊂ sectional
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTechnicianScopeSubset:

    def test_technician_sees_others_assigned_tickets_in_same_section(
        self, api_client, campus, service_item, section, priority
    ):
        """Sectional scope includes tickets assigned to OTHER techs in the same section.

        Verifies that assigned_to=self (individual) is a strict subset of section scope:
        a ticket assigned to tech B is visible to tech A through sectional scope.
        """
        from apps.org.models import SectionTechnician

        tech_a = make_user(
            "sub_tech_a", campus=campus, role="technician", section=section
        )
        tech_b = make_user(
            "sub_tech_b", campus=campus, role="technician", section=section
        )
        SectionTechnician.objects.create(user=tech_a, section=section)
        SectionTechnician.objects.create(user=tech_b, section=section)

        raiser = make_user("sub_raiser", campus=campus)
        t_assigned_a = make_ticket(raiser, campus, service_item, section, priority)
        t_assigned_b = make_ticket(raiser, campus, service_item, section, priority)
        # Assign tickets
        from apps.tickets.models import Ticket

        Ticket.objects.filter(pk=t_assigned_a.pk).update(
            assigned_to=tech_a, status="assigned"
        )
        Ticket.objects.filter(pk=t_assigned_b.pk).update(
            assigned_to=tech_b, status="assigned"
        )

        api_client.force_authenticate(user=tech_a)
        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        # Sectional scope: both tickets visible (individual ⊂ sectional)
        assert t_assigned_a.id in ids
        assert t_assigned_b.id in ids


# ---------------------------------------------------------------------------
# TestExpiredCoverScope — expired cover assignment grants nothing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExpiredCoverScope:

    def test_expired_cover_grants_no_scope(
        self, api_client, campus, service_item, section, section2, priority
    ):
        """An expired cover assignment must NOT extend the user's ticket scope.

        We bypass switch-role (which already checks is_active) and issue a JWT
        for the expired cover directly, so the test exercises the scope resolver's
        _active_q guard rather than the switch-role guard.
        """
        from apps.accounts.models import RoleAssignment
        from apps.accounts.jwt_utils import build_tokens_for_assignment

        user = make_user(
            "exp_cover_user", campus=campus, role="technician", section=section
        )
        raiser = make_user("exp_cover_raiser", campus=campus)
        covered_ticket = make_ticket(raiser, campus, service_item, section2, priority)

        expired_ra = RoleAssignment.objects.create(
            user=user,
            role="hos",
            section=section2,
            is_primary=False,
            valid_until=timezone.now() - timedelta(days=1),  # already expired
        )

        # Issue a JWT scoped to the expired cover (bypassing is_active check).
        _, access = build_tokens_for_assignment(user, expired_ra)
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(access)}")

        response = api_client.get("/api/v1/tickets/")
        assert response.status_code == 200
        ids = [r["id"] for r in response.data["results"]]
        # Expired cover must grant no access to section2 tickets.
        assert covered_ticket.id not in ids
