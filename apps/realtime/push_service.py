"""Web Push delivery service.

Sends push notifications to all registered devices for a user.
No-ops gracefully when VAPID keys are not configured or pywebpush is absent.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_ADMIN_EMAIL = os.getenv("VAPID_ADMIN_EMAIL", "admin@resolver.local")

_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)


def send_push_to_user(user_id: int, title: str, body: str, data: dict | None = None) -> None:
    """Send a push notification to all subscribed devices for a user."""
    if not _ENABLED:
        return
    try:
        from apps.realtime.models import PushSubscription
        subs = PushSubscription.objects.filter(user_id=user_id)
        stale_ids = []
        for sub in subs:
            success = _send_one(sub, title, body, data or {})
            if not success:
                stale_ids.append(sub.id)
        if stale_ids:
            PushSubscription.objects.filter(id__in=stale_ids).delete()
    except Exception as exc:
        logger.warning("push_to_user(%s) failed: %s", user_id, exc)


def _send_one(sub, title: str, body: str, data: dict) -> bool:
    try:
        from pywebpush import webpush, WebPushException
        import base64

        private_key_pem = base64.urlsafe_b64decode(
            VAPID_PRIVATE_KEY + "=" * (-len(VAPID_PRIVATE_KEY) % 4)
        ).decode()

        webpush(
            subscription_info=sub.as_dict(),
            data=json.dumps({"title": title, "body": body, **data}),
            vapid_private_key=private_key_pem,
            vapid_claims={"sub": f"mailto:{VAPID_ADMIN_EMAIL}"},
        )
        return True
    except Exception as exc:
        err = str(exc)
        if "410" in err or "404" in err:
            logger.info("Stale push subscription %s removed.", sub.id)
            return False
        logger.warning("Push to sub %s failed: %s", sub.id, exc)
        return True  # keep — might be a transient error


# ── Convenience helpers called from ws_utils ──────────────────────────────────

def notify_ticket_assigned(ticket) -> None:
    assignee = ticket.assigned_to
    if not assignee:
        return
    send_push_to_user(
        user_id=assignee.id,
        title="Ticket Assigned",
        body=f"{ticket.ticket_no}: {ticket.service_item.name}",
        data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "assigned"},
    )


def notify_ticket_created(ticket) -> None:
    """Push to all HOS users for the ticket's section so they know to assign it."""
    try:
        from apps.accounts.models import RoleAssignment
        hos_ids = list(
            RoleAssignment.objects.filter(
                role="hos", section_id=ticket.section_id, is_primary=True
            ).values_list("user_id", flat=True)
        )
    except Exception:
        hos_ids = []
    for uid in hos_ids:
        send_push_to_user(
            user_id=uid,
            title="New Ticket",
            body=f"{ticket.ticket_no}: {ticket.service_item.name}",
            data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "created"},
        )


def notify_ticket_status_changed(ticket, from_status: str) -> None:
    """Push to the requester when their ticket status changes."""
    send_push_to_user(
        user_id=ticket.raised_by_id,
        title="Ticket Updated",
        body=f"Ticket #{ticket.ticket_no}: {from_status.replace('_', ' ')} → {ticket.status.replace('_', ' ')}",
        data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "status_changed"},
    )


def notify_ticket_resolved(ticket) -> None:
    """Push to the requester when their ticket is resolved."""
    send_push_to_user(
        user_id=ticket.raised_by_id,
        title="Ticket Resolved",
        body=f"Ticket #{ticket.ticket_no} has been resolved. Please rate your experience.",
        data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "resolved"},
    )


def notify_comment_added(ticket, comment) -> None:
    """Push to the requester when a staff member comments on their ticket."""
    author = comment.author
    if author and author.id == ticket.raised_by_id:
        return  # requester's own comment — skip
    author_name = (author.get_full_name() or author.username) if author else "Staff"
    send_push_to_user(
        user_id=ticket.raised_by_id,
        title=f"New comment on #{ticket.ticket_no}",
        body=f"{author_name}: {(comment.body or '')[:80]}",
        data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "comment"},
    )


def notify_ticket_escalated(ticket) -> None:
    """Push to the assignee and all HOS/HOD holders for the ticket's section."""
    assignee = ticket.assigned_to
    escalation_data = {
        "ticketId": ticket.id,
        "ticket_no": ticket.ticket_no,
        "type": "escalated",
    }

    if assignee:
        send_push_to_user(
            user_id=assignee.id,
            title="Ticket Escalated",
            body=f"Ticket #{ticket.ticket_no} has been escalated to {ticket.current_level.upper()}",
            data=escalation_data,
        )

    # Also push to HOS/HOD so they can act on the escalation
    try:
        from apps.accounts.models import RoleAssignment
        from apps.org.models import Section
        cd_id = Section.objects.values_list("campus_department_id", flat=True).get(
            pk=ticket.section_id
        )
        supervisor_ids = set(
            RoleAssignment.objects.filter(
                role="hos", section_id=ticket.section_id, is_primary=True
            ).values_list("user_id", flat=True)
        ) | set(
            RoleAssignment.objects.filter(
                role="hod", campus_department_id=cd_id, is_primary=True
            ).values_list("user_id", flat=True)
        )
        # Don't double-notify the assignee if they happen to also hold a supervisor role
        supervisor_ids.discard(assignee.id if assignee else None)
    except Exception:
        supervisor_ids = set()

    for uid in supervisor_ids:
        send_push_to_user(
            user_id=uid,
            title="Ticket Escalated",
            body=f"Ticket #{ticket.ticket_no} has been escalated to {ticket.current_level.upper()}",
            data=escalation_data,
        )
