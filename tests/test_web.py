import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from retailiq.models import Job, Plan, Product
from retailiq.services.forecasting import run_forecast
from retailiq.services.jobs import process_next
from retailiq.views import safe_cell


@pytest.mark.parametrize("path", ["/", "/data/", "/products/", "/forecasts/", "/inventory/", "/scenarios/", "/runs/"])
def test_business_pages_need_login(client, path):
    assert client.get(path).status_code == 302


@pytest.mark.parametrize("path", ["/", "/data/", "/products/", "/forecasts/", "/inventory/", "/scenarios/", "/runs/"])
def test_pages_render(planner, dataset, path):
    response = planner.get(path)
    assert response.status_code == 200
    assert b"RetailIQ" in response.content


def test_empty_workspace(planner):
    assert planner.get("/").status_code == 200
    assert planner.get("/forecasts/").status_code == 200


def test_whole_user_flow(planner, dataset):
    run = run_forecast(dataset, include_ml=False)
    assert planner.get("/forecasts/").status_code == 200
    response = planner.post("/inventory/", {"budget": "1000", "review": 7, "service": ".95", "solver": "milp"})
    assert response.status_code == 302
    plan = Plan.objects.last()
    assert plan.summary["spend"] <= 1000
    assert planner.get("/inventory/").status_code == 200
    assert planner.get(f"/export/plan/{plan.pk}/").status_code == 200
    assert planner.get(f"/export/forecast/{run.pk}/").status_code == 200
    product = Product.objects.first()
    assert planner.get(f"/products/{product.id}/").status_code == 200
    assert planner.get(f"/inventory/{product.id}/edit/").status_code == 200


def test_preview_commit_and_non_get_mutation(planner):
    upload = SimpleUploadedFile(
        "sales.csv", b"date,sku,units_sold,unit_price\n2026-01-01,A,2,3\n", content_type="text/csv"
    )
    response = planner.post("/data/", {"name": "Uploaded data", "currency": "GBP", "file": upload})
    assert response.status_code == 200
    pk = planner.session["preview_batch"]
    assert planner.get(f"/data/commit/{pk}/").status_code == 405
    assert planner.post(f"/data/commit/{pk}/").status_code == 302
    assert planner.get("/").status_code == 200


def test_worker_and_failed_job(planner, dataset):
    job = Job.objects.create(dataset=dataset, kind="forecast", params={"include_ml": False})
    assert process_next().status == "succeeded"
    assert planner.get(f"/api/jobs/{job.id}/").json()["result_id"]
    Job.objects.create(dataset=dataset, kind="unknown")
    assert process_next().status == "failed"


def test_export_formula_guard():
    for text in ["=SUM(1,2)", "+formula", "  @x", "-text"]:
        assert safe_cell(text).startswith("'")
    assert safe_cell(-2) == -2


def test_csrf_is_required(dataset, db):
    from django.test import Client
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user("csrf-user")
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.post("/forecasts/").status_code == 403


def test_health(client, db):
    assert client.get("/api/health/").json()["status"] == "ok"
