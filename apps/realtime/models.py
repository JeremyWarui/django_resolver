from django.conf import settings
from django.db import models


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
