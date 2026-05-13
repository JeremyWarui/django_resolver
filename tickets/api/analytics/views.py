"""Analytics API views — one endpoint per role scope.

Architecture
────────────
Module-level helpers
    _parse_days(request)   — clamp the ?days= param, used by every view
    _forbidden(detail)     — consistent DRF-style 403 response

Base classes
    RoleBasedDashboardView — user-scoped dashboards (derive context from user)
    ResourceAnalyticsView  — resource-scoped analytics (object identified by <pk>)
                             Subclasses implement check_permission() and compute()
                             so each view only contains role-specific logic.

Resource views
    DepartmentAnalyticsView    /analytics/departments/<pk>/
    HODAnalyticsView           /analytics/campus-departments/<pk>/
    HOSAnalyticsView           /analytics/sections/<pk>/

Standalone views (permission too varied for the base class)
    TicketAnalyticsView        /analytics/tickets/
    TechnicianAnalyticsView    /analytics/technicians/
    TechnicianSelfAnalyticsView /analytics/technicians/me/
    AdminDashboardAnalyticsView /analytics/admin-dashboard/
    UserAnalyticsView           /analytics/user/

Legacy dashboard views (user-scoped, via RoleBasedDashboardView)
    ManagerDashboardView       /analytics/manager/
    HODDashboardView           /analytics/hod/
    SectionHeadDashboardView   /analytics/section-head/
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.api.analytics.admin_analytics import AdminAnalytics
from tickets.api.analytics.base_analytics import get_ticket_trend_data
from tickets.api.analytics.hod_analytics import HODAnalytics
from tickets.api.analytics.manager_analytics import ManagerAnalytics
from tickets.api.analytics.section_head_analytics import SectionHeadAnalytics
from tickets.api.analytics.technician_analytics import TechnicianAnalytics
from tickets.api.analytics.ticket_analytics import TicketAnalytics
from tickets.api.analytics.user_analytics import UserAnalytics
from tickets.models import CampusDepartment, CustomUser, Department, Section


# ── Module-level helpers ───────────────────────────────────────────────────────

def _parse_days(request, default: int = 30, max_days: int = 365) -> int:
    """Read ?days= from query params, clamped to [1, max_days]."""
    try:
        raw = int(request.query_params.get("days", default))
    except (TypeError, ValueError):
        raw = default
    return max(1, min(raw, max_days))


def _forbidden(detail: str) -> Response:
    """Consistent DRF 403 response (uses 'detail' key, not 'error')."""
    return Response({"detail": detail}, status=status.HTTP_403_FORBIDDEN)


def _not_found(detail: str) -> Response:
    return Response({"detail": detail}, status=status.HTTP_404_NOT_FOUND)


# ── Base: user-scoped dashboards ───────────────────────────────────────────────

class RoleBasedDashboardView(APIView):
    """
    Base class for user-scoped dashboards.

    Subclasses set:
        required_roles   list[str]   — allowed role values
        analytics_method callable    — takes (user, days=int) and returns a dict

    The view gates on role, then calls analytics_method(user, days=days).
    """

    permission_classes = [IsAuthenticated]
    required_roles: list = []
    analytics_method = None

    def get(self, request):
        if request.user.role not in self.required_roles:
            return _forbidden("Insufficient permissions for this endpoint.")
        days = _parse_days(request)
        return Response(self.analytics_method(request.user, days=days))


# ── Base: resource-scoped analytics ───────────────────────────────────────────

class ResourceAnalyticsView(APIView):
    """
    Base for resource-scoped analytics views.

    Fetches a model instance by <pk>, delegates permission checking and
    analytics computation to subclasses so each view stays concise.

    Subclasses must implement:
        model            — Django model class to look up
        select_related   — tuple of FK paths for select_related()
        not_found_detail — 404 message string
        check_permission(user, obj) -> Response | None
            Return a Response to deny; return None to allow.
        compute(user, obj, days) -> dict
            Return the analytics payload.

    Edge cases worth noting:
        • `check_permission` receives the already-fetched object, so it can
          inspect FK attributes without extra queries (select_related is done
          before the call).
        • `compute` receives `user` so role-dependent scoping (e.g. a HOD's
          campus filter) can be applied without duplicating the role check.
    """

    permission_classes = [IsAuthenticated]
    model = None
    select_related: tuple = ()
    not_found_detail: str = "Resource not found."

    def get(self, request, pk):
        # 1. Fetch — select_related is declared per subclass so the
        #    permission check never triggers extra queries.
        try:
            obj = self.model.objects.select_related(*self.select_related).get(pk=pk)
        except self.model.DoesNotExist:
            return _not_found(self.not_found_detail)

        # 2. Permission check — returns a Response on denial or None to proceed.
        error = self.check_permission(request.user, obj)
        if error is not None:
            return error

        # 3. Compute and respond.
        days = _parse_days(request)
        return Response(self.compute(request.user, obj, days))

    def check_permission(self, user, obj):  # pragma: no cover
        raise NotImplementedError

    def compute(self, user, obj, days):  # pragma: no cover
        raise NotImplementedError


# ── Ticket drill-down ──────────────────────────────────────────────────────────

class TicketAnalyticsView(APIView):
    """GET /api/analytics/tickets/

    Filterable ticket drill-down for admin and manager use.

    Permission: admin | manager only — other roles use their scoped endpoints.

    Query params:
        timeframe   day|week|month  count window (default: day)
        facility_id optional filter
        section_id  optional filter
        group_by    day|week|month  trend granularity (default: day)
        days        trend lookback  (default: 30, max: 365)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("admin", "manager"):
            return _forbidden(
                "Admin or manager role required for org-wide ticket analytics."
            )

        days_map = {"day": 1, "week": 7, "month": 30}
        timeframe = request.query_params.get("timeframe", "day")
        facility_id = request.query_params.get("facility_id")
        section_id = request.query_params.get("section_id")
        group_by = request.query_params.get("group_by", "day")
        days = _parse_days(request)
        time_days = days_map.get(timeframe, 1)

        return Response({
            "ticket_counts": TicketAnalytics.get_ticket_counts_by_timeframe(
                days=time_days, facility_id=facility_id, section_id=section_id,
            ),
            "status_counts": TicketAnalytics.get_ticket_counts_by_status(
                facility_id=facility_id, section_id=section_id,
            ),
            "trend_data": get_ticket_trend_data(days=days, group_by=group_by),
            "facility_distribution": TicketAnalytics.get_tickets_by_facility(),
            "section_distribution": TicketAnalytics.get_tickets_by_section(),
        })


# ── Technician analytics ───────────────────────────────────────────────────────

class TechnicianAnalyticsView(APIView):
    """GET /api/analytics/technicians/

    Admin-facing list: performance for all (or one) technicians.

    Permission:
        technician  → redirected automatically to self-service data
        admin       → all technicians; optional ?technician_id=<pk>
        manager     → all technicians (cross-department workload view)
        hod         → campus-scoped; ?technician_id validated against campus
        others      → 403

    Section ratings are included when listing all technicians (admin|manager only).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        # Technicians always see only their own KPIs.
        if user.role == "technician":
            return Response(TechnicianAnalytics.for_technician(user))

        if user.role not in ("admin", "manager", "hod"):
            return _forbidden("Analytics access requires admin, manager, or HOD role.")

        technician_id = request.query_params.get("technician_id")

        # HODs may only query technicians on their campus.
        # Edge case: if a HOD has no primary_campus set they should see nothing.
        if user.role == "hod" and technician_id:
            try:
                tech = CustomUser.objects.get(pk=technician_id, role="technician")
            except CustomUser.DoesNotExist:
                return _not_found("Technician not found.")
            if tech.primary_campus != user.primary_campus:
                return _forbidden("That technician is not on your campus.")

        performance = TechnicianAnalytics.get_technician_performance(
            technician_id=int(technician_id) if technician_id else None
        )
        data = {"technician_performance": performance}
        if not technician_id and user.role in ("admin", "manager"):
            data["section_ratings"] = TechnicianAnalytics.get_technician_ratings_by_section()

        return Response(data)


class TechnicianSelfAnalyticsView(APIView):
    """GET /api/analytics/technicians/me/

    Self-service dashboard for the authenticated technician.

    Permission:
        technician  → own data only
        admin       → can pass ?user_id=<pk> to inspect any technician
        others      → 403
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user_id = request.query_params.get("user_id")

        if user.role == "admin":
            if user_id:
                try:
                    target = CustomUser.objects.get(pk=user_id, role="technician")
                except CustomUser.DoesNotExist:
                    return _not_found("Technician not found.")
                return Response(TechnicianAnalytics.for_technician(target))
        elif user_id:
            return _forbidden("This endpoint is for technicians only.")

        if user.role != "technician":
            return _forbidden("This endpoint is for technicians only.")

        return Response(TechnicianAnalytics.for_technician(user))


# ── Admin dashboard ────────────────────────────────────────────────────────────

class AdminDashboardAnalyticsView(APIView):
    """GET /api/analytics/admin-dashboard/

    System-wide admin dashboard.

    Permission:
        admin   → full access: overview + overdue + org breakdown
        manager → overview + overdue only (use /analytics/departments/<pk>/ for drill-down)
        others  → 403

    Query params: days (default 30, max 365)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ("admin", "manager"):
            return _forbidden("Admin or manager role required.")

        days = _parse_days(request)
        data = {
            "system_overview": AdminAnalytics.get_system_overview(),
            "overdue_tickets": AdminAnalytics.get_overdue_tickets(),
        }
        # Full org drilldown is admin-only; managers use /analytics/departments/<pk>/
        if request.user.role == "admin":
            data["organisation"] = AdminAnalytics.get_organisation_analytics(days=days)
        return Response(data)


# ── User dashboard ─────────────────────────────────────────────────────────────

class UserAnalyticsView(APIView):
    """GET /api/analytics/user/

    Personal ticket dashboard — available to every authenticated role.
    Always scoped to request.user regardless of role.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserAnalytics.for_user(request.user))


# ── Legacy user-scoped dashboards ─────────────────────────────────────────────

class ManagerDashboardView(RoleBasedDashboardView):
    required_roles = ["manager", "admin"]
    analytics_method = staticmethod(ManagerAnalytics.manager_dashboard)


class HODDashboardView(RoleBasedDashboardView):
    required_roles = ["hod", "admin"]
    analytics_method = staticmethod(HODAnalytics.hod_dashboard)


class SectionHeadDashboardView(RoleBasedDashboardView):
    required_roles = ["head_of_section", "admin"]
    analytics_method = staticmethod(SectionHeadAnalytics.section_head_dashboard)


# ── Resource-scoped analytics (ResourceAnalyticsView subclasses) ───────────────

class DepartmentAnalyticsView(ResourceAnalyticsView):
    """GET /api/analytics/departments/<pk>/

    Cross-campus ticket metrics for a Department.

    Permission:
        admin    → any department
        manager  → only user.primary_department
        hod      → any department on their campus; results narrowed to that campus
        others   → 403

    Edge case — HOD narrows compute() via campus_filter:
        check_permission() validates the department is on the HOD's campus, but
        compute() must also pass that campus to ManagerAnalytics so the response
        only contains data for their campus. Both methods receive `user` so
        this is handled without storing state on the view instance.
    """

    model = Department
    select_related = ()
    not_found_detail = "Department not found."

    def check_permission(self, user, department):
        if user.role == "admin":
            return None
        if user.role == "manager":
            if not user.primary_department or user.primary_department != department:
                return _forbidden("You may only view analytics for your own department.")
        elif user.role == "hod":
            if not user.primary_campus:
                return _forbidden("No primary campus assigned to your account.")
            if not CampusDepartment.objects.filter(
                campus=user.primary_campus, department=department
            ).exists():
                return _forbidden("This department is not present on your campus.")
        else:
            return _forbidden("Analytics access requires manager, HOD, or admin role.")
        return None

    def compute(self, user, department, days):
        # HOD scope: narrow to their campus so they cannot see other campuses'
        # data even though they passed check_permission.
        campus_filter = user.primary_campus if user.role == "hod" else None
        return ManagerAnalytics.for_department(department, days=days, campus=campus_filter)


class HODAnalyticsView(ResourceAnalyticsView):
    """GET /api/analytics/campus-departments/<pk>/

    Metrics for a single CampusDepartment (campus + department pair).

    Permission:
        admin    → any CampusDepartment
        manager  → only CampusDepartments whose department == user.primary_department
        hod      → only the CampusDepartment they are head_of_department for
                   (campus_department.head_of_department == user)
        others   → 403
    """

    model = CampusDepartment
    select_related = ("campus", "department", "head_of_department")
    not_found_detail = "CampusDepartment not found."

    def check_permission(self, user, campus_department):
        if user.role == "admin":
            return None
        if user.role == "manager":
            if (
                not user.primary_department
                or campus_department.department != user.primary_department
            ):
                return _forbidden(
                    "Managers may only access analytics for their own department."
                )
        elif user.role == "hod":
            # Edge case: a HOD is explicitly assigned via head_of_department FK,
            # not via primary_campus/primary_department. A HOD on the same campus
            # but NOT the head_of_department for this CD should still be blocked.
            if campus_department.head_of_department != user:
                return _forbidden(
                    "HODs may only access analytics for the CampusDepartment "
                    "they are assigned to head."
                )
        else:
            return _forbidden("Analytics access requires admin, manager, or HOD role.")
        return None

    def compute(self, user, campus_department, days):
        return HODAnalytics.for_campus_department(campus_department, days=days)


class HOSAnalyticsView(ResourceAnalyticsView):
    """GET /api/analytics/sections/<pk>/

    Metrics for a single Section.

    Permission:
        admin           → any Section
        manager         → Sections whose department == user.primary_department
        hod             → Sections under their CampusDepartment
        head_of_section → only Sections where section.head_of_section == user
        others          → 403

    Edge case — HOD check uses primary_campus_department property:
        primary_campus_department is a computed property (one DB lookup) rather
        than a stored FK.  It returns None if the user has no campus/department
        set, which we treat as a deny.
    """

    model = Section
    select_related = (
        "campus_department__campus",
        "campus_department__department",
        "campus_department__head_of_department",
        "section_type",
        "head_of_section",
    )
    not_found_detail = "Section not found."

    def check_permission(self, user, section):
        cd = section.campus_department
        if user.role == "admin":
            return None
        if user.role == "manager":
            if not user.primary_department or cd.department != user.primary_department:
                return _forbidden(
                    "Managers may only access analytics for sections in their own department."
                )
        elif user.role == "hod":
            user_cd = user.primary_campus_department
            if not user_cd or cd != user_cd:
                return _forbidden(
                    "HODs may only access analytics for sections within their CampusDepartment."
                )
        elif user.role == "head_of_section":
            if section.head_of_section != user:
                return _forbidden(
                    "Heads of Section may only access analytics for sections they head."
                )
        else:
            return _forbidden(
                "Analytics access requires admin, manager, HOD, or head_of_section role."
            )
        return None

    def compute(self, user, section, days):
        return SectionHeadAnalytics.for_section(section, days=days)
