"""WebSocket emit helpers for Django Channels.

These are no-ops when channels is not installed or the channel layer is not
configured. All emit calls are wrapped in try/except so views work in
environments without Redis/channels.
"""

import logging

logger = logging.getLogger(__name__)


def emit_ws_event(group_name: str, event_type: str, data: dict) -> None:
    """Send an event to a Django Channels group."""
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


def emit_ticket_created(ticket) -> None:
    if not ticket.section_id or not ticket.campus_department_id:
        return
    campus_id = ticket.campus_department.campus_id
    group = f"section_{ticket.section_id}_{campus_id}"
    emit_ws_event(
        group,
        "ticket_created",
        {
            "ticketId": ticket.id,
            "ticket_no": ticket.ticket_no,
            "title": ticket.title,
            "priority": ticket.priority,
            "sectionId": ticket.section_id,
            "campusId": campus_id,
        },
    )


def emit_ticket_assigned(ticket) -> None:
    assignee = ticket.assigned_to
    campus_id = ticket.campus_department.campus_id
    payload = {
        "ticketId": ticket.id,
        "assignedToId": assignee.id if assignee else None,
        "assignedToName": assignee.get_full_name() or assignee.username if assignee else None,
    }
    for group in [
        f"ticket_{ticket.id}",
        f"section_{ticket.section_id}_{campus_id}",
        f"user_{ticket.raised_by_id}",
    ]:
        emit_ws_event(group, "ticket_assigned", payload)


def emit_ticket_status_changed(ticket, from_status: str, note: str = "") -> None:
    campus_id = ticket.campus_department.campus_id
    payload = {
        "ticketId": ticket.id,
        "fromStatus": from_status,
        "toStatus": ticket.status,
        "note": note,
    }
    for group in [
        f"ticket_{ticket.id}",
        f"section_{ticket.section_id}_{campus_id}",
        f"user_{ticket.raised_by_id}",
    ]:
        emit_ws_event(group, "ticket_status_changed", payload)


def emit_comment_added(ticket, comment) -> None:
    body_preview = (comment.text or "")[:100]
    author = comment.author
    payload = {
        "ticketId": ticket.id,
        "commentId": comment.id,
        "authorName": author.get_full_name() or author.username if author else "",
        "preview": body_preview,
    }
    emit_ws_event(f"ticket_{ticket.id}", "comment_added", payload)


def emit_ticket_escalated(ticket, escalated_by) -> None:
    campus_id = ticket.campus_department.campus_id if ticket.campus_department_id else None
    dept_id = ticket.campus_department.department_id if ticket.campus_department_id else None
    by_name = escalated_by.get_full_name() or escalated_by.username
    payload = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "escalatedBy": by_name,
        "reason": (ticket.escalation_reason or "")[:100],
    }
    for group in [
        f"ticket_{ticket.id}",
        *(
            [f"dept_{dept_id}_{campus_id}"]
            if dept_id and campus_id
            else []
        ),
    ]:
        emit_ws_event(group, "ticket_escalated", payload)


def emit_ticket_resolved(ticket) -> None:
    assignee = ticket.assigned_to
    resolved_by = assignee.get_full_name() or assignee.username if assignee else "System"
    payload = {
        "ticketId": ticket.id,
        "resolvedBy": resolved_by,
    }
    for group in [
        f"ticket_{ticket.id}",
        f"user_{ticket.raised_by_id}",
    ]:
        emit_ws_event(group, "ticket_resolved", payload)
