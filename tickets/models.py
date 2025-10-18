from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.core.validators import MinValueValidator, MaxValueValidator

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

    def __str__(self):
        return f"{self.username}"


# SECTIONS MODEL
class Section(models.Model):
    """Maintenance sections e.g. IT, Plumbing, Electrical e.t.c."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.name}"


# FACILITY MODEL

class Facility(models.Model):
    """Facilities e.g. Building, ICT Equipment, Kitchen Equipment, Residential, e.t.c"""
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
        return f"{self.name}"


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
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='assigned_tickets'
    )

    def save(self, *args, **kwargs):
        """auto generate the ticket_no if not set"""
        if not self.ticket_no:
            with transaction.atomic():
                last_ticket = Ticket.objects.all().order_by('-id').first()
                next_id = 1 if not last_ticket else last_ticket.id + 1
                self.ticket_no = f"TKT-{next_id:06d}"

        super(Ticket, self).save(*args, **kwargs)

    def __str__(self):
        return "{self.ticket_no}: {self.title}"

    @classmethod
    def total_tickets(cls):
        """ return number of tickets """
        return cls.objects.count()

    def set_to_pending(self):
        """set ticket status to pending"""
        self.status = 'pending'
        self.save()

    def is_overdue(self):
        """check time lapsed beyond 24 hours"""
        if self.status == 'open':
            elapsed_time = timezone.now() - self.created_at
            return elapsed_time > timedelta(hours=24)
        return False

    def time_since_creation(self):
        """return time since creation"""
        return timezone.now() - self.created_at

    def comments_count(self):
        """return number of comments"""
        return self.comments.count()


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

    @classmethod
    def total_comments(cls):
        return cls.objects.count()


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
    rating = models.FloatField(
        validators=[
            MinValueValidator(1.0),
            MaxValueValidator(5.0)
        ]
    )
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
