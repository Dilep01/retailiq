import pytest
from retailiq.services.simulation import simulate_path, run_simulation


def test_delivery_timing_and_conservation():
    result, ledger = simulate_path([10] * 10, [10] * 30, lead=2, review=7, initial=0, policy="fixed", pack=1, moq=1)
    assert ledger[0]["ordered"] == 90
    assert ledger[0]["fulfilled"] == 0 and ledger[1]["fulfilled"] == 0
    assert ledger[2]["receipts"] == 90 and ledger[2]["fulfilled"] == 10
    assert result["demand"] == result["fulfilled"] + result["lost"]
    assert result["comparison_cost"] == pytest.approx(
        result["holding_cost"] + result["ordering_cost"] + result["shortage_cost"]
    )


def test_zero_budget_and_zero_demand():
    result, ledger = simulate_path([0] * 14, [0] * 30, daily_budget=0, initial=0)
    assert result["orders"] == 0 and result["fill_rate"] is None
    assert all(row["on_hand"] >= 0 for row in ledger)


def test_delay_changes_receipt_day():
    _, ledger = simulate_path([10] * 12, [10] * 30, lead=2, delay=3, initial=0, policy="fixed")
    assert all(row["receipts"] == 0 for row in ledger[:5])
    assert ledger[5]["receipts"] > 0


def test_reproducible_matched_scenarios(dataset):
    first = run_simulation(dataset, days=14, seeds=(17, 29), include_ml=False)
    second = run_simulation(dataset, days=14, seeds=(17, 29), include_ml=False)
    assert first.results == second.results
    rows = first.results["policies"]
    assert rows[0]["demand"] == rows[1]["demand"]
    assert all(x["fulfilled"] + x["lost"] == x["demand"] for x in rows)
