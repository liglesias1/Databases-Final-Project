from django.core.management.base import BaseCommand
from analytics.services import rebuild_snapshots


class Command(BaseCommand):
    help = "Rebuild DemandSnapshot aggregation cache from CheckIn data"

    def handle(self, *args, **options):
        count = rebuild_snapshots()
        self.stdout.write(self.style.SUCCESS(f"Rebuilt {count} snapshot rows."))
