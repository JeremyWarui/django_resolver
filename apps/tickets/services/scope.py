from django.db.models import Q
from django.utils import timezone

from apps.common.time_windows import active_window_q


def scoped_ticket_qs(user, role):
    """Return a Ticket queryset scoped to what `user` can see for the given `role`.

    Returns an empty queryset for users with no role or an unknown role.
    Does NOT apply ?mine=1 — that is handled separately in the view (R15).
    """
    from apps.tickets.models import Ticket
    from apps.org.models import SectionTechnician
    from apps.accounts.models import RoleAssignment

    base = Ticket.objects.select_related(
        "section__campus_department__department",
        "section__campus_department__campus",
        "section__section_type",
        "section__hos",
        "priority",
        "service_item__category",
        "assigned_to",
        "raised_by",
        "requester_campus",
    ).order_by("-updated_at")

    if role == "admin":
        return base

    if role == "manager":
        # Manager sees all tickets in their department across all campuses.
        return base.filter(
            section__campus_department__department__manager_user=user
        )

    if role == "hod":
        now = timezone.now()
        # Primary scope: HOD of their campus_department.
        primary_q = Q(section__campus_department__head_of_department=user)
        # Cover scope: active RoleAssignment(role=hod) for other campus_departments.
        covered_cd_ids = (
            RoleAssignment.objects.filter(
                user=user,
                role="hod",
                is_primary=False,
            )
            .filter(active_window_q(now))
            .values_list("campus_department_id", flat=True)
        )
        cover_q = Q(section__campus_department__in=covered_cd_ids) if covered_cd_ids else Q(pk__in=[])
        return base.filter(primary_q | cover_q)

    if role == "hos":
        now = timezone.now()
        # Primary scope: HOS of their section(s).
        primary_q = Q(section__hos=user)
        # Cover scope: active RoleAssignment(role=hos) for other sections.
        covered_section_ids = (
            RoleAssignment.objects.filter(
                user=user,
                role="hos",
                is_primary=False,
            )
            .filter(active_window_q(now))
            .values_list("section_id", flat=True)
        )
        cover_q = Q(section__in=covered_section_ids) if covered_section_ids else Q(pk__in=[])
        return base.filter(primary_q | cover_q)

    if role == "technician":
        # Technician sees all sections they are linked to via SectionTechnician.
        section_ids = SectionTechnician.objects.filter(user=user).values_list(
            "section_id", flat=True
        )
        return base.filter(section__in=section_ids)

    if role == "user":
        # Requester (universal): own tickets only (SoT §3.5 scope table).
        return base.filter(raised_by=user)

    return Ticket.objects.none()


def scoped_section_qs(user, role):
    """Return a Section queryset scoped to what `user` manages for the given `role`.

    Mirrors the section traversal in ``scoped_ticket_qs`` so technician rosters
    and section pickers stay consistent with ticket scope. Fail-closed: returns
    an empty queryset for users with no role or an unknown role.
    """
    from apps.org.models import Section, SectionTechnician
    from apps.accounts.models import RoleAssignment

    base = Section.objects.select_related(
        "campus_department__department",
        "campus_department__campus",
        "section_type",
    )

    if role == "admin":
        return base

    if role == "manager":
        return base.filter(campus_department__department__manager_user=user)

    if role == "hod":
        now = timezone.now()
        primary_q = Q(campus_department__head_of_department=user)
        covered_cd_ids = (
            RoleAssignment.objects.filter(user=user, role="hod", is_primary=False)
            .filter(active_window_q(now))
            .values_list("campus_department_id", flat=True)
        )
        cover_q = Q(campus_department__in=covered_cd_ids) if covered_cd_ids else Q(pk__in=[])
        return base.filter(primary_q | cover_q)

    if role == "hos":
        now = timezone.now()
        primary_q = Q(hos=user)
        covered_section_ids = (
            RoleAssignment.objects.filter(user=user, role="hos", is_primary=False)
            .filter(active_window_q(now))
            .values_list("section_id", flat=True)
        )
        cover_q = Q(pk__in=covered_section_ids) if covered_section_ids else Q(pk__in=[])
        return base.filter(primary_q | cover_q)

    if role == "technician":
        section_ids = SectionTechnician.objects.filter(user=user).values_list(
            "section_id", flat=True
        )
        return base.filter(pk__in=section_ids)

    return Section.objects.none()
