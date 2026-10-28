import secrets
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from retailiq.models import ForecastRun, Plan, Simulation
from retailiq.services.data import seed_demo
from retailiq.services.forecasting import run_forecast
from retailiq.services.inventory import make_plan
from retailiq.services.simulation import run_simulation


class Command(BaseCommand):
    help = "Prepare a complete synthetic review workspace and a private local account."

    def add_arguments(self, parser):
        parser.add_argument("--skip-simulation", action="store_true")

    def handle(self, **options):
        user_model = get_user_model()
        if not user_model.objects.filter(username="planner").exists():
            password = secrets.token_urlsafe(16)
            user_model.objects.create_user("planner", password=password)
            (settings.RUNTIME / "review_credentials.txt").write_text(
                f"RetailIQ local review\nURL: http://127.0.0.1:8877\nUsername: planner\nPassword: {password}\n\nPrivate: do not commit or share this file.\n",
                encoding="utf-8",
            )
        dataset = seed_demo()
        run = ForecastRun.objects.filter(dataset=dataset).last()
        if not run:
            run = run_forecast(dataset)
        if not Plan.objects.filter(dataset=dataset).exists():
            make_plan(run, budget=25000, solver="milp")
        if not options["skip_simulation"] and not Simulation.objects.filter(dataset=dataset).exists():
            run_simulation(dataset)
        Path(settings.BASE_DIR / "artifacts/reports").mkdir(parents=True, exist_ok=True)
        self.stdout.write("Demo ready. Private login: .runtime/review_credentials.txt")
