"""ASGI config — Django Channels WebSocket support.

Serves both HTTP (via Django's ASGI application) and WebSocket
(via ServiceDeskConsumer) through a single ProtocolTypeRouter.

WebSocket URL: ws[s]://host/ws/?token=<jwt>
  - Token validated by JWTWebSocketMiddleware before consumer handshake.
  - Invalid/missing token → close with code 4001.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "resolver.settings")

from django.core.asgi import get_asgi_application

# Django setup must run before importing channels or our consumers.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

from apps.realtime.middleware import JWTWebSocketMiddleware
from apps.realtime.consumers import ServiceDeskConsumer

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            JWTWebSocketMiddleware(
                URLRouter(
                    [
                        path("ws/", ServiceDeskConsumer.as_asgi()),
                    ]
                )
            )
        ),
    }
)
