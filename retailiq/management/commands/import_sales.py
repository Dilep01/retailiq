from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from retailiq.services.data import preview_import, commit_batch


class Command(BaseCommand):
    help = "Validate and atomically import a canonical daily-sales CSV."

    def add_arguments(self, parser):
        parser.add_argument("path")
        parser.add_argument("--currency", default="INR")

    def handle(self, **options):
        path = Path(options["path"])
        batch = preview_import(path.stem, path.read_bytes(), options["currency"])
        if batch.errors:
            raise CommandError("\n".join(batch.errors))
        ds = commit_batch(batch)
        self.stdout.write(f"Dataset {ds.id}; {len(batch.rows)} rows.")
