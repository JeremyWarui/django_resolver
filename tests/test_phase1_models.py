"""
Phase 1 acceptance tests — SoT §7 Phase 1.

Covers invariants R1–R3, R11, R17, D10, D12, JWT claims (SoT §3.6),
and the seed_reference management command.

Uses pytest + pytest-django. All tests target the 8-app layout (apps.*).
"""

import pytest
from datetime import timedelta
from django.utils import timezone


# ── shared fixtures ───────────────────────────────────────────────────────────

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
def user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def user_with_profile(user, campus):
    from apps.accounts.models import UserProfile
    UserProfile.objects.create(user=user, campus=campus)
    return user


@pytest.fixture
def ticket(user_with_profile, campus, service_item, section, priority):
    from apps.tickets.models import Ticket
    return Ticket.objects.create(
        raised_by=user_with_profile,
        requester_campus=campus,
        service_item=service_item,
        section=section,
        priority=priority,
    )


# ── R1: CampusDepartment unique (campus, department) ─────────────────────────

@pytest.mark.django_db
class TestR1CampusDepartmentUnique:

    def test_duplicate_raises(self, campus, dept):
        from apps.org.models import CampusDepartment
        CampusDepartment.objects.create(campus=campus, department=dept)
        with pytest.raises(Exception):
            CampusDepartment.objects.create(campus=campus, department=dept)

    def test_same_campus_different_dept_allowed(self, campus):
        from apps.org.models import CampusDepartment, Department
        d1 = Department.objects.create(name="HR", code="HR")
        d2 = Department.objects.create(name="Finance", code="FIN")
        CampusDepartment.objects.create(campus=campus, department=d1)
        cd2 = CampusDepartment.objects.create(campus=campus, department=d2)
        assert cd2.pk is not None

    def test_same_dept_different_campus_allowed(self, dept):
        from apps.org.models import CampusDepartment, Campus
        c1 = Campus.objects.create(name="Mombasa", code="MSA")
        c2 = Campus.objects.create(name="Kisumu", code="KSM")
        CampusDepartment.objects.create(campus=c1, department=dept)
        cd2 = CampusDepartment.objects.create(campus=c2, department=dept)
        assert cd2.pk is not None


# ── R2: Section.clean() — section_type.department == campus_department.department ──

@pytest.mark.django_db
class TestR2SectionTypeMatch:

    def test_mismatched_department_raises_validation_error(self, campus, dept):
        from apps.org.models import (
            CampusDepartment, Department, SectionType, Section
        )
        from django.core.exceptions import ValidationError

        other_dept = Department.objects.create(name="Finance2", code="FIN2")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st_other = SectionType.objects.create(
            department=other_dept, name="Payroll", code="PAY"
        )
        section = Section(campus_department=cd, section_type=st_other, is_active=True)
        with pytest.raises(ValidationError):
            section.clean()

    def test_matching_department_passes(self, campus_dept, section_type):
        from apps.org.models import Section
        section = Section(
            campus_department=campus_dept, section_type=section_type, is_active=True
        )
        section.clean()  # must not raise

    def test_r2_enforced_via_full_clean(self, campus, dept):
        from apps.org.models import (
            CampusDepartment, Department, SectionType, Section
        )
        from django.core.exceptions import ValidationError

        other_dept = Department.objects.create(name="Security3", code="SEC3")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st_other = SectionType.objects.create(
            department=other_dept, name="Gate", code="GAT"
        )
        section = Section(campus_department=cd, section_type=st_other, is_active=True)
        with pytest.raises(ValidationError):
            section.full_clean()


# ── R3: Section unique (campus_department, section_type) ─────────────────────

@pytest.mark.django_db
class TestR3SectionUnique:

    def test_duplicate_raises(self, campus_dept, section_type):
        from apps.org.models import Section
        Section.objects.create(
            campus_department=campus_dept, section_type=section_type, is_active=True
        )
        with pytest.raises(Exception):
            Section.objects.create(
                campus_department=campus_dept, section_type=section_type, is_active=True
            )

    def test_same_section_type_different_campus_dept_allowed(self, campus_dept, section_type):
        from apps.org.models import Campus, Section, CampusDepartment, Department
        Section.objects.create(
            campus_department=campus_dept, section_type=section_type, is_active=True
        )
        campus2 = Campus.objects.create(name="Eldoret", code="ELD")
        dept = campus_dept.department
        cd2 = CampusDepartment.objects.create(campus=campus2, department=dept)
        s2 = Section.objects.create(campus_department=cd2, section_type=section_type, is_active=True)
        assert s2.pk is not None


# ── R11: TicketLog is append-only / immutable ─────────────────────────────────

@pytest.mark.django_db
class TestR11TicketLogImmutable:

    def test_create_succeeds(self, ticket, user):
        from apps.tickets.models import TicketLog
        log = TicketLog.objects.create(
            ticket=ticket, actor=user, event_type="created", to_value="open"
        )
        assert log.pk is not None

    def test_update_raises(self, ticket, user):
        from apps.tickets.models import TicketLog
        log = TicketLog.objects.create(
            ticket=ticket, actor=user, event_type="created"
        )
        with pytest.raises(ValueError, match="immutable"):
            log.event_type = "status_changed"
            log.save()

    def test_delete_raises(self, ticket, user):
        from apps.tickets.models import TicketLog
        log = TicketLog.objects.create(
            ticket=ticket, actor=user, event_type="created"
        )
        with pytest.raises(ValueError, match="cannot be deleted"):
            log.delete()

    def test_system_log_null_actor_allowed(self, ticket):
        from apps.tickets.models import TicketLog
        log = TicketLog.objects.create(
            ticket=ticket, actor=None, event_type="escalated"
        )
        assert log.pk is not None
        assert log.actor is None


# ── D10: User.role is a derived property, not a stored field ─────────────────

@pytest.mark.django_db
class TestD10RoleProperty:

    def test_role_is_not_a_db_field(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        field_names = [f.name for f in User._meta.get_fields()]
        assert "role" not in field_names

    def test_role_none_without_assignment(self, user):
        assert user.role is None

    def test_role_reads_from_primary_assignment(self, user, section):
        from apps.accounts.models import RoleAssignment
        RoleAssignment.objects.create(
            user=user, role="technician", section=section, is_primary=True
        )
        user.refresh_from_db()
        assert user.role == "technician"

    def test_non_primary_does_not_set_role(self, user, section):
        from apps.accounts.models import RoleAssignment
        RoleAssignment.objects.create(
            user=user, role="hos", section=section, is_primary=False
        )
        assert user.role is None


# ── D12: Ticket holds only intrinsic current state ────────────────────────────

@pytest.mark.django_db
class TestD12TicketIntrinsicState:
    FORBIDDEN = [
        "sla_breached", "sla_warning_sent",
        "escalated_to", "escalated_at", "escalation_reason", "escalation_level",
        "rating", "rating_comment", "rated_at",
        "floor", "room", "area", "tenant_name", "unit_number",
        "title", "due_date", "campus_department",
        "requester",  # FK must be raised_by (D11)
    ]
    REQUIRED = [
        "ticket_no", "raised_by", "requester_campus", "service_item",
        "section", "priority", "assigned_to", "status", "current_level",
        "response_due_at", "resolution_due_at", "paused_at",
        "accumulated_pause", "created_at", "updated_at", "resolved_at", "closed_at",
    ]

    def _field_names(self):
        from apps.tickets.models import Ticket
        return [f.name for f in Ticket._meta.get_fields()]

    def test_forbidden_fields_absent(self):
        names = self._field_names()
        for f in self.FORBIDDEN:
            assert f not in names, f"Ticket must not have field '{f}' (SoT §3.2a)"

    def test_required_fields_present(self):
        names = self._field_names()
        for f in self.REQUIRED:
            assert f in names, f"Ticket must have field '{f}'"


# ── Ticket status choices — canonical set ────────────────────────────────────

@pytest.mark.django_db
class TestTicketStatusChoices:
    CANONICAL = {"open", "assigned", "in_progress", "pending", "resolved", "closed"}
    FORBIDDEN = {"pending_approval", "approved", "rejected", "escalated", "on_hold"}

    def test_exact_status_set(self):
        from apps.tickets.models import Ticket
        actual = {v for v, _ in Ticket.STATUS}
        assert actual == self.CANONICAL

    def test_no_forbidden_statuses(self):
        from apps.tickets.models import Ticket
        actual = {v for v, _ in Ticket.STATUS}
        assert not (actual & self.FORBIDDEN), f"Forbidden statuses found: {actual & self.FORBIDDEN}"

    def test_level_choices(self):
        from apps.tickets.models import Ticket
        actual = {v for v, _ in Ticket.LEVEL}
        assert actual == {"technician", "hos", "hod"}


# ── R17: RoleAssignment scope validation ─────────────────────────────────────

@pytest.mark.django_db
class TestR17RoleAssignmentScope:

    def test_technician_without_section_raises(self, user):
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError
        ra = RoleAssignment(user=user, role="technician")
        with pytest.raises(ValidationError):
            ra.clean()

    def test_technician_with_section_passes(self, user, section):
        from apps.accounts.models import RoleAssignment
        ra = RoleAssignment(user=user, role="technician", section=section)
        ra.clean()

    def test_hos_without_section_raises(self, user):
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError
        ra = RoleAssignment(user=user, role="hos")
        with pytest.raises(ValidationError):
            ra.clean()

    def test_hod_without_campus_department_raises(self, user):
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError
        ra = RoleAssignment(user=user, role="hod")
        with pytest.raises(ValidationError):
            ra.clean()

    def test_hod_with_campus_department_passes(self, user, campus_dept):
        from apps.accounts.models import RoleAssignment
        ra = RoleAssignment(user=user, role="hod", campus_department=campus_dept)
        ra.clean()

    def test_manager_without_department_raises(self, user):
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError
        ra = RoleAssignment(user=user, role="manager")
        with pytest.raises(ValidationError):
            ra.clean()

    def test_manager_with_department_passes(self, user, dept):
        from apps.accounts.models import RoleAssignment
        ra = RoleAssignment(user=user, role="manager", department=dept)
        ra.clean()

    def test_admin_with_scope_raises(self, user, section):
        from apps.accounts.models import RoleAssignment
        from django.core.exceptions import ValidationError
        ra = RoleAssignment(user=user, role="admin", section=section)
        with pytest.raises(ValidationError):
            ra.clean()

    def test_admin_without_scope_passes(self, user):
        from apps.accounts.models import RoleAssignment
        ra = RoleAssignment(user=user, role="admin")
        ra.clean()

    def test_one_primary_per_user_constraint(self, user, section):
        from apps.accounts.models import RoleAssignment
        RoleAssignment.objects.create(user=user, role="admin", is_primary=True)
        with pytest.raises(Exception):
            RoleAssignment.objects.create(
                user=user, role="technician", section=section, is_primary=True
            )

    def test_is_active_false_when_expired(self, user):
        from apps.accounts.models import RoleAssignment
        past = timezone.now() - timedelta(hours=1)
        ra = RoleAssignment(user=user, role="admin", valid_until=past)
        assert ra.is_active() is False

    def test_is_active_true_within_window(self, user):
        from apps.accounts.models import RoleAssignment
        future = timezone.now() + timedelta(days=7)
        ra = RoleAssignment(user=user, role="admin", valid_until=future)
        assert ra.is_active() is True

    def test_is_active_true_no_window(self, user):
        from apps.accounts.models import RoleAssignment
        ra = RoleAssignment(user=user, role="admin")
        assert ra.is_active() is True


# ── JWT login claims (SoT §3.6) ──────────────────────────────────────────────

@pytest.mark.django_db
class TestJWTLoginClaims:

    @pytest.fixture(autouse=True)
    def setup(self, db):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import RoleAssignment, UserProfile
        from apps.org.models import Campus

        User = get_user_model()
        self.campus = Campus.objects.create(name="JWT Campus", code="JWT")
        self.user = User.objects.create_user(username="jwt_user", password="jwtpass")
        UserProfile.objects.create(user=self.user, campus=self.campus)
        self.ra = RoleAssignment.objects.create(
            user=self.user, role="admin", is_primary=True
        )

    def test_login_returns_200(self, client):
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "jwtpass"},
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_access_token_present(self, client):
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "jwtpass"},
            content_type="application/json",
        )
        data = resp.json()
        assert "accessToken" in data
        assert isinstance(data["accessToken"], str)

    def test_token_has_role_claim(self, client):
        from rest_framework_simplejwt.tokens import AccessToken
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "jwtpass"},
            content_type="application/json",
        )
        token = AccessToken(resp.json()["accessToken"])
        assert token["role"] == "admin"

    def test_token_has_sub_claim(self, client):
        from rest_framework_simplejwt.tokens import AccessToken
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "jwtpass"},
            content_type="application/json",
        )
        token = AccessToken(resp.json()["accessToken"])
        assert int(token["sub"]) == self.user.pk

    def test_token_has_campus_id_claim(self, client):
        from rest_framework_simplejwt.tokens import AccessToken
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "jwtpass"},
            content_type="application/json",
        )
        token = AccessToken(resp.json()["accessToken"])
        assert "campus_id" in token.payload
        assert token["campus_id"] == self.campus.pk

    def test_token_has_role_assignment_id_claim(self, client):
        from rest_framework_simplejwt.tokens import AccessToken
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "jwtpass"},
            content_type="application/json",
        )
        token = AccessToken(resp.json()["accessToken"])
        assert "role_assignment_id" in token.payload
        assert token["role_assignment_id"] == self.ra.pk

    def test_invalid_credentials_returns_401(self, client):
        resp = client.post(
            "/api/auth/login/",
            data={"username": "jwt_user", "password": "wrong"},
            content_type="application/json",
        )
        assert resp.status_code == 401

    def test_technician_token_carries_section_id(self, db):
        from django.test import Client
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken
        from apps.accounts.models import RoleAssignment, UserProfile
        from apps.org.models import Campus, Department, CampusDepartment, SectionType, Section

        User = get_user_model()
        campus = Campus.objects.create(name="TechCampus", code="TCH")
        dept = Department.objects.create(name="TechDept", code="TDT")
        cd = CampusDepartment.objects.create(campus=campus, department=dept)
        st = SectionType.objects.create(department=dept, name="Networks2", code="NET2")
        section = Section.objects.create(campus_department=cd, section_type=st, is_active=True)

        tech = User.objects.create_user(username="tech_jwt", password="techpass")
        UserProfile.objects.create(user=tech, campus=campus)
        RoleAssignment.objects.create(
            user=tech, role="technician", section=section, is_primary=True
        )

        c = Client()
        resp = c.post(
            "/api/auth/login/",
            data={"username": "tech_jwt", "password": "techpass"},
            content_type="application/json",
        )
        assert resp.status_code == 200
        token = AccessToken(resp.json()["accessToken"])
        assert token["role"] == "technician"
        assert token["section_id"] == section.pk


# ── seed_reference management command ────────────────────────────────────────

@pytest.mark.django_db
class TestSeedReference:

    @pytest.fixture(autouse=True)
    def run_seed(self, db):
        from django.core.management import call_command
        call_command("seed_reference", verbosity=0)

    def test_five_facility_types(self):
        from apps.facilities.models import FacilityType
        codes = set(FacilityType.objects.values_list("code", flat=True))
        assert codes == {"office_block", "building", "equipment", "residential", "grounds"}

    def test_four_priorities(self):
        from apps.sla.models import Priority
        assert Priority.objects.count() == 4
        ranks = sorted(Priority.objects.values_list("rank", flat=True))
        assert ranks == [1, 2, 3, 4]

    def test_sla_minutes_positive_and_ordered(self):
        from apps.sla.models import Priority
        for p in Priority.objects.all():
            assert p.response_minutes > 0
            assert p.resolution_minutes > 0
            assert p.resolution_minutes > p.response_minutes

    def test_eight_escalation_rules(self):
        from apps.sla.models import EscalationRule
        assert EscalationRule.objects.count() == 8

    def test_two_rules_per_priority(self):
        from apps.sla.models import Priority, EscalationRule
        for p in Priority.objects.all():
            count = EscalationRule.objects.filter(priority=p).count()
            assert count == 2, f"Priority '{p.name}' must have 2 escalation rules"

    def test_each_priority_has_hos_and_hod_rung(self):
        from apps.sla.models import Priority, EscalationRule
        for p in Priority.objects.all():
            levels = set(
                EscalationRule.objects.filter(priority=p).values_list("to_level", flat=True)
            )
            assert "hos" in levels, f"Priority '{p.name}' missing HOS rung"
            assert "hod" in levels, f"Priority '{p.name}' missing HOD rung"

    def test_seed_idempotent(self):
        from django.core.management import call_command
        from apps.facilities.models import FacilityType
        from apps.sla.models import Priority, EscalationRule
        call_command("seed_reference", verbosity=0)
        assert FacilityType.objects.count() == 5
        assert Priority.objects.count() == 4
        assert EscalationRule.objects.count() == 8
