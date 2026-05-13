from django.db import models

from .organisation import Campus


class Facility(models.Model):
    """A physical building or asset on a campus."""

    FACILITY_CHOICES = [
        ("building", "Building"),
        ("workshop", "Workshop"),
        ("equipment", "Equipment"),
        ("outdoor", "Outdoor Area"),
        ("residential", "Residential"),
        ("other", "Other"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("maintenance", "Under Maintenance"),
        ("inactive", "Inactive"),
        ("decommissioned", "Decommissioned"),
    ]

    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="facilities",
    )
    name = models.CharField(max_length=100)
    facility_code = models.CharField(max_length=20, blank=True)
    type = models.CharField(
        max_length=50, choices=FACILITY_CHOICES, default="building")
    location = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=50, choices=STATUS_CHOICES, default="active")
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    asset_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        app_label = "tickets"
        ordering = ["campus", "name"]
        verbose_name_plural = "Facilities"

    def __str__(self):
        code = self.facility_code or "?"
        return f"{self.campus.code}-{code}: {self.name}"


class FacilityFloor(models.Model):
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="floors"
    )
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "tickets"
        ordering = ["facility", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["facility", "name"], name="unique_floor_per_facility"
            )
        ]

    def __str__(self):
        return f"{self.facility.name} – {self.name}"


class FacilityRoom(models.Model):
    floor = models.ForeignKey(
        FacilityFloor, on_delete=models.CASCADE, related_name="rooms"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)

    class Meta:
        app_label = "tickets"
        ordering = ["floor", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["floor", "name"], name="unique_room_per_floor"
            )
        ]

    def __str__(self):
        return f"{self.floor.name} – {self.name}"
