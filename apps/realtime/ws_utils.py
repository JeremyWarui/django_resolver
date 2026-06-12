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


def _campus_department_id(ticket) -> int | None:
    """Return the campus_department_id for a ticket's section — one targeted query."""
    try:
        from apps.org.models import Section
        return Section.objects.values_list("campus_department_id", flat=True).get(pk=ticket.section_id)
    except Exception:
        return None


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


def emit_ticket_assigned(ticket) -> None:
    assignee = ticket.assigned_to
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "assignedToId": assignee.id if assignee else None,
        "assignedToName": (assignee.get_full_name() or assignee.username) if assignee else None,
    }
    for group in [f"ticket_{ticket.id}", f"section_{ticket.section_id}", f"user_{ticket.raised_by_id}"]:
        emit_ws_event(group, "ticket_assigned", payload)


def emit_ticket_status_changed(ticket, from_status: str) -> None:
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "fromStatus": from_status,
        "toStatus": ticket.status,
    }
    for group in [f"ticket_{ticket.id}", f"section_{ticket.section_id}", f"user_{ticket.raised_by_id}"]:
        emit_ws_event(group, "ticket_status_changed", payload)


def emit_ticket_resolved(ticket) -> None:
    assignee = ticket.assigned_to
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "resolvedBy": (assignee.get_full_name() or assignee.username) if assignee else "System",
    }
    for group in [f"ticket_{ticket.id}", f"user_{ticket.raised_by_id}"]:
        emit_ws_event(group, "ticket_resolved", payload)


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


def emit_ticket_escalated(ticket) -> None:
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "currentLevel": ticket.current_level,
    }
    for group in [f"ticket_{ticket.id}", f"section_{ticket.section_id}", f"user_{ticket.raised_by_id}"]:
        emit_ws_event(group, "ticket_escalated", payload)
    cd_id = _campus_department_id(ticket)
    if cd_id:
        emit_ws_event(f"campus_department_{cd_id}", "ticket_escalated", payload)
