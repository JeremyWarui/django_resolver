"""JWT authentication middleware for Django Channels WebSocket connections.

Reads the JWT from the `token` query-string parameter, validates it with
SimpleJWT, and populates `scope["user"]` and scope claim keys before the
consumer is invoked.

On failure: closes the WebSocket with code 4001 (auth error).
"""

from urllib.parse import parse_qs

from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _get_user_and_claims_from_token(token_key: str):
    """Validate the JWT and return (user, claims_dict), or (AnonymousUser, {})."""
    try:
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model

        User = get_user_model()
        access = AccessToken(token_key)
        user_id = access.get("sub") or access.get("user_id")
        claims = {
            "role": access.get("role"),
            "section_id": access.get("section_id"),
            "campus_department_id": access.get("campus_department_id"),
            "department_id": access.get("department_id"),
            "role_assignment_id": access.get("role_assignment_id"),
        }
        return User.objects.get(pk=user_id), claims
    except Exception:
        return AnonymousUser(), {}


class JWTWebSocketMiddleware(BaseMiddleware):
    """Validate JWT from ?token= before accepting the WebSocket connection."""

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "websocket":
            await super().__call__(scope, receive, send)
            return

        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token_list = params.get("token", [])

        reject = False
        if not token_list:
            reject = True
        else:
            user, claims = await _get_user_and_claims_from_token(token_list[0])
            if isinstance(user, AnonymousUser) or not user.is_authenticated:
                reject = True
            else:
                scope["user"] = user
                scope["active_role"] = claims.get("role")
                scope["section_id"] = claims.get("section_id")
                scope["campus_department_id"] = claims.get("campus_department_id")
                scope["department_id"] = claims.get("department_id")
                scope["role_assignment_id"] = claims.get("role_assignment_id")

        if reject:
            message = await receive()
            assert message["type"] == "websocket.connect"
            await send({"type": "websocket.close", "code": 4001})
            return

        await super().__call__(scope, receive, send)
