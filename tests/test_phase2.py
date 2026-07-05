"""
Phase 2 acceptance tests — SoT §7 Phase 2.

Covers:
  - R4: ServiceCategory has no department FK (derived via section_type.department)
  - R5: Catalogue visibility — campus-filtered /catalog/ endpoint
  - §3.7 pagination shapes (config lists: PageNumber; append-only feeds: cursor envelope)
  - §5.2 admin CRUD endpoints (access control + basic CRUD smoke)
  - FacilityTypeViewSet read-only (D9)

Uses pytest + pytest-django. All tests target the 8-app layout (apps.*).
"""

import pytest
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

# ── fixtures ──────────────────────────────────────────────────────────────────


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
def inactive_section(campus_dept, section_type):
    from apps.org.models import Section

    return Section.objects.create(
        campus_department=campus_dept, section_type=section_type, is_active=False
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
        is_active=True,
    )


@pytest.fixture
def service_item(service_category, priority):
    from apps.catalog.models import ServiceItem

    return ServiceItem.objects.create(
        category=service_category,
        name="No Internet",
        is_active=True,
    )


@pytest.fixture
def admin_group(db):
    group, _ = Group.objects.get_or_create(name="admin")
    return group


@pytest.fixture
def admin_user(db):
    from apps.accounts.models import CustomUser, RoleAssignment

    user = CustomUser.objects.create_user(username="adminuser", password="pass")
    RoleAssignment.objects.create(user=user, role="admin", is_primary=True)
    return user


@pytest.fixture
def regular_user(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create_user(username="regular", password="pass")


# ── R4: No department FK on ServiceCategory ───────────────────────────────────


@pytest.mark.django_db
def test_service_category_has_no_department_field():
    """R4: ServiceCategory must NOT have a 'department' database field."""
    from apps.catalog.models import ServiceCategory

    field_names = [f.name for f in ServiceCategory._meta.get_fields()]
    assert "department" not in field_names, (
        "ServiceCategory must not have a 'department' DB field (R4); "
        "department derives via section_type.department"
    )


@pytest.mark.django_db
def test_service_category_serializer_department_is_derived(service_category):
    """R4: ServiceCategorySerializer must expose 'department' as a derived read-only field."""
    from apps.catalog.serializers import ServiceCategorySerializer

    data = ServiceCategorySerializer(service_category).data
    assert "department" in data, "Serializer must expose 'department' key"
    dept = data["department"]
    assert dept["id"] == service_category.section_type.department.id
    assert dept["code"] == service_category.section_type.department.code


@pytest.mark.django_db
def test_service_category_serializer_department_not_writable(
    service_category, priority, section_type
):
    """R4: 'department' must not be accepted as a write field."""
    from apps.catalog.serializers import ServiceCategorySerializer

    payload = {
        "section_type": section_type.id,
        "name": "New Category",
        "default_priority": priority.id,
        "department": 999,  # should be silently ignored
    }
    s = ServiceCategorySerializer(data=payload)
    assert s.is_valid(), s.errors
    # department should not appear in validated_data
    assert "department" not in s.validated_data


# ── R5: Catalogue visibility ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_catalog_shows_active_section(
    api_client, regular_user, campus, active_section, service_category
):
    """R5: Category IS visible when an active section exists at the campus."""
    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/catalog/", {"campus": campus.id})
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.data["results"]]
    assert service_category.id in ids


@pytest.mark.django_db
def test_catalog_hides_inactive_section(
    api_client, regular_user, campus, inactive_section, service_category
):
    """R5: Category is NOT visible when only inactive sections exist at the campus."""
    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/catalog/", {"campus": campus.id})
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.data["results"]]
    assert service_category.id not in ids


@pytest.mark.django_db
def test_catalog_campus_isolation(
    api_client,
    regular_user,
    campus,
    campus_b,
    active_section,  # section at campus, not campus_b
    service_category,
):
    """R5: Category visible at campus A must not appear at campus B if B has no matching section."""
    api_client.force_authenticate(user=regular_user)

    resp_a = api_client.get("/api/v1/catalog/", {"campus": campus.id})
    assert resp_a.status_code == 200
    ids_a = [item["id"] for item in resp_a.data["results"]]
    assert service_category.id in ids_a, "Category should appear at campus A"

    resp_b = api_client.get("/api/v1/catalog/", {"campus": campus_b.id})
    assert resp_b.status_code == 200
    ids_b = [item["id"] for item in resp_b.data["results"]]
    assert service_category.id not in ids_b, "Category must not appear at campus B"


@pytest.mark.django_db
def test_catalog_requires_campus_param(api_client, regular_user):
    """R5: GET /catalog/ without ?campus → 400."""
    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/catalog/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_catalog_requires_authentication(api_client):
    """Unauthenticated request to /catalog/ → 401."""
    resp = api_client.get("/api/v1/catalog/", {"campus": 1})
    assert resp.status_code == 401


@pytest.mark.django_db
def test_catalog_response_includes_items(
    api_client, regular_user, campus, active_section, service_category, service_item
):
    """Categories in the catalogue tree include their nested service items."""
    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/catalog/", {"campus": campus.id})
    assert resp.status_code == 200
    cat = next(c for c in resp.data["results"] if c["id"] == service_category.id)
    item_ids = [i["id"] for i in cat["items"]]
    assert service_item.id in item_ids


# ── §3.7 Pagination shape — config lists ─────────────────────────────────────


@pytest.mark.django_db
def test_config_list_pagination_shape(api_client, admin_user, campus):
    """Config list endpoints must return PageNumber envelope: {count, next, previous, results}."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.get("/api/v1/campuses/")
    assert resp.status_code == 200
    assert "count" in resp.data
    assert "next" in resp.data
    assert "previous" in resp.data
    assert "results" in resp.data


@pytest.mark.django_db
def test_priorities_list_pagination_shape(api_client, admin_user, priority):
    """Priority list must return PageNumber envelope."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.get("/api/v1/priorities/")
    assert resp.status_code == 200
    assert "count" in resp.data
    assert "results" in resp.data


def test_append_only_feed_pagination_envelope():
    """AppendOnlyFeedPagination must produce {results, meta:{nextCursor,prevCursor,total}}."""
    from apps.common.pagination import AppendOnlyFeedPagination

    p = AppendOnlyFeedPagination()
    # Stub cursor link methods — they require paginate_queryset to have run first.
    p.get_next_link = lambda: "http://example.com/next"
    p.get_previous_link = lambda: None
    response = p.get_paginated_response(["item1", "item2"])
    body = response.data
    assert "results" in body
    assert "meta" in body
    assert "nextCursor" in body["meta"]
    assert "prevCursor" in body["meta"]
    assert "total" in body["meta"]


# ── §5.2 Admin CRUD — access control ─────────────────────────────────────────


@pytest.mark.django_db
def test_campus_crud_requires_auth(api_client):
    """Anonymous GET /campuses/ → 401."""
    resp = api_client.get("/api/v1/campuses/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_campus_crud_requires_admin_role(api_client, regular_user):
    """Non-admin authenticated user → 403."""
    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/campuses/")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_campus_list_as_admin(api_client, admin_user, campus):
    """Admin user can list campuses."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.get("/api/v1/campuses/")
    assert resp.status_code == 200
    assert resp.data["count"] >= 1


@pytest.mark.django_db
def test_create_campus(api_client, admin_user):
    """Admin can create a campus."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/campuses/",
        {"name": "Kisumu", "code": "KSM", "location": "Lakeside"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["code"] == "KSM"


@pytest.mark.django_db
def test_create_department(api_client, admin_user):
    """Admin can create a department."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/departments/",
        {"name": "Finance", "code": "FIN"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["code"] == "FIN"


@pytest.mark.django_db
def test_departments_filtered_by_campus(api_client, regular_user, campus, campus_b, dept):
    """GET /departments/?campus=X returns only departments present at campus X."""
    from apps.org.models import CampusDepartment, Department

    dept_b = Department.objects.create(name="Human Resources", code="HR")
    CampusDepartment.objects.create(campus=campus, department=dept)
    CampusDepartment.objects.create(campus=campus_b, department=dept_b)

    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/departments/", {"campus": campus.id})
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.data["results"]]
    assert dept.id in ids
    assert dept_b.id not in ids


@pytest.mark.django_db
def test_sections_filtered_by_department(api_client, regular_user, campus_dept):
    """GET /sections/?department=X returns only sections under department X."""
    from apps.org.models import CampusDepartment, Department, Section, SectionType

    dept_b = Department.objects.create(name="Human Resources", code="HR")
    campus_dept_b = CampusDepartment.objects.create(
        campus=campus_dept.campus, department=dept_b
    )
    section_type_b = SectionType.objects.create(department=dept_b, name="Payroll", code="PAY")
    section_type_a = SectionType.objects.create(
        department=campus_dept.department, name="Support", code="SUP2"
    )
    section_a = Section.objects.create(
        campus_department=campus_dept, section_type=section_type_a, is_active=True
    )
    section_b = Section.objects.create(
        campus_department=campus_dept_b, section_type=section_type_b, is_active=True
    )

    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/sections/", {"department": campus_dept.department_id})
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.data["results"]]
    assert section_a.id in ids
    assert section_b.id not in ids


@pytest.mark.django_db
def test_create_section_type(api_client, admin_user, dept):
    """Admin can create a section type."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/section-types/",
        {"department": dept.id, "name": "Helpdesk", "code": "HELP"},
        format="json",
    )
    assert resp.status_code == 201


@pytest.mark.django_db
def test_create_priority(api_client, admin_user):
    """Admin can create a priority."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/priorities/",
        {
            "name": "Critical",
            "rank": 9,
            "response_minutes": 60,
            "resolution_minutes": 240,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["name"] == "Critical"


@pytest.mark.django_db
def test_create_escalation_rule(api_client, admin_user, priority):
    """Admin can create an escalation rule nested under a priority."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        f"/api/v1/priorities/{priority.id}/escalation-rules/",
        {
            "priority": priority.id,
            "to_level": "hos",
            "threshold_minutes": 120,
            "order": 1,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["to_level"] == "hos"


@pytest.mark.django_db
def test_priority_detail_includes_escalation_rules(api_client, admin_user, priority):
    """Priority detail response nests its escalation rules."""
    from apps.sla.models import EscalationRule

    EscalationRule.objects.create(
        priority=priority, to_level="hos", threshold_minutes=120, order=1
    )
    api_client.force_authenticate(user=admin_user)
    resp = api_client.get(f"/api/v1/priorities/{priority.id}/")
    assert resp.status_code == 200
    assert len(resp.data["escalation_rules"]) == 1
    assert resp.data["escalation_rules"][0]["to_level"] == "hos"


# ── §5.2 Facilities ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_facility_type_list_any_auth(api_client, regular_user):
    """Any authenticated user can list facility types (D9 — read-only)."""
    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/facility-types/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_facility_type_is_read_only(api_client, admin_user):
    """POST /facility-types/ must return 405 — the viewset is read-only (D9)."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/facility-types/",
        {"name": "New Type", "code": "new_type"},
        format="json",
    )
    assert resp.status_code == 405


@pytest.mark.django_db
def test_create_facility(api_client, admin_user, campus):
    """Admin can create a facility (building) for a campus."""
    from apps.facilities.models import FacilityType

    ft = FacilityType.objects.create(name="Office Block", code="office_block")
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/facilities/",
        {
            "campus": campus.id,
            "facility_type": ft.id,
            "name": "Block A",
            "code": "BLK-A",
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["name"] == "Block A"


@pytest.mark.django_db
def test_facilities_filtered_by_campus(api_client, regular_user, campus, campus_b):
    """GET /facilities/?campus=X returns only facilities at campus X."""
    from apps.facilities.models import FacilityType, Facility

    ft = FacilityType.objects.create(name="Building", code="building")
    f_a = Facility.objects.create(campus=campus, facility_type=ft, name="Block A")
    f_b = Facility.objects.create(campus=campus_b, facility_type=ft, name="Block B")

    api_client.force_authenticate(user=regular_user)
    resp = api_client.get("/api/v1/facilities/", {"campus": campus.id})
    assert resp.status_code == 200
    ids = [f["id"] for f in resp.data["results"]]
    assert f_a.id in ids
    assert f_b.id not in ids


# ── §5.2 Catalogue admin CRUD ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_create_service_category(api_client, admin_user, section_type, priority):
    """Admin can create a service category; response contains derived department."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/service-categories/",
        {
            "section_type": section_type.id,
            "name": "Printer Issues",
            "default_priority_id": priority.id,
        },
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["department"]["code"] == section_type.department.code


@pytest.mark.django_db
def test_create_service_item(api_client, admin_user, service_category):
    """Admin can create a service item within a category."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        "/api/v1/service-items/",
        {"category": service_category.id, "name": "Paper Jam"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["name"] == "Paper Jam"


# ── Nested section technicians ────────────────────────────────────────────────


@pytest.mark.django_db
def test_list_section_technicians(api_client, admin_user, active_section):
    """Admin can list technicians for a section."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.get(f"/api/v1/sections/{active_section.id}/technicians/")
    assert resp.status_code == 200
    assert "results" in resp.data


@pytest.mark.django_db
def test_add_section_technician(api_client, admin_user, active_section, regular_user):
    """Admin can add a technician to a section."""
    api_client.force_authenticate(user=admin_user)
    resp = api_client.post(
        f"/api/v1/sections/{active_section.id}/technicians/",
        {"user": regular_user.id, "section": active_section.id},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["user"] == regular_user.id
