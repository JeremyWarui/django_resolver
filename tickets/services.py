from django.shortcuts import get_object_or_404
from rest_framework.settings import perform_import

from .models import Ticket, Comment, Feedback, TicketLog

# ---------------------
# TICKET SERVICES
# ----------------------

# class TicketService:
#     @staticmethod
#     def assign_ticket(ticket, technician, assigned_by):
#         if technician.section != ticket.section:
#             raise ValidationError("Technician not in the same section")
#         ticket.assigned_to = technician
#         ticket.status = "assigned"
#         ticket.save()
#         return ticket

def create_ticket(serializer, user):
    """ Logic for creating a ticket """
    serializer.save(raised_by=user)
    TicketLog.objects.create(
        ticket = serializer.instance,
        performed_by = user,
        action = f"Ticket created by {user.username}"
    )

def update_ticket(serializer, user):
    """ logic for updating ticket """
    old_ticket = Ticket.objects.get(pk=serializer.instance.pk)
    new_ticket = serializer.save()

     # log changes
    if old_ticket.status != new_ticket.status:
        TicketLog.objects.create(
            ticket=new_ticket,
            performed_by=user,
            action=f"Status changed from {old_ticket.status} to {new_ticket.status}"
        )

    if old_ticket.assigned_to != new_ticket.assigned_to:
        TicketLog.objects.create(
            ticket=new_ticket,
            performed_by=user,
            action=f"Reassigned to {new_ticket.assigned_to or 'None'}"
        )

# ---------------------
# COMMENT SERVICES
# ----------------------
def create_comment(serializer, user, ticket_id):
    """Attach author and ticket to comment"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    serializer.save(author=user, ticket=ticket)

    TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action=f"Comment added by {user.username}"
    )

# ----------------------------
# FEEDBACK SERVICES
# ----------------------------
def create_feedback(serializer, user, ticket_id):
    """Ensure only ticket raiser can give feedback"""
    ticket = get_object_or_404(Ticket, id=ticket_id)

    if ticket.raised_by != user:
        raise PermissionError("Only the ticket raiser can give feedback.")

    serializer.save(rated_by=user, ticket=ticket)

    TicketLog.objects.create(
        ticket=ticket,
        performed_by=user,
        action=f"Feedback ({serializer.validated_data['rating']}/5) added by {user.username}"
    )