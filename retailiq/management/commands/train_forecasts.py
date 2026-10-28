from django.core.management.base import BaseCommand
from retailiq.models import Dataset
from retailiq.services.forecasting import run_forecast


class Command(BaseCommand):
    help = "Backtest, select and publish a new forecast atomically."

    def add_arguments(self, parser):
        parser.add_argument("--dataset", type=int)
        parser.add_argument("--baseline-only", action="store_true")

    def handle(self, **options):
        ds = Dataset.objects.get(pk=options["dataset"]) if options["dataset"] else Dataset.objects.latest("id")
        run = run_forecast(ds, not options["baseline_only"])
        self.stdout.write(f"Run {run.id}: {run.model_name}; {run.evaluation}")
