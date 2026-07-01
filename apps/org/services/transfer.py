def transfer_open_tickets(departing_user, section) -> int:
    from apps.tickets.models import Ticket, TicketLog

    tickets = Ticket.objects.filter(
        section=section,
        assigned_to=departing_user,
        status__in=("open", "assigned", "in_progress", "pending"),
    )

    count = 0
    for ticket in tickets:
        ticket.assigned_to = None
        ticket.save(update_fields=["assigned_to", "updated_at"])
        TicketLog.objects.create(
            ticket=ticket,
            actor=None,
            event_type="reassigned",
            from_value=str(departing_user.pk),
            to_value="",
            reason="Role change: ticket returned to section pool.",
        )
        count += 1

    return count
