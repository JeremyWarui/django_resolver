# Magic link functionality temporarily disabled - uncomment when email is configured
# from .auth_models import MagicLink, LoginSession
# from .auth_models import LoginSession  # Temporarily disabled for clean migration
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

# Create your models here.

# ORGANIZATIONAL HIERARCHY MODELS


class Organization(models.Model):
    """Root organizational entity - corporation, university, government agency"""

    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=10, unique=True)  # e.g., "UNIV", "CORP"
    organization_type = models.CharField(
        max_length=50,
        choices=[
            ("corporate", "Corporate"),
            ("education", "Educational Institution"),
            ("government", "Government Agency"),
            ("healthcare", "Healthcare System"),
            ("other", "Other"),
        ],
    )
    headquarters = models.CharField(max_length=200)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Campus(models.Model):
    """Geographic or operational division - campus, branch, site"""

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="campuses"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10)  # e.g., "MAIN", "WEST", "HQ"
    location = models.CharField(max_length=200)
    is_headquarters = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["organization", "name"]
        unique_together = [["organization", "code"]]
        verbose_name_plural = "Campuses"

    def __str__(self):
        return f"{self.organization.code}-{self.code}: {self.name}"


class Department(models.Model):
    """Functional division within campus - academics, operations, admin"""

    campus = models.ForeignKey(
        Campus, on_delete=models.CASCADE, related_name="departments"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10)  # e.g., "IT", "HR", "OPS"
    head_of_department = models.ForeignKey(
        "CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_departments",
    )
    department_type = models.ForeignKey(
        'DepartmentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='departments',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["campus", "name"]
        unique_together = [["campus", "code"]]

    def __str__(self):
        return f"{self.campus.code}-{self.code}: {self.name}"


# Custom User Model
class CustomUser(AbstractUser):
    """Enhanced user model with organizational hierarchy awareness"""

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

    # Organizational assignments - temporarily nullable for migration
    primary_campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="primary_users",
        null=True,
        blank=True,  # Temporary for migration
    )
    primary_department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="primary_users",
        null=True,
        blank=True,  # Temporary for migration
    )

    # Multi-section assignment for technicians
    sections = models.ManyToManyField(
        "Section",
        related_name="technicians",
        blank=True,
        help_text="Sections the technician is specialized in.",
    )

    # Additional user context
    phone_number = models.CharField(max_length=15, blank=True)

    # Permissions and capabilities
    can_assign_tickets = models.BooleanField(default=False)
    can_escalate_tickets = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=False)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        campus_code = self.primary_campus.code if self.primary_campus else "NO-CAMPUS"
        return f"{self.username} ({self.get_role_display()}) - {campus_code}"

    @property
    def organizational_scope(self):
        """Returns the scope of organizational access for this user"""
        scopes = {
            "user": "section",
            "technician": "section",
            "head_of_section": "section",
            "hod": "department",
            "manager": "organization",
            "admin": "system",
        }
        return scopes.get(self.role, "none")

    def get_accessible_campuses(self):
        """Returns campuses this user can access based on role"""
        if not self.primary_campus:
            return Campus.objects.none()

        if self.role == "manager":
            return Campus.objects.filter(organization=self.primary_campus.organization)
        elif self.role == "hod":
            return Campus.objects.filter(id=self.primary_campus.id)
        else:
            return Campus.objects.filter(id=self.primary_campus.id)

    def get_accessible_departments(self):
        """Returns departments this user can access"""
        if not self.primary_campus:
            return Department.objects.none()

        accessible_campuses = self.get_accessible_campuses()
        if self.role == "manager":
            return Department.objects.filter(campus__in=accessible_campuses)
        elif self.role == "hod":
            return Department.objects.filter(campus=self.primary_campus)
        elif self.primary_department:
            return Department.objects.filter(id=self.primary_department.id)
        else:
            return Department.objects.none()


# SECTIONS MODEL
class Section(models.Model):
    """Enhanced section model with departmental hierarchy"""

    # Temporarily nullable for migration
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="sections",
        null=True,
        blank=True,  # Temporary for migration
    )
    name = models.CharField(max_length=100)
    code = models.CharField(
        max_length=10, null=True, blank=True
    )  # Temporary for migration
    description = models.TextField(max_length=200, blank=True)
    head_of_section = models.ForeignKey(
        "CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_sections",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]  # Will update after migration

    def __str__(self):
        if self.department:
            return f"{self.department.campus.code}-{self.department.code}-{self.code}: {self.name}"
        return f"{self.name}"  # Fallback during migration

    @property
    def full_hierarchy_name(self):
        """Returns: ORG-CAMPUS-DEPT-SECTION"""
        if (
            self.department
            and self.department.campus
            and self.department.campus.organization
        ):
            return (
                f"{self.department.campus.organization.code}-"
                f"{self.department.campus.code}-"
                f"{self.department.code}-{self.code}"
            )
        return self.name


# FACILITY MODEL
class Facility(models.Model):
    """Enhanced facility model with organizational context"""

    FACILITY_CHOICES = [
        ("building", "Building"),
        ("ict", "ICT Equipment"),
        ("laundry", "Laundry Equipment"),
        ("kitchen", "Kitchen Equipment"),
        ("residential", "Residential"),
        ("classroom", "Classroom"),
        ("office", "Office Space"),
    ]

    name = models.CharField(max_length=100)
    # Will add unique constraint later
    facility_code = models.CharField(
        max_length=20, null=True, blank=True
    )  # Temporary for migration
    type = models.CharField(
        max_length=50, choices=FACILITY_CHOICES, default="building")

    # Organizational location - temporarily nullable for migration
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name="facilities",
        null=True,
        blank=True,  # Temporary for migration
    )
    # Physical details
    location = models.CharField(
        max_length=100, blank=True, null=True
    )  # Building, floor, room
    status = models.CharField(
        max_length=50,
        default="active",
        choices=[
            ("active", "Active"),
            ("maintenance", "Under Maintenance"),
            ("inactive", "Inactive"),
            ("decommissioned", "Decommissioned"),
        ],
    )

    # Asset management
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expiry = models.DateField(null=True, blank=True)
    asset_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["name"]  # Will update after migration
        verbose_name_plural = "Facilities"

    def __str__(self):
        if self.campus and self.facility_code:
            return f"{self.campus.code}-{self.facility_code}: {self.name}"
        return self.name  # Fallback during migration


# TICKETS MODEL
class Ticket(models.Model):
    """Enhanced ticket model with organizational hierarchy and escalation support"""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("escalated", "Escalated"),
        ("pending_approval", "Pending Approval"),
        ("rejected", "Rejected"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    PENDING_REASON_CHOICES = [
        ("material_shortage", "Material Shortage"),
        ("awaiting_procurement", "Awaiting Procurement"),
        ("awaiting_approval", "Awaiting Approval"),
        ("vendor_dependency", "Vendor Dependency"),
        ("access_issue", "Access Issue"),
        ("other", "Other"),
    ]

    # Core ticket information
    # Format: CAMPUS-DEPT-XXXXX (e.g., MAIN-MAINT-00001)
    ticket_no = models.CharField(max_length=25, unique=True, editable=False)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=500)  # Extended description

    # Organizational context
    section = models.ForeignKey(
        Section, on_delete=models.CASCADE, related_name="tickets"
    )
    facility = models.ForeignKey(
        Facility, on_delete=models.CASCADE, related_name="tickets"
    )

    # User relationships
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="raised_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_tickets",
    )
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Time when the ticket was assigned; used as reference for escalation timer",
    )

    # Status and lifecycle
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="low",
        help_text="Ticket priority - escalates with ticket level",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Automatically set when ticket status changes to resolved/closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    # Escalation tracking
    # 0=none, 1=section_head, 2=hod (max level)
    escalation_level = models.IntegerField(default=0)
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="escalated_tickets",
    )
    escalated_at = models.DateTimeField(null=True, blank=True)
    escalation_reason = models.TextField(max_length=500, blank=True)

    # Auto-escalation timing
    auto_escalation_enabled = models.BooleanField(default=True)
    next_escalation_due = models.DateTimeField(
        null=True, blank=True, editable=False)
    escalation_threshold_hours = models.IntegerField(
        default=48
    )  # Hours before auto-escalation

    # Pending state (only used when status='pending')
    pending_reason = models.CharField(
        max_length=50,
        choices=PENDING_REASON_CHOICES,
        blank=True,
        null=True,
        help_text="Reason ticket is marked as pending",
    )
    pending_comment = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Detailed explanation when marking ticket as pending",
    )

    # Additional context
    # Room, building, etc.
    location_details = models.CharField(max_length=200, blank=True)
    estimated_resolution_hours = models.IntegerField(null=True, blank=True)
    actual_resolution_hours = models.IntegerField(
        null=True, blank=True, editable=False)

    # Service catalogue integration
    service_item = models.ForeignKey(
        "ServiceItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
        help_text="Service item this ticket was raised against",
    )
    form_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Form submission data from ServiceItem",
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["status", "section", "-updated_at"],
                name="ticket_section_status_idx",
            ),
            models.Index(
                fields=["assigned_to", "status"], name="ticket_assignment_idx"
            ),
            models.Index(
                fields=["escalation_level", "-escalated_at"],
                name="ticket_escalation_idx",
            ),
            models.Index(
                fields=["next_escalation_due", "auto_escalation_enabled"],
                name="ticket_auto_escalation_idx",
            ),
            # Keep existing status index
            models.Index(
                fields=["status", "-updated_at"], name="ticket_status_updated_idx"
            ),
        ]

    def save(self, *args, performed_by=None, **kwargs):
        """Enhanced save with organizational ticket numbering and auto-escalation scheduling"""
        # 0. Ensure priority is at least what escalation level requires.
        # Critical (set by aging logic) is never downgraded.
        if self.priority != "critical":
            if self.escalation_level == 0:
                self.priority = "low"
            elif self.escalation_level == 1:
                self.priority = "medium"
            elif self.escalation_level >= 2:
                self.priority = "high"

        # 1. Handle ticket number generation for new tickets
        if not self.ticket_no:
            # Generate ticket number: CAMPUS-DEPT-XXXXX
            if (
                self.section
                and self.section.department
                and self.section.department.campus
            ):
                campus_code = self.section.department.campus.code
                dept_code = self.section.department.code

                # Get next sequence number for this department
                last_ticket = (
                    Ticket.objects.filter(
                        section__department=self.section.department)
                    .order_by("-id")
                    .first()
                )

                next_id = 1 if not last_ticket else (
                    last_ticket.id % 99999) + 1
                self.ticket_no = f"{campus_code}-{dept_code}-{next_id:05d}"
            else:
                # Fallback for migration/testing
                last_ticket = Ticket.objects.all().order_by("-id").first()
                next_id = 1 if not last_ticket else last_ticket.id + 1
                self.ticket_no = f"TKT-{next_id:06d}"

        # Auto-set closure timestamp
        if self.status == "closed" and not self.closed_at:
            self.closed_at = timezone.now()

        # If creating or saving a ticket that is already in a resolved state,
        # ensure `resolved_at` is set
        if self.status in ["resolved", "closed"] and not self.resolved_at:
            self.resolved_at = timezone.now()

        # Schedule auto-escalation on creation or status change
        # But don't override if manually set (for testing)
        if not self.next_escalation_due and (
            not self.pk or self.status in ["open", "assigned", "in_progress"]
        ):
            self._schedule_next_escalation()

        super(Ticket, self).save(*args, **kwargs)

    def _schedule_next_escalation(self):
        """Schedule next auto-escalation based on current level and timing rules.

        Escalation timer is based on assigned_at, not created_at.
        Unassigned tickets do not have an escalation timer.
        """
        if not self.auto_escalation_enabled or self.status in ["resolved", "closed"]:
            self.next_escalation_due = None
            return

        # If ticket is not assigned, do not schedule escalation
        if self.assigned_at is None:
            self.next_escalation_due = None
            return

        from datetime import timedelta

        if self.escalation_level == 0:
            # Schedule escalation to section head after 48 hours from assignment
            self.next_escalation_due = self.assigned_at + timedelta(
                hours=self.escalation_threshold_hours
            )
        elif self.escalation_level == 1:
            # Schedule escalation to HOD 24 hours after first escalation
            if self.escalated_at:
                self.next_escalation_due = self.escalated_at + \
                    timedelta(hours=24)
            else:
                # Fallback to assigned_at if escalated_at not set
                self.next_escalation_due = self.assigned_at + \
                    timedelta(hours=24)
        else:
            # No further escalation beyond HOD
            self.next_escalation_due = None

    def escalate(self, escalated_by, reason="", is_auto_escalation=False):
        """Escalate ticket to next organizational level (max: HOD)"""
        from django.db import transaction

        escalation_paths = {
            0: self._find_head_of_section(),  # To section head
            1: self._find_hod(),  # To HOD (final level)
        }

        # Check if already at maximum escalation level
        if self.escalation_level >= 2:
            raise ValueError(
                "Ticket is already at maximum escalation level (HOD)")

        next_escalation_level = self.escalation_level + 1
        escalated_to = escalation_paths.get(self.escalation_level)

        if not escalated_to:
            raise ValueError(
                f"No escalation path available for level {self.escalation_level}"
            )

        with transaction.atomic():
            self.escalation_level = next_escalation_level
            self.escalated_to = escalated_to
            self.escalated_at = timezone.now()
            self.escalation_reason = reason
            if self.status != "escalated":
                self.status = "escalated"

            # Update priority based on escalation level
            if next_escalation_level == 1:
                self.priority = "medium"  # First escalation -> MEDIUM
            elif next_escalation_level == 2:
                self.priority = "high"  # Second escalation -> HIGH

            # Schedule next auto-escalation if applicable
            self._schedule_next_escalation()

            self.save()

            # Create audit log
            escalation_type = (
                "Auto-escalated" if is_auto_escalation else "Manually escalated"
            )
            action_msg = (
                f"{escalation_type} to {escalated_to.get_role_display()}: {escalated_to.username} "
                f"- Level {next_escalation_level}"
            )
            TicketLog.objects.create(
                ticket=self, action=action_msg, performed_by=escalated_by
            )

    def is_due_for_escalation(self):
        """Check if ticket is due for automatic escalation.

        Unassigned tickets (assigned_at is NULL) are never due for escalation.
        """
        if not self.auto_escalation_enabled or not self.next_escalation_due:
            return False

        # If ticket has never been assigned, skip escalation
        if self.assigned_at is None:
            return False

        return (
            timezone.now() >= self.next_escalation_due
            and self.status not in ["resolved", "closed"]
            and self.escalation_level < 2  # Not already at max escalation
        )

    def disable_auto_escalation(self, disabled_by, reason=""):
        """Disable automatic escalation for this ticket"""
        from django.db import transaction

        with transaction.atomic():
            self.auto_escalation_enabled = False
            self.next_escalation_due = None
            self.save()

            # Create audit log
            TicketLog.objects.create(
                ticket=self,
                action=f"Auto-escalation disabled. Reason: {reason}",
                performed_by=disabled_by,
            )

    def _find_head_of_section(self):
        """Find section head for escalation"""
        return self.section.head_of_section if self.section else None

    def _find_hod(self):
        """Find HOD for escalation"""
        if self.section and self.section.department:
            return self.section.department.head_of_department
        return None

    @property
    def is_overdue(self):
        """Check if ticket is overdue (exceeds 7 days without resolution)"""
        if self.status in ["resolved", "closed"]:
            return False

        # Standard 7-day SLA for all tickets
        sla_hours = 7 * 24  # 7 days

        hours_since_creation = (
            timezone.now() - self.created_at).total_seconds() / 3600
        return hours_since_creation > sla_hours

    @property
    def organizational_path(self):
        """Return full organizational path"""
        if (
            self.section
            and self.section.department
            and self.section.department.campus
            and self.section.department.campus.organization
        ):
            return (
                f"{self.section.department.campus.organization.name} > "
                f"{self.section.department.campus.name} > "
                f"{self.section.department.name} > "
                f"{self.section.name}"
            )
        return "No organizational context"

    def check_and_mark_critical(self):
        """Auto-mark ticket as CRITICAL if unresolved for >72 hours"""
        if self.status in ["resolved", "closed"]:
            return False

        hours_since_creation = (
            timezone.now() - self.created_at).total_seconds() / 3600

        # Mark CRITICAL if >72 hours without resolution
        if hours_since_creation > 72 and self.priority != "critical":
            self.priority = "critical"
            self.save()
            TicketLog.objects.create(
                ticket=self,
                action=f"Priority auto-escalated to CRITICAL (unresolved >72 hours)",
                performed_by=None,
            )
            return True
        return False

    def change_status(self, new_status, performed_by=None):
        """Atomically change ticket status, update resolved_at, and create a TicketLog.

        This method centralizes status transition side-effects so services can
        perform validation and then call this for an atomic update+log.

        Directors cannot modify ticket status (analytics-only role).
        """
        from django.db import transaction

        # Directors have analytics-only access
        if performed_by and performed_by.role == "manager":
            raise PermissionError(
                "Directors have analytics-only access and cannot modify tickets"
            )

        original_status = self.status
        if original_status == new_status:
            return self

        is_resolving = new_status in ["resolved", "closed"]

        # Determine new resolved_at value
        if is_resolving and original_status not in ["resolved", "closed"]:
            new_resolved_at = timezone.now()
        elif not is_resolving and original_status in ["resolved", "closed"]:
            new_resolved_at = None
        else:
            new_resolved_at = self.resolved_at

        status_log = f"Status changed from {original_status} to {new_status}"
        if is_resolving and new_resolved_at:
            status_log += f" (Resolution time: {new_resolved_at})"
        elif not is_resolving and original_status in ["resolved", "closed"]:
            status_log += " (Resolution time cleared)"

        with transaction.atomic():
            # Apply changes and persist
            self.status = new_status
            self.resolved_at = new_resolved_at
            super(Ticket, self).save()
            # Create the log entry
            TicketLog.objects.create(
                ticket=self, action=status_log, performed_by=performed_by
            )

        return self

    def change_assignment(self, new_assigned_to, performed_by=None):
        """Atomically change assignment and create an assignment TicketLog."""
        from django.db import transaction

        original_assigned_to = self.assigned_to
        if original_assigned_to == new_assigned_to:
            return self

        action = f"Assigned to {getattr(new_assigned_to, 'username', 'None')}"

        with transaction.atomic():
            self.assigned_to = new_assigned_to
            # Set assigned_at when ticket is assigned (or reassigned)
            if new_assigned_to is not None:
                self.assigned_at = timezone.now()
            else:
                # If unassigning (new_assigned_to is None), clear assigned_at
                self.assigned_at = None

            # Update status to 'assigned' when assignment is made
            if self.status == "open":
                self.status = "assigned"
            super(Ticket, self).save()
            TicketLog.objects.create(
                ticket=self, action=action, performed_by=performed_by
            )

        return self

    def __str__(self):
        return f"{self.ticket_no} - {self.title} ({self.status})"


# COMMENTS MODEL
class Comment(models.Model):
    """comment for the issues or on ticket"""

    text = models.TextField(max_length=500)
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Comment by: {self.author.username}\n" f"on ticket: {self.ticket.title}\n"
        )


# FEEDBACK MODEL
class Feedback(models.Model):
    """Feedback issues or on ticket"""

    ticket = models.OneToOneField(
        Ticket, on_delete=models.CASCADE, related_name="feedback"
    )
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    rating = models.FloatField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"Feedback {self.rating}/5 for {self.ticket.title}\n"
            f"by:  {self.rated_by.username}\n"
        )


# TicketLog Model
class TicketLog(models.Model):
    """Logs every action on a ticket for auditing purposes"""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="logs")
    # e.g., "Assigned to John", "Status changed to Pending"
    action = models.CharField(max_length=255)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp}: {self.action} (Ticket: {self.ticket.title})"


# PHASE 4: SERVICE CATALOGUE MODELS


class DepartmentType(models.Model):
    """Blueprint template for departments - reusable across organizations"""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code}: {self.name}"


class SectionType(models.Model):
    """Blueprint template for sections within a department type"""

    department_type = models.ForeignKey(
        DepartmentType, on_delete=models.CASCADE, related_name="section_types"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10)
    staff_label = models.CharField(
        max_length=50,
        help_text="Display label for staff in this section (e.g., 'Technician', 'Artisan', 'Officer')"
    )
    default_sla_hours = models.IntegerField(default=72)

    class Meta:
        ordering = ["department_type", "code"]
        unique_together = [["department_type", "code"]]

    def __str__(self):
        return f"{self.department_type.code}-{self.code}: {self.name} ({self.staff_label})"


class ServiceCategory(models.Model):
    """Categories of services offered within a section type"""

    section_type = models.ForeignKey(
        SectionType, on_delete=models.CASCADE, related_name="service_categories"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name or emoji for UI")
    color = models.CharField(max_length=20, blank=True, help_text="Color code for UI")

    class Meta:
        ordering = ["section_type", "name"]
        verbose_name_plural = "Service Categories"

    def __str__(self):
        return f"{self.section_type.code}: {self.name}"


class ServiceItem(models.Model):
    """Individual service offerings with form definitions and approval workflows"""

    category = models.ForeignKey(
        ServiceCategory, on_delete=models.CASCADE, related_name="service_items"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sla_hours = models.IntegerField(null=True, blank=True, help_text="Overrides SectionType default")
    requires_approval = models.BooleanField(
        default=False, help_text="Ticket created as pending_approval if True"
    )
    form_schema = models.JSONField(
        default=list,
        help_text="Array of form field definitions for dynamic form rendering"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.category.name}: {self.name}"


# Import authentication models
