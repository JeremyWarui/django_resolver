from django.db import models


class FacilityType(models.Model):
    """A small, fixed enumeration of facility kinds (e.g. office_block, building).

    Seeded once; the set changes only with a code + seed change.
    Each type maps to one location form on the frontend.
    """

    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=20, unique=True)   # stable key used to pick the location form

    class Meta:
        app_label = "facilities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Facility(models.Model):
    """A physical building or place on a campus; drives the location dropdown."""

    campus = models.ForeignKey(
        "org.Campus",
        on_delete=models.CASCADE,
        related_name="facilities",
    )
    facility_type = models.ForeignKey(
        FacilityType,
        on_delete=models.PROTECT,
        related_name="facilities",
    )
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=40, blank=True)

    class Meta:
        app_label = "facilities"
        ordering = ["campus", "name"]
        verbose_name_plural = "Facilities"

    def __str__(self):
        return f"{self.campus} – {self.name}"
