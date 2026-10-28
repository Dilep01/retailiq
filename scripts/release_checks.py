"""Execute release checks and export factual, non-secret verification evidence."""

import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET
import django
from django.test import Client
from django.contrib.auth import get_user_model

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["TEMP"] = str(ROOT / ".runtime/tmp")
os.environ["TMP"] = os.environ["TEMP"]
report = {
    "date": datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(),
    "python": platform.python_version(),
    "platform": platform.platform(),
    "cpu": platform.processor(),
    "logical_cpus": os.cpu_count(),
    "checks": [],
}
commands = [
    ["manage.py", "check"],
    ["manage.py", "makemigrations", "--check", "--dry-run"],
    ["-m", "ruff", "check", "."],
    [
        "-m",
        "pytest",
        "--cov=retailiq",
        "--cov-report=json:.runtime/coverage.json",
        "--junitxml=docs/evidence/test-results.xml",
    ],
]
(ROOT / "docs/evidence").mkdir(parents=True, exist_ok=True)
for command in commands:
    started = time.perf_counter()
    result = subprocess.run([sys.executable, *command], check=False)
    report["checks"].append(
        {
            "command": "python " + " ".join(command),
            "exit_code": result.returncode,
            "seconds": round(time.perf_counter() - started, 2),
        }
    )
    if result.returncode:
        raise SystemExit("Release check failed; resolve it before packaging.")
coverage = json.loads((ROOT / ".runtime/coverage.json").read_text())
suite = ET.parse(ROOT / "docs/evidence/test-results.xml").getroot().find("testsuite")
report["tests"] = {key: int(suite.attrib[key]) for key in ["tests", "failures", "errors", "skipped"]}
report["coverage_percent"] = coverage["totals"]["percent_covered"]
backup_result = subprocess.run(
    [sys.executable, "manage.py", "backup_workspace"], capture_output=True, text=True, check=True
)
backup = Path(backup_result.stdout.strip().splitlines()[-1]) / "retailiq.sqlite3"
with sqlite3.connect(backup) as connection:
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not connection.execute("PRAGMA foreign_key_check").fetchall()
    counts = {
        table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in [
            "retailiq_dataset",
            "retailiq_sale",
            "retailiq_forecastrun",
            "retailiq_forecastpoint",
            "retailiq_plan",
            "retailiq_simulation",
        ]
    }
env = dict(os.environ, RETAILIQ_DB=str(backup))
subprocess.run([sys.executable, "manage.py", "check"], env=env, check=True)
read_check = f'from retailiq.models import Dataset,Sale; assert Dataset.objects.count()=={counts["retailiq_dataset"]}; assert Sale.objects.count()=={counts["retailiq_sale"]}; print("Backup ORM read passed")'
subprocess.run([sys.executable, "manage.py", "shell", "-c", read_check], env=env, check=True)
report["backup_restore"] = {
    "integrity": "ok",
    "foreign_keys": "ok",
    "django_with_backup": "passed",
    "django_data_read": "passed",
    "row_counts": counts,
}
django.setup()

client = Client()
client.force_login(get_user_model().objects.get(username="planner"))
timings = {}
for path in ["/", "/products/", "/forecasts/", "/inventory/", "/scenarios/", "/data/", "/runs/"]:
    values = []
    for _ in range(5):
        start = time.perf_counter()
        response = client.get(path)
        assert response.status_code == 200, (path, response.status_code)
        values.append((time.perf_counter() - start) * 1000)
    timings[path] = {"median_ms": round(sorted(values)[2], 2), "max_of_5_ms": round(max(values), 2)}
report["http_in_process_timings"] = timings
report["timing_limit"] = (
    "Django in-process requests on this computer, five samples/page; excludes real network and browser rendering."
)
report["browser_review_reference"] = (
    "Manual browser review on 2026-10-28: docs/VERIFICATION.md. Not rerun by this CLI script."
)
(ROOT / "docs/evidence/verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Release checks and consistent backup inspection passed. Evidence: docs/evidence/verification.json")
