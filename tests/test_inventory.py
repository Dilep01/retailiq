import pytest
from retailiq.services.inventory import rounded_order, allocate, make_plan
from retailiq.services.forecasting import run_forecast
from retailiq.models import Stock, Product


@pytest.mark.parametrize(
    "target,position,pack,moq,expected",
    [
        (138, 60, 10, 1, 80),
        (50, 60, 6, 6, 0),
        (61, 60, 6, 20, 24),
        (0, -1, 12, 1, 12),
    ],
)
def test_order_rounding(target, position, pack, moq, expected):
    assert rounded_order(target, position, pack, moq) == expected


@pytest.mark.parametrize("solver", ["heuristic", "milp"])
@pytest.mark.parametrize("budget", [0, 5, 100, 1000])
def test_allocation_constraints(solver, budget):
    lines = [
        {"requested": 120, "unit_cost": 2.5, "pack": 6, "moq": 12, "priority": 2.0},
        {"requested": 60, "unit_cost": 3.2, "pack": 10, "moq": 20, "priority": 1.0},
    ]
    allocate(lines, budget, solver)
    assert sum(x["quantity"] * x["unit_cost"] for x in lines) <= budget + 0.0001
    for line in lines:
        assert line["quantity"] % line["pack"] == 0
        assert line["quantity"] == 0 or line["quantity"] >= line["moq"]
        assert line["quantity"] <= line["requested"]


def test_missing_stale_and_long_inputs(dataset):
    run = run_forecast(dataset, include_ml=False)
    stock = Stock.objects.first()
    from datetime import timedelta

    stock.as_of -= timedelta(days=1)
    stock.save()
    product = Product.objects.last()
    product.lead_time = 21
    product.save()
    plan = make_plan(run, review=14)
    assert any("Stale" in x["status"] for x in plan.lines)
    assert any("exceeds" in x["status"] for x in plan.lines)
    assert plan.summary["spend"] <= 25000


def test_cost_required(dataset):
    run = run_forecast(dataset, include_ml=False)
    Product.objects.update(unit_cost=None)
    plan = make_plan(run)
    assert plan.summary["units"] == 0
    assert all("cost" in x["status"] for x in plan.lines)
