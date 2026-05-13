from django.db import models
from django.conf import settings

from .organisation import Department, CampusDepartment


class SectionType(models.Model):
    """Blueprint for a type of section that can exist within a Department.

    SectionType is organisation-wide (not campus-specific). Each Department
    can define multiple SectionTypes (e.g. ICT → "Software", "Networks").
    Actual campus-level sections are created as `Section` instances that
    reference both a `CampusDepartment` and a `SectionType`.

    Roles that interact with this model:
    - admin: full CRUD
    - manager / hod: read-only (used when routing tickets)
    """

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="section_types",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    description = models.TextField(blank=True)
    staff_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Display label for staff in this section type (e.g. 'Technician', 'Officer')",
    )
    default_sla_hours = models.IntegerField(
        default=72,
        help_text="Default SLA hours for tickets in sections of this type.",
    )

    class Meta:
        app_label = "tickets"
        ordering = ["department", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"],
                name="unique_section_type_per_department",
            )
        ]

    def __str__(self):
        return f"{self.department.code}-{self.code}: {self.name}"


class Section(models.Model):
    """A campus-specific instance of a SectionType under a CampusDepartment.

    A Section is the operational unit that owns tickets and employs
    technicians. The combination of (campus_department, section_type) is
    unique — you cannot have two "Software" sections under the same
    campus/department pairing.

    Roles that interact with this model:
    - head_of_section: manages this section; can assign tickets and view
      technician workload within the section.
    - head_of_department (on CampusDepartment): can view all sections under
      their campus-department.
    - admin / manager: full visibility across all sections.
    """

    campus_department = models.ForeignKey(
        "CampusDepartment",
        on_delete=models.CASCADE,
        related_name="sections",
    )
    section_type = models.ForeignKey(
        "SectionType",
        on_delete=models.CASCADE,
        related_name="sections",
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    description = models.TextField(blank=True)
    head_of_section = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_sections",
    )
    sla_hours = models.IntegerField(
        null=True,
        blank=True,
        help_text="Section-specific SLA override; falls back to SectionType default.",
    )

    class Meta:
        app_label = "tickets"
        ordering = ["campus_department", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus_department", "section_type"],
                name="unique_section_per_campus_department_type",
            )
        ]

    def __str__(self):
        campus = self.campus_department.campus.code
        dept = self.campus_department.department.code
        prefix = f"{campus}-{dept}-{self.code}" if self.code else f"{campus}-{dept}"
        return f"{prefix}: {self.name}"

    @property
    def campus(self):
        return self.campus_department.campus

    @property
    def effective_sla_hours(self):
        """Section-level override → SectionType default → 24 h fallback."""
        return self.sla_hours or self.section_type.default_sla_hours or 24

    @property
    def full_hierarchy_name(self):
        """Returns CAMPUS-DEPT-SECTION_CODE (e.g. NRB-ICT-SW)."""
        cd = self.campus_department
        return f"{cd.campus.code}-{cd.department.code}-{self.code}" if self.code else self.name


class TechnicianSection(models.Model):
    """Join table linking a technician (User) to one or more Sections.

    A technician may be assigned to multiple sections, including sections
    across different CampusDepartments (e.g. a shared resource). The
    unique constraint ensures the same assignment cannot be duplicated.

    Roles:
    - technician: the assigned user; can only act on tickets in their
      linked sections.
    - head_of_section / head_of_department: may add or remove technicians from sections
      within their scope.
    - admin: full CRUD.
    """

    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="technician_section_links",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="technician_links",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tickets"
        ordering = ["section", "technician"]
        constraints = [
            models.UniqueConstraint(
                fields=["technician", "section"],
                name="unique_technician_section",
            )
        ]

    def __str__(self):
        return f"{self.technician.username} → {self.section}"
