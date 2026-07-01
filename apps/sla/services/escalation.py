from datetime import timedelta

from django.utils import timezone

from apps.common.time_windows import active_window_q

LEVEL_ORDER = {"technician": 0, "hos": 1, "hod": 2}


def resolve_active_holder(section, level, now=None):
    from apps.accounts.models import RoleAssignment

    if now is None:
        now = timezone.now()

    if level == "hos":
        cover = (
            RoleAssignment.objects.filter(
                role="hos",
                section=section,
                is_primary=False,
            )
            .filter(active_window_q(now))
            .select_related("user")
            .first()
        )
        if cover is not None:
            return cover.user
        return section.hos

    if level == "hod":
        campus_department = section.campus_department
        cover = (
            RoleAssignment.objects.filter(
                role="hod",
                campus_department=campus_department,
                is_primary=False,
            )
            .filter(active_window_q(now))
            .select_related("user")
            .first()
        )
        if cover is not None:
            return cover.user
        return campus_department.head_of_department

    return None


def run_escalation_for_ticket(ticket, now, rules):
    from apps.tickets.models import TicketLog

    if ticket.status in ("resolved", "closed"):
        return False

    if ticket.paused_at is not None:
        active_elapsed = (
            ticket.paused_at - ticket.created_at
        ) - ticket.accumulated_pause
    else:
        active_elapsed = (now - ticket.created_at) - ticket.accumulated_pause

    current_order = LEVEL_ORDER[ticket.current_level]

    applicable = sorted(
        [r for r in rules if LEVEL_ORDER[r.to_level] > current_order],
        key=lambda r: LEVEL_ORDER[r.to_level],
    )

    if not applicable:
        return False

    first_rule = applicable[0]
    if active_elapsed < timedelta(minutes=first_rule.threshold_minutes):
        return False

    for rule in applicable:
        holder = resolve_active_holder(ticket.section, rule.to_level, now)
        if holder is not None:
            old_level = ticket.current_level
            ticket.current_level = rule.to_level
            ticket.save(update_fields=["current_level", "updated_at"])
            TicketLog.objects.create(
                ticket=ticket,
                actor=None,
                event_type="escalated",
                from_value=old_level,
                to_value=rule.to_level,
                level_user=holder,
            )
            from apps.realtime.ws_utils import emit_ticket_escalated

            emit_ticket_escalated(ticket)
            return True

    return False


def run_escalations():
    from collections import defaultdict

    from apps.sla.models import EscalationRule
    from apps.tickets.models import Ticket

    now = timezone.now()

    tickets = (
        Ticket.objects.filter(
            status__in=("open", "assigned", "in_progress", "pending"),
        )
        .exclude(current_level="hod")
        .select_related(
            "priority",
            "section__campus_department",
            "section__hos",
        )
    )

    priority_ids = {t.priority_id for t in tickets}
    rules_qs = EscalationRule.objects.filter(priority_id__in=priority_ids).order_by(
        "priority", "order"
    )
    rules_by_priority = defaultdict(list)
    for rule in rules_qs:
        rules_by_priority[rule.priority_id].append(rule)

    count = 0
    for ticket in tickets:
        rules = rules_by_priority.get(ticket.priority_id, [])
        if run_escalation_for_ticket(ticket, now, rules):
            count += 1

    return count
