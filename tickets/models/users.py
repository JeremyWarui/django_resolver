from django.contrib.auth.models import AbstractUser
from django.db import models

from .organisation import Campus, Department, CampusDepartment


class CustomUser(AbstractUser):
    """User model with role-based organisational scope."""

    ROLE_CHOICES = [
        ("user", "User"),
        ("technician", "Technician"),
        ("head_of_section", "Head of Section"),
        ("hod", "Head of Department"),
        ("manager", "Manager"),
        ("admin", "System Administrator"),
    ]

    role = models.CharField(
        max_length=15, choices=ROLE_CHOICES, default="user")
    primary_campus = models.ForeignKey(
        Campus,
        on_delete=models.SET_NULL,
        related_name="primary_users",
        null=True,
        blank=True,
    )
    primary_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name="primary_users",
        null=True,
        blank=True,
    )
    sections = models.ManyToManyField(
        "tickets.Section",
        related_name="technicians",
        blank=True,
        through="tickets.TechnicianSection",
    )
    phone_number = models.CharField(max_length=15, blank=True)
    can_assign_tickets = models.BooleanField(default=False)
    can_escalate_tickets = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=False)

    class Meta:
        app_label = "tickets"
        ordering = ["username"]

    def __str__(self):
        campus_code = self.primary_campus.code if self.primary_campus else "NO-CAMPUS"
        return f"{self.username} ({self.get_role_display()}) - {campus_code}"

    @property
    def organizational_scope(self):
        return {
            "user": "section",
            "technician": "section",
            "head_of_section": "section",
            "hod": "department",
            "manager": "organisation",
            "admin": "system",
        }.get(self.role, "none")

    def get_accessible_campuses(self):
        """All campuses for admin/manager; own campus for everyone else."""
        if self.role in ("admin", "manager"):
            return Campus.objects.all()
        if self.primary_campus:
            return Campus.objects.filter(id=self.primary_campus.id)
        return Campus.objects.none()

    def get_accessible_departments(self):
        """All departments for admin/manager; campus-scoped for hod; own for others."""
        if self.role in ("admin", "manager"):
            return Department.objects.all()
        if self.role == "hod" and self.primary_campus:
            return Department.objects.filter(
                campus_departments__campus=self.primary_campus
            ).distinct()
        if self.primary_department:
            return Department.objects.filter(id=self.primary_department.id)
        return Department.objects.none()

    @property
    def primary_campus_department(self):
        """The CampusDepartment that maps this user's primary campus + department."""
        if not self.primary_campus or not self.primary_department:
            return None
        return CampusDepartment.objects.filter(
            campus=self.primary_campus, department=self.primary_department
        ).first()
