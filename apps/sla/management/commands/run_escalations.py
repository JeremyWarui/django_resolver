from django.core.management.base import BaseCommand

from apps.sla.services.escalation import run_escalations


class Command(BaseCommand):
    help = "Advance ticket escalation levels per EscalationRule thresholds."

    def handle(self, *args, **options):
        count = run_escalations()
        self.stdout.write(self.style.SUCCESS(f"Escalated {count} ticket(s)."))
