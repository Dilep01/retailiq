import csv
import io

import pandas as pd
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .context import navigation
from .forms import ImportForm, PlanForm, SimulationForm, StockForm
from .models import (
    Dataset,
    Product,
    Sale,
    Stock,
    ForecastRun,
    ForecastPoint,
    Plan,
    Simulation,
    Job,
    ImportBatch,
    AuditEvent,
)
from .services.data import preview_import, commit_batch, sales_frame
from .services.inventory import make_plan, stock_signature


def selected(request):
    return navigation(request)["dataset"]


def audit(request, action, **detail):
    AuditEvent.objects.create(actor=request.user, action=action, detail=detail)


def chart(dataset, run=None, product=None, days=56):
    if not dataset:
        return {"labels": [], "actual": [], "forecast": []}
    query = Sale.objects.filter(product__dataset=dataset, observed=True)
    if product:
        query = query.filter(product=product)
    rows = list(query.values("date").annotate(total=Sum("units")).order_by("date"))[-days:]
    forecast = ForecastPoint.objects.filter(run=run) if run else ForecastPoint.objects.none()
    if product:
        forecast = forecast.filter(product=product)
    future = list(
        forecast.values("date").annotate(total=Sum("prediction"), lo=Sum("lower"), hi=Sum("upper")).order_by("date")
    )
    labels = [str(x["date"]) for x in rows] + [str(x["date"]) for x in future]
    return {
        "labels": labels,
        "actual": [float(x["total"]) for x in rows] + [None] * len(future),
        "forecast": [None] * (max(0, len(rows) - 1))
        + ([float(rows[-1]["total"])] if rows and future else [])
        + [round(x["total"], 1) for x in future],
        "lower": [None] * len(rows) + [round(x["lo"], 1) for x in future],
        "upper": [None] * len(rows) + [round(x["hi"], 1) for x in future],
        "boundary": len(rows) - 1,
        "aggregate": product is None or query.values("location_id").distinct().count() > 1,
        "note": "Daily marginal intervals are shown only for a single series; aggregate bounds are not calibrated.",
    }


@login_required
def overview(request):
    ds = selected(request)
    if not ds:
        return render(request, "overview.html")
    frame = sales_frame(ds)
    end = pd.Timestamp(ds.end_date)
    recent = frame[(frame.date > end - pd.Timedelta(days=28)) & frame.observed]
    prior = frame[
        (frame.date <= end - pd.Timedelta(days=28)) & (frame.date > end - pd.Timedelta(days=56)) & frame.observed
    ]
    revenue = float((recent.units * recent.price).sum())
    old = float((prior.units * prior.price).sum())
    spark_values = recent.assign(value=recent.units * recent.price).groupby("date").value.sum().tolist()
    spark_low = min(spark_values) if spark_values else 0
    spark_range = max(1, max(spark_values) - spark_low) if spark_values else 1
    spark_path = " ".join(
        ("M" if i == 0 else "L")
        + f"{i / max(1, len(spark_values) - 1) * 120:.1f},{26 - (value - spark_low) / spark_range * 24:.1f}"
        for i, value in enumerate(spark_values)
    )
    run = ForecastRun.objects.filter(dataset=ds).last()
    plan = Plan.objects.filter(dataset=ds).last()
    grouped = (
        recent.assign(revenue=recent.units * recent.price)
        .groupby("product_id")
        .agg(revenue=("revenue", "sum"), units=("units", "sum"))
        .sort_values("revenue", ascending=False)
        .head(5)
    )
    top = []
    products = {p.id: p for p in Product.objects.filter(dataset=ds)}
    maximum = max(1, float(grouped.revenue.max())) if not grouped.empty else 1
    for pid, row in grouped.iterrows():
        top.append(
            {
                "product": products[pid],
                "revenue": float(row.revenue),
                "units": int(row.units),
                "width": float(row.revenue) / maximum * 100,
            }
        )
    category = []
    bycat = {}
    for item in top:
        name = item["product"].category
        bycat[name] = bycat.get(name, 0) + item["revenue"]
    cats = recent.copy()
    cats["category"] = cats.product_id.map({p.id: p.category for p in products.values()})
    cats["revenue"] = cats.units * cats.price
    catvalues = cats.groupby("category").revenue.sum().sort_values(ascending=False)
    for i, (name, value) in enumerate(catvalues.items()):
        category.append(
            {
                "name": name,
                "value": float(value),
                "share": float(value) / max(1, revenue) * 100,
                "color": ["#206b52", "#b8d95e", "#e49c7a", "#a6a3d3", "#7d9e9e"][i % 5],
            }
        )
    return render(
        request,
        "overview.html",
        {
            "revenue": revenue,
            "spark_path": spark_path,
            "growth": (revenue / old - 1) * 100 if old else 0,
            "units": int(recent.units.sum()),
            "product_count": len(products),
            "stock_units": Stock.objects.filter(product__dataset=ds).aggregate(n=Sum("on_hand"))["n"] or 0,
            "forecast_run": run,
            "plan": plan,
            "top_products": top,
            "categories": category,
            "chart_data": chart(ds, run),
            "risk_lines": [x for x in (plan.lines if plan else []) if x["status"] == "At risk"][:4],
            "jobs": Job.objects.filter(dataset=ds, status__in=["queued", "running"]).order_by("-id"),
        },
    )


@login_required
def data_page(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    batch = None
    if request.method == "POST" and form.is_valid():
        batch = preview_import(
            form.cleaned_data["name"], form.cleaned_data["file"].read(), form.cleaned_data["currency"]
        )
        request.session["preview_batch"] = batch.id
        audit(request, "import_preview", batch=batch.id)
    ds = selected(request)
    quality = {}
    if ds:
        frame = sales_frame(ds)
        groups = frame.groupby(["product_id", "location_id"])
        expected = sum((g.date.max() - g.date.min()).days + 1 for _, g in groups)
        quality = {
            "rows": len(frame),
            "series": groups.ngroups,
            "missing_dates": expected - len(frame),
            "flagged": int((~frame.observed).sum()),
            "zeros": int((frame.units == 0).sum()),
        }
    return render(
        request,
        "data.html",
        {"form": form, "batch": batch, "quality": quality, "batches": ImportBatch.objects.order_by("-id")[:8]},
    )


@login_required
@require_POST
def commit_import(request, pk):
    if request.session.get("preview_batch") != pk:
        raise Http404
    batch = get_object_or_404(ImportBatch, pk=pk)
    try:
        ds = commit_batch(batch)
        request.session["dataset"] = ds.id
        audit(request, "import_committed", dataset=ds.id, batch=pk)
        messages.success(request, "Dataset imported. Previous datasets remain available in the selector.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("data")


@login_required
def csv_template(request):
    return csv_response(
        "retailiq-template.csv",
        ["date", "sku", "name", "category", "location", "units_sold", "unit_price", "observation_status"],
        [
            ["2026-01-01", "SKU-001", "Oat milk", "Dairy", "Main store", 12, "145.00", "observed"],
            ["2026-01-02", "SKU-001", "Oat milk", "Dairy", "Main store", 0, "145.00", "observed"],
        ],
    )


@login_required
def products(request):
    ds = selected(request)
    query = Product.objects.filter(dataset=ds)
    search = request.GET.get("q", "")[:100]
    if search:
        from django.db.models import Q

        query = query.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(category__icontains=search))
    page = Paginator(query.order_by("sku"), 20).get_page(request.GET.get("page"))
    return render(request, "products.html", {"products": page, "search": search})


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    request.session["dataset"] = product.dataset_id
    run = ForecastRun.objects.filter(dataset=product.dataset).last()
    return render(
        request,
        "product.html",
        {
            "product": product,
            "stocks": Stock.objects.filter(product=product).select_related("location"),
            "chart_data": chart(product.dataset, run, product),
            "forecast_run": run,
        },
    )


def enqueue(request, ds, kind, params):
    if Job.objects.filter(dataset=ds, kind=kind, status__in=["queued", "running"]).exists():
        messages.warning(request, "A job of this type is already queued or running.")
        return
    if Job.objects.filter(status__in=["queued", "running"]).count() >= 8:
        messages.warning(request, "The local queue is full. Let the worker finish existing jobs.")
        return
    job = Job.objects.create(dataset=ds, kind=kind, params=params)
    audit(request, "job_queued", job=job.id, kind=kind)
    messages.success(request, f"Job #{job.id} queued. The local worker will process it; run history shows progress.")


@login_required
def forecasts(request):
    ds = selected(request)
    if request.method == "POST" and ds:
        enqueue(request, ds, "forecast", {"include_ml": True})
        return redirect("forecasts")
    run = ForecastRun.objects.filter(dataset=ds).last()
    prods = Product.objects.filter(dataset=ds).order_by("sku")
    product = (
        prods.filter(pk=request.GET.get("product")).first()
        if request.GET.get("product", "").isdigit()
        else prods.first()
    )
    return render(
        request,
        "forecasts.html",
        {
            "forecast_run": run,
            "products": prods,
            "chosen_product": product,
            "chart_data": chart(ds, run, product),
            "history": ForecastRun.objects.filter(dataset=ds).order_by("-id")[:6],
        },
    )


@login_required
def inventory(request):
    ds = selected(request)
    run = ForecastRun.objects.filter(dataset=ds).last()
    plan = Plan.objects.filter(dataset=ds).last()
    initial = dict(plan.params) if plan else {}
    if "service" in initial:
        initial["service"] = str(initial["service"]).removeprefix("0")
    form = PlanForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            if not run:
                raise ValueError("Create a forecast before calculating replenishment.")
            plan = make_plan(
                run,
                form.cleaned_data["budget"],
                form.cleaned_data["review"],
                float(form.cleaned_data["service"]),
                form.cleaned_data["solver"],
            )
            audit(request, "plan_created", plan=plan.id)
            messages.success(request, "Replenishment plan calculated and saved.")
            return redirect("inventory")
        except ValueError as exc:
            messages.error(request, str(exc))
    plan = Plan.objects.filter(dataset=ds).last()
    return render(
        request,
        "inventory.html",
        {
            "form": form,
            "plan": plan,
            "forecast_run": run,
            "stale_plan": bool(
                plan
                and (
                    plan.params.get("stock_signature") != stock_signature(ds)
                    or plan.forecast_id != (run.id if run else None)
                )
            ),
            "products": Product.objects.filter(dataset=ds),
            "stocks": Stock.objects.filter(product__dataset=ds).select_related("product", "location"),
        },
    )


@login_required
def stock_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    loc = product.dataset.location_set.first()
    if request.GET.get("location", "").isdigit():
        loc = get_object_or_404(product.dataset.location_set, pk=request.GET["location"])
    stock = Stock.objects.filter(product=product, location=loc).first()
    initial = (
        {k: getattr(stock, k) for k in ["on_hand", "on_order", "allocated", "as_of", "assumptions"]}
        if stock
        else {"as_of": product.dataset.end_date}
    )
    initial.update({k: getattr(product, k) for k in ["unit_cost", "lead_time", "pack_size", "moq"]})
    form = StockForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        with transaction.atomic():
            Stock.objects.update_or_create(
                product=product,
                location=loc,
                defaults={k: data[k] for k in ["on_hand", "on_order", "allocated", "as_of", "assumptions"]},
            )
            for k in ["unit_cost", "lead_time", "pack_size", "moq"]:
                setattr(product, k, data[k])
            product.save()
            audit(request, "inventory_edited", product=pk, location=loc.id)
        messages.success(request, "Stock inputs updated. Recalculate the plan to use these values.")
        return redirect("inventory")
    request.session["dataset"] = product.dataset_id
    return render(request, "stock_edit.html", {"form": form, "product": product, "location": loc})


@login_required
def scenarios(request):
    ds = selected(request)
    previous = Simulation.objects.filter(dataset=ds).last()
    form = SimulationForm(request.POST or None, initial=previous.params if previous else {})
    if request.method == "POST" and form.is_valid() and ds:
        enqueue(
            request,
            ds,
            "simulation",
            {
                "days": form.cleaned_data["days"],
                "budget": float(form.cleaned_data["budget"]),
                "delay": form.cleaned_data["delay"],
            },
        )
        return redirect("scenarios")
    run = Simulation.objects.filter(dataset=ds).last()
    scenario_chart = None
    if run:
        daily = run.results["daily"]
        scenario_chart = {
            "labels": [str(i + 1) for i in range(run.params["days"])],
            "actual": [x["on_hand"] for x in daily["seasonal"]],
            "forecast": [x["on_hand"] for x in daily.get("ml", daily["fixed"])],
            "boundary": None,
        }
    return render(request, "scenarios.html", {"form": form, "simulation": run, "chart_data": scenario_chart})


@login_required
def runs(request):
    ds = selected(request)
    return render(
        request,
        "runs.html",
        {
            "jobs": Job.objects.filter(dataset=ds).order_by("-id")[:30],
            "events": AuditEvent.objects.order_by("-id")[:20],
            "forecasts": ForecastRun.objects.filter(dataset=ds).order_by("-id")[:10],
        },
    )


def safe_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def csv_response(name, headers, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows([[safe_cell(x) for x in row] for row in rows])
    response = HttpResponse("\ufeff" + buffer.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@login_required
def export_csv(request, kind, pk):
    if kind == "plan":
        plan = get_object_or_404(Plan, pk=pk)
        headers = ["sku", "name", "location", "status", "requested", "quantity", "spend", "constraint"]
        return csv_response(f"retailiq-plan-{pk}.csv", headers, [[x.get(k, "") for k in headers] for x in plan.lines])
    if kind == "forecast":
        run = get_object_or_404(ForecastRun, pk=pk)
        points = ForecastPoint.objects.filter(run=run).select_related("product", "location")
        return csv_response(
            f"retailiq-forecast-{pk}.csv",
            ["origin", "date", "sku", "location", "forecast", "lower", "upper", "model"],
            [
                [run.origin, p.date, p.product.sku, p.location.name, p.prediction, p.lower, p.upper, run.model_name]
                for p in points
            ],
        )
    if kind == "simulation":
        run = get_object_or_404(Simulation, pk=pk)
        headers = list(run.results["policies"][0])
        return csv_response(
            f"retailiq-simulation-{pk}.csv", headers, [[row[k] for k in headers] for row in run.results["policies"]]
        )
    raise Http404


def health(request):
    Dataset.objects.exists()
    return JsonResponse({"status": "ok", "application": "RetailIQ", "version": "1.0.0"})


@login_required
def job_status(request, pk):
    job = get_object_or_404(Job, pk=pk)
    return JsonResponse(
        {"id": job.id, "kind": job.kind, "status": job.status, "error": job.error, "result_id": job.result.get("id")}
    )
