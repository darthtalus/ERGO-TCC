from django.core.management.base import BaseCommand

from upgrades.services import generate_due_recurring_tasks


class Command(BaseCommand):
    help = 'Generate due recurring tasks from ERGO templates.'

    def handle(self, *args, **options):
        created = generate_due_recurring_tasks()
        self.stdout.write(self.style.SUCCESS(f'Generated {len(created)} recurring task(s).'))
