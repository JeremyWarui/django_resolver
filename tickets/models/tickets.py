from django.db import models
from django.conf import settings
from django.utils import timezone

from .sections import Section, TechnicianSection


class Ticket(models.Model):
    """A service request raised by a user against a specific section of a campus department.

    --- Relationships ---
    - `raised_by`: the user who submitted the request (reporter).
    - `campus_department`: the operational CampusDepartment this ticket belongs to.
      Always required — set at creation time from the user's campus + selected department.
    - `section`: the Section responsible for resolving this ticket.
      Auto-resolved at creation (see `get_eligible_assignees`); can be overridden by HOD/HOS.
    - `service_item`: the specific catalogue item selected by the user. Nullable for
      general/uncatalogued requests.
    - `assigned_to`: the current assignee — may be a technician, HOS, or HOD depending
      on escalation level. Null until assignment is made.

    --- Auto-resolution of section and assignees ---
    On ticket creation the service layer (TicketService.create_ticket) does:

      1. Resolve campus_department:
            CampusDepartment.objects.get(
                campus=raised_by.primary_campus,
                department=<selected department>,
            )

      2. Resolve section (from service catalogue):
            section_type = service_item.category.section_type
            section = Section.objects.get(
                campus_department=campus_department,
                section_type=section_type,
            )

      3. Eligible assignees (ordered by workload):
            TechnicianSection.objects.filter(section=section)
                             .select_related("technician")
            # Plus section.head_of_section as fallback if no technicians are free.

      4. Initial status:
            "pending_approval" if service_item.requires_approval else "open"

    --- Ticket number format ---
    Auto-generated as CAMPUS-DEPT-NNNNN (e.g. NRB-ICT-00001).
    All tickets in the same campus_department share a counter.

    --- Status machine ---
    open → assigned → in_progress ⇄ pending → resolved → closed
    pending_approval → (approve) → open
    pending_approval → (reject)  → rejected
    Use `change_status()`, never set `status` directly.

    --- Escalation ---
    Level 0 → section.head_of_section (after `escalation_threshold_hours` from assigned_at)
    Level 1 → campus_department.head_of_department (24 h after level-0 escalation)
    Level 2 = maximum; no further auto-escalation.
    Escalation clock starts at `assigned_at`. Unassigned tickets never escalate.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("pending", "Pending"),
        ("pending_approval", "Pending Approval"),
        ("escalated", "Escalated"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
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

    TERMINAL_STATUSES = {"resolved", "closed", "rejected"}

    # ------------------------------------------------------------------ #
    # Core fields                                                          #
    # ------------------------------------------------------------------ #

    ticket_no = models.CharField(max_length=25, unique=True, editable=False)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=500)

    # ------------------------------------------------------------------ #
    # Organisational context                                               #
    # ------------------------------------------------------------------ #

    campus_department = models.ForeignKey(
        "CampusDepartment",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )

    # Physical location (optional)
    facility = models.ForeignKey(
        "Facility",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    location_detail = models.CharField(max_length=200, blank=True)

    # ------------------------------------------------------------------ #
    # Service catalogue                                                    #
    # ------------------------------------------------------------------ #

    service_item = models.ForeignKey(
        "ServiceItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tickets",
    )
    form_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Dynamic form submission data captured from ServiceItem.form_schema.",
    )

    # ------------------------------------------------------------------ #
    # People                                                               #
    # ------------------------------------------------------------------ #

    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="raised_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        help_text="Current assignee — technician, HOS, or HOD depending on escalation level.",
    )
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        default=None,
        help_text="Set when first assigned; used as the escalation clock start.",
    )

    # ------------------------------------------------------------------ #
    # Status & priority                                                    #
    # ------------------------------------------------------------------ #

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="low",
    )

    # ------------------------------------------------------------------ #
    # Timestamps                                                           #
    # ------------------------------------------------------------------ #

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)
    due_date = models.DateTimeField(null=True, blank=True)

    # ------------------------------------------------------------------ #
    # Pending state                                                        #
    # ------------------------------------------------------------------ #

    pending_reason = models.CharField(
        max_length=50,
        choices=PENDING_REASON_CHOICES,
        blank=True,
        null=True,
    )
    pending_comment = models.TextField(max_length=500, blank=True, null=True)

    # ------------------------------------------------------------------ #
    # Escalation                                                           #
    # ------------------------------------------------------------------ #

    # 0 = none, 1 = section head, 2 = HOD (maximum)
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
    auto_escalation_enabled = models.BooleanField(default=True)
    next_escalation_due = models.DateTimeField(null=True, blank=True, editable=False)
    escalation_threshold_hours = models.IntegerField(
        default=48,
        help_text="Hours after assignment before first auto-escalation fires.",
    )

    # ------------------------------------------------------------------ #
    # Resolution metadata                                                  #
    # ------------------------------------------------------------------ #

    estimated_resolution_hours = models.IntegerField(null=True, blank=True)
    actual_resolution_hours = models.IntegerField(null=True, blank=True, editable=False)

    class Meta:
        app_label = "tickets"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(
                fields=["status", "section", "-updated_at"],
                name="ticket_section_status_idx",
            ),
            models.Index(
                fields=["assigned_to", "status"],
                name="ticket_assignment_idx",
            ),
            models.Index(
                fields=["escalation_level", "-escalated_at"],
                name="ticket_escalation_idx",
            ),
            models.Index(
                fields=["next_escalation_due", "auto_escalation_enabled"],
                name="ticket_auto_escalation_idx",
            ),
            models.Index(
                fields=["status", "-updated_at"],
                name="ticket_status_updated_idx",
            ),
        ]

    # ------------------------------------------------------------------ #
    # Save & ticket numbering                                              #
    # ------------------------------------------------------------------ #

    def save(self, *args, **kwargs):
        if not self.pk and self.service_item:
            if not self.priority or self.priority == "low":
                self.priority = self.service_item.default_priority
            if not self.due_date:
                from datetime import timedelta
                sla = (
                    self.service_item.sla_hours
                    or (self.section.effective_sla_hours if self.section else None)
                )
                if sla:
                    self.due_date = timezone.now() + timedelta(hours=sla)
            if self.service_item.requires_approval and self.status == "open":
                self.status = "pending_approval"

        # Priority floor driven by escalation level (critical is never downgraded)
        if self.priority != "critical":
            self.priority = {0: "low", 1: "medium"}.get(
                self.escalation_level, "high"
            )

        if not self.ticket_no:
            self.ticket_no = self._generate_ticket_no()

        if self.status == "closed" and not self.closed_at:
            self.closed_at = timezone.now()
        if self.status in self.TERMINAL_STATUSES and not self.resolved_at:
            self.resolved_at = timezone.now()

        if not self.next_escalation_due and (
            not self.pk or self.status in ("open", "assigned", "in_progress")
        ):
            self._schedule_next_escalation()

        super().save(*args, **kwargs)

    def _generate_ticket_no(self):
        """Build CAMPUS-DEPT-NNNNN from campus_department; fallback to TKT-NNNNNN."""
        cd = self.campus_department
        if cd:
            campus_code = cd.campus.code
            dept_code = cd.department.code
            last = (
                Ticket.objects.filter(campus_department=cd)
                .order_by("-id")
                .first()
            )
            seq = 1 if not last else (last.id % 99999) + 1
            return f"{campus_code}-{dept_code}-{seq:05d}"
        last = Ticket.objects.order_by("-id").first()
        seq = 1 if not last else last.id + 1
        return f"TKT-{seq:06d}"

    # ------------------------------------------------------------------ #
    # Escalation logic                                                     #
    # ------------------------------------------------------------------ #

    def _schedule_next_escalation(self):
        from datetime import timedelta

        if not self.auto_escalation_enabled or self.status in self.TERMINAL_STATUSES:
            self.next_escalation_due = None
            return
        if self.assigned_at is None:
            self.next_escalation_due = None
            return
        if self.escalation_level == 0:
            self.next_escalation_due = self.assigned_at + timedelta(
                hours=self.escalation_threshold_hours
            )
        elif self.escalation_level == 1:
            base = self.escalated_at or self.assigned_at
            self.next_escalation_due = base + timedelta(hours=24)
        else:
            self.next_escalation_due = None

    def escalate(self, escalated_by, reason="", is_auto_escalation=False):
        """Escalate to next level: 0 → head_of_section, 1 → head_of_department (max)."""
        from django.db import transaction

        if self.escalation_level >= 2:
            raise ValueError("Ticket is already at maximum escalation level (HOD).")

        targets = {0: self._find_head_of_section(), 1: self._find_hod()}
        target = targets.get(self.escalation_level)
        if not target:
            raise ValueError(
                f"No escalation target found at level {self.escalation_level}."
            )

        next_level = self.escalation_level + 1
        with transaction.atomic():
            self.escalation_level = next_level
            self.escalated_to = target
            self.escalated_at = timezone.now()
            self.escalation_reason = reason
            self.status = "escalated"
            self.priority = "medium" if next_level == 1 else "high"
            self._schedule_next_escalation()
            self.save()
            label = "Auto-escalated" if is_auto_escalation else "Manually escalated"
            TicketLog.objects.create(
                ticket=self,
                action=f"{label} to {target.get_role_display()}: {target.username} (level {next_level})",
                performed_by=escalated_by,
            )

    def is_due_for_escalation(self):
        """True if assigned, auto-escalation enabled, and the due time has passed."""
        return (
            self.auto_escalation_enabled
            and self.assigned_at is not None
            and self.next_escalation_due is not None
            and timezone.now() >= self.next_escalation_due
            and self.status not in self.TERMINAL_STATUSES
            and self.escalation_level < 2
        )

    def disable_auto_escalation(self, disabled_by, reason=""):
        from django.db import transaction

        with transaction.atomic():
            self.auto_escalation_enabled = False
            self.next_escalation_due = None
            self.save()
            TicketLog.objects.create(
                ticket=self,
                action=f"Auto-escalation disabled. Reason: {reason}",
                performed_by=disabled_by,
            )

    def _find_head_of_section(self):
        return self.section.head_of_section if self.section else None

    def _find_hod(self):
        return self.campus_department.head_of_department if self.campus_department else None

    # ------------------------------------------------------------------ #
    # Status & assignment transitions                                      #
    # ------------------------------------------------------------------ #

    def change_status(self, new_status, performed_by=None):
        """Atomically change status, maintain resolved_at, and write a TicketLog.

        Managers have analytics-only access and cannot change status.
        """
        from django.db import transaction

        if performed_by and performed_by.role == "manager":
            raise PermissionError(
                "Managers have analytics-only access and cannot modify tickets."
            )

        original = self.status
        if original == new_status:
            return self

        is_resolving = new_status in self.TERMINAL_STATUSES
        was_resolved = original in self.TERMINAL_STATUSES

        if is_resolving and not was_resolved:
            new_resolved_at = timezone.now()
        elif not is_resolving and was_resolved:
            new_resolved_at = None
        else:
            new_resolved_at = self.resolved_at

        with transaction.atomic():
            self.status = new_status
            self.resolved_at = new_resolved_at
            super().save()
            TicketLog.objects.create(
                ticket=self,
                action=f"Status changed from {original} to {new_status}",
                performed_by=performed_by,
            )
        return self

    def change_assignment(self, new_assigned_to, performed_by=None):
        """Atomically change assignee, update assigned_at, and write a TicketLog."""
        from django.db import transaction

        if self.assigned_to == new_assigned_to:
            return self

        with transaction.atomic():
            self.assigned_to = new_assigned_to
            self.assigned_at = timezone.now() if new_assigned_to else None
            if self.status == "open" and new_assigned_to:
                self.status = "assigned"
            super().save()
            TicketLog.objects.create(
                ticket=self,
                action=f"Assigned to {getattr(new_assigned_to, 'username', 'None')}",
                performed_by=performed_by,
            )
        return self

    # ------------------------------------------------------------------ #
    # Computed properties                                                  #
    # ------------------------------------------------------------------ #

    @property
    def is_overdue(self):
        if self.status in self.TERMINAL_STATUSES:
            return False
        if not self.due_date:
            return False
        return timezone.now() > self.due_date

    @property
    def time_remaining(self):
        """Seconds until due_date, or None if overdue or no due date."""
        if self.due_date and not self.is_overdue:
            return (self.due_date - timezone.now()).total_seconds()
        return None

    @property
    def organizational_path(self):
        """Human-readable path: Campus > Department > Section."""
        cd = self.campus_department
        if cd:
            parts = [cd.campus.name, cd.department.name]
            if self.section:
                parts.append(self.section.name)
            return " > ".join(parts)
        return "No organisational context"

    def get_eligible_assignees(self):
        """Return Users eligible to be assigned this ticket.

        Ordered by ascending current workload (open assigned tickets).
        Includes the section's head_of_section as a fallback.
        """
        if not self.section:
            return settings.AUTH_USER_MODEL and []
        from django.db.models import Count, Q
        technician_ids = (
            TechnicianSection.objects.filter(section=self.section)
            .values_list("technician_id", flat=True)
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        assignees = (
            User.objects.filter(id__in=technician_ids)
            .annotate(
                open_tickets=Count(
                    "assigned_tickets",
                    filter=Q(assigned_tickets__status__in=("assigned", "in_progress")),
                )
            )
            .order_by("open_tickets")
        )
        return assignees

    def __str__(self):
        return f"{self.ticket_no} – {self.title} ({self.status})"


class Comment(models.Model):
    """comment for the issues or on ticket"""

    text = models.TextField(max_length=500)
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tickets"

    def __str__(self):
        return (
            f"Comment by: {self.author.username}\n" f"on ticket: {self.ticket.title}\n"
        )


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

    class Meta:
        app_label = "tickets"

    def __str__(self):
        return (
            f"Feedback {self.rating}/5 for {self.ticket.title}\n"
            f"by:  {self.rated_by.username}\n"
        )


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

    class Meta:
        app_label = "tickets"

    def __str__(self):
        return f"{self.timestamp}: {self.action} (Ticket: {self.ticket.title})"
