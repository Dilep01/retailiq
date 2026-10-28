from django.core.management.base import BaseCommand
from retailiq.models import Dataset
from retailiq.services.simulation import run_simulation


class Command(BaseCommand):
    help = "Run matched inventory policy simulations."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", type=int)
        parser.add_argument("--days", type=int, default=56)
        parser.add_argument("--budget", type=float, default=750000)
        parser.add_argument("--delay", type=int, default=0)
        parser.add_argument("--baseline-only", action="store_true")

    def handle(self, **options):
        ds = Dataset.objects.get(pk=options["dataset"]) if options["dataset"] else Dataset.objects.latest("id")
        run = run_simulation(
            ds, options["days"], options["budget"], options["delay"], include_ml=not options["baseline_only"]
        )
        self.stdout.write(f"Simulation {run.id}: {run.results['policies']}")
