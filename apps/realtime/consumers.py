"""Django Channels consumer for the Service Desk WebSocket endpoint.

Connection URL: ws[s]://host/ws/?token=<jwt>

On connect the server automatically subscribes to:
  - user_{userId}  — always (covers My Requests, §5.5)
  - section_{sectionId}  — for technician/hos roles
  - campus_department_{campusDepartmentId}  — for hod role

Clients may also send join/leave messages for transient ticket-page channels:
  { "type": "join",  "channel": "ticket_42" }
  { "type": "leave", "channel": "ticket_42" }

Group naming (underscores only — Channels requirement):
  user_{userId}
  ticket_{ticketId}
  section_{sectionId}
  campus_department_{campusDepartmentId}
"""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class ServiceDeskConsumer(AsyncWebsocketConsumer):
    """Scoped pub/sub WebSocket consumer."""

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user = user
        self.joined_groups: set[str] = set()
        await self.accept()

        await self._auto_join(f"user_{user.id}")

        role = self.scope.get("active_role")
        if role in ("technician", "hos"):
            section_id = self.scope.get("section_id")
            if section_id:
                await self._auto_join(f"section_{section_id}")
        elif role == "hod":
            cd_id = self.scope.get("campus_department_id")
            if cd_id:
                await self._auto_join(f"campus_department_{cd_id}")

        logger.debug("WS connected: user=%s role=%s", user.id, role)

    async def disconnect(self, close_code):
        for group in list(self.joined_groups):
            await self.channel_layer.group_discard(group, self.channel_name)
        self.joined_groups.clear()
        logger.debug("WS disconnected: user=%s code=%s", getattr(self, "user", "?"), close_code)

    async def receive(self, text_data):
        try:
            msg = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        msg_type = msg.get("type")
        channel = msg.get("channel", "")

        if msg_type == "join" and channel:
            await self._handle_join(channel)
        elif msg_type == "leave" and channel:
            await self._handle_leave(channel)

    async def _auto_join(self, group: str):
        await self.channel_layer.group_add(group, self.channel_name)
        self.joined_groups.add(group)

    async def _handle_join(self, channel: str):
        if not self._is_allowed_channel(channel):
            await self.send(
                json.dumps({"type": "error", "message": f"Not permitted to join channel: {channel}"})
            )
            return
        await self.channel_layer.group_add(channel, self.channel_name)
        self.joined_groups.add(channel)

    async def _handle_leave(self, channel: str):
        await self.channel_layer.group_discard(channel, self.channel_name)
        self.joined_groups.discard(channel)

    def _is_allowed_channel(self, channel: str) -> bool:
        user = self.user
        # Use only the scope claim set by JWT middleware — never touch the ORM
        # from an async context (SynchronousOnlyOperation).
        role = self.scope.get("active_role")
        uid = str(user.id)

        if channel == f"user_{uid}":
            return True
        if channel.startswith("ticket_"):
            return True
        if channel.startswith("section_"):
            return role in ("technician", "hos", "hod", "admin")
        if channel.startswith("campus_department_"):
            return role in ("hod", "manager", "admin")
        return False

    async def send_event(self, event):
        await self.send(json.dumps(event.get("data", {})))
