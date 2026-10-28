import logging
import traceback
from django.db import transaction
from django.utils import timezone
from retailiq.models import Job
from .forecasting import run_forecast
from .simulation import run_simulation


def process_next():
    with transaction.atomic():
        job = Job.objects.filter(status="queued").order_by("id").first()
        if job is None:
            return None
        claimed = Job.objects.filter(id=job.id, status="queued").update(status="running", started_at=timezone.now())
        if not claimed:
            return None
    try:
        if job.kind == "forecast":
            result = run_forecast(job.dataset, **job.params)
        elif job.kind == "simulation":
            result = run_simulation(job.dataset, **job.params)
        else:
            raise ValueError("Unknown job kind")
        Job.objects.filter(pk=job.id).update(status="succeeded", result={"id": result.id}, finished_at=timezone.now())
    except Exception as exc:
        logging.exception("Job %s failed", job.id)
        Job.objects.filter(pk=job.id).update(
            status="failed",
            error=f"{type(exc).__name__}: {exc}",
            result={"traceback": traceback.format_exc()},
            finished_at=timezone.now(),
        )
    return Job.objects.get(pk=job.id)
