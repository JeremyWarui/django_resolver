from django.db import models


class Priority(models.Model):
    """A named priority level with associated SLA targets.

    Priorities are system-wide. A ticket's effective priority is resolved from:
      ServiceItem.default_priority (nullable) → ServiceCategory.default_priority

    rank: 1 = lowest, 4 = highest (used for ordering and escalation logic).
    response_minutes: SLA target from ticket creation to first assignment.
    resolution_minutes: SLA target from ticket creation to resolved status.
    """

    name = models.CharField(max_length=80)
    rank = models.PositiveIntegerField(unique=True)
    response_minutes = models.PositiveIntegerField()
    resolution_minutes = models.PositiveIntegerField()

    class Meta:
        app_label = "sla"
        ordering = ["rank"]
        verbose_name_plural = "Priorities"

    def __str__(self):
        return f"{self.name} (rank {self.rank})"


class EscalationRule(models.Model):
    """When and to whom a ticket escalates based on priority.

    threshold_minutes: minutes from ticket creation before escalating to this level.
    order: evaluation order within a priority's escalation rules.
    """

    TO_LEVEL_CHOICES = [
        ("hos", "HOS"),
        ("hod", "HOD"),
    ]

    priority = models.ForeignKey(
        Priority,
        on_delete=models.CASCADE,
        related_name="escalation_rules",
    )
    to_level = models.CharField(max_length=4, choices=TO_LEVEL_CHOICES)
    threshold_minutes = models.PositiveIntegerField()
    order = models.PositiveIntegerField()

    class Meta:
        app_label = "sla"
        ordering = ["priority", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["priority", "to_level"],
                name="unique_escalation_rule_per_priority_level",
            ),
            models.UniqueConstraint(
                fields=["priority", "order"],
                name="unique_escalation_rule_order_per_priority",
            ),
        ]

    def __str__(self):
        return (
            f"{self.priority.name} → {self.get_to_level_display()} "
            f"after {self.threshold_minutes}m"
        )
