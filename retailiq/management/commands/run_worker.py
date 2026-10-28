import time
import os
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from retailiq.models import Job
from retailiq.services.jobs import process_next


class Command(BaseCommand):
    help = "Run one local worker; use --once to process one job and exit."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, **options):
        # OS-level lock is released even after a crash; a second worker cannot recover live jobs.
        with (settings.RUNTIME / "worker.lock").open("a+b") as lock:
            lock.seek(0)
            lock.write(b"0")
            lock.flush()
            lock.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.stdout.write("A local worker is already running.")
                return
            Job.objects.filter(status="running").update(
                status="failed", error="Worker interrupted. Submit a new run.", finished_at=timezone.now()
            )
            while True:
                job = process_next()
                if job:
                    self.stdout.write(f"Job {job.id}: {job.status} {job.error}")
                if options["once"]:
                    break
                if job is None:
                    time.sleep(2)
