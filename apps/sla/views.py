from rest_framework import viewsets

from apps.common.pagination import ConfigListPagination
from apps.common.permissions import IsAdminGroup
from apps.sla.models import EscalationRule, Priority
from apps.sla.serializers import EscalationRuleSerializer, PrioritySerializer


class PriorityViewSet(viewsets.ModelViewSet):
    queryset = Priority.objects.prefetch_related("escalation_rules").order_by("rank")
    serializer_class = PrioritySerializer
    permission_classes = [IsAdminGroup]
    pagination_class = ConfigListPagination


class EscalationRuleViewSet(viewsets.ModelViewSet):
    """Nested under /priorities/<priority_pk>/escalation-rules/."""

    serializer_class = EscalationRuleSerializer
    permission_classes = [IsAdminGroup]
    pagination_class = ConfigListPagination

    def get_queryset(self):
        qs = EscalationRule.objects.select_related("priority")
        priority_pk = self.kwargs.get("priority_pk")
        if priority_pk:
            qs = qs.filter(priority_id=priority_pk)
        return qs.order_by("priority", "order")

    def perform_create(self, serializer):
        priority_pk = self.kwargs.get("priority_pk")
        if priority_pk:
            serializer.save(priority_id=priority_pk)
        else:
            serializer.save()
