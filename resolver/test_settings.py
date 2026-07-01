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
