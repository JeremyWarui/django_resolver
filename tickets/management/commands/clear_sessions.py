from django.core.management.base import BaseCommand
# from tickets.auth_models import LoginSession  # Temporarily disabled
from rest_framework.authtoken.models import Token


class Command(BaseCommand):
    help = 'Clear all login sessions and tokens (useful after reloading fixtures)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        session_count = LoginSession.objects.count()
        token_count = Token.objects.count()

        if session_count == 0 and token_count == 0:
            self.stdout.write(self.style.SUCCESS(
                '✅ No sessions or tokens to clear'))
            return

        self.stdout.write(
            f'⚠️  About to delete {session_count} sessions and {token_count} tokens'
        )

        if not options['force']:
            confirm = input('Are you sure? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Cancelled'))
                return

        LoginSession.objects.all().delete()
        Token.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Cleared {session_count} sessions and {token_count} tokens'
            )
        )
