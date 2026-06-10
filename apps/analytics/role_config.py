"""Per-role analytics configuration — the single source of truth that makes
KPIs scope-invariant (SoT §5.4).

The metric engine (`aggregate()` + `insights.py`) is identical for every role;
only three things vary by role and they all live here:

  * scope          — applied server-side via scoped_ticket_qs(user, role)
  * default_group_by + allowed_group_by — the comparison dimension(s)
  * headline / insights / comparison    — what the role is allowed to see

The frontend mirrors this shape so one generic view can render every role.
`comparison=False` plus the absence of "technician" from allowed_group_by is what
prevents a technician from seeing peer rankings.
"""

# Dimensions the analytics engine can group by. Backend validates a requested
# group_by against the role's allowed list and falls back to default_group_by.
GROUP_BY_DIMENSIONS = (
    "time",
    "status",
    "section",
    "campus",
    "campus_department",
    "department",
    "section_type",
    "service_category",
    "service_item",
    "priority",
    "facility_type",
    "facility",
    "technician",
)

# Insight types (implemented in apps/analytics/insights.py).
INSIGHT_TYPES = (
    "recurring_fault",
    "bottleneck",
    "sla_leak",
    "capacity",
    "csat_driver",
)


ROLE_VIEWS = {
    "admin": {
        "default_group_by": "department",
        "allowed_group_by": [
            "department", "campus", "campus_department", "section",
            "service_category", "service_item", "priority", "facility_type", "facility",
        ],
        "headline": [
            "sla_resolution_pct", "csat", "net_flow", "open_backlog", "escalation_rate",
        ],
        "insights": ["bottleneck", "sla_leak", "recurring_fault", "capacity", "csat_driver"],
        "facilities": True,
        "ticket_flow": True,
        "comparison": True,
    },
    "manager": {
        "default_group_by": "campus_department",
        "allowed_group_by": [
            "campus_department", "section", "service_item", "priority", "facility",
        ],
        "headline": [
            "sla_resolution_pct", "resolution_p50", "open_backlog", "csat", "escalation_rate",
        ],
        "insights": ["bottleneck", "sla_leak", "capacity"],
        "facilities": True,
        "ticket_flow": True,
        "comparison": True,
    },
    "hod": {
        "default_group_by": "section",
        "allowed_group_by": ["section", "service_item", "priority", "facility", "technician"],
        "headline": [
            "sla_resolution_pct", "open_backlog", "net_flow", "unassigned", "escalation_rate",
        ],
        "insights": ["bottleneck", "recurring_fault", "sla_leak"],
        "facilities": True,
        "ticket_flow": True,
        "comparison": True,
    },
    "hos": {
        "default_group_by": "technician",
        "allowed_group_by": ["technician", "service_item", "priority", "facility"],
        "headline": ["sla_resolution_pct", "unassigned", "open_backlog", "csat"],
        "insights": ["bottleneck", "recurring_fault", "sla_leak"],
        "facilities": True,
        "ticket_flow": True,
        "comparison": True,
    },
    "technician": {
        # Trend-only: compares the technician to their own past, never to peers.
        "default_group_by": "time",
        "allowed_group_by": ["time", "status"],
        "headline": ["my_open", "my_resolved", "my_csat", "my_resolution_p50"],
        "insights": [],
        "facilities": False,
        "ticket_flow": False,
        "comparison": False,
    },
    "user": {
        "default_group_by": "status",
        "allowed_group_by": ["status", "time"],
        "headline": ["my_open", "my_resolved", "my_avg_resolution"],
        "insights": [],
        "facilities": False,
        "ticket_flow": False,
        "comparison": False,
    },
}


def get_role_config(role):
    """Return the config for `role`, or the locked-down requester default."""
    return ROLE_VIEWS.get(role, ROLE_VIEWS["user"])


def resolve_group_by(role, requested):
    """Pick a safe group_by: the requested one if the role is allowed it,
    otherwise the role default. Fails closed (never widens what a role sees)."""
    cfg = get_role_config(role)
    if requested and requested in cfg["allowed_group_by"]:
        return requested
    return cfg["default_group_by"]
