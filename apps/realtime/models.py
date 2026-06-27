from django.conf import settings
from django.db import models


class Notification(models.Model):
    EVENT_TYPES = [
        ("ticket_created", "Ticket Created"),
        ("ticket_assigned", "Ticket Assigned"),
        ("ticket_status_changed", "Ticket Status Changed"),
        ("ticket_escalated", "Ticket Escalated"),
        ("ticket_resolved", "Ticket Resolved"),
        ("comment_added", "Comment Added"),
        ("sla_warning", "SLA Warning"),
        ("sla_breach", "SLA Breach"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPES)
    title = models.CharField(max_length=128)
    body = models.CharField(max_length=256)
    ticket = models.ForeignKey(
        "tickets.Ticket",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    ticket_no = models.CharField(max_length=24, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "realtime_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "read"]),
        ]

    def __str__(self):
        return f"Notification({self.user_id}, {self.event_type}, read={self.read})"


class PushSubscription(models.Model):
    """Stores a browser Web Push subscription for a user device."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "realtime_push_subscription"

    def __str__(self):
        return f"PushSubscription(user={self.user_id}, endpoint=…{self.endpoint[-30:]})"

    def as_dict(self):
        return {
            "endpoint": self.endpoint,
            "keys": {"p256dh": self.p256dh, "auth": self.auth},
        }
