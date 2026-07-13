"""Test settings — extends base settings, switches DATABASES to SQLite in-memory."""

from .settings import *  # noqa: F401, F403

# Allow all origins/hosts so WebsocketCommunicator (no Origin header) passes OriginValidator.
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use in-memory channel layer so WS tests don't require Redis.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Send invite/reset emails synchronously in tests: DATABASES above is an
# in-memory SQLite DB, which is connection-local, so a background thread
# would open its own empty database and any DB-touching send would silently
# no-op. Synchronous sending also keeps mail.outbox assertions deterministic.
EMAIL_SEND_ASYNC = False
