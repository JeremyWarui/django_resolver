import os

from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.realtime.models import Notification, PushSubscription


def _serialize_notification(n):
    return {
        "id": str(n.pk),
        "eventType": n.event_type,
        "title": n.title,
        "body": n.body,
        "ticketId": str(n.ticket_id) if n.ticket_id else None,
        "read": n.read,
        "createdAt": n.created_at.isoformat(),
    }


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user).order_by("-created_at")[:50]
        data = [_serialize_notification(n) for n in qs]
        return Response({
            "data": data,
            "unreadCount": sum(1 for n in data if not n["read"]),
        })


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        n = get_object_or_404(Notification, pk=pk, user=request.user)
        n.read = True
        n.save(update_fields=["read"])
        return Response(status=204)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, read=False).update(read=True)
        return Response(status=204)


class PushSubscribeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        endpoint = request.data.get("endpoint")
        p256dh = request.data.get("keys", {}).get("p256dh")
        auth = request.data.get("keys", {}).get("auth")

        if not all([endpoint, p256dh, auth]):
            return Response({"detail": "endpoint, keys.p256dh, and keys.auth are required."}, status=400)

        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user": request.user, "p256dh": p256dh, "auth": auth},
        )
        return Response({"detail": "Subscribed."}, status=201)

    def delete(self, request):
        endpoint = request.data.get("endpoint")
        if not endpoint:
            return Response({"detail": "endpoint is required."}, status=400)
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
        return Response(status=204)


class VapidPublicKeyView(APIView):
    """Returns the VAPID public key so the frontend can subscribe."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"vapid_public_key": os.getenv("VAPID_PUBLIC_KEY", "")})
