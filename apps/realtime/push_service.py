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
        body=f"{ticket.ticket_no}: {ticket.title}",
        data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "assigned"},
    )


def notify_ticket_escalated(ticket) -> None:
    assignee = ticket.assigned_to
    if not assignee:
        return
    send_push_to_user(
        user_id=assignee.id,
        title="Ticket Escalated",
        body=f"{ticket.ticket_no} has been escalated to level {ticket.current_level}",
        data={"ticketId": ticket.id, "ticket_no": ticket.ticket_no, "type": "escalated"},
    )
