from django.db import models

from .sections import SectionType


class ServiceCategory(models.Model):
    """A grouping of related services within a SectionType.

    Ticket creation flow (step 1 of 2):
      User picks a Department → the system looks up the matching SectionType
      → filters ServiceCategories for that SectionType and presents them as
      the first selection step (e.g. "Hardware", "Software", "Networking").
    """

    section_type = models.ForeignKey(
        SectionType,
        on_delete=models.CASCADE,
        related_name="service_categories",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "tickets"
        ordering = ["section_type", "order", "name"]
        verbose_name_plural = "Service Categories"
        constraints = [
            models.UniqueConstraint(
                fields=["section_type", "name"],
                name="unique_service_category_per_section_type",
            )
        ]

    def __str__(self):
        return f"{self.section_type.code}: {self.name}"


class ServiceItem(models.Model):
    """A specific, requestable service within a ServiceCategory.

    Ticket creation flow (step 2 of 2):
      After the user picks a ServiceCategory, the system lists its
      ServiceItems (e.g. "Laptop Repair", "Password Reset"). Selecting one
      completes catalogue resolution — the ticket is then stamped with this
      item and the system derives: SectionType → Section → CampusDepartment
      → available technicians. If `requires_approval` is True the ticket
      opens as `pending_approval` instead of `open`.
    """

    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name="service_items",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    requires_approval = models.BooleanField(
        default=False,
        help_text="If True, ticket opens as pending_approval instead of open.",
    )
    sla_hours = models.IntegerField(
        null=True,
        blank=True,
        help_text="Item-level SLA override; falls back to Section → SectionType defaults.",
    )
    form_schema = models.JSONField(
        default=list,
        help_text="Array of field definitions for dynamic form rendering.",
    )
    default_priority = models.CharField(
        max_length=20,
        choices=[
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="low",
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "tickets"
        ordering = ["category", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_service_item_per_category",
            )
        ]

    def __str__(self):
        return f"{self.category.name} → {self.name}"
