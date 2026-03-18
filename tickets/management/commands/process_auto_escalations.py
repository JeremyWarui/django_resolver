"""
Django management command to process automatic ticket escalations.

This command should be run periodically (e.g., hourly) via a cron job or task scheduler.

Usage:
    python manage.py process_auto_escalations
    python manage.py process_auto_escalations --verbose
    python manage.py process_auto_escalations --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from tickets.api.services import TicketService
from tickets.models import Ticket


class Command(BaseCommand):
    help = 'Process automatic ticket escalations for tickets exceeding time thresholds'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making actual changes, just show what would happen',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each escalation attempt',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit processing to N tickets',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        limit = options['limit']

        self.stdout.write(
            self.style.HTTP_INFO(
                f'🔄 Starting auto-escalation processing... ({"DRY RUN" if dry_run else "LIVE"})'
            )
        )

        # Find tickets due for auto-escalation
        tickets_due = Ticket.objects.filter(
            auto_escalation_enabled=True,
            next_escalation_due__lte=timezone.now(),
            status__in=['open', 'assigned', 'in_progress', 'pending']
        ).exclude(escalation_level=2).order_by('next_escalation_due')

        if limit:
            tickets_due = tickets_due[:limit]

        total = tickets_due.count()
        self.stdout.write(
            self.style.HTTP_INFO(f'📋 Found {total} tickets due for escalation')
        )

        if total == 0:
            self.stdout.write(self.style.SUCCESS('✓ No escalations needed'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '⚠️  DRY RUN MODE - No changes will be made'))
            for i, ticket in enumerate(tickets_due, 1):
                self.stdout.write(
                    f"  [{i}/{total}] {ticket.ticket_no} - {ticket.title[:50]} "
                    f"(Level {ticket.escalation_level})"
                )
            return

        # Process escalations
        results = TicketService.process_auto_escalations()

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Auto-escalation processing complete'))
        self.stdout.write(f'  Processed: {results["processed"]}')
        self.stdout.write(
            f'  Escalated: {self.style.SUCCESS(str(results["escalated"]))}')
        self.stdout.write(
            f'  Failed: {self.style.ERROR(str(results["failed"]))}')

        if results['errors']:
            self.stdout.write(self.style.ERROR(f'\n⚠️  Errors encountered:'))
            for error in results['errors']:
                self.stdout.write(f'  - {error}')
        else:
            self.stdout.write(self.style.SUCCESS('  No errors'))

        if verbose and results['escalated'] > 0:
            self.stdout.write(self.style.HTTP_INFO(f'\n📊 Escalation Details:'))
            for ticket in Ticket.objects.filter(
                escalated_at__gte=timezone.now() - timezone.timedelta(seconds=60)
            ).order_by('-escalated_at')[:results['escalated']]:
                self.stdout.write(
                    f'  {ticket.ticket_no}: Level {ticket.escalation_level} - {ticket.escalation_reason}'
                )
