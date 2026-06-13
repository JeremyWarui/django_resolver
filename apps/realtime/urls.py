from django.urls import path
from apps.realtime.views import PushSubscribeView, VapidPublicKeyView

urlpatterns = [
    path("push/subscribe/", PushSubscribeView.as_view(), name="push-subscribe"),
    path("push/vapid-key/", VapidPublicKeyView.as_view(), name="push-vapid-key"),
]
