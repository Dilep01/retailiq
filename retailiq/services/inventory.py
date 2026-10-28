import math
import hashlib
import json
from decimal import Decimal
from statistics import NormalDist

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from retailiq.models import ForecastPoint, Plan, Stock
from .data import sales_frame


def stock_signature(dataset):
    rows = list(
        Stock.objects.filter(product__dataset=dataset)
        .order_by("id")
        .values(
            "product_id",
            "location_id",
            "as_of",
            "on_hand",
            "on_order",
            "allocated",
            "product__unit_cost",
            "product__lead_time",
            "product__pack_size",
            "product__moq",
        )
    )
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def rounded_order(target, position, pack, moq):
    if pack < 1 or moq < 1:
        raise ValueError("Pack size and minimum quantity must be positive.")
    gap = max(0, target - position)
    return int(math.ceil(max(gap, moq) / pack) * pack) if gap > 0 else 0


def allocate(lines, budget, solver="heuristic"):
    """Bounded allocation maximizing linear priority benefit, not long-run profit."""
    eligible = [x for x in lines if x.get("requested", 0) > 0 and x.get("unit_cost", 0) > 0]
    cents = int(Decimal(str(budget)) * 100)
    for line in lines:
        line["quantity"] = 0
    if not eligible:
        return "No eligible orders"
    if solver == "milp":
        n = len(eligible)
        costs = np.array([round(x["unit_cost"] * 100) * x["pack"] for x in eligible])
        maxpacks = np.array([x["requested"] // x["pack"] for x in eligible])
        minpacks = np.array([math.ceil(x["moq"] / x["pack"]) for x in eligible])
        benefit = np.array([x["priority"] * x["pack"] for x in eligible])
        matrix = np.zeros((1 + 2 * n, 2 * n))
        matrix[0, :n] = costs
        for i in range(n):
            matrix[1 + i, i], matrix[1 + i, n + i] = 1, -maxpacks[i]
            matrix[1 + n + i, i], matrix[1 + n + i, n + i] = -1, minpacks[i]
        result = milp(
            c=np.r_[-benefit, np.zeros(n)],
            integrality=np.ones(2 * n),
            bounds=Bounds(np.zeros(2 * n), np.r_[maxpacks, np.ones(n)]),
            constraints=LinearConstraint(matrix, -np.inf, np.r_[cents, np.zeros(2 * n)]),
            options={"time_limit": 5},
        )
        if result.x is not None:
            for line, value in zip(eligible, result.x[:n], strict=True):
                line["quantity"] = int(round(value)) * line["pack"]
            spend = sum(round(x["unit_cost"] * 100) * x["quantity"] for x in eligible)
            valid = spend <= cents and all(
                x["quantity"] == 0
                or (x["quantity"] >= x["moq"] and x["quantity"] <= x["requested"] and x["quantity"] % x["pack"] == 0)
                for x in eligible
            )
            if valid:
                return (
                    f"MILP status {result.status}; gap {getattr(result, 'mip_gap', None)}. Linear priority objective."
                )
        for line in lines:
            line["quantity"] = 0
        status = "MILP unavailable/infeasible; heuristic fallback."
    else:
        status = "Priority-per-cost heuristic; no optimality claim."
    for line in sorted(eligible, key=lambda x: x["priority"] / x["unit_cost"], reverse=True):
        cost = round(line["unit_cost"] * 100)
        qty = min(line["requested"], (cents // (cost * line["pack"])) * line["pack"])
        if qty >= line["moq"]:
            line["quantity"] = int(qty)
            cents -= int(qty) * cost
    return status


def make_plan(run, budget=25000, review=7, service=0.95, solver="heuristic"):
    if not 0 <= float(budget) <= 100000000 or not 1 <= review <= 21 or not 0.5 <= service <= 0.99:
        raise ValueError("Budget, review interval or service parameter is out of range.")
    frame = sales_frame(run.dataset)
    z = NormalDist().inv_cdf(service)
    stocks = {
        (s.product_id, s.location_id): s
        for s in Stock.objects.filter(product__dataset=run.dataset).select_related("product", "location")
    }
    forecasts = {}
    for p in ForecastPoint.objects.filter(run=run).order_by("date"):
        forecasts.setdefault((p.product_id, p.location_id), []).append(p.prediction)
    lines = []
    for key, prediction in forecasts.items():
        stock = stocks.get(key)
        if stock is None:
            lines.append(
                {
                    "product_id": key[0],
                    "location_id": key[1],
                    "status": "Missing inventory snapshot",
                    "requested": 0,
                    "quantity": 0,
                }
            )
            continue
        product = stock.product
        line = {
            "product_id": key[0],
            "location_id": key[1],
            "sku": product.sku,
            "name": product.name,
            "location": stock.location.name,
            "pack": product.pack_size,
            "moq": product.moq,
            "on_hand": stock.on_hand,
            "on_order": stock.on_order,
            "requested": 0,
            "quantity": 0,
            "assumptions": stock.assumptions,
            "unit_cost": float(product.unit_cost or 0),
        }
        if stock.as_of != run.origin:
            line["status"] = "Stale stock: snapshot must match forecast origin"
        elif not product.unit_cost or product.unit_cost <= 0:
            line["status"] = "Missing positive procurement cost"
        elif product.lead_time + review > run.horizon:
            line["status"] = "Protection period exceeds forecast horizon"
        else:
            period = product.lead_time + review
            history = frame[(frame.product_id == key[0]) & (frame.location_id == key[1]) & frame.observed].tail(28)
            safety = z * float(history.units.std(ddof=0)) * math.sqrt(period)
            expected = sum(prediction[:period])
            target = math.ceil(expected + safety)
            position = stock.on_hand + stock.on_order - stock.allocated
            requested = rounded_order(target, position, product.pack_size, product.moq)
            daily = max(0.01, float(np.mean(prediction[:7])))
            line.update(
                {
                    "period": period,
                    "expected": round(expected, 1),
                    "safety": round(safety, 1),
                    "target": target,
                    "position": position,
                    "requested": requested,
                    "coverage": round(stock.on_hand / daily, 1),
                    "priority": max(0.1, (period - stock.on_hand / daily) / period + 1),
                    "status": "At risk" if stock.on_hand / daily < product.lead_time else "Covered",
                }
            )
        lines.append(line)
    status = allocate(lines, budget, solver)
    for line in lines:
        line["spend"] = round(line.get("unit_cost", 0) * line["quantity"], 2)
        if line["requested"] > line["quantity"]:
            line["constraint"] = "Budget-limited"
        else:
            line["constraint"] = "Within policy" if line["requested"] else "No order"
    summary = {
        "spend": round(sum(x["spend"] for x in lines), 2),
        "budget": float(budget),
        "units": sum(x["quantity"] for x in lines),
        "requested": sum(x["requested"] for x in lines),
        "risk_count": sum(x["status"] == "At risk" for x in lines),
        "allocation": status,
        "limitation": "Normal daily-variability approximation; outstanding stock is assumed to arrive before needed. No dated PO ledger in v1.",
    }
    return Plan.objects.create(
        dataset=run.dataset,
        forecast=run,
        params={
            "budget": float(budget),
            "review": review,
            "service": service,
            "solver": solver,
            "safety_method": "IID normal approximation",
            "stock_signature": stock_signature(run.dataset),
        },
        lines=lines,
        summary=summary,
    )
