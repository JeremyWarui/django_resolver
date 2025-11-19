"""
Management command to clear all application caches.
Usage: python manage.py clear_cache [--pattern PATTERN]
"""
from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Clear all application caches or specific cache patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pattern',
            type=str,
            help='Specific cache key pattern to clear (e.g., "analytics:*")',
        )

    def handle(self, *args, **options):
        pattern = options.get('pattern')

        if pattern:
            # Clear specific pattern
            self.stdout.write(f'Clearing cache pattern: {pattern}')
            try:
                cache.delete_pattern(pattern)
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Successfully cleared cache pattern: {pattern}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'✗ Error clearing pattern: {e}'))
        else:
            # Clear all caches
            self.stdout.write('Clearing all caches...')
            try:
                cache.clear()
                self.stdout.write(self.style.SUCCESS(
                    '✓ Successfully cleared all caches'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'✗ Error clearing cache: {e}'))

        # Show cache stats
        self.stdout.write('\nCache patterns in use:')
        self.stdout.write(
            '  - analytics:tickets:*    (Ticket analytics, 5 min TTL)')
        self.stdout.write(
            '  - analytics:technician:* (Technician stats, 10 min TTL)')
        self.stdout.write(
            '  - analytics:admin:*      (Admin dashboard, 5 min TTL)')
        self.stdout.write(
            '  - list:tickets:*         (Ticket lists, 2 min TTL)')
        self.stdout.write(
            '  - list:users:*           (User lists, 15 min TTL)')
        self.stdout.write('  - lookup:sections:*      (Sections, 1 hour TTL)')
        self.stdout.write(
            '  - lookup:facilities:*    (Facilities, 1 hour TTL)')
