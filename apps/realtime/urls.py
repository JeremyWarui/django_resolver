from django.urls import path
from apps.realtime.views import (
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    PushSubscribeView,
    VapidPublicKeyView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notifications-list"),
    path(
        "notifications/<int:pk>/read",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    path(
        "notifications/read-all/",
        NotificationMarkAllReadView.as_view(),
        name="notifications-read-all",
    ),
    path("push/subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    path("push/vapid-key/", VapidPublicKeyView.as_view(), name="push-vapid-key"),
]
