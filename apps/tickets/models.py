from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Ticket(models.Model):
    """A service request — intrinsic current state only (SoT §3.2a).

    No derived values, no history, no child data on this row.
    Business logic lives in tickets/api/services/.
    """

    STATUS = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In progress"),
        ("pending", "Pending"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]
    LEVEL = [
        ("technician", "Technician"),
        ("hos", "HOS"),
        ("hod", "HOD"),
    ]

    ticket_no = models.CharField(max_length=24, unique=True)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="raised_tickets",
    )
    requester_campus = models.ForeignKey(
        "org.Campus",
        on_delete=models.PROTECT,
        related_name="+",
    )
    service_item = models.ForeignKey(
        "catalog.ServiceItem",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    section = models.ForeignKey(
        "org.Section",
        on_delete=models.PROTECT,
        related_name="tickets",
    )
    priority = models.ForeignKey(
        "sla.Priority",
        on_delete=models.PROTECT,
        related_name="+",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
    )
    description = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=STATUS, default="open")
    current_level = models.CharField(
        max_length=12, choices=LEVEL, default="technician")
    response_due_at = models.DateTimeField(null=True, blank=True)
    resolution_due_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    accumulated_pause = models.DurationField(default=timedelta)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

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
                fields=["current_level", "status"],
                name="ticket_level_status_idx",
            ),
            models.Index(
                fields=["raised_by", "-updated_at"],
                name="ticket_raised_by_idx",
            ),
            # Analytics group-by indexes (Phase 7)
            models.Index(
                fields=["status", "created_at"],
                name="ticket_status_created_idx",
            ),
            models.Index(
                fields=["resolved_at", "status"],
                name="ticket_resolved_status_idx",
            ),
            models.Index(
                fields=["resolution_due_at", "status"],
                name="ticket_resolution_due_idx",
            ),
            models.Index(
                fields=["section", "created_at"],
                name="ticket_section_created_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.ticket_no:
            self.ticket_no = self._generate_ticket_no()
        super().save(*args, **kwargs)

    def _generate_ticket_no(self):
        if not self.section_id:
            last = Ticket.objects.order_by("-id").first()
            seq = (last.id + 1) if last else 1
            return f"TKT-{seq:06d}"

        campus_code = self.section.campus_department.campus.code.upper()
        department_code = self.section.campus_department.department.code.upper()
        prefix = f"{campus_code}-{department_code}-"
        ticket_prefix = f"TKT-{prefix}"

        latest_ticket = (
            Ticket.objects.filter(
                Q(ticket_no__startswith=ticket_prefix) | Q(
                    ticket_no__startswith=prefix)
            )
            .order_by("-ticket_no")
            .first()
        )
        latest_ticket_no = latest_ticket.ticket_no if latest_ticket else None

        if latest_ticket_no:
            try:
                seq = int(latest_ticket_no.rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                seq = 1
        else:
            seq = 1

        return f"{ticket_prefix}{seq:04d}"

    def __str__(self):
        return f"{self.ticket_no} ({self.status})"


class TicketLocation(models.Model):
    """Location detail for a ticket — present iff category.location_details (R13)."""

    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name="location",
    )
    facility_type = models.ForeignKey(
        "facilities.FacilityType",
        on_delete=models.PROTECT,
        related_name="+",
    )
    facility = models.ForeignKey(
        "facilities.Facility",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    values = models.JSONField(default=dict)

    class Meta:
        app_label = "tickets"

    def __str__(self):
        return f"Location for {self.ticket_id}"


class TicketLog(models.Model):
    """Append-only/immutable audit log (R11).

    Snapshots the acting user and, for escalations, the level owner.
    Business logic (status service, escalation engine) writes entries here.
    """

    EVENT_TYPES = [
        ("created", "Created"),
        ("assigned", "Assigned"),
        ("reassigned", "Reassigned"),
        ("status_changed", "Status Changed"),
        ("escalated", "Escalated"),
        ("priority_changed", "Priority Changed"),
        ("comment_added", "Comment Added"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("reopened", "Reopened"),
        ("rated", "Rated"),
        ("sla_breach", "SLA Breach"),
    ]

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_log_actions",
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    from_value = models.CharField(max_length=100, blank=True)
    to_value = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    level_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tickets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["ticket", "-created_at"],
                name="ticketlog_ticket_created_idx",
            )
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("TicketLog records are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("TicketLog records cannot be deleted.")

    def __str__(self):
        return f"{self.event_type} on {self.ticket_id} at {self.created_at}"


class TicketComment(models.Model):
    """Mutable comment on a ticket. Internal comments are hidden from requesters."""

    VISIBILITY = [
        ("public", "Public"),
        ("internal", "Internal"),
    ]

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
    )
    body = models.TextField()
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY, default="public")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Comment by {self.author_id} on {self.ticket_id}"


class TicketFeedback(models.Model):
    """One-per-ticket feedback from the requester, at or after resolved (R11)."""

    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "tickets"

    def clean(self):
        if not (1 <= self.rating <= 5):
            raise ValidationError(
                {"rating": "Rating must be between 1 and 5."})

    def __str__(self):
        return f"Feedback {self.rating}/5 for {self.ticket_id}"
