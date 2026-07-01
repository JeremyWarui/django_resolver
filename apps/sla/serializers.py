from rest_framework import serializers

from apps.sla.models import EscalationRule, Priority


class EscalationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = EscalationRule
        fields = ["id", "priority", "to_level", "threshold_minutes", "order"]


class PrioritySerializer(serializers.ModelSerializer):
    escalation_rules = EscalationRuleSerializer(many=True, read_only=True)

    class Meta:
        model = Priority
        fields = [
            "id",
            "name",
            "rank",
            "response_minutes",
            "resolution_minutes",
            "escalation_rules",
        ]
        read_only_fields = ["escalation_rules"]
