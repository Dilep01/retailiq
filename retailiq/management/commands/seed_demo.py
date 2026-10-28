from django.core.management.base import BaseCommand
from retailiq.services.data import seed_demo


class Command(BaseCommand):
    help = "Create a deterministic synthetic dataset (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--days", type=int, default=730)
        parser.add_argument("--products", type=int, default=20)
        parser.add_argument("--locations", type=int, default=1)

    def handle(self, **options):
        ds = seed_demo(options["seed"], options["days"], options["products"], options["locations"])
        self.stdout.write(f"Dataset {ds.id}: {ds.name}")
