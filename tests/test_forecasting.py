import numpy as np
import pandas as pd
import pytest
from retailiq.services.forecasting import features, seasonal, metrics, training_rows, series_map, run_forecast
from retailiq.services.data import sales_frame
from retailiq.models import ForecastPoint


def test_seasonal_is_frozen():
    result = seasonal(np.arange(1, 29), 28)
    assert list(result[:7]) == list(range(22, 29))
    assert np.array_equal(result[:7], result[7:14])


def test_features_have_no_future_dependency():
    full = np.arange(100, dtype=float)
    before = features(full[:50], "2026-01-01", 28)
    full[50:] = 999999
    assert before == features(full[:50], "2026-01-01", 28)
    assert before[0] == 49 and before[8] == 28


def test_training_target_cutoff_guard():
    s = pd.Series(np.arange(200, dtype=float), index=pd.date_range("2026-01-01", periods=200))
    cutoff = pd.Timestamp("2026-04-01")
    x, y, dates = training_rows({(1, 1): s}, cutoff)
    assert x.shape[0] == len(y) == len(dates)
    assert max(dates) <= cutoff
    altered = s.copy()
    altered.loc[cutoff + pd.Timedelta(days=1) :] = 99999
    x2, y2, _ = training_rows({(1, 1): altered}, cutoff)
    np.testing.assert_array_equal(x, x2)
    np.testing.assert_array_equal(y, y2)


def test_unknown_recent_history_rejected():
    with pytest.raises(ValueError):
        seasonal([1, 2, 3, np.nan, 4, 5, 6])
    with pytest.raises(ValueError):
        features([1] * 27, "2026-01-01", 1)


def test_metrics_zero_denominator_and_sign():
    assert metrics([0, 0], [1, 2])["wape"] is None
    assert metrics([10], [12])["bias"] > 0.0
    assert metrics([], [])["mae"] is None


def test_series_does_not_fill_missing(dataset):
    frame = sales_frame(dataset)
    row = frame.iloc[10]
    frame = frame.drop(index=10)
    series = series_map(frame)
    assert np.isnan(series[(row.product_id, row.location_id)].loc[row.date])


def test_full_baseline_run(dataset):
    run = run_forecast(dataset, include_ml=False)
    assert run.model_name == "seasonal_naive"
    assert ForecastPoint.objects.filter(run=run).count() == 84
    assert min(p.date for p in ForecastPoint.objects.filter(run=run)) > dataset.end_date
    assert len(run.evaluation["validation"]) == 3
    assert run.evaluation["selected"]["n"] == 84
    assert run.evaluation["interval"]["test_coverage"] is not None


def test_ml_model_fit_predict_and_holdout(dataset):
    from retailiq.services.forecasting import fit_model, predict_series

    series = series_map(sales_frame(dataset))
    cutoff = pd.Timestamp(dataset.end_date) - pd.Timedelta(days=28)
    model = fit_model(series, cutoff)
    predictions, skipped, fallback = predict_series(series, cutoff, model)
    assert not skipped and not fallback
    assert len(predictions) == 3
    assert all(len(p) == 28 and np.isfinite(p).all() and (p >= 0).all() for p in predictions.values())
