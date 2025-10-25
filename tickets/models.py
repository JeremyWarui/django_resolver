from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone


# Create your models here.

# Custom User Model
class CustomUser(AbstractUser):
    """Extends Django's AbstractUser class to include additional fields"""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('admin', 'Admin'),
        ('technician', 'Technician'),
        ('manager', 'Manager'),
    ]
    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default='user')

    # add section - many-to-many relationship
    # allows to query section.objects.get(name-'IT').technicians.all()
    sections = models.ManyToManyField(
        'Section',
        related_name="technicians",
        blank=True,
        help_text='Sections the technician is specialized in.'
    )

    def __str__(self):
        return f"{self.username}"


# SECTIONS MODEL
class Section(models.Model):
    """Maintenance sections e.g. IT, Plumbing, Electrical e.t.c."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.name}\n"


# FACILITY MODEL
class Facility(models.Model):
    """Facilities e.g. Building, ICT Equipment, Kitchen Equipment, Residential, e.t.c """
    FACILITY_CHOICES = [
        ('building', 'Building'),
        ('ict', 'ICT Equipment'),
        ('laundry', 'Laundry Equipment'),
        ('kitchen', 'Kitchen Equipment'),
        ('residential', 'Residential'),
    ]
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(
        max_length=50,
        choices=FACILITY_CHOICES,
        blank=True,
        null=True
    )
    status = models.CharField(max_length=50, default="active")
    location = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.name}\n"


# TICKETS MODEL
class Ticket(models.Model):
    """Tickets: maintenance issues such as leaking pipe...e.t.c"""
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('pending', 'Pending'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]

    ticket_no = models.CharField(max_length=10, unique=True, editable=False)
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=200)
    section = models.ForeignKey(Section, on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, on_delete=models.CASCADE)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='raised_tickets'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,  # Users can't edit this field directly
        help_text='Automatically set when ticket status changes to resolved/closed'
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_tickets'
    )

    def save(self, *args, performed_by=None, **kwargs):
        """auto generate the ticket_no if not set and handle status changes"""
        # 1. Handle ticket number generation for new tickets
        if not self.ticket_no:
            last_ticket = Ticket.objects.all().order_by('-id').first()
            next_id = 1 if not last_ticket else last_ticket.id + 1
            self.ticket_no = f"TKT-{next_id:06d}"

        # 2. Handle resolved_at timestamp logic and logging
        is_resolving_status = self.status in ['resolved', 'closed']

        # Only check if the ticket already exists in the database
        if self.pk:
            try:
                original = Ticket.objects.get(pk=self.pk)

                # Handle status change logging
                if original.status != self.status:
                    status_log = f"Status changed from '{original.status}' to '{self.status}'"

                    # Handle resolution timestamp
                    if is_resolving_status and original.status not in ['resolved', 'closed']:
                        if not self.resolved_at:
                            self.resolved_at = timezone.now()
                            status_log += f" (Resolution time: {self.resolved_at})"

                    # Handle reopening
                    elif not is_resolving_status and original.status in ['resolved', 'closed']:
                        self.resolved_at = None
                        status_log += " (Resolution time cleared)"

                    # Create the log entry BEFORE saving
                    log_entry = TicketLog(
                        ticket=self,
                        action=status_log,
                        performed_by=performed_by
                    )

                    # Save the ticket first
                    super(Ticket, self).save(*args, **kwargs)

                    # Now save the log entry
                    log_entry.save()
                    return  # We've already saved above

            except Ticket.DoesNotExist:
                pass

        # For a new ticket with resolved/closed status (rare case)
        elif is_resolving_status:
            self.resolved_at = timezone.now()
            # Save the ticket first
            super(Ticket, self).save(*args, **kwargs)

            # Log the initial resolved status
            TicketLog.objects.create(
                ticket=self,
                action=f"Ticket created with '{self.status}' status (Resolution time: {self.resolved_at})",
                performed_by=performed_by
            )
            return  # We've already saved above

        # If we haven't returned yet, save the ticket
        super(Ticket, self).save(*args, **kwargs)

    def __str__(self):
        return (f"{self.ticket_no}\n"
                f"{self.title}\n"
                f"{self.status}\n")


# COMMENTS MODEL
class Comment(models.Model):
    """comment for the issues or on ticket"""
    text = models.TextField(max_length=500)
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (f"Comment by: {self.author.username}\n"
                f"on ticket: {self.ticket.title}\n")


# FEEDBACK MODEL
class Feedback(models.Model):
    """Feedback issues or on ticket"""
    ticket = models.OneToOneField(
        Ticket,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    rated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    rating = models.FloatField()
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (f"Feedback {self.rating}/5 for {self.ticket.title}\n"
                f"by:  {self.rated_by.username}\n")


# TicketLog Model
class TicketLog(models.Model):
    """Logs every action on a ticket for auditing purposes"""
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    # e.g., "Assigned to John", "Status changed to Pending"
    action = models.CharField(max_length=255)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp}: {self.action} (Ticket: {self.ticket.title})"
