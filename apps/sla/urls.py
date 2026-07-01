from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.sla.views import EscalationRuleViewSet, PriorityViewSet

router = DefaultRouter()
router.register("priorities", PriorityViewSet, basename="priority")

urlpatterns = router.urls + [
    path(
        "priorities/<int:priority_pk>/escalation-rules/",
        EscalationRuleViewSet.as_view({"get": "list", "post": "create"}),
        name="escalation-rules-list",
    ),
    path(
        "priorities/<int:priority_pk>/escalation-rules/<int:pk>/",
        EscalationRuleViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="escalation-rules-detail",
    ),
]
