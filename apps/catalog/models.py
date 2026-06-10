from django.db import models


class ServiceCategory(models.Model):
    """A grouping of related services within a SectionType.

    department is intentionally absent (R4): it derives via section_type.department.
    location_details controls whether the ticket creation wizard shows a location
    section (replaces the old context_config JSON).
    default_priority is the fallback priority for all tickets in this category;
    individual ServiceItems may override it with their own default_priority.
    """

    section_type = models.ForeignKey(
        "org.SectionType",
        on_delete=models.CASCADE,
        related_name="service_categories",
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    location_details = models.BooleanField(
        default=False,
        help_text="Whether the ticket creation wizard should collect location information.",
    )
    default_priority = models.ForeignKey(
        "sla.Priority",
        on_delete=models.PROTECT,
        related_name="service_categories",
    )

    class Meta:
        app_label = "catalog"
        ordering = ["section_type", "name"]
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

    default_priority is a nullable FK override. When null, the ticket inherits
    default_priority from the parent ServiceCategory.
    """

    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name="service_items",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    default_priority = models.ForeignKey(
        "sla.Priority",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_items",
        help_text="Optional item-level priority override; falls back to category default when null.",
    )

    class Meta:
        app_label = "catalog"
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_service_item_per_category",
            )
        ]

    @property
    def resolved_priority(self):
        """Return this item's effective priority (item override or category default)."""
        return self.default_priority or self.category.default_priority

    def __str__(self):
        return f"{self.category.name} → {self.name}"
