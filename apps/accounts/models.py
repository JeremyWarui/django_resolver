from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    """User model. Role is derived from the active primary RoleAssignment — not stored."""

    phone_number = models.CharField(max_length=15, blank=True)

    class Meta:
        app_label = "accounts"
        ordering = ["username"]

    def __str__(self):
        return self.username

    @property
    def primary_role_assignment(self):
        """Return the active primary RoleAssignment, or None."""
        return (
            self.role_assignments.filter(is_primary=True)
            .select_related("section", "campus_department", "department")
            .first()
        )

    @property
    def role(self):
        """Derived accessor — reads from the active primary RoleAssignment."""
        ra = self.primary_role_assignment
        return ra.role if ra else None

    @property
    def campus(self):
        """Convenience: the user's home campus from their UserProfile."""
        try:
            return self.profile.campus
        except UserProfile.DoesNotExist:
            return None


class UserProfile(models.Model):
    """One-to-one extension of CustomUser carrying campus placement."""

    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    campus = models.ForeignKey(
        "org.Campus",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
    )

    class Meta:
        app_label = "accounts"

    def __str__(self):
        campus_code = self.campus.code if self.campus else "NO-CAMPUS"
        return f"{self.user.username} @ {campus_code}"


class RoleAssignment(models.Model):
    """Maps a user to a role with an explicit organisational scope.

    Scope constraints per role (enforced in clean(), not DB CheckConstraints):
      technician / hos → section required
      hod            → campus_department required
      manager        → department required
      admin          → no scope (all three must be null)

    The unique_primary_role_per_user constraint ensures only one primary
    assignment per user (partial unique index on is_primary=True).
    """

    ROLE_CHOICES = [
        ("user", "User"),
        ("technician", "Technician"),
        ("hos", "HOS"),
        ("hod", "HOD"),
        ("manager", "Manager"),
        ("admin", "Admin"),
    ]

    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.CharField(max_length=12, choices=ROLE_CHOICES)

    # Scope FKs — nullable; which one is set depends on the role.
    section = models.ForeignKey(
        "org.Section",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    campus_department = models.ForeignKey(
        "org.CampusDepartment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    department = models.ForeignKey(
        "org.Department",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )

    is_primary = models.BooleanField(default=False)
    valid_from = models.DateTimeField(null=True, blank=True)    # null = effective now
    valid_until = models.DateTimeField(null=True, blank=True)   # null = standing role
    assigned_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="given_role_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "accounts"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_primary=True),
                name="one_primary_role_per_user",
            ),
        ]

    def is_active(self, now=None):
        from apps.common.time_windows import is_window_active

        now = now or timezone.now()
        return is_window_active(self.valid_from, self.valid_until, now)

    def clean(self):
        """Per-role scope rules — one readable, testable place."""
        if self.role in ("technician", "hos"):
            if not self.section_id:
                raise ValidationError(
                    {"section": f"A {self.role} assignment requires a section."}
                )
        elif self.role == "hod":
            if not self.campus_department_id:
                raise ValidationError(
                    {"campus_department": "An HOD assignment requires a campus_department."}
                )
        elif self.role == "manager":
            if not self.department_id:
                raise ValidationError(
                    {"department": "A manager assignment requires a department."}
                )
        elif self.role == "admin":
            # Admin has no scope — all three must be null.
            if self.section_id or self.campus_department_id or self.department_id:
                raise ValidationError(
                    "Admin assignments must have no scope (section, campus_department, department all null)."
                )

    def __str__(self):
        parts = [self.role]
        if self.section_id:
            parts.append(f"section={self.section_id}")
        if self.campus_department_id:
            parts.append(f"cd={self.campus_department_id}")
        if self.department_id:
            parts.append(f"dept={self.department_id}")
        suffix = " [primary]" if self.is_primary else ""
        return f"{self.user_id} / {' > '.join(parts)}{suffix}"
