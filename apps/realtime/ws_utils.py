"""WebSocket emit helpers for Django Channels.

No-ops when channels is not installed or the channel layer is not configured.
All emit calls are wrapped in try/except so views work without Redis.

Group naming (underscores only — Channels requirement, §5.7):
  user_{userId}               — personal; always joined on connect
  ticket_{ticketId}           — transient; joined/left on ticket detail page
  section_{sectionId}         — section feed (technician/hos)
  campus_department_{cdId}    — campus-dept feed (hod)
"""

import logging

logger = logging.getLogger(__name__)


# ── WebSocket emit ────────────────────────────────────────────────────────────


def emit_ws_event(group_name: str, event_type: str, data: dict) -> None:
    """Send an event to a Django Channels group (no-op without a channel layer)."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        async_to_sync(channel_layer.group_send)(
            group_name,
            {"type": "send_event", "data": {"type": event_type, **data}},
        )
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("WS emit to %s failed: %s", group_name, exc)


# ── Scope helpers ─────────────────────────────────────────────────────────────


def _campus_department_id(ticket) -> int | None:
    """Return the campus_department_id for a ticket's section — one targeted query."""
    try:
        from apps.org.models import Section

        return Section.objects.values_list("campus_department_id", flat=True).get(
            pk=ticket.section_id
        )
    except Exception:
        return None


def _hos_user_ids(section_id) -> list[int]:
    """User IDs of all active HOS role-holders for a section."""
    try:
        from apps.accounts.models import RoleAssignment

        return list(
            RoleAssignment.objects.filter(
                role="hos", section_id=section_id, is_primary=True
            ).values_list("user_id", flat=True)
        )
    except Exception:
        return []


def _hod_user_ids(cd_id) -> list[int]:
    """User IDs of all active HOD role-holders for a campus-department."""
    if not cd_id:
        return []
    try:
        from apps.accounts.models import RoleAssignment

        return list(
            RoleAssignment.objects.filter(
                role="hod", campus_department_id=cd_id, is_primary=True
            ).values_list("user_id", flat=True)
        )
    except Exception:
        return []


# ── DB notification helper ────────────────────────────────────────────────────


def _notify_users(
    user_ids: list[int],
    event_type: str,
    title: str,
    body: str,
    ticket=None,
) -> None:
    """Persist in-app notifications for a list of users (bulk insert, no-op on error)."""
    if not user_ids:
        return
    try:
        from apps.realtime.models import Notification

        Notification.objects.bulk_create(
            [
                Notification(
                    user_id=uid,
                    event_type=event_type,
                    title=title,
                    body=body,
                    ticket=ticket,
                    ticket_no=ticket.ticket_no if ticket else "",
                )
                for uid in set(user_ids)
            ]
        )
    except Exception as exc:
        logger.warning("_notify_users failed: %s", exc)


# ── Public emit functions ─────────────────────────────────────────────────────


def emit_ticket_created(ticket) -> None:
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "sectionId": ticket.section_id,
    }
    for group in [f"section_{ticket.section_id}", f"user_{ticket.raised_by_id}"]:
        emit_ws_event(group, "ticket_created", payload)
    cd_id = _campus_department_id(ticket)
    if cd_id:
        emit_ws_event(f"campus_department_{cd_id}", "ticket_created", payload)

    recipients = _hos_user_ids(ticket.section_id) + _hod_user_ids(cd_id)
    _notify_users(
        recipients,
        "ticket_created",
        "New ticket raised",
        f"Ticket #{ticket.ticket_no} has been submitted in your section.",
        ticket,
    )

    try:
        from apps.realtime.push_service import notify_ticket_created

        notify_ticket_created(ticket)
    except Exception as exc:
        logger.warning("Push notify_ticket_created failed: %s", exc)


def emit_ticket_assigned(ticket, previous_assignee=None) -> None:
    assignee = ticket.assigned_to
    assignee_name = (
        (assignee.get_full_name() or assignee.username) if assignee else None
    )
    is_reassignment = previous_assignee is not None
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "assignedToId": assignee.id if assignee else None,
        "assignedToName": assignee_name,
        "isReassignment": is_reassignment,
    }
    for group in [
        f"ticket_{ticket.id}",
        f"section_{ticket.section_id}",
        f"user_{ticket.raised_by_id}",
    ]:
        emit_ws_event(group, "ticket_assigned", payload)
    cd_id = _campus_department_id(ticket)
    if cd_id:
        emit_ws_event(f"campus_department_{cd_id}", "ticket_assigned", payload)

    if assignee:
        title = (
            "Ticket reassigned to you" if is_reassignment else "Ticket assigned to you"
        )
        _notify_users(
            [assignee.id],
            "ticket_assigned",
            title,
            f"Ticket #{ticket.ticket_no} has been assigned to you.",
            ticket,
        )

    if is_reassignment and previous_assignee:
        prev_name = assignee_name or "another technician"
        _notify_users(
            [previous_assignee.id],
            "ticket_assigned",
            "Ticket reassigned",
            f"Ticket #{ticket.ticket_no} has been reassigned to {prev_name}.",
            ticket,
        )

    requester_title = "Ticket reassigned" if is_reassignment else "Ticket assigned"
    requester_body = (
        f"Ticket #{ticket.ticket_no} has been reassigned to {assignee_name or 'a technician'}."
        if is_reassignment
        else f"Ticket #{ticket.ticket_no} has been assigned to {assignee_name or 'a technician'}."
    )
    _notify_users(
        [ticket.raised_by_id],
        "ticket_assigned",
        requester_title,
        requester_body,
        ticket,
    )

    try:
        from apps.realtime.push_service import notify_ticket_assigned

        notify_ticket_assigned(ticket)
    except Exception as exc:
        logger.warning("Push notify_ticket_assigned failed: %s", exc)


def emit_ticket_status_changed(ticket, from_status: str) -> None:
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "fromStatus": from_status,
        "toStatus": ticket.status,
    }
    for group in [
        f"ticket_{ticket.id}",
        f"section_{ticket.section_id}",
        f"user_{ticket.raised_by_id}",
    ]:
        emit_ws_event(group, "ticket_status_changed", payload)
    cd_id = _campus_department_id(ticket)
    if cd_id:
        emit_ws_event(f"campus_department_{cd_id}", "ticket_status_changed", payload)

    _notify_users(
        [ticket.raised_by_id],
        "ticket_status_changed",
        "Ticket updated",
        f"Ticket #{ticket.ticket_no} status changed to {ticket.status.replace('_', ' ')}.",
        ticket,
    )

    try:
        from apps.realtime.push_service import notify_ticket_status_changed

        notify_ticket_status_changed(ticket, from_status)
    except Exception as exc:
        logger.warning("Push notify_ticket_status_changed failed: %s", exc)


def emit_ticket_resolved(ticket) -> None:
    assignee = ticket.assigned_to
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "resolvedBy": (
            (assignee.get_full_name() or assignee.username) if assignee else "System"
        ),
    }
    for group in [f"ticket_{ticket.id}", f"user_{ticket.raised_by_id}"]:
        emit_ws_event(group, "ticket_resolved", payload)

    _notify_users(
        [ticket.raised_by_id],
        "ticket_resolved",
        "Your ticket has been resolved",
        f"Ticket #{ticket.ticket_no} has been resolved. Please rate your experience.",
        ticket,
    )

    try:
        from apps.realtime.push_service import notify_ticket_resolved

        notify_ticket_resolved(ticket)
    except Exception as exc:
        logger.warning("Push notify_ticket_resolved failed: %s", exc)


def emit_comment_added(ticket, comment) -> None:
    author = comment.author
    payload = {
        "ticketId": ticket.id,
        "commentId": comment.id,
        "authorName": (author.get_full_name() or author.username) if author else "",
        "preview": (comment.body or "")[:100],
    }
    emit_ws_event(f"ticket_{ticket.id}", "comment_added", payload)
    emit_ws_event(f"user_{ticket.raised_by_id}", "comment_added", payload)

    if author and author.id != ticket.raised_by_id:
        _notify_users(
            [ticket.raised_by_id],
            "comment_added",
            "New comment on your ticket",
            f"{payload['authorName']} commented on #{ticket.ticket_no}: {payload['preview']}",
            ticket,
        )

    try:
        from apps.realtime.push_service import notify_comment_added

        notify_comment_added(ticket, comment)
    except Exception as exc:
        logger.warning("Push notify_comment_added failed: %s", exc)


def emit_role_changed(user_id: int, old_role: str | None, new_role: str | None) -> None:
    """Push a live signal to a user whose effective role changed via a
    RoleAssignment create/update/delete, so the frontend can force a clean
    re-login immediately instead of waiting for the next silent token refresh
    to notice (jwt_refresh's own roleChanged check remains the fallback if
    this socket is disconnected or the tab is backgrounded).

    WS-only — no Notification DB row. This isn't a ticket-oriented item for
    a user to review later; it's a transient control-plane signal.
    """
    emit_ws_event(
        f"user_{user_id}",
        "role_changed",
        {"oldRole": old_role, "newRole": new_role},
    )


def emit_ticket_escalated(ticket) -> None:
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "currentLevel": ticket.current_level,
    }
    for group in [
        f"ticket_{ticket.id}",
        f"section_{ticket.section_id}",
        f"user_{ticket.raised_by_id}",
    ]:
        emit_ws_event(group, "ticket_escalated", payload)
    cd_id = _campus_department_id(ticket)
    if cd_id:
        emit_ws_event(f"campus_department_{cd_id}", "ticket_escalated", payload)

    recipients = _hod_user_ids(cd_id) + _hos_user_ids(ticket.section_id)
    _notify_users(
        recipients,
        "ticket_escalated",
        "Ticket escalated",
        f"Ticket #{ticket.ticket_no} has been escalated to {ticket.current_level.upper()}.",
        ticket,
    )

    try:
        from apps.realtime.push_service import notify_ticket_escalated

        notify_ticket_escalated(ticket)
    except Exception as exc:
        logger.warning("Push notify_ticket_escalated failed: %s", exc)
