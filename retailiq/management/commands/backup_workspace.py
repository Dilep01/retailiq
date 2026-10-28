import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create a consistent SQLite backup and copy local model manifests (private backup)."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=".runtime/backups")

    def handle(self, **options):
        root = Path(options["output"]).resolve()
        target = root / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
        target.mkdir(parents=True, exist_ok=False)
        with (
            sqlite3.connect(str(settings.DATABASES["default"]["NAME"])) as source,
            sqlite3.connect(target / "retailiq.sqlite3") as dest,
        ):
            source.backup(dest)
        models = settings.BASE_DIR / "artifacts/models"
        if models.exists():
            shutil.copytree(models, target / "models")
        (target / "manifest.json").write_text(
            json.dumps(
                {
                    "created_utc": datetime.now(timezone.utc).isoformat(),
                    "private": True,
                    "secrets_excluded": True,
                    "restore": "Stop app; select this DB via RETAILIQ_DB. Keep backup private: it includes account password hashes.",
                },
                indent=2,
            )
        )
        self.stdout.write(str(target))
