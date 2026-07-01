"""Analytics views — role-scoped endpoints over the aggregate() core (SoT §5.4).

Every view:
  1. Extracts role from JWT payload (role claim set at login).
  2. Obtains a scoped queryset from Phase 6 scope resolver — NEVER re-derives scope.
  3. Calls aggregate(scoped_qs, date_range, group_by) once (or twice for technician).
  4. Returns a slice of the metrics dict relevant to the endpoint.

The dashboard preset (OverviewView) and deep-dive endpoints call the same core,
so the same scope+window yields identical headline numbers in both.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.common.roles import resolve_role
from apps.tickets.models import Ticket
from apps.tickets.services.scope import scoped_ticket_qs

from .insights import compute_insights
from .role_config import get_role_config, resolve_group_by
from .services import (
    ACTIVE_STATUSES,
    aggregate,
    breakdown,
    config_health,
    resolve_date_range,
    technician_load,
)


class BaseAnalyticsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_role(self, request):
        return resolve_role(request)

    def get_scoped_qs(self, request, role=None):
        user = request.user
        role = role or self.get_role(request)
        return scoped_ticket_qs(user, role)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _date_range_meta(date_range):
    return {
        "from": date_range["date_from"].isoformat(),
        "to": date_range["date_to"].isoformat(),
    }


def _overview_slice(data: dict) -> dict:
    """The four health headlines + supporting metrics for the overview preset.
    status_distribution (windowed) is for charts; live_status_distribution
    counts ALL scoped tickets by current status so stat cards always reflect
    the true current state regardless of the selected date window."""
    return {
        "open_backlog": data["open_backlog"],
        "created": data["created"],
        "resolved": data["resolved"],
        "net_flow": data["net_flow"],
        "status_distribution": data.get("status_distribution", []),
        "live_status_distribution": data.get("live_status_distribution", []),
        "resolution_sla_pct": data["resolution_sla_pct"],
        "response_sla_pct": data["response_sla_pct"],
        "csat": data["csat"],
        "reopen_rate": data["reopen_rate"],
        "at_risk": data["at_risk"],
        "breached": data["breached"],
        "escalation_rate": data["escalation_rate"],
        "delta": data["delta"],
    }


def _sectional_slice(data: dict) -> dict:
    """Sectional context for technician — separate key, never shown as own perf."""
    return {
        "open_backlog": data["open_backlog"],
        "created": data["created"],
        "resolved": data["resolved"],
        "net_flow": data["net_flow"],
        "status_distribution": data["status_distribution"],
        "live_status_distribution": data.get("live_status_distribution", []),
        "unassigned": data.get("unassigned", 0),
    }


# ── Overview (dashboard preset) ────────────────────────────────────────────────

class OverviewView(BaseAnalyticsView):
    """Role-scoped summary — same core as all other endpoints (SoT §5.4)."""

    def get(self, request):
        role = self.get_role(request)
        user = request.user
        date_range = resolve_date_range(request.query_params)

        if role == "technician":
            # TWO scopes in SEPARATE keys (SoT §5.4 — never mix them)
            individual_qs = Ticket.objects.filter(assigned_to=user)
            sectional_qs = scoped_ticket_qs(user, "technician")
            individual_data = aggregate(individual_qs, date_range)
            sectional_data = aggregate(sectional_qs, date_range)
            return Response({
                "date_range": _date_range_meta(date_range),
                "individual": _overview_slice(individual_data),
                "sectional": _sectional_slice(sectional_data),
            })

        # HOD → group by section; Manager → group by campus; others → no breakdown
        group_by_map = {"hod": "section", "manager": "campus"}
        group_by = group_by_map.get(role)

        scoped_qs = scoped_ticket_qs(user, role)

        data = aggregate(scoped_qs, date_range, group_by)
        response_data = {
            "date_range": _date_range_meta(date_range),
            **_overview_slice(data),
        }
        if data.get("breakdown") is not None:
            response_data["breakdown"] = data["breakdown"]
        if role == "admin":
            response_data["config_health"] = config_health()
        return Response(response_data)


# ── SLA compliance ─────────────────────────────────────────────────────────────

class SLAComplianceView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        data = aggregate(scoped_qs, date_range)
        return Response({
            "date_range": _date_range_meta(date_range),
            "resolution_sla_pct": data["resolution_sla_pct"],
            "response_sla_pct": data["response_sla_pct"],
            "at_risk": data["at_risk"],
            "breached": data["breached"],
            "delta": {
                "resolution_sla_pct": data["delta"]["resolution_sla_pct"],
                "response_sla_pct": data["delta"]["response_sla_pct"],
            },
        })


# ── Resolution times (p50/p90) ─────────────────────────────────────────────────

class ResolutionTimesView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        data = aggregate(scoped_qs, date_range)
        return Response({
            "date_range": _date_range_meta(date_range),
            "resolution_time_p50_seconds": data["resolution_time_p50_seconds"],
            "resolution_time_p90_seconds": data["resolution_time_p90_seconds"],
            "first_response_p50_seconds": data["first_response_p50_seconds"],
            "first_response_p90_seconds": data["first_response_p90_seconds"],
        })


# ── Flow (created / resolved / net / trend) ───────────────────────────────────

class FlowView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        granularity = request.query_params.get("granularity", "day")
        if granularity not in ("day", "week", "month", "quarter"):
            granularity = "day"
        data = aggregate(scoped_qs, date_range, granularity=granularity)
        return Response({
            "date_range": _date_range_meta(date_range),
            "open_backlog": data["open_backlog"],
            "created": data["created"],
            "resolved": data["resolved"],
            "net_flow": data["net_flow"],
            "flow_trend": data["flow_trend"],
            "status_distribution": data["status_distribution"],
            "priority_distribution": data["priority_distribution"],
            "delta": {
                "created": data["delta"]["created"],
                "resolved": data["delta"]["resolved"],
            },
        })


# ── Quality (CSAT + reopen) ───────────────────────────────────────────────────

class QualityView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        data = aggregate(scoped_qs, date_range)
        return Response({
            "date_range": _date_range_meta(date_range),
            "csat": data["csat"],
            "feedback_response_rate": data["feedback_response_rate"],
            "reopen_rate": data["reopen_rate"],
            "delta": {
                "csat": data["delta"]["csat"],
                "reopen_rate": data["delta"]["reopen_rate"],
            },
        })


# ── Demand shape ──────────────────────────────────────────────────────────────

class DemandView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        data = aggregate(scoped_qs, date_range)
        return Response({
            "date_range": _date_range_meta(date_range),
            **data["demand"],
        })


# ── Performance endpoints ─────────────────────────────────────────────────────

class PerformanceTechniciansView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        # Two cheap queries (live load + windowed breakdown) instead of the
        # ~23-query full aggregate (see services.breakdown / technician_load).
        return Response({
            "date_range": _date_range_meta(date_range),
            "technician_load": technician_load(scoped_qs),
            "breakdown": breakdown(scoped_qs, date_range, group_by="technician"),
        })


class PerformanceSectionsView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        # breakdown-only: skip the ~40-query headline (see services.breakdown()).
        return Response({
            "date_range": _date_range_meta(date_range),
            "breakdown": breakdown(scoped_qs, date_range, group_by="section"),
        })


class PerformanceCampusDepartmentsView(BaseAnalyticsView):
    def get(self, request):
        role = self.get_role(request)
        scoped_qs = self.get_scoped_qs(request, role)
        date_range = resolve_date_range(request.query_params)
        # breakdown-only: skip the ~40-query headline (see services.breakdown()).
        return Response({
            "date_range": _date_range_meta(date_range),
            "breakdown": breakdown(scoped_qs, date_range, group_by="campus_department"),
        })


# ── Unified analytics endpoint (one view serves every role) ────────────────────

def _range_meta(dr):
    return {
        "from": dr["date_from"].isoformat(),
        "to": dr["date_to"].isoformat(),
        "prev_from": dr["prior_from"].isoformat(),
        "prev_to": dr["prior_to"].isoformat(),
    }


def _headline(data: dict) -> dict:
    """The full headline metric set. Scope is already applied; the frontend
    picks which of these to surface per the role config (KPIs are scope-invariant,
    so we compute once and let the client slice)."""
    keys = (
        "open_backlog", "created", "resolved", "net_flow",
        "resolution_sla_pct", "response_sla_pct",
        "resolution_time_p50_seconds", "resolution_time_p90_seconds",
        "first_response_p50_seconds", "first_response_p90_seconds",
        "at_risk", "breached", "escalation_rate", "escalated_count",
        "reassignment_rate", "unassigned", "currently_paused",
        "pause_total_seconds", "pause_avg_seconds", "ever_paused_count",
        "csat", "csat_satisfied_pct", "feedback_response_rate", "reopen_rate",
        "aging_buckets", "delta",
    )
    return {k: data.get(k) for k in keys}


class AnalyticsView(BaseAnalyticsView):
    """Single role-scoped analytics endpoint returning the full envelope
    {scope, range, headline, series, breakdown, ticket_flow, insights}.

    The metric engine is identical for every role; the role config controls the
    default breakdown dimension, the enabled insights, and (client-side) which
    headline KPIs are shown. group_by is validated against the role's allowed
    list and falls back to the role default (a technician can never request peer
    rankings)."""

    def get(self, request):
        role = self.get_role(request)
        user = request.user
        date_range = resolve_date_range(request.query_params)
        cfg = get_role_config(role)
        granularity = request.query_params.get("granularity", "day")
        if granularity not in ("day", "week", "month", "quarter"):
            granularity = "day"

        # Technician: two scopes in SEPARATE keys, never mixed (SoT §5.4).
        if role == "technician":
            individual = aggregate(Ticket.objects.filter(assigned_to=user), date_range, granularity=granularity)
            sectional = aggregate(scoped_ticket_qs(user, "technician"), date_range, granularity=granularity)
            return Response({
                "scope": {"role": role},
                "range": _range_meta(date_range),
                "individual": _headline(individual),
                "sectional": _sectional_slice(sectional),
                "series": {"flow_trend": individual["flow_trend"]},
                "ticket_flow": sectional["ticket_flow"],
                "insights": [],
            })

        if not role:
            scoped_qs = Ticket.objects.filter(raised_by=user)
            group_by = None
        else:
            scoped_qs = scoped_ticket_qs(user, role)
            group_by = resolve_group_by(role, request.query_params.get("group_by"))

        data = aggregate(scoped_qs, date_range, group_by, granularity=granularity)
        insights = (
            compute_insights(scoped_qs, date_range, cfg["insights"])
            if role and cfg.get("insights")
            else []
        )

        envelope = {
            "scope": {"role": role, "group_by": group_by},
            "range": _range_meta(date_range),
            "headline": _headline(data),
            "series": {
                "flow_trend": data["flow_trend"],
                "status_distribution": data["status_distribution"],
                "priority_distribution": data["priority_distribution"],
            },
            "breakdown": {"dimension": group_by, "rows": data.get("breakdown", [])},
            "ticket_flow": data["ticket_flow"],
            "demand": data["demand"],
            "insights": insights,
        }
        if role == "admin":
            envelope["config_health"] = config_health()
        return Response(envelope)
