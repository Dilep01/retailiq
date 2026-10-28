import math
from datetime import timedelta

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from retailiq.models import Product, Simulation
from .data import sales_frame
from .forecasting import features, fit_model, seasonal, series_map
from .inventory import rounded_order, allocate


def simulate_path(
    demand,
    history,
    lead=5,
    review=7,
    initial=50,
    policy="seasonal",
    model=None,
    origin="2026-01-01",
    cost=10,
    price=20,
    pack=6,
    moq=6,
    daily_budget=100000,
    delay=0,
    holding_rate=0.02,
    shortage_rate=0.35,
    order_fee=50,
):
    """Single-SKU lost-sales simulator; policies see only their fulfilled sales."""
    inventory, pipeline, observed = int(initial), [], list(map(float, history))
    ledger = []
    totals = {
        "demand": 0,
        "fulfilled": 0,
        "lost": 0,
        "stockout_days": 0,
        "holding_cost": 0.0,
        "ordering_cost": 0.0,
        "shortage_cost": 0.0,
        "purchase_spend": 0.0,
        "orders": 0,
    }
    for day, wanted in enumerate(demand):
        receipt = sum(q for due, q in pipeline if due == day)
        inventory += receipt
        pipeline = [(due, q) for due, q in pipeline if due != day]
        before = inventory
        sold = min(int(wanted), inventory)
        lost = int(wanted) - sold
        inventory -= sold
        observed.append(float(sold))
        holding = inventory * cost * holding_rate / 30
        totals["demand"] += int(wanted)
        totals["fulfilled"] += sold
        totals["lost"] += lost
        totals["stockout_days"] += int(lost > 0)
        totals["holding_cost"] += holding
        totals["shortage_cost"] += lost * price * shortage_rate
        quantity = 0
        if day % review == 0:
            period = lead + review
            if policy == "fixed":
                target = float(np.mean(history[-28:])) * period
            else:
                if policy == "ml" and model is not None:
                    x = np.array(
                        [
                            features(observed, pd.Timestamp(origin) + pd.Timedelta(days=day), h)
                            for h in range(1, period + 1)
                        ]
                    )
                    with threadpool_limits(limits=2):
                        expected = float(np.maximum(0, model.predict(x)).sum())
                else:
                    expected = float(seasonal(observed, period).sum())
                target = expected + 1.645 * float(np.std(observed[-28:])) * math.sqrt(period)
            position = inventory + sum(q for _, q in pipeline)
            quantity = rounded_order(math.ceil(target), position, pack, moq)
            # This function's budget is per SKU per review. Portfolio simulation uses an explicit equal share.
            line = {"requested": quantity, "unit_cost": cost, "pack": pack, "moq": moq, "priority": 1.0}
            allocate([line], daily_budget)
            quantity = line["quantity"]
            if quantity:
                pipeline.append((day + lead + delay, quantity))
                totals["purchase_spend"] += quantity * cost
                totals["orders"] += 1
                totals["ordering_cost"] += order_fee
        assert before - sold == inventory and inventory >= 0 and sold + lost == wanted
        ledger.append(
            {
                "day": day,
                "demand": int(wanted),
                "receipts": receipt,
                "fulfilled": sold,
                "lost": lost,
                "on_hand": inventory,
                "ordered": quantity,
            }
        )
    totals.update(
        {
            "ending_stock": inventory,
            "in_transit": sum(q for _, q in pipeline),
            "mean_stock": float(np.mean([x["on_hand"] for x in ledger])),
            "fill_rate": totals["fulfilled"] / totals["demand"] if totals["demand"] else None,
        }
    )
    totals["comparison_cost"] = totals["holding_cost"] + totals["ordering_cost"] + totals["shortage_cost"]
    return totals, ledger


def run_simulation(dataset, days=56, budget=750000, delay=0, seeds=(17, 29, 53), include_ml=True):
    if not 14 <= days <= 84 or not 0 <= budget <= 100000000 or not 0 <= delay <= 14:
        raise ValueError("Simulation parameters are outside allowed bounds.")
    series = series_map(sales_frame(dataset))
    start = pd.Timestamp(dataset.end_date) - pd.Timedelta(days=days - 1)
    cutoff = start - pd.Timedelta(days=1)
    eligible = {
        key: s
        for key, s in series.items()
        if len(s.loc[:cutoff]) >= 60 and np.isfinite(s.loc[:cutoff].iloc[-28:]).all()
    }
    if not eligible:
        raise ValueError("No series has enough complete pre-simulation history.")
    if len(eligible) > 100:
        raise ValueError("Simulation supports at most 100 series per run.")
    products = {p.id: p for p in Product.objects.filter(dataset=dataset)}
    if any(not products[k[0]].unit_cost for k in eligible):
        raise ValueError("Simulation needs positive procurement costs. Edit stock assumptions first.")
    model = fit_model(eligible, cutoff) if include_ml else None
    policies = ["fixed", "seasonal"] + (["ml"] if include_ml else [])
    summaries, daily = [], {}
    for policy in policies:
        samples = []
        aggregate_ledger = [
            {"day": i, "demand": 0, "receipts": 0, "fulfilled": 0, "lost": 0, "on_hand": 0, "ordered": 0}
            for i in range(days)
        ]
        for seed in seeds:
            totals = {
                k: 0.0
                for k in [
                    "demand",
                    "fulfilled",
                    "lost",
                    "stockout_days",
                    "holding_cost",
                    "ordering_cost",
                    "shortage_cost",
                    "purchase_spend",
                    "orders",
                    "ending_stock",
                    "in_transit",
                    "mean_stock",
                ]
            }
            for index, (key, s) in enumerate(sorted(eligible.items())):
                product = products[key[0]]
                history = s.loc[:cutoff].iloc[-60:].tolist()
                rng = np.random.default_rng(seed + index * 1009)
                if dataset.source_kind == "synthetic":
                    level = np.mean(history[-28:])
                    demand = [
                        int(
                            rng.poisson(
                                max(
                                    0.1,
                                    level
                                    * (1 + 0.18 * np.sin(2 * np.pi * (start + timedelta(days=i)).weekday() / 7))
                                    * (1.6 if days // 2 <= i < days // 2 + 7 else 1),
                                )
                            )
                        )
                        for i in range(days)
                    ]
                else:
                    values = s.reindex(pd.date_range(start, periods=days)).to_numpy()
                    if not np.isfinite(values).all():
                        raise ValueError("Public sales replay needs complete observed scenario dates.")
                    demand = values.astype(int).tolist()
                result, ledger = simulate_path(
                    demand,
                    history,
                    lead=product.lead_time,
                    initial=math.ceil(np.mean(history[-28:]) * 5),
                    policy=policy,
                    model=model,
                    origin=start,
                    cost=float(product.unit_cost),
                    price=float(product.price),
                    pack=product.pack_size,
                    moq=product.moq,
                    daily_budget=budget / len(eligible),
                    delay=delay,
                )
                for k in totals:
                    totals[k] += result[k]
                if seed == seeds[0]:
                    for i, row in enumerate(ledger):
                        for k in row:
                            if k != "day":
                                aggregate_ledger[i][k] += row[k]
            totals["fill_rate"] = totals["fulfilled"] / totals["demand"] if totals["demand"] else None
            totals["comparison_cost"] = totals["holding_cost"] + totals["ordering_cost"] + totals["shortage_cost"]
            samples.append(totals)
        summary = {
            k: round(float(np.mean([x[k] for x in samples])), 4) if samples[0][k] is not None else None
            for k in samples[0]
        }
        summary.update(
            {
                "policy": policy,
                "cost_min": round(min(x["comparison_cost"] for x in samples), 2),
                "cost_max": round(max(x["comparison_cost"] for x in samples), 2),
            }
        )
        summaries.append(summary)
        daily[policy] = aggregate_ledger
    return Simulation.objects.create(
        dataset=dataset,
        params={
            "days": days,
            "budget": budget,
            "delay": delay,
            "seeds": list(seeds),
            "cutoff": str(cutoff.date()),
            "series": len(eligible),
            "budget_policy": "Equal per-series shares per weekly review; no budget carry-over.",
            "demand_source": "Independent synthetic latent demand paths"
            if dataset.source_kind == "synthetic"
            else "Historical sales replay; unmet demand unobserved",
            "cost_policy": "2% unit cost/month holding; 35% selling price/lost unit penalty; 50 currency/order.",
            "terminal_policy": "Report ending and in-transit stock; no salvage credit. Procurement spend excluded from comparison cost.",
        },
        results={
            "policies": summaries,
            "daily": daily,
            "limitation": "Simulation only. Short horizon, assumed costs and terminal stock can change the ranking.",
        },
    )
