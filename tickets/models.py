from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

# Create your models here.


# Custom User Model
class CustomUser(AbstractUser):
    """Extends Django's AbstractUser class to include additional fields"""

    ROLE_CHOICES = [
        ("user", "User"),
        ("admin", "Admin"),
        ("technician", "Technician"),
        ("manager", "Manager"),
    ]
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="user")

    # add section - many-to-many relationship
    # allows to query section.objects.get(name-'IT').technicians.all()
    sections = models.ManyToManyField(
        "Section",
        related_name="technicians",
        blank=True,
        help_text="Sections the technician is specialized in.",
    )

    def __str__(self):
        return f"{self.username}"


# SECTIONS MODEL
class Section(models.Model):
    """Maintenance sections e.g. IT, Plumbing, Electrical e.t.c."""

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=200, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}\n"


# FACILITY MODEL
class Facility(models.Model):
    """Facilities e.g. Building, ICT Equipment, Kitchen Equipment, Residential, e.t.c"""

    FACILITY_CHOICES = [
        ("building", "Building"),
        ("ict", "ICT Equipment"),
        ("laundry", "Laundry Equipment"),
        ("kitchen", "Kitchen Equipment"),
        ("residential", "Residential"),
    ]
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(
        max_length=50, choices=FACILITY_CHOICES, blank=True, null=True
    )
    status = models.CharField(max_length=50, default="active")
    location = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Facilities"

    def __str__(self):
        return f"{self.name}\n"


# TICKETS MODEL
class Ticket(models.Model):
    """Tickets: maintenance issues such as leaking pipe...e.t.c"""

    STATUS_CHOICES = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    ticket_no = models.CharField(max_length=10, unique=True, editable=False)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=200)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="raised_tickets",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,  # Users can't edit this field directly
        help_text="Automatically set when ticket status changes to resolved/closed",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_tickets",
    )
    pending_reason = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Reason provided when ticket status is changed to pending (e.g., waiting for parts)",
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            # Keep only composite index for common filter patterns
            models.Index(
                fields=["status", "-updated_at"], name="ticket_status_updated_idx"
            ),
        ]

    def save(self, *args, performed_by=None, **kwargs):
        """Generate ticket number if missing. Status-change logging is handled
        explicitly by model helper methods (`change_status`, `change_assignment`).

        Keep save lightweight so services or model helpers can control when
        logging happens atomically.
        """
        # 1. Handle ticket number generation for new tickets
        if not self.ticket_no:
            last_ticket = Ticket.objects.all().order_by("-id").first()
            next_id = 1 if not last_ticket else last_ticket.id + 1
            self.ticket_no = f"TKT-{next_id:06d}"

        # If creating or saving a ticket that is already in a resolved state,
        # ensure `resolved_at` is set so analytics that rely on this field
        # (resolved_tickets counting) include these records. We avoid creating
        # a TicketLog here because creation (fixtures) should not be treated
        # as an explicit state-change event performed by a user.
        if self.status in ["resolved", "closed"] and not self.resolved_at:
            self.resolved_at = timezone.now()

        super(Ticket, self).save(*args, **kwargs)

    def change_status(self, new_status, performed_by=None):
        """Atomically change ticket status, update resolved_at, and create a TicketLog.

        This method centralizes status transition side-effects so services can
        perform validation and then call this for an atomic update+log.
        """
        from django.db import transaction

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
            super(Ticket, self).save()
            TicketLog.objects.create(
                ticket=self, action=action, performed_by=performed_by
            )

        return self

    def __str__(self):
        return f"{self.ticket_no}\n" f"{self.title}\n" f"{self.status}\n"


# COMMENTS MODEL
class Comment(models.Model):
    """comment for the issues or on ticket"""

    text = models.TextField(max_length=500)
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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
    rated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="logs")
    # e.g., "Assigned to John", "Status changed to Pending"
    action = models.CharField(max_length=255)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp}: {self.action} (Ticket: {self.ticket.title})"
