import urllib.request
import zipfile
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from retailiq.services.uci import import_uci


class Command(BaseCommand):
    help = "Import the UCI XLSX; --download retrieves the official free dataset."

    def add_arguments(self, parser):
        parser.add_argument("--path")
        parser.add_argument("--download", action="store_true")
        parser.add_argument("--products", type=int, default=20)

    def handle(self, **options):
        if options["download"]:
            folder = settings.BASE_DIR / "data/raw"
            folder.mkdir(parents=True, exist_ok=True)
            archive = folder / "uci-online-retail.zip"
            if not archive.exists():
                with urllib.request.urlopen(
                    "https://archive.ics.uci.edu/static/public/352/online+retail.zip", timeout=90
                ) as response:
                    archive.write_bytes(response.read(40 * 1024 * 1024))
            with zipfile.ZipFile(archive) as zipped:
                name = next(n for n in zipped.namelist() if n.lower().endswith(".xlsx"))
                path = folder / "Online Retail.xlsx"
                path.write_bytes(zipped.read(name))
        elif options["path"]:
            path = Path(options["path"])
        else:
            raise ValueError("Provide --path or --download.")
        ds = import_uci(path, options["products"])
        self.stdout.write(f"UCI dataset {ds.id}: {ds.name}")
