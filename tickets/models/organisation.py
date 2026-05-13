from django.db import models
from django.conf import settings


class Campus(models.Model):
    """Physical campus or branch — standalone, not scoped to an Organisation."""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=10, unique=True)  # e.g. "NRB", "MSA"
    location = models.CharField(max_length=200, blank=True)

    class Meta:
        app_label = "tickets"
        ordering = ["name"]
        verbose_name_plural = "Campuses"

    def __str__(self):
        return f"{self.code}: {self.name}"


class Department(models.Model):
    """Global functional division — one canonical record per department type.

    A Department exists once in the system and is present at one or more
    campuses via `CampusDepartment`. The optional `manager_user` is the
    organisation-wide manager (not campus-specific; campus HODs live on
    `CampusDepartment.head_of_department`).
    """

    name = models.CharField(max_length=200, unique=True)
    # e.g. "ICT", "HR", "ADM"
    code = models.CharField(max_length=10, unique=True)
    manager_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
    )

    class Meta:
        app_label = "tickets"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"], name="unique_department_name"),
            models.UniqueConstraint(
                fields=["code"], name="unique_department_code"),
        ]

    def __str__(self):
        return f"{self.code}: {self.name}"


class CampusDepartment(models.Model):
    """Operational mapping between a `Campus` and a global `Department`.

    Each CampusDepartment represents the presence of a global Department at
    a particular Campus and ties to the campus-level HOD user.
    """

    campus = models.ForeignKey(
        Campus, on_delete=models.CASCADE, related_name="campus_departments"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="campus_departments"
    )
    head_of_department = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        # user.headed_campus_departments.all()
        related_name="headed_campus_departments",
    )

    class Meta:
        app_label = "tickets"
        ordering = ["campus", "department"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "department"],
                name="unique_campus_department",
            )
        ]

    def __str__(self):
        return f"{self.campus.code} – {self.department.code}"
